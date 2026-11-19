"""Shipment Management API Endpoints.

Provides REST endpoints for querying, filtering, Mendix ingestion,
and status transitions, protected by granular RBAC permissions.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.integrations.mendix.client import MendixClient
from app.modules.shipments.models import Shipment
from app.modules.shipments.repository import ShipmentRepository
from app.modules.shipments.schemas import (
    ShipmentDetailResponse,
    ShipmentListResponse,
    ShipmentStatusUpdateRequest,
    ShipmentSummaryResponse,
    ShipmentSyncResponse,
)
from app.modules.shipments.service import ShipmentService

router = APIRouter()


def get_mendix_client() -> MendixClient:
    """Dependency producing Mendix REST adapter client."""
    return MendixClient()


def get_shipment_service(
    session: AsyncSession = Depends(get_db_session),
    mendix_client: MendixClient = Depends(get_mendix_client),
) -> ShipmentService:
    repo = ShipmentRepository(session)
    return ShipmentService(repository=repo, mendix_client=mendix_client)


@router.get(
    "",
    response_model=ApiResponse[ShipmentListResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:read"))],
    summary="List shipments with search, filtering, and pagination",
)
async def list_shipments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[str] = Query(None, description="Filter by status (CREATED, BOOKED, IN_TRANSIT, etc.)"),
    carrier_code: Optional[str] = Query(None, description="Filter by carrier code"),
    transport_mode: Optional[str] = Query(None, description="Filter by mode (ROAD, AIR, OCEAN, RAIL)"),
    origin_city: Optional[str] = Query(None, description="Filter by origin city"),
    destination_city: Optional[str] = Query(None, description="Filter by destination city"),
    search: Optional[str] = Query(None, description="Search by order, tracking number, or external ID"),
    start_date: Optional[datetime] = Query(None, description="Earliest estimated delivery"),
    end_date: Optional[datetime] = Query(None, description="Latest estimated delivery"),
    service: ShipmentService = Depends(get_shipment_service),
) -> ApiResponse[ShipmentListResponse]:
    """Retrieves paginated shipments matching specified criteria."""
    items, total, total_pages = await service.list_shipments(
        page=page,
        page_size=page_size,
        status=status,
        carrier_code=carrier_code,
        transport_mode=transport_mode,
        origin_city=origin_city,
        destination_city=destination_city,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )

    summaries = [ShipmentSummaryResponse.model_validate(s) for s in items]
    data = ShipmentListResponse(
        items=summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

    return ApiResponse(
        success=True,
        data=data,
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/{shipment_id}",
    response_model=ApiResponse[ShipmentDetailResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:read"))],
    summary="Get full shipment details by UUID",
)
async def get_shipment_by_id(
    shipment_id: uuid.UUID,
    service: ShipmentService = Depends(get_shipment_service),
) -> ApiResponse[ShipmentDetailResponse]:
    """Retrieves complete details for a single shipment including cargo items, parties, and milestones."""
    shipment = await service.get_shipment_by_id(shipment_id)
    return ApiResponse(
        success=True,
        data=ShipmentDetailResponse.model_validate(shipment),
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/sync/{external_reference}",
    response_model=ApiResponse[ShipmentDetailResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:write"))],
    summary="Trigger on-demand ingestion/sync for a shipment from Mendix",
)
async def sync_single_shipment(
    external_reference: str,
    service: ShipmentService = Depends(get_shipment_service),
) -> ApiResponse[ShipmentDetailResponse]:
    """Fetches a shipment from Mendix by reference ID, transforms it to Canonical model, and upserts locally."""
    shipment = await service.ingest_from_mendix(external_reference)
    return ApiResponse(
        success=True,
        data=ShipmentDetailResponse.model_validate(shipment),
        message=f"Shipment '{external_reference}' successfully synchronized from Mendix",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/sync",
    response_model=ApiResponse[ShipmentSyncResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:write"))],
    summary="Trigger batch synchronization of updated shipments from Mendix",
)
async def sync_batch_shipments(
    since: Optional[datetime] = Query(None, description="Sync shipments updated since this timestamp"),
    limit: int = Query(50, ge=1, le=100, description="Max shipments to fetch"),
    service: ShipmentService = Depends(get_shipment_service),
) -> ApiResponse[ShipmentSyncResponse]:
    """Polls Mendix for all updated shipments and upserts them into the database."""
    from_date = since or datetime(2026, 1, 1, tzinfo=timezone.utc)
    synced = await service.sync_batch_from_mendix(since=from_date, limit=limit)

    return ApiResponse(
        success=True,
        data=ShipmentSyncResponse(
            synced_count=len(synced),
            message=f"Successfully synchronized {len(synced)} shipments from Mendix",
            shipment_ids=[s.id for s in synced],
        ),
        correlation_id=get_correlation_id(),
    )


@router.patch(
    "/{shipment_id}/status",
    response_model=ApiResponse[ShipmentDetailResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("shipments:write"))],
    summary="Update shipment operational status with state machine enforcement",
)
async def update_shipment_status(
    shipment_id: uuid.UUID,
    payload: ShipmentStatusUpdateRequest,
    service: ShipmentService = Depends(get_shipment_service),
) -> ApiResponse[ShipmentDetailResponse]:
    """Transitions shipment lifecycle status validating against legal state transitions."""
    updated = await service.update_status(
        shipment_id=shipment_id,
        target_status=payload.status,
        notes=payload.notes,
        actual_delivery=payload.actual_delivery,
    )
    return ApiResponse(
        success=True,
        data=ShipmentDetailResponse.model_validate(updated),
        message=f"Shipment status transitioned to {payload.status.upper()}",
        correlation_id=get_correlation_id(),
    )
