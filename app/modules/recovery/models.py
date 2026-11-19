"""Carrier Recovery & Resource Dispatch Database Models.

Defines PostgreSQL entities for exception recovery plans, resource allocations,
carrier quotes/responses, and dispatch audit logs.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.authentication.models import User
from app.modules.exceptions.models import ShipmentException


class RecoveryPlanType(str, enum.Enum):
    """Operational recovery strategy categorization."""

    VEHICLE_REPLACEMENT = "VEHICLE_REPLACEMENT"
    CROSS_DOCK = "CROSS_DOCK"
    ROUTE_REDIRECT = "ROUTE_REDIRECT"
    AIR_EXPEDITE = "AIR_EXPEDITE"
    WAREHOUSE_HOLD = "WAREHOUSE_HOLD"
    RETURN_TO_ORIGIN = "RETURN_TO_ORIGIN"
    OTHER = "OTHER"


class RecoveryStatus(str, enum.Enum):
    """Lifecycle state machine for recovery execution."""

    DRAFT = "DRAFT"
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RecoveryAction(str, enum.Enum):
    """Audit action types recorded during recovery plan lifecycle."""

    CREATED = "CREATED"
    REQUESTED = "REQUESTED"
    CARRIER_ACCEPTED = "CARRIER_ACCEPTED"
    CARRIER_REJECTED = "CARRIER_REJECTED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    COMMENT_ADDED = "COMMENT_ADDED"


class RecoveryPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational plan designed to resolve an active shipment disruption."""

    __tablename__ = "recovery_plans"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipment_exceptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Associated shipment exception",
    )
    plan_type: Mapped[str] = mapped_column(
        String(50),
        default=RecoveryPlanType.VEHICLE_REPLACEMENT.value,
        index=True,
        nullable=False,
        comment="Recovery method / strategy",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=RecoveryStatus.DRAFT.value,
        index=True,
        nullable=False,
        comment="Lifecycle status (DRAFT, REQUESTED, ACCEPTED, DISPATCHED, COMPLETED, CANCELLED)",
    )

    # Carrier Identification
    carrier_code: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="Carrier assigned to execute recovery",
    )
    carrier_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Carrier commercial name",
    )

    # Cost & Time Estimates
    estimated_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Estimated cost in currency",
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )
    estimated_recovery_hours: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Estimated turnaround duration in hours",
    )

    # Allocated Resources
    driver_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Designated recovery driver",
    )
    driver_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Contact phone for dispatched driver",
    )
    vehicle_plate: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Dispatched vehicle registration/license plate",
    )

    # Instructions & Feedback
    instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Standard operating instructions for carrier and driver",
    )
    carrier_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Feedback or confirmation notes from carrier",
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Reason recorded if carrier rejected the recovery request",
    )

    # User Tracking
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Operator who drafted the plan",
    )
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Manager who approved or closed the recovery",
    )

    # Milestones & Timestamps
    requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    exception: Mapped["ShipmentException"] = relationship(
        "ShipmentException",
        foreign_keys=[exception_id],
        lazy="selectin",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
    approved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by_id],
        lazy="selectin",
    )
    audit_logs: Mapped[List["RecoveryAuditLog"]] = relationship(
        "RecoveryAuditLog",
        back_populates="recovery_plan",
        cascade="all, delete-orphan",
        order_by="RecoveryAuditLog.timestamp",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_recovery_plans_status_carrier", "status", "carrier_code"),
        Index("ix_recovery_plans_exception_status", "exception_id", "status"),
    )


class RecoveryAuditLog(Base, UUIDPrimaryKeyMixin):
    """Immutable audit entry tracking state changes and carrier interactions."""

    __tablename__ = "recovery_audit_logs"

    recovery_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    new_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    recovery_plan: Mapped["RecoveryPlan"] = relationship(
        "RecoveryPlan",
        back_populates="audit_logs",
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[actor_id],
        lazy="selectin",
    )
