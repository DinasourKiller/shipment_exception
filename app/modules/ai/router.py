"""AI Module API Endpoints.

Provides REST endpoints for AI-driven root cause diagnosis, recovery recommendations,
proactive customer communications, and Ollama subsystem health checks.
"""

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.modules.ai.schemas import (
    AICustomerCommunicationResponse,
    AIHealthResponse,
    AIRecoveryRecommendationResponse,
    AIRootCauseResponse,
)
from app.modules.ai.service import AIService
from app.modules.authentication.models import User

router = APIRouter()


def get_ai_service(session: AsyncSession = Depends(get_db_session)) -> AIService:
    """Dependency producing initialized AIService."""
    return AIService(db=session)


@router.get(
    "/health",
    response_model=ApiResponse[AIHealthResponse],
    status_code=status.HTTP_200_OK,
    summary="AI Subsystem Health & Diagnostics",
    description="Inspects local Ollama runtime connectivity and installed model availability.",
)
async def get_ai_health(
    service: AIService = Depends(get_ai_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AIHealthResponse]:
    health_data = await service.check_health()
    return ApiResponse(
        success=True,
        data=health_data,
        message="AI subsystem status retrieved successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/root-cause/{exception_id}",
    response_model=ApiResponse[AIRootCauseResponse],
    status_code=status.HTTP_200_OK,
    summary="AI Root Cause Analysis",
    description="Synthesizes incident diagnostics, contributing factors, and severity using Ollama/Gemma 2.",
)
async def analyze_root_cause(
    exception_id: uuid.UUID,
    service: AIService = Depends(get_ai_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[AIRootCauseResponse]:
    result = await service.analyze_root_cause(exception_id=exception_id)
    return ApiResponse(
        success=True,
        data=result,
        message="AI root cause analysis completed successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/recommend-recovery/{exception_id}",
    response_model=ApiResponse[AIRecoveryRecommendationResponse],
    status_code=status.HTTP_200_OK,
    summary="AI Tactical Recovery Recommendation",
    description="Recommends optimal recovery action, cost, turnaround time, and risk trade-offs.",
)
async def recommend_recovery(
    exception_id: uuid.UUID,
    service: AIService = Depends(get_ai_service),
    current_user: User = Depends(require_permissions("recovery:request")),
) -> ApiResponse[AIRecoveryRecommendationResponse]:
    result = await service.recommend_recovery(exception_id=exception_id)
    return ApiResponse(
        success=True,
        data=result,
        message="AI recovery recommendation generated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/draft-communication/{exception_id}",
    response_model=ApiResponse[AICustomerCommunicationResponse],
    status_code=status.HTTP_200_OK,
    summary="AI Proactive Customer Communication",
    description="Drafts empathetic, transparent customer advisory email.",
)
async def draft_customer_communication(
    exception_id: uuid.UUID,
    service: AIService = Depends(get_ai_service),
    current_user: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[AICustomerCommunicationResponse]:
    result = await service.draft_customer_communication(exception_id=exception_id)
    return ApiResponse(
        success=True,
        data=result,
        message="Customer advisory communication drafted successfully.",
        correlation_id=get_correlation_id(),
    )
