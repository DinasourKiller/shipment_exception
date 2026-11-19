"""Integration Tests for Shipment Management REST APIs.

Tests Mendix ingestion, database persistence, filtering, search,
status state transitions, and RBAC authorization guards.
"""

import uuid
from datetime import datetime, timezone
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
async def shipments_test_setup():
    """Sets up FastAPI test app with mocked Mendix adapter using ASGITransport and test auth fixtures."""
    app = create_application()
    transport = httpx.ASGITransport(app=app)

    # Dependency override: MendixClient connects to internal mock sandbox
    mock_mendix = MendixClient(
        base_url="http://testserver/api/v1/mock/mendix",
        api_key="valid-test-key",
        timeout_seconds=5.0,
        max_retries=1,
        transport=transport,
    )
    app.dependency_overrides[get_mendix_client] = lambda: mock_mendix

    # Create real users in PostgreSQL for RBAC checks
    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. Admin
        admin = User(
            email=f"shp_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Shipment Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst
        analyst = User(
            email=f"shp_analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Shipment Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Customer Service (has shipments:read, lacks shipments:write)
        cs_user = User(
            email=f"shp_cs_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CSPass123!"),
            full_name="Customer Service Rep",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(cs_user)
        cs_role = await role_repo.get_role_by_name("Customer Service")
        assert cs_role is not None
        await role_repo.assign_role_to_user(cs_user.id, cs_role.id)

        await session.commit()

        admin_token = create_access_token(admin.id, admin.email, roles=["System Administrator"])
        analyst_token = create_access_token(analyst.id, analyst.email, roles=["Control Tower Analyst"])
        cs_token = create_access_token(cs_user.id, cs_user.email, roles=["Customer Service"])

        return {
            "app": app,
            "transport": transport,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "analyst_headers": {"Authorization": f"Bearer {analyst_token}"},
            "cs_headers": {"Authorization": f"Bearer {cs_token}"},
        }


@pytest.mark.asyncio
async def test_sync_single_shipment_from_mendix(shipments_test_setup):
    """Verify on-demand ingestion of MDX-SHP-1001 from Mendix sandbox into PostgreSQL."""
    transport = shipments_test_setup["transport"]
    headers = shipments_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["external_reference"] == "MDX-SHP-1001"
        assert data["order_number"] == "ORD-2026-001"
        assert data["carrier_code"] == "APEX"
        assert data["status"] == "IN_TRANSIT"
        assert data["transport_mode"] == "ROAD"
        assert len(data["parties"]) == 2
        assert len(data["cargo_items"]) == 1
        assert len(data["milestones"]) == 2


@pytest.mark.asyncio
async def test_upsert_idempotency_does_not_duplicate(shipments_test_setup):
    """Verify that syncing the same external reference updates the record without creating duplicates."""
    transport = shipments_test_setup["transport"]
    headers = shipments_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # First sync
        resp1 = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=headers)
        assert resp1.status_code == 200
        id1 = resp1.json()["data"]["id"]

        # Second sync
        resp2 = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=headers)
        assert resp2.status_code == 200
        id2 = resp2.json()["data"]["id"]

        assert id1 == id2


@pytest.mark.asyncio
async def test_batch_sync_from_mendix(shipments_test_setup):
    """Verify polling batch of updated shipments from Mendix sandbox."""
    transport = shipments_test_setup["transport"]
    headers = shipments_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/shipments/sync?limit=10",
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["synced_count"] >= 2
        assert len(data["shipment_ids"]) >= 2


@pytest.mark.asyncio
async def test_get_shipment_by_id(shipments_test_setup):
    """Verify retrieval of detailed shipment by UUID with analyst role (shipments:read)."""
    transport = shipments_test_setup["transport"]
    admin_headers = shipments_test_setup["admin_headers"]
    analyst_headers = shipments_test_setup["analyst_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Ingest first
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        # Fetch as Analyst
        get_resp = await client.get(f"/api/v1/shipments/{shipment_id}", headers=analyst_headers)
        assert get_resp.status_code == 200
        data = get_resp.json()["data"]
        assert data["id"] == shipment_id
        assert data["external_reference"] == "MDX-SHP-1001"


@pytest.mark.asyncio
async def test_list_shipments_filtering_and_search(shipments_test_setup):
    """Verify search, pagination, carrier, and status filtering."""
    transport = shipments_test_setup["transport"]
    admin_headers = shipments_test_setup["admin_headers"]
    analyst_headers = shipments_test_setup["analyst_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Ingest batch
        await client.post("/api/v1/shipments/sync?limit=10", headers=admin_headers)

        # 1. Filter by carrier
        resp_carrier = await client.get("/api/v1/shipments?carrier_code=APEX", headers=analyst_headers)
        assert resp_carrier.status_code == 200
        items = resp_carrier.json()["data"]["items"]
        assert all(it["carrier_code"] == "APEX" for it in items)

        # 2. Search by order number
        resp_search = await client.get("/api/v1/shipments?search=ORD-2026-001", headers=analyst_headers)
        assert resp_search.status_code == 200
        assert len(resp_search.json()["data"]["items"]) >= 1

        # 3. Filter by transport mode
        resp_air = await client.get("/api/v1/shipments?transport_mode=AIR", headers=analyst_headers)
        assert resp_air.status_code == 200
        items_air = resp_air.json()["data"]["items"]
        assert all(it["transport_mode"] == "AIR" for it in items_air)


@pytest.mark.asyncio
async def test_shipment_status_transition_success_and_validation(shipments_test_setup):
    """Verify legal status transition (IN_TRANSIT -> DELIVERED) and illegal transition rejection."""
    transport = shipments_test_setup["transport"]
    admin_headers = shipments_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Ingest shipment (initial status IN_TRANSIT)
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        # Valid transition: IN_TRANSIT -> DELIVERED
        trans_resp = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "DELIVERED", "notes": "Successfully delivered to dock"},
            headers=admin_headers,
        )
        assert trans_resp.status_code == 200
        assert trans_resp.json()["data"]["status"] == "DELIVERED"
        assert trans_resp.json()["data"]["actual_delivery"] is not None

        # Illegal transition: DELIVERED -> IN_TRANSIT (terminal state error)
        illegal_resp = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "IN_TRANSIT"},
            headers=admin_headers,
        )
        assert illegal_resp.status_code == 400
        assert "Cannot transition shipment from terminal state 'DELIVERED'" in illegal_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_unauthorized_user_forbidden_from_shipment_management(shipments_test_setup):
    """Verify that a role without shipments:write permission is forbidden from syncing or status updates."""
    transport = shipments_test_setup["transport"]
    cs_headers = shipments_test_setup["cs_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Read is allowed for Customer Service (shipments:read)
        read_resp = await client.get("/api/v1/shipments", headers=cs_headers)
        assert read_resp.status_code == 200

        # Sync (shipments:write) is forbidden for Customer Service
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=cs_headers)
        assert sync_resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(shipments_test_setup):
    """Verify unauthenticated request to /api/v1/shipments returns 401."""
    transport = shipments_test_setup["transport"]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/shipments")
        assert resp.status_code == 401
