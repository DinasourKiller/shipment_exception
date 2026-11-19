"""Pytest configuration and global fixtures."""

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.database.connection import async_engine
from app.main import app


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing testing settings."""
    return get_settings()


@pytest.fixture
def client() -> TestClient:
    """Synchronous FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncClient:
    """Asynchronous HTTPX test client fixture."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    """Clean up connection pool across test event loops."""
    yield
    await async_engine.dispose()
