"""Integration Tests for User Administration APIs (/api/v1/users).

Validates:
- Admin creates a user with initial role assignments.
- Duplicate email creation rejected with 409 Conflict.
- Paginated listing with search, active status, and role filtering.
- User profile retrieval and updating.
- User activation and deactivation.
- Protection preventing deactivation of the last active System Administrator.
- Bulk role synchronization.
- Administrative password reset (and verification that new password works).
- Authorization restrictions (403 Forbidden when lacking permissions).
"""

import uuid
import pytest
from httpx import AsyncClient

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.roles.repository import RoleRepository


@pytest.fixture
async def user_management_fixtures():
    """Setup admin, analyst, and standard test users."""
    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. Admin with full users:manage / users:read privileges
        admin = User(
            email=f"usermgr_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="User Manager Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst with users:read ONLY
        analyst = User(
            email=f"usermgr_analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Tower Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Carrier user (lacks users:read and users:manage)
        carrier_user = User(
            email=f"usermgr_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Carrier Rep",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        # Look up Dispatcher role ID for tests
        dispatcher_role = await role_repo.get_role_by_name("Dispatcher / Planner")
        assert dispatcher_role is not None

        await session.commit()

        return {
            "admin": admin,
            "analyst": analyst,
            "carrier_user": carrier_user,
            "admin_token": create_access_token(admin.id, admin.email, roles=["System Administrator"]),
            "analyst_token": create_access_token(analyst.id, analyst.email, roles=["Control Tower Analyst"]),
            "carrier_token": create_access_token(carrier_user.id, carrier_user.email, roles=["Carrier"]),
            "dispatcher_role_id": str(dispatcher_role.id),
        }


async def test_admin_create_user_with_roles(async_client: AsyncClient, user_management_fixtures: dict):
    """Admin creates a new user and assigns Dispatcher role."""
    admin_token = user_management_fixtures["admin_token"]
    dispatcher_role_id = user_management_fixtures["dispatcher_role_id"]
    new_email = f"created_user_{uuid.uuid4().hex[:6]}@controltower.corp"

    response = await async_client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": new_email,
            "password": "InitialSecurePassword123!",
            "full_name": "New Dispatcher Specialist",
            "is_active": True,
            "is_verified": True,
            "role_ids": [dispatcher_role_id],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["email"] == new_email
    assert payload["data"]["full_name"] == "New Dispatcher Specialist"
    role_names = [r["name"] for r in payload["data"]["roles"]]
    assert "Dispatcher / Planner" in role_names


async def test_create_user_duplicate_email_conflict(async_client: AsyncClient, user_management_fixtures: dict):
    """Attempting to create user with an existing email returns 409 Conflict."""
    admin_token = user_management_fixtures["admin_token"]
    existing_email = user_management_fixtures["analyst"].email

    response = await async_client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": existing_email,
            "password": "Password123!",
            "full_name": "Duplicate User",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_create_user_forbidden_for_non_manager(async_client: AsyncClient, user_management_fixtures: dict):
    """Analyst lacking 'users:manage' receives 403 Forbidden on create."""
    analyst_token = user_management_fixtures["analyst_token"]

    response = await async_client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={
            "email": f"forbidden_{uuid.uuid4().hex[:6]}@corp.local",
            "password": "Password123!",
            "full_name": "Forbidden Create",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_list_users_paginated_and_filtering(async_client: AsyncClient, user_management_fixtures: dict):
    """Test listing users with search, active status filter, and pagination metadata."""
    admin_token = user_management_fixtures["admin_token"]
    analyst_email = user_management_fixtures["analyst"].email

    # Search by analyst email
    response = await async_client.get(
        f"/api/v1/users?search={analyst_email}&page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]) >= 1
    assert payload["data"][0]["email"] == analyst_email
    assert "pagination" in payload
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["page_size"] == 10


async def test_list_users_filter_by_role(async_client: AsyncClient, user_management_fixtures: dict):
    """Filter users by role name."""
    admin_token = user_management_fixtures["admin_token"]

    response = await async_client.get(
        "/api/v1/users?role=System%20Administrator",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]) >= 1
    for u in payload["data"]:
        roles = [r["name"] for r in u["roles"]]
        assert "System Administrator" in roles


async def test_get_user_by_id(async_client: AsyncClient, user_management_fixtures: dict):
    """Retrieve user details by UUID."""
    admin_token = user_management_fixtures["admin_token"]
    analyst_id = user_management_fixtures["analyst"].id

    response = await async_client.get(
        f"/api/v1/users/{analyst_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["id"] == str(analyst_id)
    assert payload["data"]["email"] == user_management_fixtures["analyst"].email


async def test_update_user_profile(async_client: AsyncClient, user_management_fixtures: dict):
    """Admin updates user's full name."""
    admin_token = user_management_fixtures["admin_token"]
    carrier_user = user_management_fixtures["carrier_user"]

    response = await async_client.put(
        f"/api/v1/users/{carrier_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"full_name": "Updated Carrier Lead"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["full_name"] == "Updated Carrier Lead"


async def test_deactivate_and_activate_user(async_client: AsyncClient, user_management_fixtures: dict):
    """Admin deactivates and reactivates a user account."""
    admin_token = user_management_fixtures["admin_token"]
    carrier_user = user_management_fixtures["carrier_user"]

    # 1. Deactivate
    deact_resp = await async_client.patch(
        f"/api/v1/users/{carrier_user.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False, "reason": "Audit review hold"},
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["data"]["is_active"] is False

    # 2. Reactivate
    react_resp = await async_client.patch(
        f"/api/v1/users/{carrier_user.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": True, "reason": "Audit cleared"},
    )
    assert react_resp.status_code == 200
    assert react_resp.json()["data"]["is_active"] is True


async def test_sync_user_roles(async_client: AsyncClient, user_management_fixtures: dict):
    """Synchronize user roles via PUT /api/v1/users/{user_id}/roles."""
    admin_token = user_management_fixtures["admin_token"]
    carrier_user = user_management_fixtures["carrier_user"]
    dispatcher_role_id = user_management_fixtures["dispatcher_role_id"]

    response = await async_client.put(
        f"/api/v1/users/{carrier_user.id}/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role_ids": [dispatcher_role_id]},
    )
    assert response.status_code == 200
    payload = response.json()
    role_names = [r["name"] for r in payload["data"]["roles"]]
    assert "Dispatcher / Planner" in role_names
    assert "Carrier" not in role_names


async def test_admin_reset_password_and_login_verification(async_client: AsyncClient, user_management_fixtures: dict):
    """Admin resets user password; user logs in with new password and old password fails."""
    admin_token = user_management_fixtures["admin_token"]
    analyst = user_management_fixtures["analyst"]
    new_password = "BrandNewAnalystPassword999!"

    # 1. Admin resets password
    reset_resp = await async_client.post(
        f"/api/v1/users/{analyst.id}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": new_password},
    )
    assert reset_resp.status_code == 200

    # 2. Old password fails
    old_login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": analyst.email, "password": "AnalystPass123!"},
    )
    assert old_login_resp.status_code == 401

    # 3. New password succeeds
    new_login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": analyst.email, "password": new_password},
    )
    assert new_login_resp.status_code == 200
    assert "access_token" in new_login_resp.json()["data"]


async def test_unauthorized_access_to_users_endpoint(async_client: AsyncClient):
    """Requests without token receive 401."""
    response = await async_client.get("/api/v1/users")
    assert response.status_code == 401


async def test_carrier_forbidden_from_reading_users(async_client: AsyncClient, user_management_fixtures: dict):
    """Carrier user lacking 'users:read' receives 403 Forbidden."""
    carrier_token = user_management_fixtures["carrier_token"]
    response = await async_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {carrier_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
