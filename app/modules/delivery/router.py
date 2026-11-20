"""Delivery Management & Proof of Delivery (e-POD) API Router."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.delivery.schemas import (
    DeliveryAttemptResponse,
    DeliveryHistoryResponse,
    DeliveryOtpGenerateResponse,
    FailedDeliveryAttemptRequest,
    PodSubmissionRequest,
    ProofOfDeliveryResponse,
)
from app.modules.delivery.service import DeliveryService

logger = get_logger("control_tower.delivery.router")

router = APIRouter(prefix="/deliveries", tags=["Delivery & Proof of Delivery"])


def get_delivery_service(session: AsyncSession = Depends(get_db_session)) -> DeliveryService:
    return DeliveryService(session=session)


@router.post(
    "/shipments/{shipment_id}/otp/generate",
    response_model=ApiResponse[DeliveryOtpGenerateResponse],
    summary="Generate 6-digit delivery release OTP",
    status_code=status.HTTP_201_CREATED,
)
async def generate_delivery_otp(
    shipment_id: uuid.UUID,
    service: DeliveryService = Depends(get_delivery_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager", "Dispatcher", "Carrier", "Customer Service Agent")
    ),
) -> ApiResponse[DeliveryOtpGenerateResponse]:
    """Issue a 6-digit delivery release OTP valid for 30 minutes."""
    data = await service.generate_otp(shipment_id)
    return ApiResponse(
        success=True,
        data=data,
        message="Delivery release OTP generated successfully.",
    )


@router.post(
    "/shipments/{shipment_id}/pod",
    response_model=ApiResponse[ProofOfDeliveryResponse],
    summary="Submit electronic Proof of Delivery (e-POD)",
    status_code=status.HTTP_201_CREATED,
)
async def submit_proof_of_delivery(
    shipment_id: uuid.UUID,
    request: PodSubmissionRequest,
    service: DeliveryService = Depends(get_delivery_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ProofOfDeliveryResponse]:
    """Record signed e-POD handover, verify OTP, mark shipment DELIVERED, and resolve exceptions."""
    data = await service.submit_pod(
        shipment_id=shipment_id,
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    return ApiResponse(
        success=True,
        data=data,
        message="Proof of Delivery recorded. Shipment marked as DELIVERED.",
    )


@router.get(
    "/shipments/{shipment_id}/pod",
    response_model=ApiResponse[ProofOfDeliveryResponse],
    summary="Get Proof of Delivery certificate",
)
async def get_proof_of_delivery(
    shipment_id: uuid.UUID,
    service: DeliveryService = Depends(get_delivery_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ProofOfDeliveryResponse]:
    """Retrieve recorded e-POD certificate including digital signature and handover coordinates."""
    data = await service.get_pod(shipment_id)
    return ApiResponse(
        success=True,
        data=data,
        message="Proof of Delivery retrieved successfully.",
    )


@router.post(
    "/shipments/{shipment_id}/failed-attempt",
    response_model=ApiResponse[DeliveryAttemptResponse],
    summary="Log unsuccessful delivery attempt",
    status_code=status.HTTP_201_CREATED,
)
async def record_failed_delivery_attempt(
    shipment_id: uuid.UUID,
    request: FailedDeliveryAttemptRequest,
    service: DeliveryService = Depends(get_delivery_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DeliveryAttemptResponse]:
    """Log an unsuccessful delivery attempt and trigger automated exception if attempts >= 2."""
    data = await service.record_failed_attempt(
        shipment_id=shipment_id,
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    return ApiResponse(
        success=True,
        data=data,
        message="Unsuccessful delivery attempt recorded.",
    )


@router.get(
    "/shipments/{shipment_id}/history",
    response_model=ApiResponse[DeliveryHistoryResponse],
    summary="Get delivery lifecycle history",
)
async def get_delivery_history(
    shipment_id: uuid.UUID,
    service: DeliveryService = Depends(get_delivery_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DeliveryHistoryResponse]:
    """Retrieve full delivery lifecycle audit history, all attempts, and final e-POD if confirmed."""
    data = await service.get_delivery_history(shipment_id)
    return ApiResponse(
        success=True,
        data=data,
        message="Delivery history retrieved successfully.",
    )
