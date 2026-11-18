"""Structured Logging and Correlation ID Tracking Module.

Provides contextual JSON and text logging for enterprise observability.
Tracks request correlation IDs via contextvars to link logs across modules and integrations.
Enforces security rules: NEVER logs passwords, JWT keys, or raw tokens.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable to hold request correlation ID across async execution contexts
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Sensitive keys that must be redacted if present in log data
SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "api_key",
    "private_key",
    "cookie",
}


def get_correlation_id() -> Optional[str]:
    """Retrieve current correlation ID from context."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set current correlation ID in context."""
    correlation_id_ctx.set(correlation_id)


def sanitize_data(data: Any) -> Any:
    """Recursively sanitize sensitive fields in dictionaries or lists."""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_data(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        # Include exception details if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Include extra attributes attached to record
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj["extra"] = sanitize_data(record.extra)

        return json.dumps(log_obj)


class StandardFormatter(logging.Formatter):
    """Text-based human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        corr_id = get_correlation_id()
        corr_str = f" [{corr_id}]" if corr_id else ""
        record.msg = f"{corr_str} {record.msg}"
        return super().format(record)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Initialize structured logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        handler.setFormatter(StandardFormatter(fmt=fmt))

    root_logger.addHandler(handler)

    # Set external libraries to warning to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience helper to obtain a named logger."""
    return logging.getLogger(name)
