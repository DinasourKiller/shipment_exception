"""Integration Tests for Delivery Management & e-POD REST API."""

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
async def delivery_test_setup():
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

        # 1. System Admin
        admin = User(
            email=f"del_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Delivery Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Carrier Rep
        carrier_user = User(
            email=f"del_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Delivery Carrier",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        # Clean up any leftover test delivery records for test idempotency
        from app.modules.delivery.models import ProofOfDelivery, DeliveryAttempt, DeliveryOtp
        from sqlalchemy import delete
        await session.execute(delete(ProofOfDelivery))
        await session.execute(delete(DeliveryAttempt))
        await session.execute(delete(DeliveryOtp))

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
async def test_delivery_full_epod_lifecycle(delivery_test_setup):
    """Verify complete delivery flow: OTP generation, e-POD submission, exception resolution, and certificate fetch."""
    env = delivery_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Ingest test shipment
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # Reset status for test idempotency
        async for session in get_db_session():
            from app.modules.shipments.models import Shipment
            from sqlalchemy import update
            await session.execute(
                update(Shipment)
                .where(Shipment.id == shipment_id)
                .values(status="IN_TRANSIT", actual_delivery=None)
            )
            await session.commit()
            break

        # 2. Create an open exception to test auto-resolution on delivery
        exc_res = await client.post(
            "/api/v1/exceptions",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "exception_type": "VEHICLE_BREAKDOWN",
                "severity": "MEDIUM",
                "title": "Severe Engine Breakdown",
                "description": "Ground fleet delayed due to engine malfunction",
            },
        )
        assert exc_res.status_code == 201
        exc_id = exc_res.json()["data"]["id"]

        # 3. Generate delivery release OTP
        otp_res = await client.post(
            f"/api/v1/deliveries/shipments/{shipment_id}/otp/generate",
            headers=env["carrier_headers"],
        )
        assert otp_res.status_code == 201
        otp_data = otp_res.json()["data"]
        plain_otp = otp_data["otp_code"]
        assert len(plain_otp) == 6

        # 4. Submit e-POD handover with valid OTP and digital signature
        pod_payload = {
            "recipient_name": "Marcus Vance",
            "recipient_signature_svg": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGQ9Ik0xMCAxMCBMOTAgOTAiLz48L3N2Zz4=",
            "photo_url": "https://storage.controltower.corp/epod/proof_99214.jpg",
            "otp_code": plain_otp,
            "handover_latitude": 32.7767,
            "handover_longitude": -96.7970,
            "notes": "Delivered to loading bay 4, signed on digital tablet",
        }
        pod_res = await client.post(
            f"/api/v1/deliveries/shipments/{shipment_id}/pod",
            headers=env["carrier_headers"],
            json=pod_payload,
        )
        assert pod_res.status_code == 201
        pod_data = pod_res.json()["data"]
        assert pod_data["recipient_name"] == "Marcus Vance"
        assert pod_data["is_otp_verified"] is True
        assert pod_data["delivery_status"] == "CONFIRMED"

        # 5. Verify shipment status advanced to DELIVERED
        shp_res = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=env["admin_headers"],
        )
        assert shp_res.status_code == 200
        assert shp_res.json()["data"]["status"] == "DELIVERED"
        assert shp_res.json()["data"]["actual_delivery"] is not None

        # 6. Verify exception was auto-resolved
        exc_verify = await client.get(
            f"/api/v1/exceptions/{exc_id}",
            headers=env["admin_headers"],
        )
        assert exc_verify.status_code == 200
        assert exc_verify.json()["data"]["status"] == "RESOLVED"
        assert "POD" in exc_verify.json()["data"]["root_cause"]

        # 7. Fetch recorded e-POD certificate
        get_pod_res = await client.get(
            f"/api/v1/deliveries/shipments/{shipment_id}/pod",
            headers=env["admin_headers"],
        )
        assert get_pod_res.status_code == 200
        cert = get_pod_res.json()["data"]
        assert cert["recipient_name"] == "Marcus Vance"
        assert cert["photo_url"] == "https://storage.controltower.corp/epod/proof_99214.jpg"

        # 8. Check delivery history aggregate
        hist_res = await client.get(
            f"/api/v1/deliveries/shipments/{shipment_id}/history",
            headers=env["admin_headers"],
        )
        assert hist_res.status_code == 200
        hist = hist_res.json()["data"]
        assert hist["is_delivered"] is True
        assert hist["proof_of_delivery"] is not None


@pytest.mark.asyncio
async def test_failed_delivery_attempt_and_history(delivery_test_setup):
    """Verify failed delivery attempt logging, status transition to DELAYED, and history tracking."""
    env = delivery_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        ingest_res = await client.post(
            "/api/v1/shipments/sync/MDX-SHP-1002",
            headers=env["admin_headers"],
        )
        assert ingest_res.status_code == 200
        shipment_id = ingest_res.json()["data"]["id"]

        # Check initial attempts count
        init_hist = await client.get(
            f"/api/v1/deliveries/shipments/{shipment_id}/history",
            headers=env["admin_headers"],
        )
        assert init_hist.status_code == 200
        initial_count = len(init_hist.json()["data"]["attempts"])

        # Log failed attempt
        attempt_res = await client.post(
            f"/api/v1/deliveries/shipments/{shipment_id}/failed-attempt",
            headers=env["carrier_headers"],
            json={
                "reason_code": "PREMISES_CLOSED",
                "notes": "Business gate shuttered at 17:30",
                "driver_name": "Sam Bridges",
                "latitude": 42.3601,
                "longitude": -71.0589,
            },
        )
        assert attempt_res.status_code == 201
        att_data = attempt_res.json()["data"]
        assert att_data["attempt_number"] == initial_count + 1
        assert att_data["reason_code"] == "PREMISES_CLOSED"

        # Verify shipment status is DELAYED
        shp_res = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=env["admin_headers"],
        )
        assert shp_res.status_code == 200
        assert shp_res.json()["data"]["status"] == "DELAYED"

        # Fetch history to verify attempt is listed
        hist_res = await client.get(
            f"/api/v1/deliveries/shipments/{shipment_id}/history",
            headers=env["admin_headers"],
        )
        assert hist_res.status_code == 200
        hist = hist_res.json()["data"]
        assert hist["is_delivered"] is False
        assert len(hist["attempts"]) == initial_count + 1
        assert hist["proof_of_delivery"] is None
