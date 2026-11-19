"""Unit Tests for Resilient HTTP Client.

Verifies retry logic, exponential backoff, correlation ID propagation,
and exception translation under various HTTP and network conditions.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.common.constants import CORRELATION_ID_HEADER
from app.core.logging import set_correlation_id
from app.integrations.base.exceptions import (
    IntegrationAuthenticationException,
    IntegrationConnectionException,
    IntegrationException,
    IntegrationTimeoutException,
)
from app.integrations.base.http_client import ResilientHttpClient


@pytest.mark.asyncio
async def test_http_client_correlation_id_propagation():
    """Verify that current correlation ID in context is automatically attached to outbound requests."""
    set_correlation_id("test-corr-id-12345")

    client = ResilientHttpClient(
        system_name="TEST_SYS",
        base_url="https://api.test.corp",
        timeout_seconds=5.0,
        max_retries=1,
    )

    mock_resp = httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", "https://api.test.corp/test"))

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        resp = await client.get("/test")
        assert resp.status_code == 200

        # Assert headers passed to httpx.request contained X-Correlation-ID
        call_kwargs = mock_req.call_args[1]
        assert call_kwargs["headers"][CORRELATION_ID_HEADER] == "test-corr-id-12345"

    await client.close()


@pytest.mark.asyncio
async def test_http_client_retries_transient_failure_and_succeeds():
    """Verify that transient 503 Service Unavailable triggers retry with backoff and returns 200 on success."""
    client = ResilientHttpClient(
        system_name="TEST_SYS",
        base_url="https://api.test.corp",
        timeout_seconds=5.0,
        max_retries=2,
        backoff_factor=0.01,  # Fast for tests
    )

    resp_503 = httpx.Response(503, text="Service Unavailable", request=httpx.Request("GET", "https://api.test.corp/retry"))
    resp_200 = httpx.Response(200, json={"success": True}, request=httpx.Request("GET", "https://api.test.corp/retry"))

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = [resp_503, resp_200]
        resp = await client.get("/retry")
        assert resp.status_code == 200
        assert mock_req.call_count == 2

    await client.close()


@pytest.mark.asyncio
async def test_http_client_authentication_failure():
    """Verify 401 Unauthorized raises IntegrationAuthenticationException immediately without retry."""
    client = ResilientHttpClient(
        system_name="TEST_SYS",
        base_url="https://api.test.corp",
        timeout_seconds=5.0,
        max_retries=3,
    )

    resp_401 = httpx.Response(401, text="Unauthorized", request=httpx.Request("GET", "https://api.test.corp/auth"))

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = resp_401
        with pytest.raises(IntegrationAuthenticationException) as exc_info:
            await client.get("/auth")

        assert "Authentication rejected" in str(exc_info.value)
        # Authentication errors must not retry
        assert mock_req.call_count == 1

    await client.close()


@pytest.mark.asyncio
async def test_http_client_timeout_raises_integration_timeout():
    """Verify read/connect timeouts exhaust retries and raise IntegrationTimeoutException."""
    client = ResilientHttpClient(
        system_name="TEST_SYS",
        base_url="https://api.test.corp",
        timeout_seconds=1.0,
        max_retries=2,
        backoff_factor=0.01,
    )

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = httpx.ReadTimeout("Read timed out")
        with pytest.raises(IntegrationTimeoutException) as exc_info:
            await client.get("/timeout")

        assert "Request timed out after 1.0s" in str(exc_info.value)
        assert mock_req.call_count == 3  # initial + 2 retries

    await client.close()


@pytest.mark.asyncio
async def test_http_client_connect_error_raises_connection_exception():
    """Verify socket/connection drop exhausts retries and raises IntegrationConnectionException."""
    client = ResilientHttpClient(
        system_name="TEST_SYS",
        base_url="https://api.test.corp",
        timeout_seconds=2.0,
        max_retries=1,
        backoff_factor=0.01,
    )

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = httpx.ConnectError("Connection refused")
        with pytest.raises(IntegrationConnectionException) as exc_info:
            await client.get("/disconnect")

        assert "Connection failed after 2 attempts" in str(exc_info.value)
        assert mock_req.call_count == 2

    await client.close()
