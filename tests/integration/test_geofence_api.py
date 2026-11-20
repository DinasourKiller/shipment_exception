"""Integration Tests for Geofencing, Dynamic Corridors & Dwell Anomaly Engine REST API."""

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
async def geofence_test_setup():
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
            email=f"gf_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Geofence Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Operations Manager
        mgr = User(
            email=f"gf_mgr_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("MgrPass123!"),
            full_name="Geofence Manager",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(mgr)
        mgr_role = await role_repo.get_role_by_name("Operations Manager")
        assert mgr_role is not None
        await role_repo.assign_role_to_user(mgr.id, mgr_role.id)

        # 3. Carrier Rep
        carrier = User(
            email=f"gf_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Geofence Carrier Rep",
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
            "admin_user": admin,
        }


@pytest.mark.asyncio
async def test_geofence_crud_lifecycle(geofence_test_setup):
    env = geofence_test_setup
    code_suffix = uuid.uuid4().hex[:5].upper()

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # 1. Create Circular Geofence
        create_circ_res = await client.post(
            "/api/v1/geofences",
            headers=env["admin_headers"],
            json={
                "zone_code": f"GF-ORD-{code_suffix}",
                "name": "O'Hare Air Freight Hub",
                "zone_type": "ORIGIN_FACILITY",
                "geometry_type": "CIRCULAR",
                "center_latitude": 41.9742,
                "center_longitude": -87.9073,
                "radius_meters": 1200.0,
                "max_permitted_dwell_minutes": 180,
            },
        )
        assert create_circ_res.status_code == 201
        circ_data = create_circ_res.json()["data"]
        circ_id = circ_data["id"]
        assert circ_data["zone_code"] == f"GF-ORD-{code_suffix}"
        assert circ_data["radius_meters"] == 1200.0

        # 2. Create Polygonal Geofence
        create_poly_res = await client.post(
            "/api/v1/geofences",
            headers=env["admin_headers"],
            json={
                "zone_code": f"GF-CORR-{code_suffix}",
                "name": "Midwest Secure Corridor",
                "zone_type": "TRANSIT_CROSSDOCK",
                "geometry_type": "POLYGON",
                "polygon_coordinates": [
                    [42.0, -88.0],
                    [42.0, -87.0],
                    [41.0, -87.0],
                    [41.0, -88.0],
                ],
                "max_permitted_dwell_minutes": 90,
            },
        )
        assert create_poly_res.status_code == 201
        poly_id = create_poly_res.json()["data"]["id"]

        # 3. List Geofences with search
        list_res = await client.get(
            f"/api/v1/geofences?search={code_suffix}",
            headers=env["carrier_headers"],
        )
        assert list_res.status_code == 200
        items = list_res.json()["data"]["items"]
        assert len(items) >= 2

        # 4. Get Geofence by ID
        get_res = await client.get(f"/api/v1/geofences/{circ_id}", headers=env["carrier_headers"])
        assert get_res.status_code == 200
        assert get_res.json()["data"]["name"] == "O'Hare Air Freight Hub"

        # 5. Update Geofence (Operations Manager)
        upd_res = await client.put(
            f"/api/v1/geofences/{circ_id}",
            headers=env["mgr_headers"],
            json={"radius_meters": 2000.0, "max_permitted_dwell_minutes": 240},
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["data"]["radius_meters"] == 2000.0
        assert upd_res.json()["data"]["max_permitted_dwell_minutes"] == 240

        # 6. Delete Geofence (System Admin)
        del_res = await client.delete(f"/api/v1/geofences/{poly_id}", headers=env["admin_headers"])
        assert del_res.status_code == 200

        # Verify deletion
        get_after_del = await client.get(f"/api/v1/geofences/{poly_id}", headers=env["admin_headers"])
        assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_geofence_rbac_enforcement(geofence_test_setup):
    env = geofence_test_setup
    code = f"GF-RBAC-{uuid.uuid4().hex[:4].upper()}"

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Carrier representative attempting to create a geofence -> 403 Forbidden
        carrier_res = await client.post(
            "/api/v1/geofences",
            headers=env["carrier_headers"],
            json={
                "zone_code": code,
                "name": "Carrier Unauthorized Zone",
                "geometry_type": "CIRCULAR",
                "center_latitude": 40.0,
                "center_longitude": -80.0,
            },
        )
        assert carrier_res.status_code == 403

        # Admin creates it
        admin_res = await client.post(
            "/api/v1/geofences",
            headers=env["admin_headers"],
            json={
                "zone_code": code,
                "name": "Admin Authorized Zone",
                "geometry_type": "CIRCULAR",
                "center_latitude": 40.0,
                "center_longitude": -80.0,
            },
        )
        assert admin_res.status_code == 201
        zone_id = admin_res.json()["data"]["id"]

        # Operations Manager attempts to DELETE the zone -> 403 Forbidden (Admin only)
        mgr_del = await client.delete(f"/api/v1/geofences/{zone_id}", headers=env["mgr_headers"])
        assert mgr_del.status_code == 403

        # Clean up by Admin
        admin_del = await client.delete(f"/api/v1/geofences/{zone_id}", headers=env["admin_headers"])
        assert admin_del.status_code == 200


@pytest.mark.asyncio
async def test_spatial_evaluation_and_dwell_tracking(geofence_test_setup):
    env = geofence_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Sync shipment MDX-SHP-1001
        sync_res = await client.post("/api/v1/shipments/sync/MDX-SHP-1001", headers=env["admin_headers"])
        assert sync_res.status_code == 200
        shipment_id = sync_res.json()["data"]["id"]

        # Create active geofence zone for Chicago Terminal
        code = f"GF-CHI-{uuid.uuid4().hex[:4].upper()}"
        await client.post(
            "/api/v1/geofences",
            headers=env["admin_headers"],
            json={
                "zone_code": code,
                "name": "Chicago Freight Gate",
                "zone_type": "TRANSIT_CROSSDOCK",
                "geometry_type": "CIRCULAR",
                "center_latitude": 41.8781,
                "center_longitude": -87.6298,
                "radius_meters": 5000.0,  # 5 km
            },
        )

        # 1. Evaluate coordinate inside Chicago Gate at 50 km/h
        eval_res1 = await client.post(
            "/api/v1/geofences/evaluate",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "latitude": 41.8790,
                "longitude": -87.6290,
                "speed_kmh": 50.0,
                "location_name": "Chicago Terminal Gate",
            },
        )
        assert eval_res1.status_code == 200
        d1 = eval_res1.json()["data"]
        assert "Chicago Freight Gate" in d1["current_geofence_zones"]
        assert d1["is_dwell_active"] is False

        # 2. Evaluate stationary coordinate (speed = 0.0) -> commences dwell
        eval_res2 = await client.post(
            "/api/v1/geofences/evaluate",
            headers=env["admin_headers"],
            json={
                "shipment_id": shipment_id,
                "latitude": 41.8790,
                "longitude": -87.6290,
                "speed_kmh": 0.0,
                "location_name": "Chicago Terminal Gate",
            },
        )
        assert eval_res2.status_code == 200
        d2 = eval_res2.json()["data"]
        assert d2["is_dwell_active"] is True

        # 3. Retrieve dwell events history for this shipment
        dwell_res = await client.get(
            f"/api/v1/geofences/shipments/{shipment_id}/dwells",
            headers=env["admin_headers"],
        )
        assert dwell_res.status_code == 200
        dwell_events = dwell_res.json()["data"]
        assert len(dwell_events) >= 1
        assert dwell_events[0]["geofence_zone_name"] == "Chicago Freight Gate"
