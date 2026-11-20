"""Unit Tests for Geofencing, Dynamic Corridors & Dwell Anomaly Engine."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.exceptions import ConflictException, ValidationException
from app.modules.geofence.geometry import (
    calculate_cross_track_deviation_meters,
    haversine_distance_meters,
    is_point_in_circular_geofence,
    is_point_in_polygon,
)
from app.modules.geofence.models import GeofenceZone, ShipmentDwellEvent
from app.modules.geofence.schemas import GeofenceZoneCreateRequest, SpatialEvaluationRequest
from app.modules.geofence.service import GeofenceService


# --- Geometry Algorithm Unit Tests ---

def test_haversine_distance_calculation():
    # Chicago (41.8781, -87.6298) to Dallas (32.7767, -96.7970) ~ 1288 km
    dist = haversine_distance_meters(41.8781, -87.6298, 32.7767, -96.7970)
    assert 1_280_000 < dist < 1_300_000

    # Same point distance is zero
    assert haversine_distance_meters(41.8781, -87.6298, 41.8781, -87.6298) == 0.0


def test_circular_geofence_containment():
    center_lat, center_lon = 41.8781, -87.6298  # Chicago downtown
    radius_meters = 1000.0  # 1 km

    # Point ~ 200m away
    assert is_point_in_circular_geofence(41.8790, -87.6298, center_lat, center_lon, radius_meters) is True

    # Point 10 km away
    assert is_point_in_circular_geofence(41.9742, -87.9073, center_lat, center_lon, radius_meters) is False


def test_polygon_ray_casting_containment():
    # Define rectangular polygon [lat, lon]
    poly = [
        [40.0, -90.0],
        [40.0, -80.0],
        [30.0, -80.0],
        [30.0, -90.0],
    ]

    # Inside
    assert is_point_in_polygon(35.0, -85.0, poly) is True

    # Outside
    assert is_point_in_polygon(45.0, -85.0, poly) is False
    assert is_point_in_polygon(35.0, -75.0, poly) is False


def test_corridor_cross_track_deviation():
    # Route straight from Chicago (41.8781, -87.6298) to Dallas (32.7767, -96.7970)
    # A point slightly off the track
    dev = calculate_cross_track_deviation_meters(
        current_lat=37.0,
        current_lon=-93.0,
        origin_lat=41.8781,
        origin_lon=-87.6298,
        dest_lat=32.7767,
        dest_lon=-96.7970,
    )
    # Deviation should be non-negative and finite
    assert dev >= 0.0
    assert dev < 500_000  # Less than 500 km offset


# --- Service Unit Tests ---

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def geofence_service(mock_session):
    return GeofenceService(session=mock_session)


@pytest.mark.asyncio
async def test_create_circular_geofence_success(geofence_service, mock_session):
    geofence_service.geofence_repo.get_by_code = AsyncMock(return_value=None)
    now_utc = datetime.now(timezone.utc)

    async def mock_create(z):
        z.id = uuid.uuid4()
        z.created_at = now_utc
        z.updated_at = now_utc
        return z

    geofence_service.geofence_repo.create_zone = AsyncMock(side_effect=mock_create)

    req = GeofenceZoneCreateRequest(
        zone_code="GF-ORD-01",
        name="O'Hare Cargo Terminal",
        zone_type="ORIGIN_FACILITY",
        geometry_type="CIRCULAR",
        center_latitude=41.9742,
        center_longitude=-87.9073,
        radius_meters=1500.0,
        max_permitted_dwell_minutes=180,
    )

    res = await geofence_service.create_geofence_zone(req)
    assert res.zone_code == "GF-ORD-01"
    assert res.name == "O'Hare Cargo Terminal"
    assert res.radius_meters == 1500.0


@pytest.mark.asyncio
async def test_create_geofence_duplicate_fails(geofence_service):
    existing = GeofenceZone(zone_code="GF-ORD-01", name="Duplicate")
    geofence_service.geofence_repo.get_by_code = AsyncMock(return_value=existing)

    req = GeofenceZoneCreateRequest(
        zone_code="GF-ORD-01",
        name="Duplicate",
        geometry_type="CIRCULAR",
        center_latitude=41.97,
        center_longitude=-87.90,
    )
    with pytest.raises(ConflictException):
        await geofence_service.create_geofence_zone(req)


@pytest.mark.asyncio
async def test_create_geofence_validation_error(geofence_service):
    geofence_service.geofence_repo.get_by_code = AsyncMock(return_value=None)

    # Missing center coordinates for CIRCULAR
    req = GeofenceZoneCreateRequest(
        zone_code="GF-BAD-01",
        name="Invalid Zone",
        geometry_type="CIRCULAR",
        center_latitude=None,
        center_longitude=None,
    )
    with pytest.raises(ValidationException):
        await geofence_service.create_geofence_zone(req)


@pytest.mark.asyncio
async def test_evaluate_spatial_restricted_area_intrusion(geofence_service, mock_session):
    shipment_id = uuid.uuid4()
    mock_shipment = MagicMock(
        id=shipment_id,
        tracking_number="TRK-1001",
        status="IN_TRANSIT",
        origin_city="Chicago",
        destination_city="Dallas",
    )
    geofence_service.shipment_repo.get_by_id = AsyncMock(return_value=mock_shipment)

    # Active restricted zone
    restricted_zone = GeofenceZone(
        id=uuid.uuid4(),
        zone_code="GF-RESTRICTED-01",
        name="Secure Hazardous Compound",
        zone_type="RESTRICTED_AREA",
        geometry_type="CIRCULAR",
        center_latitude=41.8781,
        center_longitude=-87.6298,
        radius_meters=1000.0,
        is_active=True,
    )
    geofence_service.geofence_repo.get_all_active_zones = AsyncMock(return_value=[restricted_zone])
    geofence_service.geofence_repo.get_active_dwell_for_shipment = AsyncMock(return_value=None)

    # Mock spatial exception trigger
    mock_exc = MagicMock(id=uuid.uuid4())
    geofence_service._trigger_spatial_exception = AsyncMock(return_value=mock_exc)

    req = SpatialEvaluationRequest(
        shipment_id=shipment_id,
        latitude=41.8785,
        longitude=-87.6295,
        speed_kmh=45.0,
    )

    resp = await geofence_service.evaluate_shipment_spatial_telemetry(req)
    assert resp.is_inside_restricted_zone is True
    assert "Secure Hazardous Compound" in resp.current_geofence_zones
    assert resp.generated_exception_type == "GEOFENCE_BREACH"


@pytest.mark.asyncio
async def test_evaluate_spatial_dwell_anomaly_escalation(geofence_service, mock_session):
    shipment_id = uuid.uuid4()
    mock_shipment = MagicMock(
        id=shipment_id,
        tracking_number="TRK-1002",
        status="IN_TRANSIT",
        origin_city="Chicago",
        destination_city="Dallas",
    )
    geofence_service.shipment_repo.get_by_id = AsyncMock(return_value=mock_shipment)
    geofence_service.geofence_repo.get_all_active_zones = AsyncMock(return_value=[])

    # Existing dwell started 150 minutes ago
    dwell_start = datetime.now(timezone.utc) - timedelta(minutes=150)
    existing_dwell = ShipmentDwellEvent(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        latitude=41.50,
        longitude=-88.00,
        dwell_started_at=dwell_start,
        stationary_pings_count=5,
        is_authorized=True,
        is_alert_dispatched=False,
    )
    geofence_service.geofence_repo.get_active_dwell_for_shipment = AsyncMock(return_value=existing_dwell)
    geofence_service.geofence_repo.update_dwell_event = AsyncMock(return_value=existing_dwell)

    mock_exc = MagicMock(id=uuid.uuid4())
    geofence_service._trigger_spatial_exception = AsyncMock(return_value=mock_exc)

    # Ingest stationary ping (speed = 0)
    req = SpatialEvaluationRequest(
        shipment_id=shipment_id,
        latitude=41.50,
        longitude=-88.00,
        speed_kmh=0.0,
    )

    resp = await geofence_service.evaluate_shipment_spatial_telemetry(req)
    assert resp.is_dwell_active is True
    assert resp.is_unauthorized_dwell is True
    assert resp.generated_exception_type == "UNAUTHORIZED_DWELL"
    assert resp.dwell_duration_minutes >= 149.0
