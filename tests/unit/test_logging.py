"""Unit tests for structured logging and correlation ID handling."""

from app.core.logging import (
    get_correlation_id,
    sanitize_data,
    set_correlation_id,
)


def test_correlation_id_context():
    """Verify correlation ID context variable operations."""
    set_correlation_id("test-corr-id-12345")
    assert get_correlation_id() == "test-corr-id-12345"


def test_sanitize_sensitive_data():
    """Ensure sensitive credentials, tokens, and keys are redacted in logs."""
    raw_payload = {
        "username": "dispatcher_john",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJh...sample.token",
        "nested": {
            "api_key": "mendix-key-secret",
            "normal_field": "safe_value",
        },
        "list_items": [
            {"secret": "hidden_value", "id": 10},
        ],
    }

    sanitized = sanitize_data(raw_payload)
    assert sanitized["username"] == "dispatcher_john"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["normal_field"] == "safe_value"
    assert sanitized["list_items"][0]["secret"] == "[REDACTED]"
    assert sanitized["list_items"][0]["id"] == 10
