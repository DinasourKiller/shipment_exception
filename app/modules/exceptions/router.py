"""Shipment Exception Management API Endpoints.

Provides REST endpoints for querying, creating, escalating, assigning,
and resolving shipment disruptions with granular RBAC authorization.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.integrations.mendix.client import MendixClient
from app.modules.authentication.models import User
from app.modules.exceptions.schemas import (
    ExceptionAssignRequest,
    ExceptionCloseRequest,
    ExceptionCreateRequest,
    ExceptionEscalateRequest,
    ExceptionResolveRequest,
    ExceptionResponse,
    ExceptionStatusUpdateRequest,
    PaginatedExceptionResponse,
)
from app.modules.exceptions.service import ExceptionService

router = APIRouter()


def get_exception_service(
    session: AsyncSession = Depends(get_db_session),
) -> ExceptionService:
    """Dependency producing initialized ExceptionService."""
    return ExceptionService(session=session, mendix_client=MendixClient())


@router.post(
    "",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Log a shipment exception",
    description="Creates an operational disruption record with automated SLA computation and Mendix synchronization.",
)
async def create_exception(
    payload: ExceptionCreateRequest,
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[ExceptionResponse]:
    exception = await service.create_exception(request=payload, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(exception),
        message="Shipment exception logged successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedExceptionResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("exceptions:read"))],
    summary="List shipment exceptions",
    description="Retrieves a paginated collection of exceptions with filtering on status, severity, type, and SLA breach.",
)
async def list_exceptions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    shipment_id: Optional[uuid.UUID] = Query(None, description="Filter by shipment UUID"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    severity: Optional[str] = Query(None, description="Filter by impact severity"),
    exception_type: Optional[str] = Query(None, description="Filter by category"),
    assigned_to_user_id: Optional[uuid.UUID] = Query(None, description="Filter by assigned operator"),
    is_sla_breached: Optional[bool] = Query(None, description="Filter by SLA violation status"),
    search: Optional[str] = Query(None, description="Keyword search across title, description, and shipment"),
    service: ExceptionService = Depends(get_exception_service),
) -> ApiResponse[PaginatedExceptionResponse]:
    data = await service.list_exceptions(
        page=page,
        page_size=page_size,
        shipment_id=shipment_id,
        status=status,
        severity=severity,
        exception_type=exception_type,
        assigned_to_user_id=assigned_to_user_id,
        is_sla_breached=is_sla_breached,
        search=search,
    )
    return ApiResponse(
        success=True,
        data=data,
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/shipment/{shipment_id}",
    response_model=ApiResponse[List[ExceptionResponse]],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("exceptions:read"))],
    summary="Get all exceptions for a shipment",
    description="Returns all active and resolved exceptions associated with a specific shipment.",
)
async def list_shipment_exceptions(
    shipment_id: uuid.UUID,
    service: ExceptionService = Depends(get_exception_service),
) -> ApiResponse[List[ExceptionResponse]]:
    exceptions = await service.list_by_shipment(shipment_id)
    return ApiResponse(
        success=True,
        data=[ExceptionResponse.model_validate(e) for e in exceptions],
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/{exception_id}",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("exceptions:read"))],
    summary="Get exception details and audit history",
    description="Retrieves a single exception by UUID along with complete audit log timeline and shipment context.",
)
async def get_exception_detail(
    exception_id: uuid.UUID,
    service: ExceptionService = Depends(get_exception_service),
) -> ApiResponse[ExceptionResponse]:
    exception = await service.get_exception(exception_id)
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(exception),
        correlation_id=get_correlation_id(),
    )


@router.patch(
    "/{exception_id}/status",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Transition exception lifecycle status",
    description="Advances or transitions the exception through its lifecycle state machine.",
)
async def update_exception_status(
    exception_id: uuid.UUID,
    payload: ExceptionStatusUpdateRequest,
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[ExceptionResponse]:
    updated = await service.update_status(
        exception_id=exception_id,
        request=payload,
        actor_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(updated),
        message=f"Exception status transitioned to '{updated.status}'.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{exception_id}/assign",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Assign exception to operator",
    description="Assigns or reassigns ownership of an exception to an operator user.",
)
async def assign_exception(
    exception_id: uuid.UUID,
    payload: ExceptionAssignRequest,
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[ExceptionResponse]:
    updated = await service.assign_exception(
        exception_id=exception_id,
        request=payload,
        actor_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(updated),
        message="Exception assignment updated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{exception_id}/escalate",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Escalate an exception",
    description="Elevates urgency to HIGH or CRITICAL, tightens resolution SLA, and notifies managers.",
)
async def escalate_exception(
    exception_id: uuid.UUID,
    payload: ExceptionEscalateRequest,
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:escalate")),
) -> ApiResponse[ExceptionResponse]:
    updated = await service.escalate_exception(
        exception_id=exception_id,
        request=payload,
        actor_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(updated),
        message=f"Exception escalated to {updated.severity} with status ESCALATED.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{exception_id}/resolve",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Resolve an exception",
    description="Marks exception as RESOLVED with mandatory root cause classification and recovery action notes.",
)
async def resolve_exception(
    exception_id: uuid.UUID,
    payload: ExceptionResolveRequest,
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[ExceptionResponse]:
    updated = await service.resolve_exception(
        exception_id=exception_id,
        request=payload,
        actor_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(updated),
        message="Exception marked as RESOLVED.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{exception_id}/close",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Close an exception",
    description="Formally closes an exception into terminal status.",
)
async def close_exception(
    exception_id: uuid.UUID,
    payload: ExceptionCloseRequest,
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:close")),
) -> ApiResponse[ExceptionResponse]:
    updated = await service.close_exception(
        exception_id=exception_id,
        request=payload,
        actor_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        data=ExceptionResponse.model_validate(updated),
        message="Exception closed permanently.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/detect-anomalies/{shipment_id}",
    response_model=ApiResponse[List[ExceptionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Run automated anomaly detection on a shipment",
    description="Executes rule-based anomaly detection engines against milestones and telemetry pings for the target shipment.",
)
async def detect_shipment_anomalies(
    shipment_id: uuid.UUID,
    delay_threshold: int = Query(60, ge=15, le=1440, description="Delay threshold in minutes"),
    service: ExceptionService = Depends(get_exception_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[List[ExceptionResponse]]:
    delay_exceptions = await service.detect_milestone_delay_anomalies(
        shipment_id=shipment_id,
        delay_threshold_minutes=delay_threshold,
    )
    comm_loss = await service.detect_telemetry_silence_anomalies(shipment_id=shipment_id)
    all_triggered = list(delay_exceptions)
    if comm_loss:
        all_triggered.append(comm_loss)

    return ApiResponse(
        success=True,
        data=[ExceptionResponse.model_validate(e) for e in all_triggered],
        message=f"Anomaly detection complete. Triggered {len(all_triggered)} new exception(s).",
        correlation_id=get_correlation_id(),
    )
