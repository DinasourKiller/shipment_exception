"""Application Configuration Module.

Loads and validates settings from environment variables using Pydantic Settings.
Strictly avoids hardcoded credentials and provides validated defaults for development.
"""

from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings validated against environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    ENVIRONMENT: str = Field(default="development", description="Runtime environment: development, staging, production")
    APP_NAME: str = Field(default="Shipment Exception Control Tower", description="Human-readable application name")
    APP_VERSION: str = Field(default="1.0.0", description="SemVer application version")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    API_V1_PREFIX: str = Field(default="/api/v1", description="Prefix for Version 1 API routes")
    HOST: str = Field(default="0.0.0.0", description="Host interface to bind")
    PORT: int = Field(default=8000, description="Port to listen on")

    # Security & CORS
    ALLOWED_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-change-in-production-must-be-min-32-chars",
        description="Master secret key for internal cryptographic operations",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, description="Access token TTL in minutes (10-15m)")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token TTL in days (7-30d)")
    JWT_ALGORITHM: str = Field(default="RS256", description="JWT signing algorithm: RS256, ES256, or HS256")
    JWT_PRIVATE_KEY_PATH: str = Field(default="keys/jwt-private.pem", description="Path to RSA/EC private key")
    JWT_PUBLIC_KEY_PATH: str = Field(default="keys/jwt-public.pem", description="Path to RSA/EC public key")

    # Cookie Configuration (for refresh token)
    COOKIE_SECURE: bool = Field(default=False, description="Set True in production for HTTPS only cookies")
    COOKIE_SAMESITE: str = Field(default="lax", description="SameSite policy: lax, strict, none")
    COOKIE_DOMAIN: str = Field(default="", description="Cookie domain scope")

    # Database Configuration (PostgreSQL)
    POSTGRES_SERVER: str = Field(default="localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(default="postgres", description="PostgreSQL password")
    POSTGRES_DB: str = Field(default="shipment_control_tower", description="PostgreSQL database name")
    POSTGRES_SCHEMA: str = Field(default="public", description="Default PostgreSQL schema")
    DATABASE_POOL_SIZE: int = Field(default=10, description="SQLAlchemy connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Max overflow connections")
    DATABASE_POOL_TIMEOUT: int = Field(default=30, description="Pool connection timeout in seconds")

    # External Integrations - Mendix
    MENDIX_BASE_URL: str = Field(
        default="https://mendix-test.enterprise.local/rest",
        description="Base URL for Mendix REST API",
    )
    MENDIX_API_KEY: str = Field(default="mendix-placeholder-key", description="Mendix REST API Key")
    MENDIX_TIMEOUT_SECONDS: int = Field(default=10, description="HTTP timeout for Mendix requests")
    MENDIX_MAX_RETRIES: int = Field(default=3, description="Maximum retry count for transient errors")

    # AI Runtime - Ollama
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    OLLAMA_MODEL: str = Field(default="gemma2:2b", description="Default Ollama model for analysis")
    OLLAMA_TIMEOUT_SECONDS: int = Field(default=30, description="Timeout for LLM inference requests")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or text")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse allowed origins from JSON string or comma-separated list if provided as string."""
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def async_database_url(self) -> str:
        """Construct PostgreSQL async connection URI for asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Construct PostgreSQL sync connection URI for Alembic and sync tools."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        """Helper to determine whether the app is running in production."""
        return self.ENVIRONMENT.lower() in ("production", "prod")


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of Settings."""
    return Settings()
