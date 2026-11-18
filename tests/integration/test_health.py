"""Integration tests for health, liveness, readiness, and ping endpoints."""

from fastapi.testclient import TestClient
from app.common.constants import CORRELATION_ID_HEADER


def test_health_endpoint(client: TestClient):
    """Test comprehensive health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"
    assert data["data"]["app_name"] == "Shipment Exception Control Tower"
    assert "components" in data["data"]
    assert CORRELATION_ID_HEADER in response.headers


def test_liveness_endpoint(client: TestClient):
    """Test Kubernetes/Docker liveness probe."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_readiness_endpoint(client: TestClient):
    """Test Kubernetes/Docker readiness probe."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_api_ping_endpoint(client: TestClient):
    """Test API v1 ping endpoint and correlation propagation."""
    custom_corr_id = "custom-test-correlation-id-999"
    response = client.get(
        "/api/v1/ping",
        headers={CORRELATION_ID_HEADER: custom_corr_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"] == {"message": "pong"}
    assert response.headers.get(CORRELATION_ID_HEADER) == custom_corr_id
    assert data["correlation_id"] == custom_corr_id


def test_response_time_header(client: TestClient):
    """Ensure X-Response-Time-Ms header is present on responses."""
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert "x-response-time-ms" in response.headers
