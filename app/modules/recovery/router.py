"""Carrier Recovery & Resource Dispatch API Endpoints.

Provides REST endpoints for drafting recovery plans, carrier quoting and acceptance,
driver/vehicle dispatching, and resolution tracking with granular RBAC permissions.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.recovery.schemas import (
    PaginatedRecoveryResponse,
    RecoveryPlanCarrierResponseRequest,
    RecoveryPlanCompleteRequest,
    RecoveryPlanCreateRequest,
    RecoveryPlanDispatchRequest,
    RecoveryPlanResponse,
)
from app.modules.recovery.service import RecoveryService

router = APIRouter()


def get_recovery_service(session: AsyncSession = Depends(get_db_session)) -> RecoveryService:
    """Dependency producing initialized RecoveryService."""
    return RecoveryService(session=session)


@router.post(
    "",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Draft a recovery plan",
    description="Creates a new operational recovery plan linked to an exception.",
)
async def create_recovery_plan(
    payload: RecoveryPlanCreateRequest,
    service: RecoveryService = Depends(get_recovery_service),
    current_user: User = Depends(require_permissions("recovery:request")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.create_plan(request=payload, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message="Recovery plan drafted successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{plan_id}/request-carrier",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Request carrier recovery proposal",
    description="Transmits recovery proposal to the assigned carrier.",
)
async def request_carrier_proposal(
    plan_id: uuid.UUID,
    service: RecoveryService = Depends(get_recovery_service),
    current_user: User = Depends(require_permissions("recovery:request")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.request_carrier(plan_id=plan_id, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message=f"Recovery request transmitted to carrier {plan.carrier_name}.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{plan_id}/carrier-respond",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Carrier response to recovery request",
    description="Allows carrier to accept or reject the recovery proposal with revised terms.",
)
async def carrier_response(
    plan_id: uuid.UUID,
    payload: RecoveryPlanCarrierResponseRequest,
    service: RecoveryService = Depends(get_recovery_service),
    current_user: User = Depends(require_permissions("carriers:respond")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.carrier_respond(plan_id=plan_id, request=payload, actor_id=current_user.id)
    status_label = "accepted" if payload.accepted else "rejected"
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message=f"Carrier recovery request {status_label}.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{plan_id}/dispatch",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Dispatch resources for recovery",
    description="Allocates driver/vehicle and transitions underlying exception to RESOLVING.",
)
async def dispatch_recovery_resources(
    plan_id: uuid.UUID,
    payload: RecoveryPlanDispatchRequest,
    service: RecoveryService = Depends(get_recovery_service),
    current_user: User = Depends(require_permissions("recovery:dispatch")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.dispatch_resources(plan_id=plan_id, request=payload, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message=f"Recovery dispatched: Driver {plan.driver_name} (Vehicle: {plan.vehicle_plate}).",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{plan_id}/complete",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Complete recovery operation",
    description="Confirms completion of recovery and optionally resolves the underlying exception.",
)
async def complete_recovery_plan(
    plan_id: uuid.UUID,
    payload: RecoveryPlanCompleteRequest,
    service: RecoveryService = Depends(get_recovery_service),
    current_user: User = Depends(require_permissions("recovery:approve")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.complete_recovery(plan_id=plan_id, request=payload, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message="Recovery operation completed successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{plan_id}/cancel",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel recovery plan",
    description="Aborts or cancels an in-progress recovery plan.",
)
async def cancel_recovery_plan(
    plan_id: uuid.UUID,
    reason: Optional[str] = Query(default=None),
    service: RecoveryService = Depends(get_recovery_service),
    current_user: User = Depends(require_permissions("recovery:approve")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.cancel_plan(plan_id=plan_id, reason=reason, actor_id=current_user.id)
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message="Recovery plan cancelled.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/exception/{exception_id}",
    response_model=ApiResponse[List[RecoveryPlanResponse]],
    status_code=status.HTTP_200_OK,
    summary="List recovery plans for an exception",
    description="Retrieves all recovery plans and proposals associated with a specific exception.",
)
async def get_plans_by_exception(
    exception_id: uuid.UUID,
    service: RecoveryService = Depends(get_recovery_service),
    _: User = Depends(require_permissions("recovery:read")),
) -> ApiResponse[List[RecoveryPlanResponse]]:
    plans = await service.list_by_exception(exception_id)
    return ApiResponse(
        success=True,
        data=[RecoveryPlanResponse.model_validate(p) for p in plans],
        message=f"Retrieved {len(plans)} recovery plans.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/{plan_id}",
    response_model=ApiResponse[RecoveryPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Get recovery plan by ID",
    description="Retrieves full recovery plan operational details and lifecycle audit trail.",
)
async def get_recovery_plan(
    plan_id: uuid.UUID,
    service: RecoveryService = Depends(get_recovery_service),
    _: User = Depends(require_permissions("recovery:read")),
) -> ApiResponse[RecoveryPlanResponse]:
    plan = await service.get_plan(plan_id)
    return ApiResponse(
        success=True,
        data=RecoveryPlanResponse.model_validate(plan),
        message="Recovery plan retrieved successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedRecoveryResponse],
    status_code=status.HTTP_200_OK,
    summary="List recovery plans",
    description="Returns paginated recovery plans with filtering by status, carrier, and plan type.",
)
async def list_recovery_plans(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    carrier_code: Optional[str] = Query(default=None),
    plan_type: Optional[str] = Query(default=None),
    exception_id: Optional[uuid.UUID] = Query(default=None),
    service: RecoveryService = Depends(get_recovery_service),
    _: User = Depends(require_permissions("recovery:read")),
) -> ApiResponse[PaginatedRecoveryResponse]:
    result = await service.list_plans(
        page=page,
        page_size=page_size,
        status=status,
        carrier_code=carrier_code,
        plan_type=plan_type,
        exception_id=exception_id,
    )
    return ApiResponse(
        success=True,
        data=result,
        message=f"Retrieved {len(result.items)} recovery plans.",
        correlation_id=get_correlation_id(),
    )
