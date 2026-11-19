"""Integration Tests for Impact Analysis Engine REST API.

Tests impact evaluation calculation, customer tier weighting, automated priority escalations,
summary reporting metrics, and RBAC authorization.
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
from app.modules.exceptions.models import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentException,
)
from app.modules.roles.repository import RoleRepository
from app.modules.shipments.models import CargoItem, Shipment
from app.modules.shipments.router import get_mendix_client


@pytest.fixture
async def impact_test_setup():
    """Sets up FastAPI test app with database entities and authenticated RBAC credentials."""
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

        # 1. Admin (has exceptions:read, exceptions:manage)
        admin = User(
            email=f"impact_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Impact Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Carrier Rep (lacks exceptions:read, exceptions:manage)
        carrier_user = User(
            email=f"impact_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Impact Carrier",
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
            "admin_user": admin,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
        }


@pytest.mark.asyncio
async def test_assess_exception_impact_endpoint(impact_test_setup):
    """Verify evaluating impact calculates financial loss and composite risk score."""
    env = impact_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest a test shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # 2. Log an exception on the shipment
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "TEMPERATURE_EXCURSION",
                "severity": "HIGH",
                "title": "Reefer malfunction detected",
                "description": "Temperature rose above critical threshold of 4C",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]

        # 3. Assess impact with custom overrides
        assess_res = await client.post(
            f"/api/v1/impact/assess/{exception_id}",
            headers=env["admin_headers"],
            json={
                "custom_delay_hours": 5.0,
                "custom_hourly_penalty_rate": 200.0,
                "customer_tier": "VIP",
                "auto_escalate_threshold": 60.0,
            },
        )
        assert assess_res.status_code == 200
        impact_data = assess_res.json()["data"]
        assert impact_data["exception_id"] == exception_id
        assert impact_data["delay_cost"] == 1000.0  # 5h * $200
        assert impact_data["financial_impact"] >= 1000.0
        assert impact_data["composite_score"] > 0.0
        assert impact_data["calculation_factors"]["customer_tier"] == "VIP"
        assessment_id = impact_data["id"]

        # 4. Fetch assessment by ID
        get_res = await client.get(
            f"/api/v1/impact/{assessment_id}",
            headers=env["admin_headers"],
        )
        assert get_res.status_code == 200
        assert get_res.json()["data"]["id"] == assessment_id

        # 5. Fetch latest assessment for exception
        latest_res = await client.get(
            f"/api/v1/impact/exception/{exception_id}",
            headers=env["admin_headers"],
        )
        assert latest_res.status_code == 200
        assert latest_res.json()["data"]["id"] == assessment_id


@pytest.mark.asyncio
async def test_auto_escalation_on_high_risk(impact_test_setup):
    """Verify assessment with extreme financial exposure triggers auto-escalation of exception."""
    env = impact_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Ingest shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1002",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # Create OPEN exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "VEHICLE_BREAKDOWN",
                "severity": "HIGH",
                "title": "Engine failure on highway",
                "description": "Vehicle stranded with high-value cargo",
            },
        )
        assert exc_res.status_code == 201
        exception_id = exc_res.json()["data"]["id"]
        assert exc_res.json()["data"]["status"] == "OPEN"

        # Trigger impact assessment with catastrophic contractual penalty ($15,000)
        assess_res = await client.post(
            f"/api/v1/impact/assess/{exception_id}",
            headers=env["admin_headers"],
            json={
                "custom_contractual_penalty": 15000.0,
                "customer_tier": "VIP",
                "auto_escalate_threshold": 50.0,
            },
        )
        assert assess_res.status_code == 200
        impact_data = assess_res.json()["data"]
        assert impact_data["is_auto_escalated"] is True
        assert impact_data["financial_impact"] >= 15000.0

        # Verify underlying exception status is now ESCALATED
        get_exc_res = await client.get(
            f"/api/v1/exceptions/{exception_id}",
            headers=env["admin_headers"],
        )
        assert get_exc_res.status_code == 200
        assert get_exc_res.json()["data"]["status"] == "ESCALATED"
        assert get_exc_res.json()["data"]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_impact_summary_and_pagination(impact_test_setup):
    """Verify list pagination and aggregate summary statistics endpoints."""
    env = impact_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Fetch summary stats
        summary_res = await client.get(
            "/api/v1/impact/summary/stats",
            headers=env["admin_headers"],
        )
        assert summary_res.status_code == 200
        stats = summary_res.json()["data"]
        assert "total_assessed" in stats
        assert "total_financial_exposure_usd" in stats
        assert "critical_count" in stats
        assert "average_composite_score" in stats

        # Fetch list
        list_res = await client.get(
            "/api/v1/impact?page=1&page_size=10",
            headers=env["admin_headers"],
        )
        assert list_res.status_code == 200
        assert "items" in list_res.json()["data"]
        assert "total" in list_res.json()["data"]


@pytest.mark.asyncio
async def test_impact_rbac_enforcement(impact_test_setup):
    """Verify RBAC permissions enforce access control on impact assessment endpoints."""
    env = impact_test_setup
    dummy_id = uuid.uuid4()

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Carrier lacks exceptions:manage -> 403 Forbidden
        post_res = await client.post(
            f"/api/v1/impact/assess/{dummy_id}",
            headers=env["carrier_headers"],
            json={},
        )
        assert post_res.status_code == 403

        # Carrier lacks exceptions:read -> 403 Forbidden
        get_res = await client.get(
            "/api/v1/impact/summary/stats",
            headers=env["carrier_headers"],
        )
        assert get_res.status_code == 403
