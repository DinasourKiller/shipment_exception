"""Tracking & Milestones REST API Endpoints.

Provides endpoints for tracking event telemetry ingestion, real-time timeline auditing,
milestone progress updates, and dynamic ETA recalculations.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.modules.shipments.repository import ShipmentRepository
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import (
    EtaRecalculationResponse,
    MilestoneProgressItem,
    MilestoneUpdateRequest,
    ShipmentTrackingTimelineResponse,
    TrackingEventCreateRequest,
    TrackingEventResponse,
)
from app.modules.tracking.service import TrackingService

router = APIRouter()


def get_tracking_service(
    session: AsyncSession = Depends(get_db_session),
) -> TrackingService:
    tracking_repo = TrackingRepository(session)
    shipment_repo = ShipmentRepository(session)
    return TrackingService(tracking_repo=tracking_repo, shipment_repo=shipment_repo)


@router.post(
    "/{shipment_id}/events",
    response_model=ApiResponse[TrackingEventResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("shipments:write"))],
    summary="Record tracking event / telemetry ping and advance milestone progress",
)
async def record_tracking_event(
    shipment_id: uuid.UUID,
    payload: TrackingEventCreateRequest,
    service: TrackingService = Depends(get_tracking_service),
) -> ApiResponse[TrackingEventResponse]:
    """Ingests a telemetry ping or scan event, updates matched milestone, and evaluates ETA impact."""
    event = await service.record_event(shipment_id=shipment_id, request=payload)
    return ApiResponse(
        success=True,
        data=event,
        message=f"Tracking event '{payload.event_code}' recorded successfully",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/{shipment_id}/timeline",
    response_model=ApiResponse[ShipmentTrackingTimelineResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:read"))],
    summary="Get complete chronological tracking timeline and milestone progress",
)
async def get_tracking_timeline(
    shipment_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100, description="Max tracking events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: TrackingService = Depends(get_tracking_service),
) -> ApiResponse[ShipmentTrackingTimelineResponse]:
    """Retrieves full tracking audit trail, milestones, and delay indicators for a shipment."""
    timeline = await service.get_shipment_timeline(shipment_id=shipment_id, limit=limit, offset=offset)
    return ApiResponse(
        success=True,
        data=timeline,
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/{shipment_id}/latest",
    response_model=ApiResponse[Optional[TrackingEventResponse]],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:read"))],
    summary="Get the most recent tracking event or GPS coordinate",
)
async def get_latest_tracking_event(
    shipment_id: uuid.UUID,
    service: TrackingService = Depends(get_tracking_service),
) -> ApiResponse[Optional[TrackingEventResponse]]:
    """Retrieves the latest physical telemetry event recorded for a shipment."""
    latest = await service.get_latest_event(shipment_id=shipment_id)
    return ApiResponse(
        success=True,
        data=latest,
        correlation_id=get_correlation_id(),
    )


@router.patch(
    "/milestones/{milestone_id}",
    response_model=ApiResponse[MilestoneProgressItem],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:write"))],
    summary="Manually update milestone status and completion time",
)
async def update_milestone(
    milestone_id: uuid.UUID,
    payload: MilestoneUpdateRequest,
    service: TrackingService = Depends(get_tracking_service),
) -> ApiResponse[MilestoneProgressItem]:
    """Updates milestone status (e.g. COMPLETED, DELAYED) and recalculates shipment delivery ETA."""
    updated = await service.update_milestone_status(milestone_id=milestone_id, request=payload)
    return ApiResponse(
        success=True,
        data=updated,
        message=f"Milestone status updated to {payload.status.upper()}",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{shipment_id}/recalculate-eta",
    response_model=ApiResponse[EtaRecalculationResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:write"))],
    summary="Recalculate dynamic delivery ETA based on milestone progress",
)
async def recalculate_shipment_eta(
    shipment_id: uuid.UUID,
    service: TrackingService = Depends(get_tracking_service),
) -> ApiResponse[EtaRecalculationResponse]:
    """Performs dynamic ETA projection by calculating milestone delays and updating estimated delivery."""
    result = await service.recalculate_eta(shipment_id=shipment_id)
    return ApiResponse(
        success=True,
        data=result,
        correlation_id=get_correlation_id(),
    )
