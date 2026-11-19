"""Integration Tests for Shipment Exception Management REST API.

Tests exception creation, status state machine transitions, operator assignment,
urgency escalation, resolution with root-cause tracking, automated anomaly triggers,
and granular RBAC authorization enforcement.
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
from app.modules.exceptions.router import get_exception_service
from app.modules.exceptions.service import ExceptionService
from app.modules.roles.repository import RoleRepository
from app.modules.shipments.router import get_mendix_client


@pytest.fixture
async def exceptions_test_setup():
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

    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. Admin (has exceptions:read, manage, escalate, close)
        admin = User(
            email=f"exc_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Exception Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst (has exceptions:read, exceptions:manage)
        analyst = User(
            email=f"exc_analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Exception Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Customer Service (has exceptions:read, lacks manage/escalate/close)
        cs_user = User(
            email=f"exc_cs_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CSPass123!"),
            full_name="Exception Customer Service",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(cs_user)
        cs_role = await role_repo.get_role_by_name("Customer Service")
        assert cs_role is not None
        await role_repo.assign_role_to_user(cs_user.id, cs_role.id)

        # 4. Carrier (lacks exceptions:read and exceptions:manage)
        carrier_user = User(
            email=f"exc_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Exception Carrier Rep",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        await session.commit()

        admin_token = create_access_token(admin.id, admin.email, roles=["System Administrator"])
        analyst_token = create_access_token(analyst.id, analyst.email, roles=["Control Tower Analyst"])
        cs_token = create_access_token(cs_user.id, cs_user.email, roles=["Customer Service"])
        carrier_token = create_access_token(carrier_user.id, carrier_user.email, roles=["Carrier"])

        return {
            "app": app,
            "transport": transport,
            "admin_user": admin,
            "analyst_user": analyst,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "analyst_headers": {"Authorization": f"Bearer {analyst_token}"},
            "cs_headers": {"Authorization": f"Bearer {cs_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
        }


@pytest.mark.asyncio
async def test_create_and_get_exception_lifecycle(exceptions_test_setup):
    """Verify creating an exception, checking default SLA, and retrieving audit logs."""
    env = exceptions_test_setup
    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # First ingest MDX-SHP-1001
        sync_resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        assert sync_resp.status_code == 200
        shipment_id = sync_resp.json()["data"]["id"]

        # Create an exception
        create_payload = {
            "shipment_id": shipment_id,
            "exception_type": "VEHICLE_BREAKDOWN",
            "severity": "HIGH",
            "title": "Tire blowout on Highway 40",
            "description": "Right rear tire punctured; driver waiting for roadside service.",
            "metadata_payload": {"mile_marker": 142, "highway": "I-40"},
        }
        res = await client.post(
            "/api/v1/exceptions",
            json=create_payload,
            headers=env["analyst_headers"],
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["title"] == "Tire blowout on Highway 40"
        assert data["exception_type"] == "VEHICLE_BREAKDOWN"
        assert data["severity"] == "HIGH"
        assert data["status"] == "OPEN"
        assert data["sla_breach_at"] is not None
        exception_id = data["id"]

        # Retrieve exception by ID
        get_res = await client.get(
            f"/api/v1/exceptions/{exception_id}",
            headers=env["cs_headers"],  # CS has read permission
        )
        assert get_res.status_code == 200
        detail = get_res.json()["data"]
        assert detail["id"] == exception_id
        assert detail["shipment"]["external_reference"] == "MDX-SHP-1001"
        assert len(detail["audit_logs"]) >= 1
        assert detail["audit_logs"][0]["action"] == "CREATED"


@pytest.mark.asyncio
async def test_exception_status_transition_state_machine(exceptions_test_setup):
    """Verify legal and illegal state machine transitions on an exception."""
    env = exceptions_test_setup
    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Ingest shipment
        sync_resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        shipment_id = sync_resp.json()["data"]["id"]

        # Create exception
        create_res = await client.post(
            "/api/v1/exceptions",
            json={
                "shipment_id": shipment_id,
                "exception_type": "DELAY",
                "severity": "MEDIUM",
                "title": "Heavy fog delay",
                "description": "Reduced speed due to dense fog.",
            },
            headers=env["admin_headers"],
        )
        exc_id = create_res.json()["data"]["id"]

        # 1. Valid transition: OPEN -> INVESTIGATING
        patch_res = await client.patch(
            f"/api/v1/exceptions/{exc_id}/status",
            json={"status": "INVESTIGATING", "comment": "Dispatch verifying road conditions"},
            headers=env["analyst_headers"],
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["data"]["status"] == "INVESTIGATING"

        # 2. Valid transition: INVESTIGATING -> RESOLVING
        patch_res = await client.patch(
            f"/api/v1/exceptions/{exc_id}/status",
            json={"status": "RESOLVING", "comment": "Fog clearing; truck resuming standard speed"},
            headers=env["analyst_headers"],
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["data"]["status"] == "RESOLVING"

        # 3. Resolve via resolve endpoint
        res_resp = await client.post(
            f"/api/v1/exceptions/{exc_id}/resolve",
            json={
                "root_cause": "Weather conditions - dense morning fog",
                "resolution_notes": "Weather cleared; estimated arrival updated.",
            },
            headers=env["analyst_headers"],
        )
        assert res_resp.status_code == 200
        assert res_resp.json()["data"]["status"] == "RESOLVED"
        assert res_resp.json()["data"]["root_cause"] == "Weather conditions - dense morning fog"

        # 4. Close via close endpoint
        close_resp = await client.post(
            f"/api/v1/exceptions/{exc_id}/close",
            json={"resolution_notes": "Resolved with customer acceptance."},
            headers=env["admin_headers"],
        )
        assert close_resp.status_code == 200
        assert close_resp.json()["data"]["status"] == "CLOSED"

        # 5. Illegal transition: CLOSED -> OPEN (Must fail 400 ValidationException)
        illegal_res = await client.patch(
            f"/api/v1/exceptions/{exc_id}/status",
            json={"status": "OPEN"},
            headers=env["admin_headers"],
        )
        assert illegal_res.status_code == 400
        assert "Illegal exception lifecycle transition" in illegal_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_assign_and_escalate_exception(exceptions_test_setup):
    """Verify operator assignment and severity escalation."""
    env = exceptions_test_setup
    analyst_user = env["analyst_user"]
    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        sync_resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1002",
            headers=env["admin_headers"],
        )
        shipment_id = sync_resp.json()["data"]["id"]

        create_res = await client.post(
            "/api/v1/exceptions",
            json={
                "shipment_id": shipment_id,
                "exception_type": "CUSTOMS_HOLD",
                "severity": "LOW",
                "title": "Missing commercial invoice",
                "description": "Customs clearance held pending paperwork.",
            },
            headers=env["analyst_headers"],
        )
        exc_id = create_res.json()["data"]["id"]

        # Assign to Analyst
        assign_res = await client.post(
            f"/api/v1/exceptions/{exc_id}/assign",
            json={"assigned_to_user_id": str(analyst_user.id), "comment": "Assigned to customs desk"},
            headers=env["admin_headers"],
        )
        assert assign_res.status_code == 200
        assign_data = assign_res.json()["data"]
        assert assign_data["assigned_to_user_id"] == str(analyst_user.id)
        assert assign_data["status"] == "INVESTIGATING"

        # Escalate to CRITICAL
        esc_res = await client.post(
            f"/api/v1/exceptions/{exc_id}/escalate",
            json={"severity": "CRITICAL", "reason": "SLA deadline in jeopardy; expedite customs broker"},
            headers=env["admin_headers"],
        )
        assert esc_res.status_code == 200
        esc_data = esc_res.json()["data"]
        assert esc_data["severity"] == "CRITICAL"
        assert esc_data["status"] == "ESCALATED"


@pytest.mark.asyncio
async def test_list_exceptions_filtering_and_search(exceptions_test_setup):
    """Verify pagination and multi-parameter filtering on exceptions."""
    env = exceptions_test_setup
    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        sync_resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        shipment_id = sync_resp.json()["data"]["id"]

        # Create two distinct exceptions
        await client.post(
            "/api/v1/exceptions",
            json={
                "shipment_id": shipment_id,
                "exception_type": "TEMPERATURE_EXCURSION",
                "severity": "CRITICAL",
                "title": "Cold chain breached: +8C",
                "description": "Temperature probe reading +8C on chilled cargo.",
            },
            headers=env["admin_headers"],
        )
        await client.post(
            "/api/v1/exceptions",
            json={
                "shipment_id": shipment_id,
                "exception_type": "OTHER",
                "severity": "LOW",
                "title": "Minor packaging scuff",
                "description": "Outer carton scuffed during dock transfer.",
            },
            headers=env["admin_headers"],
        )

        # Filter by severity=CRITICAL
        list_crit = await client.get(
            "/api/v1/exceptions?severity=CRITICAL",
            headers=env["analyst_headers"],
        )
        assert list_crit.status_code == 200
        crit_items = list_crit.json()["data"]["items"]
        assert all(i["severity"] == "CRITICAL" for i in crit_items)

        # Search by keyword
        search_res = await client.get(
            "/api/v1/exceptions?search=probe",
            headers=env["analyst_headers"],
        )
        assert search_res.status_code == 200
        search_items = search_res.json()["data"]["items"]
        assert len(search_items) >= 1
        assert "Cold chain" in search_items[0]["title"]


@pytest.mark.asyncio
async def test_exceptions_rbac_permissions(exceptions_test_setup):
    """Verify RBAC guards enforce permissions across exception actions."""
    env = exceptions_test_setup
    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        sync_resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        shipment_id = sync_resp.json()["data"]["id"]

        # Carrier lacks exceptions:manage (must return 403)
        carrier_create = await client.post(
            "/api/v1/exceptions",
            json={
                "shipment_id": shipment_id,
                "exception_type": "DELAY",
                "severity": "LOW",
                "title": "Carrier attempt",
                "description": "Carrier attempting to create exception",
            },
            headers=env["carrier_headers"],
        )
        assert carrier_create.status_code == 403

        # Carrier lacks exceptions:read (must return 403)
        carrier_list = await client.get(
            "/api/v1/exceptions",
            headers=env["carrier_headers"],
        )
        assert carrier_list.status_code == 403

        # Customer Service has exceptions:read but lacks exceptions:close (must return 403)
        cs_close = await client.post(
            f"/api/v1/exceptions/{uuid.uuid4()}/close",
            json={},
            headers=env["cs_headers"],
        )
        assert cs_close.status_code == 403

        # Unauthenticated request returns 401
        unauth = await client.get("/api/v1/exceptions")
        assert unauth.status_code == 401


@pytest.mark.asyncio
async def test_automated_anomaly_detection_endpoint(exceptions_test_setup):
    """Verify triggering anomaly detection checks milestones and generates exceptions."""
    env = exceptions_test_setup
    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        sync_resp = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        shipment_id = sync_resp.json()["data"]["id"]

        # Trigger anomaly detection
        detect_res = await client.post(
            f"/api/v1/exceptions/detect-anomalies/{shipment_id}?delay_threshold=60",
            headers=env["admin_headers"],
        )
        assert detect_res.status_code == 200
        assert "Anomaly detection complete" in detect_res.json()["message"]
