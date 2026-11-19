"""Resilient Async HTTP Client for Integrations.

Provides robust HTTP capabilities for external adapters with:
- Configurable timeouts
- Exponential backoff retry with jitter on transient network/server failures
- Automatic correlation ID propagation (X-Correlation-ID)
- Comprehensive audit logging and latency metrics
"""

import asyncio
import random
import time
from typing import Any, Dict, Optional, Set
import httpx

from app.common.constants import CORRELATION_ID_HEADER
from app.core.logging import get_correlation_id, get_logger
from app.integrations.base.exceptions import (
    IntegrationAuthenticationException,
    IntegrationConnectionException,
    IntegrationException,
    IntegrationTimeoutException,
)

logger = get_logger("control_tower.integrations.http")

# HTTP status codes that represent transient failures eligible for retry
TRANSIENT_STATUS_CODES: Set[int] = {408, 429, 500, 502, 503, 504}

# Network-level exceptions eligible for retry
RETRIABLE_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


class ResilientHttpClient:
    """Async HTTP client featuring exponential backoff, correlation tracing, and telemetry."""

    def __init__(
        self,
        system_name: str,
        base_url: str,
        default_headers: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.system_name = system_name
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds),
                headers=self.default_headers,
                transport=self.transport,
            )
        return self._client

    async def close(self) -> None:
        """Close underlying HTTP client connections."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _prepare_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Merges default headers with request-specific headers and injects Correlation ID."""
        headers = dict(self.default_headers)
        if custom_headers:
            headers.update(custom_headers)

        # Inject current context correlation ID if available
        cid = get_correlation_id()
        if cid and CORRELATION_ID_HEADER not in headers:
            headers[CORRELATION_ID_HEADER] = cid

        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Executes an HTTP request with automatic retry, jittered backoff, and tracing."""
        client = self._get_client()
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}/{endpoint.lstrip('/')}"
        merged_headers = self._prepare_headers(headers)
        cid = merged_headers.get(CORRELATION_ID_HEADER, "none")

        last_exception: Optional[Exception] = None
        attempt = 0

        while attempt <= self.max_retries:
            attempt += 1
            start_time = time.perf_counter()

            logger.info(
                f"[{self.system_name}] HTTP {method} {url} (attempt {attempt}/{self.max_retries + 1}) "
                f"[correlation_id={cid}]"
            )

            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=merged_headers,
                )
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                # Check if transient error eligible for retry
                if response.status_code in TRANSIENT_STATUS_CODES and attempt <= self.max_retries:
                    logger.warning(
                        f"[{self.system_name}] Received transient status {response.status_code} in {latency_ms}ms. "
                        f"Retrying..."
                    )
                    await self._sleep_backoff(attempt)
                    continue

                # Log response completion
                logger.info(
                    f"[{self.system_name}] HTTP {method} {url} returned {response.status_code} in {latency_ms}ms "
                    f"[correlation_id={cid}]"
                )

                # Handle specific authentication failures
                if response.status_code in (401, 403):
                    raise IntegrationAuthenticationException(
                        system_name=self.system_name,
                        message=f"HTTP {response.status_code} - Authentication rejected",
                        details={"status_code": response.status_code, "body": response.text[:200]},
                    )

                # Raise for generic client/server errors if not 2xx
                response.raise_for_status()
                return response

            except RETRIABLE_NETWORK_ERRORS as net_err:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                last_exception = net_err
                logger.warning(
                    f"[{self.system_name}] Network error during {method} {url} ({type(net_err).__name__}: {net_err}) "
                    f"after {latency_ms}ms. Attempt {attempt}/{self.max_retries + 1}"
                )

                if attempt <= self.max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                else:
                    if isinstance(net_err, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
                        raise IntegrationTimeoutException(
                            system_name=self.system_name,
                            timeout_seconds=self.timeout_seconds,
                            details={"method": method, "url": url, "error": str(net_err)},
                        ) from net_err
                    raise IntegrationConnectionException(
                        system_name=self.system_name,
                        message=f"Connection failed after {self.max_retries + 1} attempts: {net_err}",
                        details={"method": method, "url": url},
                    ) from net_err

            except httpx.HTTPStatusError as http_err:
                # Permanent non-transient HTTP error (e.g., 400 Bad Request, 404 Not Found)
                raise IntegrationException(
                    system_name=self.system_name,
                    message=f"HTTP {http_err.response.status_code}: {http_err.response.text[:200]}",
                    details={"status_code": http_err.response.status_code, "url": url},
                    status_code=http_err.response.status_code,
                ) from http_err

        # If loops terminates without explicit return or raise
        raise IntegrationException(
            system_name=self.system_name,
            message="Request failed after all retries exhausted",
            details={"last_error": str(last_exception)},
        )

    async def _sleep_backoff(self, attempt: int) -> None:
        """Applies exponential backoff with random jitter."""
        delay = (self.backoff_factor * (2 ** (attempt - 1))) + random.uniform(0.01, 0.1)
        await asyncio.sleep(delay)

    # Convenience HTTP verbs
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        return await self.request("GET", endpoint, params=params, **kwargs)

    async def post(self, endpoint: str, json_data: Optional[Any] = None, **kwargs) -> httpx.Response:
        return await self.request("POST", endpoint, json_data=json_data, **kwargs)

    async def put(self, endpoint: str, json_data: Optional[Any] = None, **kwargs) -> httpx.Response:
        return await self.request("PUT", endpoint, json_data=json_data, **kwargs)

    async def patch(self, endpoint: str, json_data: Optional[Any] = None, **kwargs) -> httpx.Response:
        return await self.request("PATCH", endpoint, json_data=json_data, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        return await self.request("DELETE", endpoint, **kwargs)
