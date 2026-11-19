"""Integration Tests for Carrier Recovery & Resource Dispatch REST API.

Tests full recovery workflow: draft plan, request carrier, carrier quote response,
driver/vehicle resource dispatch, completion with exception resolution, and RBAC authorization.
"""

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
async def recovery_test_setup():
    """Sets up FastAPI test app with database entities and authenticated RBAC credentials."""
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

        # 1. Admin
        admin = User(
            email=f"rec_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Recovery Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Carrier Rep (has carriers:respond, lacks recovery:request, recovery:dispatch, recovery:approve)
        carrier_user = User(
            email=f"rec_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Recovery Carrier",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        # 3. Dispatcher (has shipments:write, shipments:read, lacks carriers:respond)
        dispatcher_user = User(
            email=f"rec_dispatcher_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("DispatchPass123!"),
            full_name="Recovery Dispatcher",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(dispatcher_user)
        dispatcher_role = await role_repo.get_role_by_name("Dispatcher / Planner")
        assert dispatcher_role is not None
        await role_repo.assign_role_to_user(dispatcher_user.id, dispatcher_role.id)

        await session.commit()

        admin_token = create_access_token(admin.id, admin.email, roles=["System Administrator"])
        carrier_token = create_access_token(carrier_user.id, carrier_user.email, roles=["Carrier"])
        dispatcher_token = create_access_token(dispatcher_user.id, dispatcher_user.email, roles=["Dispatcher / Planner"])

        return {
            "app": app,
            "transport": transport,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
            "dispatcher_headers": {"Authorization": f"Bearer {dispatcher_token}"},
        }


@pytest.mark.asyncio
async def test_full_recovery_workflow_and_exception_lifecycle(recovery_test_setup):
    """Verify end-to-end recovery lifecycle from drafting to dispatch and resolution."""
    env = recovery_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # 2. Log an exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "VEHICLE_BREAKDOWN",
                "severity": "HIGH",
                "title": "Transmission failure on I-55",
                "description": "Tractor immobile near Springfield",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]

        # 3. Draft a recovery plan
        create_res = await client.post(
            "/api/v1/recovery",
            headers=env["admin_headers"],
            json={
                "exception_id": exception_id,
                "plan_type": "VEHICLE_REPLACEMENT",
                "carrier_code": "APEX",
                "carrier_name": "Apex Logistics",
                "estimated_cost": 1800.0,
                "estimated_recovery_hours": 4.0,
                "instructions": "Dispatch replacement tractor to Springfield interchange",
            },
        )
        assert create_res.status_code == 201
        plan_data = create_res.json()["data"]
        plan_id = plan_data["id"]
        assert plan_data["status"] == "DRAFT"
        assert plan_data["carrier_code"] == "APEX"

        # 4. Request carrier proposal
        req_res = await client.post(
            f"/api/v1/recovery/{plan_id}/request-carrier",
            headers=env["admin_headers"],
        )
        assert req_res.status_code == 200
        assert req_res.json()["data"]["status"] == "REQUESTED"

        # 5. Carrier accepts the proposal
        accept_res = await client.post(
            f"/api/v1/recovery/{plan_id}/carrier-respond",
            headers=env["carrier_headers"],
            json={
                "accepted": True,
                "carrier_notes": "Unit 402 dispatched from Bloomington terminal",
                "revised_estimated_cost": 1750.0,
                "revised_recovery_hours": 3.5,
            },
        )
        assert accept_res.status_code == 200
        assert accept_res.json()["data"]["status"] == "ACCEPTED"
        assert accept_res.json()["data"]["estimated_cost"] == 1750.0

        # 6. Dispatch resources
        dispatch_res = await client.post(
            f"/api/v1/recovery/{plan_id}/dispatch",
            headers=env["admin_headers"],
            json={
                "driver_name": "David Miller",
                "driver_phone": "+1-555-443-2211",
                "vehicle_plate": "IL-TRK-9012",
                "dispatch_notes": "Departed terminal at 14:30 CST",
            },
        )
        assert dispatch_res.status_code == 200
        assert dispatch_res.json()["data"]["status"] == "DISPATCHED"

        # Verify underlying exception status transitioned to RESOLVING
        get_exc_res = await client.get(
            f"/api/v1/exceptions/{exception_id}",
            headers=env["admin_headers"],
        )
        assert get_exc_res.status_code == 200
        assert get_exc_res.json()["data"]["status"] == "RESOLVING"

        # 7. Complete recovery operation
        complete_res = await client.post(
            f"/api/v1/recovery/{plan_id}/complete",
            headers=env["admin_headers"],
            json={
                "completion_notes": "Handover executed; cargo rolling again.",
                "resolve_exception": True,
            },
        )
        assert complete_res.status_code == 200
        assert complete_res.json()["data"]["status"] == "COMPLETED"

        # Verify underlying exception is now RESOLVED
        get_exc_final = await client.get(
            f"/api/v1/exceptions/{exception_id}",
            headers=env["admin_headers"],
        )
        assert get_exc_final.status_code == 200
        assert get_exc_final.json()["data"]["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_recovery_carrier_rejection_workflow(recovery_test_setup):
    """Verify carrier rejection logs rejection reason and marks plan REJECTED."""
    env = recovery_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Ingest shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1002",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # Create exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "TEMPERATURE_EXCURSION",
                "severity": "CRITICAL",
                "title": "Cryogenic unit power loss",
                "description": "Backup power failing",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]

        # Draft & request recovery plan
        draft_res = await client.post(
            "/api/v1/recovery",
            headers=env["admin_headers"],
            json={
                "exception_id": exception_id,
                "plan_type": "CROSS_DOCK",
                "carrier_code": "SKYCARGO",
                "carrier_name": "Skyward Air Cargo",
                "estimated_cost": 5000.0,
            },
        )
        plan_id = draft_res.json()["data"]["id"]

        await client.post(
            f"/api/v1/recovery/{plan_id}/request-carrier",
            headers=env["admin_headers"],
        )

        # Carrier rejects
        reject_res = await client.post(
            f"/api/v1/recovery/{plan_id}/carrier-respond",
            headers=env["carrier_headers"],
            json={
                "accepted": False,
                "rejection_reason": "No certified cold-chain vehicles in region.",
            },
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["data"]["status"] == "REJECTED"
        assert reject_res.json()["data"]["rejection_reason"] == "No certified cold-chain vehicles in region."


@pytest.mark.asyncio
async def test_recovery_rbac_enforcement(recovery_test_setup):
    """Verify RBAC authorization prevents unauthorized actions."""
    env = recovery_test_setup
    dummy_id = uuid.uuid4()

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Carrier lacks recovery:request -> 403 Forbidden
        draft_res = await client.post(
            "/api/v1/recovery",
            headers=env["carrier_headers"],
            json={
                "exception_id": str(dummy_id),
                "carrier_code": "TEST",
                "carrier_name": "Test Carrier",
            },
        )
        assert draft_res.status_code == 403

        # Carrier lacks recovery:dispatch -> 403 Forbidden
        dispatch_res = await client.post(
            f"/api/v1/recovery/{dummy_id}/dispatch",
            headers=env["carrier_headers"],
            json={
                "driver_name": "John Doe",
                "driver_phone": "+1-555-000-1111",
                "vehicle_plate": "ABC-123",
            },
        )
        assert dispatch_res.status_code == 403
