"""Integration Tests for Carrier Claims & SLA Penalty Settlement REST API."""

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
async def claims_test_setup():
    """Sets up FastAPI test app with authenticated RBAC credentials."""
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

        # 1. System Admin
        admin = User(
            email=f"claim_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Claims Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Operations Manager
        mgr = User(
            email=f"claim_mgr_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("MgrPass123!"),
            full_name="Claims Manager",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(mgr)
        mgr_role = await role_repo.get_role_by_name("Operations Manager")
        assert mgr_role is not None
        await role_repo.assign_role_to_user(mgr.id, mgr_role.id)

        # 3. Carrier Rep
        carrier = User(
            email=f"claim_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Claims Carrier",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier.id, carrier_role.id)

        await session.commit()

        admin_token = create_access_token(admin.id, admin.email, roles=["System Administrator"])
        mgr_token = create_access_token(mgr.id, mgr.email, roles=["Operations Manager"])
        carrier_token = create_access_token(carrier.id, carrier.email, roles=["Carrier"])

        return {
            "app": app,
            "transport": transport,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "mgr_headers": {"Authorization": f"Bearer {mgr_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
        }


@pytest.mark.asyncio
async def test_claims_end_to_end_lifecycle(claims_test_setup):
    """Verify complete claim flow: auto-creation, carrier dispute, settlement, and audit events."""
    env = claims_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # 2. Create exception
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "TEMPERATURE_EXCURSION",
                "severity": "HIGH",
                "title": "Cold-chain reefer temp exceeded 8C",
                "description": "Temperature data logger reported cargo temp excursion for 3 hours",
            },
        )
        assert exc_res.status_code == 201
        exc_id = exc_res.json()["data"]["id"]

        # 3. Auto-derive claim from exception
        auto_res = await client.post(
            "/api/v1/claims/auto-from-exception",
            headers=env["mgr_headers"],
            json={"exception_id": exc_id},
        )
        assert auto_res.status_code == 201
        claim = auto_res.json()["data"]
        claim_id = claim["id"]
        assert claim["claim_number"].startswith("CLM-")
        assert claim["status"] == "SUBMITTED"
        assert claim["claimed_amount_usd"] > 0

        # 4. Carrier disputes claim with counter-offer
        dispute_res = await client.post(
            f"/api/v1/claims/{claim_id}/dispute",
            headers=env["carrier_headers"],
            json={
                "dispute_reason": "Pre-cooling was delayed by shipper warehouse dock congestion.",
                "counter_offer_amount_usd": 450.0,
            },
        )
        assert dispute_res.status_code == 200
        disputed_claim = dispute_res.json()["data"]
        assert disputed_claim["status"] == "CARRIER_DISPUTED"
        assert disputed_claim["counter_offer_amount_usd"] == 450.0

        # 5. Operations Manager settles the claim
        settle_res = await client.post(
            f"/api/v1/claims/{claim_id}/settle",
            headers=env["mgr_headers"],
            json={
                "settled_amount_usd": 650.0,
                "settlement_method": "INVOICE_OFFSET",
                "settlement_notes": "Mediated settlement: 50% split on warehouse pre-cooling delay.",
            },
        )
        assert settle_res.status_code == 200
        settled_claim = settle_res.json()["data"]
        assert settled_claim["status"] == "SETTLED"
        assert settled_claim["settled_amount_usd"] == 650.0
        assert settled_claim["settled_at"] is not None

        # 6. Verify audit timeline includes all 3 milestone events
        get_res = await client.get(
            f"/api/v1/claims/{claim_id}",
            headers=env["admin_headers"],
        )
        assert get_res.status_code == 200
        timeline = get_res.json()["data"]["audit_events"]
        actions = [ev["action"] for ev in timeline]
        assert "SUBMITTED" in actions
        assert "DISPUTED" in actions
        assert "SETTLED" in actions


@pytest.mark.asyncio
async def test_claims_rbac_enforcement(claims_test_setup):
    """Verify RBAC protection on sensitive claims settlement operations."""
    env = claims_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Ingest shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1002",
            headers=env["admin_headers"],
        )
        shipment_id = ingest_res.json()["data"]["id"]

        # Admin files a claim
        claim_res = await client.post(
            "/api/v1/claims",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "carrier_code": "SKYCARGO",
                "carrier_name": "Skyward Air Cargo",
                "claim_type": "CARGO_DAMAGE",
                "claimed_amount_usd": 1500.0,
                "incident_description": "Pallet corner crushed during aircraft pallet loading",
            },
        )
        assert claim_res.status_code == 201
        claim_id = claim_res.json()["data"]["id"]

        # Carrier attempts to authorize their own settlement -> 403 Forbidden
        settle_res = await client.post(
            f"/api/v1/claims/{claim_id}/settle",
            headers=env["carrier_headers"],
            json={"settled_amount_usd": 500.0, "settlement_method": "INVOICE_OFFSET"},
        )
        assert settle_res.status_code == 403


@pytest.mark.asyncio
async def test_claims_summary_and_csv_export(claims_test_setup):
    """Verify claims summary metrics and RFC-4180 CSV reconciliation export."""
    env = claims_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Summary metrics
        sum_res = await client.get("/api/v1/claims/summary", headers=env["admin_headers"])
        assert sum_res.status_code == 200
        data = sum_res.json()["data"]
        assert "total_claims_count" in data
        assert "total_claimed_usd" in data
        assert "total_settled_usd" in data

        # 2. CSV export
        csv_res = await client.get("/api/v1/claims/export/csv", headers=env["admin_headers"])
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        assert "Claim Number,Carrier Code" in csv_res.text
