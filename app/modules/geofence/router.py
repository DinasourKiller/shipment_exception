"""Geofencing, Dynamic Corridors & Dwell Anomaly API Router."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.geofence.schemas import (
    GeofenceZoneCreateRequest,
    GeofenceZoneResponse,
    GeofenceZoneUpdateRequest,
    PaginatedGeofenceResponse,
    ShipmentDwellEventResponse,
    SpatialEvaluationRequest,
    SpatialEvaluationResponse,
)
from app.modules.geofence.service import GeofenceService

logger = get_logger("control_tower.geofence.router")

router = APIRouter(prefix="/geofences", tags=["Geofences & Dwell Monitoring"])


def get_geofence_service(session: AsyncSession = Depends(get_db_session)) -> GeofenceService:
    return GeofenceService(session=session)


@router.post(
    "",
    response_model=ApiResponse[GeofenceZoneResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new geofence zone",
)
async def create_geofence_zone(
    payload: GeofenceZoneCreateRequest,
    current_user: User = Depends(require_roles("System Administrator", "Operations Manager")),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[GeofenceZoneResponse]:
    """Create a new circular or polygonal geofence perimeter boundary."""
    data = await service.create_geofence_zone(payload, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        message="Geofence zone created successfully",
        data=data,
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedGeofenceResponse],
    summary="List all geofence zones",
)
async def list_geofence_zones(
    active_only: bool = Query(False, description="Filter only active boundaries"),
    zone_type: Optional[str] = Query(None, description="Filter by zone type"),
    search: Optional[str] = Query(None, description="Search zone code or name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[PaginatedGeofenceResponse]:
    """Retrieve paginated list of geofence zones."""
    data = await service.list_geofence_zones(
        active_only=active_only,
        zone_type=zone_type,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        data=data,
    )


@router.get(
    "/{zone_id}",
    response_model=ApiResponse[GeofenceZoneResponse],
    summary="Get geofence zone by ID",
)
async def get_geofence_zone(
    zone_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[GeofenceZoneResponse]:
    """Fetch details for a specific geofence perimeter."""
    data = await service.get_geofence_zone(zone_id)
    return ApiResponse(
        success=True,
        data=data,
    )


@router.put(
    "/{zone_id}",
    response_model=ApiResponse[GeofenceZoneResponse],
    summary="Update an existing geofence zone",
)
async def update_geofence_zone(
    zone_id: uuid.UUID,
    payload: GeofenceZoneUpdateRequest,
    current_user: User = Depends(require_roles("System Administrator", "Operations Manager")),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[GeofenceZoneResponse]:
    """Update geofence zone radius, coordinates, or permitted dwell limits."""
    data = await service.update_geofence_zone(zone_id, payload)
    return ApiResponse(
        success=True,
        message="Geofence zone updated successfully",
        data=data,
    )


@router.delete(
    "/{zone_id}",
    response_model=ApiResponse[dict],
    summary="Delete a geofence zone",
)
async def delete_geofence_zone(
    zone_id: uuid.UUID,
    current_user: User = Depends(require_roles("System Administrator")),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[dict]:
    """Remove a geofence boundary."""
    await service.delete_geofence_zone(zone_id)
    return ApiResponse(
        success=True,
        message="Geofence zone deleted successfully",
        data={"id": str(zone_id)},
    )


@router.post(
    "/evaluate",
    response_model=ApiResponse[SpatialEvaluationResponse],
    summary="Evaluate GPS telemetry against geofences, corridors & dwells",
)
async def evaluate_spatial_telemetry(
    payload: SpatialEvaluationRequest,
    current_user: User = Depends(get_current_user),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[SpatialEvaluationResponse]:
    """Execute spatial evaluation on an incoming GPS telemetry coordinate.

    Checks:
    1. Perimeter inclusion against active circular and polygonal geofences.
    2. Restricted area breach alerts.
    3. Stationary dwell duration vs maximum permitted dwell thresholds.
    4. Great-circle route corridor deviation distance.
    """
    data = await service.evaluate_shipment_spatial_telemetry(payload)
    return ApiResponse(
        success=True,
        data=data,
    )


@router.get(
    "/shipments/{shipment_id}/dwells",
    response_model=ApiResponse[List[ShipmentDwellEventResponse]],
    summary="List dwell events for a shipment",
)
async def list_shipment_dwell_events(
    shipment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: GeofenceService = Depends(get_geofence_service),
) -> ApiResponse[List[ShipmentDwellEventResponse]]:
    """Retrieve full stationary dwell and detention history for a shipment."""
    data = await service.list_dwell_events_for_shipment(shipment_id)
    return ApiResponse(
        success=True,
        data=data,
    )
