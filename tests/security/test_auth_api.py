"""Security Integration Tests for Authentication, JWT, and Refresh Token Rotation."""

import uuid
import pytest
from httpx import AsyncClient

from app.common.constants import REFRESH_TOKEN_COOKIE_NAME
from app.core.security import hash_password
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository


@pytest.fixture
async def seeded_user() -> User:
    """Fixture creating an active test user in the database."""
    test_email = f"testuser_{uuid.uuid4().hex[:8]}@controltower.corp"
    user = User(
        email=test_email,
        hashed_password=hash_password("SuperSecretPassword123!"),
        full_name="Operations Specialist",
        is_active=True,
        is_verified=True,
    )
    async for session in get_db_session():
        repo = AuthenticationRepository(session)
        created = await repo.create_user(user)
        await session.commit()
        return created


async def test_login_success_and_cookie(async_client: AsyncClient, seeded_user: User):
    """Verify login returns JWT access token and sets HttpOnly refresh cookie."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "SuperSecretPassword123!"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert "access_token" in payload["data"]
    assert payload["data"]["token_type"] == "Bearer"

    # Verify cookie attributes
    assert REFRESH_TOKEN_COOKIE_NAME in response.cookies
    cookie = response.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    assert len(cookie) > 20


async def test_login_invalid_password(async_client: AsyncClient, seeded_user: User):
    """Verify login failure with wrong credentials returns 401."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "IncorrectPassword999!"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"


async def test_auth_me_endpoint(async_client: AsyncClient, seeded_user: User):
    """Verify /me returns current user info when valid Bearer token is provided."""
    # 1. Login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "SuperSecretPassword123!"},
    )
    token = login_resp.json()["data"]["access_token"]

    # 2. Query /me with token
    me_resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()["data"]
    assert me_data["email"] == seeded_user.email
    assert me_data["full_name"] == "Operations Specialist"


async def test_auth_me_unauthorized(async_client: AsyncClient):
    """Verify /me rejects unauthenticated requests."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_refresh_token_rotation_and_reuse_detection(async_client: AsyncClient, seeded_user: User):
    """Test full refresh token lifecycle:

    1. Login to receive Token A.
    2. Refresh using Token A -> receive Token B (Token A is now revoked).
    3. Refresh using Token B -> receive Token C.
    4. Replay attack: attempt refresh using revoked Token A -> triggers reuse detection!
    5. Verify Token C is now also revoked due to reuse detection.
    """
    # 1. Login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "SuperSecretPassword123!"},
    )
    token_a = login_resp.cookies.get(REFRESH_TOKEN_COOKIE_NAME)

    # 2. Refresh with Token A -> Get Token B
    refresh_resp_1 = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE_NAME: token_a},
    )
    assert refresh_resp_1.status_code == 200
    token_b = refresh_resp_1.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    assert token_b != token_a

    # 3. Refresh with Token B -> Get Token C
    refresh_resp_2 = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE_NAME: token_b},
    )
    assert refresh_resp_2.status_code == 200
    token_c = refresh_resp_2.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    assert token_c != token_b

    # 4. Attempt Replay Attack: Present OLD Token A
    reuse_resp = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE_NAME: token_a},
    )
    assert reuse_resp.status_code == 401
    assert "reuse detected" in reuse_resp.json()["error"]["message"].lower()

    # 5. Verify Token C is now revoked because reuse revoked all sessions for that user
    blocked_resp = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE_NAME: token_c},
    )
    assert blocked_resp.status_code == 401


async def test_logout(async_client: AsyncClient, seeded_user: User):
    """Verify logout revokes refresh token and clears cookie."""
    # Login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "SuperSecretPassword123!"},
    )
    refresh_token = login_resp.cookies.get(REFRESH_TOKEN_COOKIE_NAME)

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        cookies={REFRESH_TOKEN_COOKIE_NAME: refresh_token},
    )
    assert logout_resp.status_code == 200

    # Ensure refresh token no longer works
    attempt_resp = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE_NAME: refresh_token},
    )
    assert attempt_resp.status_code == 401
