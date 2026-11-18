"""Unit tests for application configuration."""

from app.config import Settings


def test_default_settings():
    """Verify default settings initialization."""
    settings = Settings()
    assert settings.APP_NAME == "Shipment Exception Control Tower"
    assert settings.APP_VERSION == "1.0.0"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.POSTGRES_PORT == 5432
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_cors_origins_parsing():
    """Verify comma-separated and JSON string CORS parsing."""
    s1 = Settings(ALLOWED_ORIGINS="http://localhost:3000,http://app.local")
    assert len(s1.ALLOWED_ORIGINS) == 2
    assert "http://localhost:3000" in s1.ALLOWED_ORIGINS
    assert "http://app.local" in s1.ALLOWED_ORIGINS

    s2 = Settings(ALLOWED_ORIGINS='["http://mendix.local"]')
    assert len(s2.ALLOWED_ORIGINS) == 1
    assert "http://mendix.local" in s2.ALLOWED_ORIGINS


def test_database_urls():
    """Verify construction of async and sync database connection URLs."""
    settings = Settings(
        POSTGRES_USER="testuser",
        POSTGRES_PASSWORD="testpassword",
        POSTGRES_SERVER="db.internal",
        POSTGRES_PORT=5433,
        POSTGRES_DB="test_control_tower",
    )
    assert settings.async_database_url == "postgresql+asyncpg://testuser:testpassword@db.internal:5433/test_control_tower"
    assert settings.sync_database_url == "postgresql+psycopg2://testuser:testpassword@db.internal:5433/test_control_tower"
