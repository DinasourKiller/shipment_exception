"""Integration Tests for Cryptographic Audit Logging & Regulatory Compliance API."""

import uuid
import httpx
import pytest

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.database.connection import get_db_session
from app.integrations.mendix.client import MendixClient
from app.main import create_application
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.roles.repository import RoleRepository
from app.modules.shipments.router import get_mendix_client


@pytest.fixture
async def audit_test_setup():
    """Sets up FastAPI test app with authenticated RBAC users and Mendix mock."""
    app = create_application()
    transport = httpx.ASGITransport(app=app)

    mock_mendix = MendixClient(
        base_url="http://testserver/api/v1/mock/mendix",
        api_key="valid-test-key",
        timeout_seconds=5.0,
        max_retries=1,
        transport=transport,
    )
    app.dependency_overrides[get_mendix_client] = lambda: mock_mendix

    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. System Admin (has users:read, bypasses RBAC)
        admin = User(
            email=f"aud_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Audit Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Carrier Rep (lacks users:read)
        carrier_user = User(
            email=f"aud_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Audit Carrier",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        await session.commit()

        admin_token = create_access_token(admin.id, admin.email, roles=["System Administrator"])
        carrier_token = create_access_token(carrier_user.id, carrier_user.email, roles=["Carrier"])

        return {
            "app": app,
            "transport": transport,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
        }


@pytest.mark.asyncio
async def test_audit_logs_list_and_rbac(audit_test_setup):
    """Verify GET /api/v1/audit/logs returns paginated list and enforces RBAC."""
    env = audit_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Unauthenticated -> 401
        unauth_res = await client.get("/api/v1/audit/logs")
        assert unauth_res.status_code == 401

        # Carrier -> 403 Forbidden
        forbidden_res = await client.get("/api/v1/audit/logs", headers=env["carrier_headers"])
        assert forbidden_res.status_code == 403

        # Admin -> 200 OK
        res = await client.get("/api/v1/audit/logs", headers=env["admin_headers"])
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "total" in body["data"]


@pytest.mark.asyncio
async def test_audit_cryptographic_verification(audit_test_setup):
    """Verify GET /api/v1/audit/verify confirms hash chain validity."""
    env = audit_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        res = await client.get("/api/v1/audit/verify", headers=env["admin_headers"])
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["is_valid"] is True
        assert data["total_records_checked"] >= 0


@pytest.mark.asyncio
async def test_audit_export_csv(audit_test_setup):
    """Verify GET /api/v1/audit/export/compliance-csv returns valid formatted CSV."""
    env = audit_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        res = await client.get("/api/v1/audit/export/compliance-csv", headers=env["admin_headers"])
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/csv")
        csv_text = res.text
        assert "Sequence Number" in csv_text
        assert "Cryptographic Record SHA-256" in csv_text


@pytest.mark.asyncio
async def test_end_to_end_audit_recording_on_exception(audit_test_setup):
    """Verify operational mutations automatically generate SHA-256 chained audit entries."""
    env = audit_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Sync shipment
        sync_res = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=env["admin_headers"])
        assert sync_res.status_code == 200
        shipment_id = sync_res.json()["data"]["id"]

        # 2. Create exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "ROUTE_DEVIATION",
                "severity": "MEDIUM",
                "title": "Unplanned highway detour",
                "description": "Vehicle departed corridor by 15km",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]

        # 3. Query audit logs for this exception
        audit_res = await client.get(
            f"/api/v1/audit/logs?resource_id={exception_id}",
            headers=env["admin_headers"],
        )
        assert audit_res.status_code == 200
        items = audit_res.json()["data"]["items"]
        assert len(items) >= 1
        created_log = items[0]
        assert created_log["action"] == "EXCEPTION_CREATED"
        assert len(created_log["record_hash"]) == 64
        assert len(created_log["prev_record_hash"]) == 64

        # 4. Verify chain integrity across all records remains unbroken
        verify_res = await client.get("/api/v1/audit/verify", headers=env["admin_headers"])
        assert verify_res.status_code == 200
        assert verify_res.json()["data"]["is_valid"] is True
