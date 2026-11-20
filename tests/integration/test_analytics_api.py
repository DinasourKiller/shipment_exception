"""Integration Tests for Analytics, Reporting & Trend REST API.

Tests carrier performance scorecards, root-cause Pareto distributions,
SLA compliance percentages, cumulative financial exposure, CSV exports, and RBAC guards.
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
async def analytics_test_setup():
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

        # 1. Admin (has reporting:read)
        admin = User(
            email=f"an_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Analytics Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst (has reporting:read)
        analyst = User(
            email=f"an_analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Analytics Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Carrier Rep (lacks reporting:read)
        carrier_user = User(
            email=f"an_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Analytics Carrier",
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
        carrier_token = create_access_token(carrier_user.id, carrier_user.email, roles=["Carrier"])

        return {
            "app": app,
            "transport": transport,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "analyst_headers": {"Authorization": f"Bearer {analyst_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
        }


@pytest.mark.asyncio
async def test_analytics_endpoints_workflow(analytics_test_setup):
    """Verify carrier performance, root-cause distribution, SLA compliance, and financial exposure."""
    env = analytics_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Ingest a shipment first to ensure data exists
        await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=env["admin_headers"])

        # 1. Carrier Performance Scorecards
        perf_res = await client.get("/api/v1/analytics/carrier-performance", headers=env["analyst_headers"])
        assert perf_res.status_code == 200
        perf_data = perf_res.json()["data"]
        assert "carriers" in perf_data
        assert "total_carriers" in perf_data

        # 2. Root Cause Distribution
        root_res = await client.get("/api/v1/analytics/root-cause-distribution", headers=env["analyst_headers"])
        assert root_res.status_code == 200
        root_data = root_res.json()["data"]
        assert "items" in root_data
        assert "total_exceptions" in root_data
        assert "most_frequent_type" in root_data

        # 3. SLA Compliance
        sla_res = await client.get("/api/v1/analytics/sla-compliance", headers=env["analyst_headers"])
        assert sla_res.status_code == 200
        sla_data = sla_res.json()["data"]
        assert "compliance_rate_pct" in sla_data
        assert "total_exceptions" in sla_data

        # 4. Financial Exposure
        fin_res = await client.get("/api/v1/analytics/financial-exposure", headers=env["analyst_headers"])
        assert fin_res.status_code == 200
        fin_data = fin_res.json()["data"]
        assert "total_exposure_usd" in fin_data
        assert "delay_costs_usd" in fin_data


@pytest.mark.asyncio
async def test_export_exceptions_csv_endpoint(analytics_test_setup):
    """Verify downloading operational exceptions CSV export."""
    env = analytics_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Ingest shipment and create an exception
        ingest_res = await client.post("/api/v1/shipments/sync/MDX-SHP-1002", headers=env["admin_headers"])
        shipment_id = ingest_res.json()["data"]["id"]

        await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "CUSTOMS_HOLD",
                "severity": "MEDIUM",
                "title": "Customs inspection hold",
                "description": "Paperwork audit in progress",
            },
        )

        csv_res = await client.get("/api/v1/analytics/export/exceptions-csv", headers=env["admin_headers"])
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        assert "attachment; filename=operational_exceptions_report.csv" in csv_res.headers.get("content-disposition", "")
        content = csv_res.text
        assert "Exception_ID,Shipment_Ref,Order_Number" in content
        assert "MDX-SHP-1002" in content
        assert "CUSTOMS_HOLD" in content


@pytest.mark.asyncio
async def test_analytics_rbac_enforcement(analytics_test_setup):
    """Verify unauthorized role (Carrier) receives 403 Forbidden on analytics endpoints."""
    env = analytics_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Carrier lacks reporting:read -> 403
        get_res = await client.get("/api/v1/analytics/carrier-performance", headers=env["carrier_headers"])
        assert get_res.status_code == 403

        csv_res = await client.get("/api/v1/analytics/export/exceptions-csv", headers=env["carrier_headers"])
        assert csv_res.status_code == 403

        # Unauthenticated request -> 401
        unauth_res = await client.get("/api/v1/analytics/carrier-performance")
        assert unauth_res.status_code == 401
