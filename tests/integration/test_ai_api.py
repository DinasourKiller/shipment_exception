"""Integration Tests for AI-Driven Control Tower API Endpoints.

Verifies AI health check, root cause analysis, tactical recovery recommendations,
customer communication drafts, and strict RBAC authorization rules.
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
async def ai_test_setup():
    """Sets up FastAPI test app with seeded shipment, exception, and authenticated RBAC users."""
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
            email=f"ai_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="AI Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Carrier Rep (lacks exceptions:manage and recovery:request)
        carrier_user = User(
            email=f"ai_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="AI Carrier",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        # 3. Dispatcher (has recovery:request)
        dispatcher_user = User(
            email=f"ai_dispatcher_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("DispatchPass123!"),
            full_name="AI Dispatcher",
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
async def test_ai_health_endpoint(ai_test_setup):
    """Verify GET /api/v1/ai/health returns subsystem state and configured model."""
    env = ai_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Unauthenticated request -> 401
        unauth_res = await client.get("/api/v1/ai/health")
        assert unauth_res.status_code == 401

        # Authenticated request -> 200
        res = await client.get("/api/v1/ai/health", headers=env["admin_headers"])
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["model_configured"] == "gemma2:2b"
        assert body["data"]["status"] in ["online", "offline", "degraded"]
        assert "ollama" in body["data"]["active_provider"] or "fallback" in body["data"]["active_provider"]


@pytest.mark.asyncio
async def test_ai_root_cause_and_rbac(ai_test_setup):
    """Verify POST /api/v1/ai/root-cause/{id} analyzes exception and enforces RBAC."""
    env = ai_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest shipment
        sync_res = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=env["admin_headers"])
        assert sync_res.status_code == 200
        shipment_id = sync_res.json()["data"]["id"]

        # 2. Create exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "TEMPERATURE_EXCURSION",
                "severity": "CRITICAL",
                "title": "Cold-Chain Thermal Alert",
                "description": "Temperature probe reading 12C in refrigerated compartment",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]

        # 3. Carrier attempts to run root cause -> 403 Forbidden
        carrier_res = await client.post(
            f"/api/v1/ai/root-cause/{exception_id}",
            headers=env["carrier_headers"],
        )
        assert carrier_res.status_code == 403

        # 4. Admin runs root cause -> 200 OK
        admin_res = await client.post(
            f"/api/v1/ai/root-cause/{exception_id}",
            headers=env["admin_headers"],
        )
        assert admin_res.status_code == 200
        body = admin_res.json()
        assert body["success"] is True
        assert body["data"]["exception_id"] == exception_id
        assert len(body["data"]["synthesized_cause"]) > 20
        assert len(body["data"]["contributing_factors"]) >= 1
        assert body["data"]["confidence_score"] > 0.0


@pytest.mark.asyncio
async def test_ai_recovery_recommendation(ai_test_setup):
    """Verify POST /api/v1/ai/recommend-recovery/{id} generates tactical proposal."""
    env = ai_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest shipment
        sync_res = await client.post("/api/v1/shipments/sync/MDX-SHP-1002", headers=env["admin_headers"])
        assert sync_res.status_code == 200
        shipment_id = sync_res.json()["data"]["id"]

        # 2. Create exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "VEHICLE_BREAKDOWN",
                "severity": "HIGH",
                "title": "Engine failure on I-80",
                "description": "Coolant leak causing engine shutdown",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]

        # 3. Dispatcher calls recovery recommendation -> 200 OK
        rec_res = await client.post(
            f"/api/v1/ai/recommend-recovery/{exception_id}",
            headers=env["dispatcher_headers"],
        )
        assert rec_res.status_code == 200
        data = rec_res.json()["data"]
        assert data["recommended_strategy"] in [
            "VEHICLE_REPLACEMENT",
            "CROSS_DOCK",
            "ROUTE_REDIRECT",
            "AIR_EXPEDITE",
            "WAREHOUSE_HOLD",
            "RETURN_TO_ORIGIN",
        ]
        assert data["estimated_cost_usd"] > 0.0
        assert data["estimated_turnaround_hours"] > 0.0
        assert len(data["rationale"]) > 10


@pytest.mark.asyncio
async def test_ai_draft_communication_and_not_found(ai_test_setup):
    """Verify POST /api/v1/ai/draft-communication/{id} and 404 handling."""
    env = ai_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest shipment
        sync_res = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=env["admin_headers"])
        shipment_id = sync_res.json()["data"]["id"]

        # 2. Create exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "DELAY",
                "severity": "MEDIUM",
                "title": "Severe Highway Traffic Backlog",
                "description": "Multi-vehicle collision delayed delivery corridor by 3 hours",
            },
        )
        exception_id = exc_res.json()["data"]["id"]

        # 3. Draft communication -> 200 OK
        comm_res = await client.post(
            f"/api/v1/ai/draft-communication/{exception_id}",
            headers=env["admin_headers"],
        )
        assert comm_res.status_code == 200
        comm_data = comm_res.json()["data"]
        assert comm_data["customer_email"] != ""
        assert "MDX-SHP-1001" in comm_data["email_subject"]
        assert len(comm_data["email_body"]) > 50

        # 4. Request for non-existent exception -> 404
        non_existent_id = uuid.uuid4()
        not_found_res = await client.post(
            f"/api/v1/ai/root-cause/{non_existent_id}",
            headers=env["admin_headers"],
        )
        assert not_found_res.status_code == 404
