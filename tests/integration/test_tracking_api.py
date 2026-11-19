"""Integration Tests for Tracking & Milestones REST API.

Tests tracking event ingestion, automated milestone progression,
dynamic ETA recalculation, timeline auditing, and RBAC authorization guards.
"""

import uuid
from datetime import datetime, timedelta, timezone
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
async def tracking_test_setup():
    """Sets up FastAPI test app with mocked Mendix adapter and database auth fixtures."""
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

    # Setup database users
    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. Admin (has shipments:write & shipments:read)
        admin = User(
            email=f"tr_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Tracking Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst (has shipments:read)
        analyst = User(
            email=f"tr_analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Tracking Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Customer Service (has shipments:read, lacks shipments:write)
        cs_user = User(
            email=f"tr_cs_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CSPass123!"),
            full_name="Tracking Customer Service",
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
async def test_record_tracking_event_and_milestone_progression(tracking_test_setup):
    """Verify recording an event matches milestone, sets actual_time, and marks milestone COMPLETED."""
    transport = tracking_test_setup["transport"]
    admin_headers = tracking_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Ingest test shipment from Mendix (has milestone HUB_TRANSIT)
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        assert sync_resp.status_code == 200
        shipment_id = sync_resp.json()["data"]["id"]

        # 2. Record tracking event for HUB_TRANSIT
        event_payload = {
            "event_code": "HUB_TRANSIT",
            "event_name": "Arrived at St. Louis Sorting Hub",
            "event_timestamp": "2026-11-19T14:15:00Z",
            "source": "CARRIER_API",
            "location_name": "St. Louis, MO",
            "notes": "Unloaded on dock 12 for sort",
        }
        event_resp = await client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json=event_payload,
            headers=admin_headers,
        )
        assert event_resp.status_code == 201, event_resp.text
        event_data = event_resp.json()["data"]
        assert event_data["event_code"] == "HUB_TRANSIT"
        assert event_data["milestone_id"] is not None

        # 3. Verify timeline shows milestone as COMPLETED
        timeline_resp = await client.get(
            f"/api/v1/tracking/{shipment_id}/timeline",
            headers=admin_headers,
        )
        assert timeline_resp.status_code == 200
        timeline = timeline_resp.json()["data"]
        hub_milestone = next(m for m in timeline["milestones"] if m["event_code"] == "HUB_TRANSIT")
        assert hub_milestone["status"] == "COMPLETED"
        assert hub_milestone["actual_time"] is not None


@pytest.mark.asyncio
async def test_record_gps_telemetry_ping(tracking_test_setup):
    """Verify GPS telemetry event stores coordinates without requiring milestone matching."""
    transport = tracking_test_setup["transport"]
    admin_headers = tracking_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        gps_payload = {
            "event_code": "GPS_PING",
            "event_name": "In-transit telemetry heartbeat",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "location_name": "I-55 Southbound Mile Marker 42",
            "source": "GPS_DEVICE",
        }
        resp = await client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json=gps_payload,
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["latitude"] == 41.8781
        assert data["longitude"] == -87.6298
        assert data["source"] == "GPS_DEVICE"
        assert data["milestone_id"] is None


@pytest.mark.asyncio
async def test_get_latest_tracking_event(tracking_test_setup):
    """Verify retrieving the latest physical tracking event."""
    transport = tracking_test_setup["transport"]
    admin_headers = tracking_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1002", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        # Record two events with distinct timestamps
        t1 = "2026-11-19T10:00:00Z"
        t2 = "2026-11-19T12:00:00Z"

        await client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json={"event_code": "SCAN_1", "event_name": "First Scan", "event_timestamp": t1},
            headers=admin_headers,
        )
        await client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json={"event_code": "SCAN_2", "event_name": "Latest Scan", "event_timestamp": t2},
            headers=admin_headers,
        )

        latest_resp = await client.get(
            f"/api/v1/tracking/{shipment_id}/latest",
            headers=admin_headers,
        )
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()["data"]
        assert latest_data["event_code"] == "SCAN_2"
        assert latest_data["event_name"] == "Latest Scan"


@pytest.mark.asyncio
async def test_recalculate_eta_endpoint(tracking_test_setup):
    """Verify dynamic ETA recalculation endpoint computes delay."""
    transport = tracking_test_setup["transport"]
    admin_headers = tracking_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        recalc_resp = await client.post(
            f"/api/v1/tracking/{shipment_id}/recalculate-eta",
            headers=admin_headers,
        )
        assert recalc_resp.status_code == 200
        data = recalc_resp.json()["data"]
        assert "shipment_id" in data
        assert "updated_estimated_delivery" in data
        assert "is_delayed" in data


@pytest.mark.asyncio
async def test_manual_milestone_update(tracking_test_setup):
    """Verify manual update of milestone status and actual timestamp."""
    transport = tracking_test_setup["transport"]
    admin_headers = tracking_test_setup["admin_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        # Get milestone ID from timeline
        timeline_resp = await client.get(f"/api/v1/tracking/{shipment_id}/timeline", headers=admin_headers)
        milestone = timeline_resp.json()["data"]["milestones"][0]
        milestone_id = milestone["id"]

        # Update milestone status to COMPLETED
        update_resp = await client.patch(
            f"/api/v1/tracking/milestones/{milestone_id}",
            json={"status": "COMPLETED", "notes": "Manually verified by dispatcher"},
            headers=admin_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["data"]["status"] == "COMPLETED"
        assert update_resp.json()["data"]["notes"] == "Manually verified by dispatcher"


@pytest.mark.asyncio
async def test_tracking_rbac_permissions(tracking_test_setup):
    """Verify that role lacking shipments:write (Customer Service) cannot post tracking events but can read timeline."""
    transport = tracking_test_setup["transport"]
    admin_headers = tracking_test_setup["admin_headers"]
    cs_headers = tracking_test_setup["cs_headers"]

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        sync_resp = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=admin_headers)
        shipment_id = sync_resp.json()["data"]["id"]

        # Read timeline: Allowed (Customer Service has shipments:read)
        read_resp = await client.get(f"/api/v1/tracking/{shipment_id}/timeline", headers=cs_headers)
        assert read_resp.status_code == 200

        # Post event: Forbidden (Customer Service lacks shipments:write)
        write_resp = await client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json={"event_code": "GPS_PING", "event_name": "Ping"},
            headers=cs_headers,
        )
        assert write_resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_request_to_tracking_returns_401(tracking_test_setup):
    """Verify unauthenticated request returns 401."""
    transport = tracking_test_setup["transport"]
    dummy_id = str(uuid.uuid4())

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(f"/api/v1/tracking/{dummy_id}/timeline")
        assert resp.status_code == 401
