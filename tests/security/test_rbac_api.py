"""Security Integration Tests for Role-Based Access Control (RBAC).

Validates:
- System Administrator bypass across protected endpoints.
- Permission enforcement: 200 OK when user holds required permission.
- Permission denial: 403 Forbidden when user lacks required permission.
- Role management API workflows (list roles, permissions, create role, assign role).
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
async def rbac_test_users():
    """Create test users with various roles for RBAC verification."""
    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. Admin User
        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="System Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst User (has roles:read, but NOT roles:manage)
        analyst = User(
            email=f"analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Tower Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Plain User (No roles / unassigned)
        plain = User(
            email=f"plain_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("PlainPass123!"),
            full_name="Plain User",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(plain)

        await session.commit()

        return {
            "admin": admin,
            "analyst": analyst,
            "plain": plain,
            "admin_token": create_access_token(admin.id, admin.email, roles=["System Administrator"]),
            "analyst_token": create_access_token(analyst.id, analyst.email, roles=["Control Tower Analyst"]),
            "plain_token": create_access_token(plain.id, plain.email, roles=[]),
        }


async def test_list_roles_authorized(async_client: AsyncClient, rbac_test_users: dict):
    """Analyst holds 'roles:read' permission -> should successfully view roles."""
    response = await async_client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {rbac_test_users['analyst_token']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]) >= 7  # 7 seeded roles


async def test_list_roles_forbidden(async_client: AsyncClient, rbac_test_users: dict):
    """Plain user has no roles/permissions -> must receive 403 Forbidden."""
    response = await async_client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {rbac_test_users['plain_token']}"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "FORBIDDEN"


async def test_list_permissions_authorized(async_client: AsyncClient, rbac_test_users: dict):
    """Admin can list permissions via System Administrator bypass."""
    response = await async_client.get(
        "/api/v1/roles/permissions",
        headers={"Authorization": f"Bearer {rbac_test_users['admin_token']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]) >= 19  # 19 seeded permissions


async def test_create_role_forbidden_for_analyst(async_client: AsyncClient, rbac_test_users: dict):
    """Analyst holds 'roles:read' but lacks 'roles:manage' -> 403 Forbidden."""
    response = await async_client.post(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {rbac_test_users['analyst_token']}"},
        json={"name": f"Unauthorized Role {uuid.uuid4().hex[:4]}", "description": "Should fail"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_role_authorized_for_admin(async_client: AsyncClient, rbac_test_users: dict):
    """Admin holds full access -> 201 Created."""
    role_name = f"Custom Inspector {uuid.uuid4().hex[:6]}"
    response = await async_client.post(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {rbac_test_users['admin_token']}"},
        json={"name": role_name, "description": "Custom inspection role"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["name"] == role_name


async def test_role_assignment_lifecycle(async_client: AsyncClient, rbac_test_users: dict):
    """Admin assigns Dispatcher role to plain user, then revokes it."""
    admin_token = rbac_test_users["admin_token"]
    plain_user = rbac_test_users["plain"]

    # 1. Look up Dispatcher role ID
    roles_resp = await async_client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    dispatcher_role = next(
        r for r in roles_resp.json()["data"] if r["name"] == "Dispatcher / Planner"
    )
    dispatcher_role_id = dispatcher_role["id"]

    # 2. Assign role to plain user
    assign_resp = await async_client.post(
        f"/api/v1/roles/assign/{plain_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role_ids": [dispatcher_role_id]},
    )
    assert assign_resp.status_code == 200
    assigned_roles = [r["name"] for r in assign_resp.json()["data"]["roles"]]
    assert "Dispatcher / Planner" in assigned_roles

    # 3. Remove role from plain user
    remove_resp = await async_client.delete(
        f"/api/v1/roles/assign/{plain_user.id}/{dispatcher_role_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert remove_resp.status_code == 200
    remaining_roles = [r["name"] for r in remove_resp.json()["data"]["roles"]]
    assert "Dispatcher / Planner" not in remaining_roles


async def test_jwt_claims_contain_roles_after_login(async_client: AsyncClient, rbac_test_users: dict):
    """Verify that logging in issues a JWT containing the user's assigned roles."""
    from app.core.jwt import decode_access_token

    analyst = rbac_test_users["analyst"]
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": analyst.email, "password": "AnalystPass123!"},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["data"]["access_token"]

    payload = decode_access_token(access_token)
    assert "roles" in payload
    assert "Control Tower Analyst" in payload["roles"]


async def test_duplicate_role_creation_returns_conflict(async_client: AsyncClient, rbac_test_users: dict):
    """Attempting to create an existing role must return 409 Conflict."""
    response = await async_client.post(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {rbac_test_users['admin_token']}"},
        json={"name": "System Administrator", "description": "Duplicate role"},
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "CONFLICT"


async def test_assign_role_to_nonexistent_user_returns_404(async_client: AsyncClient, rbac_test_users: dict):
    """Assigning a role to a non-existent user UUID must return 404."""
    random_user_id = uuid.uuid4()
    response = await async_client.post(
        f"/api/v1/roles/assign/{random_user_id}",
        headers={"Authorization": f"Bearer {rbac_test_users['admin_token']}"},
        json={"role_ids": [str(uuid.uuid4())]},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "ENTITY_NOT_FOUND"


async def test_assign_nonexistent_role_to_user_returns_404(async_client: AsyncClient, rbac_test_users: dict):
    """Assigning a non-existent role UUID to an existing user must return 404."""
    plain_user = rbac_test_users["plain"]
    random_role_id = uuid.uuid4()
    response = await async_client.post(
        f"/api/v1/roles/assign/{plain_user.id}",
        headers={"Authorization": f"Bearer {rbac_test_users['admin_token']}"},
        json={"role_ids": [str(random_role_id)]},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "ENTITY_NOT_FOUND"


async def test_unauthenticated_request_to_roles_returns_401(async_client: AsyncClient):
    """Requesting protected role endpoints without token must return 401."""
    response = await async_client.get("/api/v1/roles")
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"


async def test_tampered_token_to_roles_returns_401(async_client: AsyncClient):
    """Requesting protected role endpoints with tampered JWT must return 401."""
    response = await async_client.get(
        "/api/v1/roles",
        headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.invalidpayload.invalidsignature"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"

