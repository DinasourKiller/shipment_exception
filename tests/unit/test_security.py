"""Unit tests for Argon2id password hashing and cryptographic token utilities."""

from app.core.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)


def test_password_hashing_and_verification():
    """Verify password hashing with Argon2id and verification."""
    password = "SuperSecurePassword987!"
    hashed = hash_password(password)

    # Argon2id produces hash starting with $argon2id$
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert needs_rehash(hashed) is False


def test_opaque_token_and_hashing():
    """Verify opaque token generation and SHA-256 digest calculation."""
    token1 = generate_opaque_token(48)
    token2 = generate_opaque_token(48)

    assert len(token1) >= 64
    assert token1 != token2

    digest1 = hash_token(token1)
    digest2 = hash_token(token2)

    # SHA-256 hexadecimal output is 64 characters
    assert len(digest1) == 64
    assert len(digest2) == 64
    assert digest1 != digest2

    # Deterministic hashing
    assert hash_token(token1) == digest1
