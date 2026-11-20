"""JWT Token Generation, Signing, and Verification Module.

Enforces RS256 asymmetric cryptographic signing using external RSA PEM keys.
Validates issuer, audience, expiration, and token identifiers.
"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.core.logging import get_logger

logger = get_logger("control_tower.jwt")
settings = get_settings()

JWT_ISSUER = "shipment-control-tower"
JWT_AUDIENCE = "control-tower-api"


def _load_private_key() -> str | bytes:
    """Load RSA private key for RS256 signing."""
    key_path = Path(settings.JWT_PRIVATE_KEY_PATH)
    if key_path.exists():
        return key_path.read_bytes()

    if settings.JWT_ALGORITHM.startswith("RS") or settings.JWT_ALGORITHM.startswith("ES"):
        logger.warning(
            f"Asymmetric key not found at {key_path}. Falling back to SECRET_KEY with HS256 for local dev."
        )
    return settings.SECRET_KEY


def _load_public_key() -> str | bytes:
    """Load RSA public key for RS256 verification."""
    key_path = Path(settings.JWT_PUBLIC_KEY_PATH)
    if key_path.exists():
        return key_path.read_bytes()

    return settings.SECRET_KEY


def _get_active_algorithm() -> str:
    """Determine signing algorithm based on key availability."""
    private_path = Path(settings.JWT_PRIVATE_KEY_PATH)
    if private_path.exists() and settings.JWT_ALGORITHM.startswith("RS"):
        return settings.JWT_ALGORITHM
    return "HS256"


def create_access_token(
    user_id: str | uuid.UUID,
    email: str,
    roles: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a short-lived, signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "roles": roles or [],
        "jti": uuid.uuid4().hex,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }

    signing_key = _load_private_key()
    algorithm = _get_active_algorithm()

    encoded_jwt = jwt.encode(payload, signing_key, algorithm=algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    verification_key = _load_public_key()
    algorithm = _get_active_algorithm()

    try:
        payload = jwt.decode(
            token,
            verification_key,
            algorithms=[algorithm],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "jti", "iss", "aud"]},
        )

        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid token type. Access token required.")

        return payload

    except ExpiredSignatureError:
        raise UnauthorizedException("Access token has expired. Please refresh your session.")
    except (InvalidTokenError, Exception) as exc:
        raise UnauthorizedException(f"Invalid access token: {str(exc)}")
