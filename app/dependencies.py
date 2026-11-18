"""Global FastAPI dependencies for injection."""

from fastapi import Header
from app.common.constants import CORRELATION_ID_HEADER
from app.config import Settings, get_settings
from app.core.logging import get_correlation_id


def get_app_settings() -> Settings:
    """Dependency that returns validated application settings."""
    return get_settings()


def get_correlation_id_dep(
    x_correlation_id: str | None = Header(default=None, alias=CORRELATION_ID_HEADER)
) -> str | None:
    """Dependency that extracts correlation ID from header or context."""
    return x_correlation_id or get_correlation_id()
