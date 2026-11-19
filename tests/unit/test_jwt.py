"""Unit tests for JWT token generation and verification."""

import uuid
from datetime import timedelta
import pytest

from app.core.exceptions import UnauthorizedException
from app.core.jwt import create_access_token, decode_access_token


def test_jwt_encode_and_decode():
    """Verify RS256 JWT encoding, claims preservation, and decoding."""
    user_id = uuid.uuid4()
    email = "analyst@controltower.corp"
    roles = ["Control Tower Analyst"]

    token = create_access_token(user_id=user_id, email=email, roles=roles)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["roles"] == roles
    assert payload["iss"] == "shipment-control-tower"
    assert payload["aud"] == "control-tower-api"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "jti" in payload


def test_jwt_expiration():
    """Verify that expired JWTs raise UnauthorizedException."""
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        email="test@expired.corp",
        expires_delta=timedelta(seconds=-10),  # Expired in past
    )

    with pytest.raises(UnauthorizedException) as exc_info:
        decode_access_token(token)

    assert "expired" in str(exc_info.value).lower()


def test_invalid_jwt():
    """Verify that malformed or tampered tokens raise UnauthorizedException."""
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_access_token("not.a.valid.jwt.token")

    assert "invalid" in str(exc_info.value).lower()
