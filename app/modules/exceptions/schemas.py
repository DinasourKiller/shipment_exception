"""Pydantic Request & Response Schemas for Exception Management."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.modules.exceptions.models import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
)


class UserSummarySchema(BaseModel):
    """Compact summary of a user actor or assignee."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class ShipmentSummarySchema(BaseModel):
    """Compact summary of the affected shipment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_reference: str
    order_number: str
    carrier_code: str
    transport_mode: str
    status: str


class ExceptionCreateRequest(BaseModel):
    """Request payload to manually or systematically log a shipment exception."""

    shipment_id: uuid.UUID = Field(..., description="Target shipment UUID")
    exception_type: ExceptionType = Field(..., description="Exception category")
    severity: ExceptionSeverity = Field(
        default=ExceptionSeverity.MEDIUM,
        description="Initial impact level",
    )
    title: str = Field(..., min_length=3, max_length=255, description="Short summary")
    description: str = Field(..., min_length=5, description="Full explanation of the disruption")
    metadata_payload: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Sensor readings, delay minutes, location coordinates, or telemetry",
    )
    sla_breach_at: Optional[datetime] = Field(
        default=None,
        description="Explicit SLA breach deadline (auto-computed if omitted)",
    )


class ExceptionStatusUpdateRequest(BaseModel):
    """Request payload to transition exception lifecycle state."""

    status: ExceptionStatus = Field(..., description="Target lifecycle state")
    comment: Optional[str] = Field(None, max_length=1000, description="Audit note for transition")


class ExceptionAssignRequest(BaseModel):
    """Request payload to assign or reassign an exception to an operator."""

    assigned_to_user_id: Optional[uuid.UUID] = Field(
        None,
        description="Operator user UUID (None to unassign)",
    )
    comment: Optional[str] = Field(None, max_length=1000, description="Assignment rationale")


class ExceptionEscalateRequest(BaseModel):
    """Request payload to escalate an exception's severity and alert management."""

    severity: Optional[ExceptionSeverity] = Field(
        None,
        description="Escalated severity level (defaults to CRITICAL or bumps level)",
    )
    reason: str = Field(..., min_length=3, max_length=1000, description="Justification for escalation")


class ExceptionResolveRequest(BaseModel):
    """Request payload to resolve an exception with root cause documentation."""

    root_cause: str = Field(..., min_length=3, description="Identified root cause")
    resolution_notes: str = Field(..., min_length=5, description="Steps taken to recover or resolve")


class ExceptionCloseRequest(BaseModel):
    """Request payload to formally close an exception."""

    resolution_notes: Optional[str] = Field(None, description="Final closing comments")


class ExceptionAuditLogResponse(BaseModel):
    """Audit log entry response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exception_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor: Optional[UserSummarySchema] = None
    action: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
    created_at: datetime


class ExceptionResponse(BaseModel):
    """Detailed exception response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shipment_id: uuid.UUID
    exception_type: str
    severity: str
    status: str
    title: str
    description: str
    root_cause: Optional[str] = None
    resolution_notes: Optional[str] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_to: Optional[UserSummarySchema] = None
    sla_breach_at: Optional[datetime] = None
    is_sla_breached: bool = False
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    shipment: Optional[ShipmentSummarySchema] = None
    audit_logs: Optional[List[ExceptionAuditLogResponse]] = None


class PaginatedExceptionResponse(BaseModel):
    """Paginated collection of exception responses."""

    items: List[ExceptionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
