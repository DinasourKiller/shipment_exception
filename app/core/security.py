"""Core Cryptography and Security Module.

Implements Argon2id password hashing and cryptographic token generation.
Strictly adheres to enterprise security rules:
- Passwords are hashed with Argon2id.
- Refresh tokens are cryptographically random and stored exclusively as SHA-256 hashes.
"""

import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.logging import get_logger

logger = get_logger("control_tower.security")

# Initialize Argon2id password hasher with secure defaults
ph = PasswordHasher(
    time_cost=3,        # 3 iterations
    memory_cost=65536,  # 64 MiB
    parallelism=4,      # 4 lanes/threads
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception as exc:
        logger.warning(f"Password verification encountered an unexpected error: {exc}")
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if hash parameters require upgrade."""
    return ph.check_needs_rehash(hashed_password)


def generate_opaque_token(nbytes: int = 48) -> str:
    """Generate a cryptographically random, URL-safe opaque string."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 digest of an opaque token for secure storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
