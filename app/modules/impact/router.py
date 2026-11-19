"""Impact Analysis API Endpoints.

Provides REST endpoints for evaluating financial impact, customer risk,
and composite priority scores with automated operational escalation.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.impact.schemas import (
    ImpactAssessRequest,
    ImpactAssessmentResponse,
    ImpactSummaryStatsResponse,
    PaginatedImpactResponse,
)
from app.modules.impact.service import ImpactService

router = APIRouter()


def get_impact_service(session: AsyncSession = Depends(get_db_session)) -> ImpactService:
    """Dependency producing initialized ImpactService."""
    return ImpactService(session=session)


@router.post(
    "/assess/{exception_id}",
    response_model=ApiResponse[ImpactAssessmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate exception impact",
    description="Calculates financial loss, customer tier impact, and composite risk score (0-100).",
)
async def assess_exception(
    exception_id: uuid.UUID,
    payload: Optional[ImpactAssessRequest] = None,
    service: ImpactService = Depends(get_impact_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[ImpactAssessmentResponse]:
    assessment = await service.assess_exception_impact(
        exception_id=exception_id,
        request=payload,
        actor_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        data=ImpactAssessmentResponse.model_validate(assessment),
        message="Impact assessment calculated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/summary/stats",
    response_model=ApiResponse[ImpactSummaryStatsResponse],
    status_code=status.HTTP_200_OK,
    summary="Aggregated impact metrics",
    description="Retrieves aggregate financial exposure, critical assessments, and average priority scores.",
)
async def get_impact_summary(
    service: ImpactService = Depends(get_impact_service),
    _: User = Depends(require_permissions("exceptions:read")),
) -> ApiResponse[ImpactSummaryStatsResponse]:
    stats = await service.get_summary_statistics()
    return ApiResponse(
        success=True,
        data=stats,
        message="Impact summary statistics retrieved successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/exception/{exception_id}",
    response_model=ApiResponse[Optional[ImpactAssessmentResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get latest impact assessment for an exception",
    description="Retrieves the most recent impact evaluation for the specified exception ID.",
)
async def get_latest_by_exception(
    exception_id: uuid.UUID,
    service: ImpactService = Depends(get_impact_service),
    _: User = Depends(require_permissions("exceptions:read")),
) -> ApiResponse[Optional[ImpactAssessmentResponse]]:
    assessment = await service.get_latest_by_exception(exception_id)
    return ApiResponse(
        success=True,
        data=ImpactAssessmentResponse.model_validate(assessment) if assessment else None,
        message="Latest impact assessment retrieved." if assessment else "No assessment found.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/{assessment_id}",
    response_model=ApiResponse[ImpactAssessmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get impact assessment by ID",
    description="Retrieves a specific impact assessment by its UUID.",
)
async def get_assessment(
    assessment_id: uuid.UUID,
    service: ImpactService = Depends(get_impact_service),
    _: User = Depends(require_permissions("exceptions:read")),
) -> ApiResponse[ImpactAssessmentResponse]:
    assessment = await service.get_assessment(assessment_id)
    return ApiResponse(
        success=True,
        data=ImpactAssessmentResponse.model_validate(assessment),
        message="Impact assessment retrieved successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedImpactResponse],
    status_code=status.HTTP_200_OK,
    summary="List impact assessments",
    description="Returns paginated impact assessments with filtering by minimum score, auto-escalation, and exception ID.",
)
async def list_assessments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    is_auto_escalated: Optional[bool] = Query(default=None),
    exception_id: Optional[uuid.UUID] = Query(default=None),
    service: ImpactService = Depends(get_impact_service),
    _: User = Depends(require_permissions("exceptions:read")),
) -> ApiResponse[PaginatedImpactResponse]:
    result = await service.list_assessments(
        page=page,
        page_size=page_size,
        min_score=min_score,
        is_auto_escalated=is_auto_escalated,
        exception_id=exception_id,
    )
    return ApiResponse(
        success=True,
        data=result,
        message=f"Retrieved {len(result.items)} impact assessments.",
        correlation_id=get_correlation_id(),
    )
