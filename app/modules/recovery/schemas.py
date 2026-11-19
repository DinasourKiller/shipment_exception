"""Pydantic Request and Response Schemas for Carrier Recovery & Resource Dispatch."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.modules.recovery.models import (
    RecoveryAction,
    RecoveryPlanType,
    RecoveryStatus,
)


class RecoveryPlanCreateRequest(BaseModel):
    """Payload to draft a new recovery plan for an operational exception."""

    exception_id: uuid.UUID = Field(..., description="Target exception UUID")
    plan_type: RecoveryPlanType = Field(
        default=RecoveryPlanType.VEHICLE_REPLACEMENT,
        description="Recovery strategy type",
    )
    carrier_code: str = Field(..., min_length=2, max_length=50, description="Carrier identifier")
    carrier_name: str = Field(..., min_length=2, max_length=200, description="Carrier commercial name")
    estimated_cost: float = Field(default=0.0, ge=0.0, description="Estimated recovery cost in USD")
    estimated_recovery_hours: float = Field(default=0.0, ge=0.0, description="Turnaround estimate in hours")
    instructions: Optional[str] = Field(
        default=None,
        description="Operating instructions for carrier and recovery team",
    )


class RecoveryPlanCarrierResponseRequest(BaseModel):
    """Payload submitted by a carrier to accept or decline a recovery request."""

    accepted: bool = Field(..., description="True if carrier accepts recovery dispatch request")
    carrier_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Carrier notes, counter-proposals, or acceptance remarks",
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Mandatory explanation if carrier rejects recovery request",
    )
    revised_estimated_cost: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Revised carrier quote in USD",
    )
    revised_recovery_hours: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Revised ETA / duration in hours",
    )


class RecoveryPlanDispatchRequest(BaseModel):
    """Payload to confirm resource allocation and dispatch vehicle/driver."""

    driver_name: str = Field(..., min_length=2, max_length=100, description="Assigned driver name")
    driver_phone: str = Field(..., min_length=5, max_length=50, description="Driver contact phone number")
    vehicle_plate: str = Field(..., min_length=2, max_length=50, description="Dispatched vehicle license plate")
    dispatch_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Special dispatch instructions",
    )


class RecoveryPlanCompleteRequest(BaseModel):
    """Payload to mark recovery completed and optionally resolve exception."""

    completion_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Summary of recovery resolution and handover",
    )
    resolve_exception: bool = Field(
        default=True,
        description="Whether to automatically advance underlying exception to RESOLVED",
    )


class RecoveryAuditLogResponse(BaseModel):
    """Audit entry recording recovery plan state transitions."""

    id: uuid.UUID
    action: str
    actor_id: Optional[uuid.UUID] = None
    previous_state: Dict[str, Any]
    new_state: Dict[str, Any]
    comment: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryPlanResponse(BaseModel):
    """Detailed operational representation of a carrier recovery plan."""

    id: uuid.UUID
    exception_id: uuid.UUID
    plan_type: str
    status: str
    carrier_code: str
    carrier_name: str
    estimated_cost: float
    currency: str
    estimated_recovery_hours: float
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    instructions: Optional[str] = None
    carrier_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_by_id: Optional[uuid.UUID] = None
    approved_by_id: Optional[uuid.UUID] = None
    requested_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    audit_logs: List[RecoveryAuditLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedRecoveryResponse(BaseModel):
    """Paginated collection of carrier recovery plans."""

    items: List[RecoveryPlanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
