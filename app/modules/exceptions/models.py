"""Shipment Exception Management Database Models.

Defines PostgreSQL entities for Shipment Exceptions and their lifecycle Audit Logs.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.authentication.models import User
from app.modules.shipments.models import Shipment


class ExceptionType(str, enum.Enum):
    """Categorization of shipment exceptions."""

    DELAY = "DELAY"
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"
    TEMPERATURE_EXCURSION = "TEMPERATURE_EXCURSION"
    COMMUNICATION_LOSS = "COMMUNICATION_LOSS"
    CUSTOMS_HOLD = "CUSTOMS_HOLD"
    WEATHER_DISRUPTION = "WEATHER_DISRUPTION"
    OTHER = "OTHER"


class ExceptionSeverity(str, enum.Enum):
    """Exception urgency and impact level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExceptionStatus(str, enum.Enum):
    """Lifecycle state machine for shipment exceptions."""

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ExceptionAction(str, enum.Enum):
    """Audit action types recorded during exception lifecycle."""

    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    COMMENT_ADDED = "COMMENT_ADDED"


class ShipmentException(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Primary operational exception record tracking transit disruptions."""

    __tablename__ = "shipment_exceptions"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Associated shipment ID",
    )
    exception_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Classification (e.g. DELAY, VEHICLE_BREAKDOWN)",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ExceptionSeverity.MEDIUM.value,
        index=True,
        comment="Impact level (LOW, MEDIUM, HIGH, CRITICAL)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ExceptionStatus.OPEN.value,
        index=True,
        comment="Lifecycle status (OPEN, INVESTIGATING, ESCALATED, RESOLVING, RESOLVED, CLOSED)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Concise exception summary",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed narrative of disruption",
    )
    root_cause: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Identified underlying root cause",
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Resolution details upon resolving or closing",
    )
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Operator or analyst responsible for handling",
    )
    sla_breach_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Projected or guaranteed resolution SLA deadline",
    )
    is_sla_breached: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Flag indicating if SLA deadline was violated",
    )
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Telemetry, sensor readings, anomaly rule triggers, and context",
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when exception was marked RESOLVED",
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when exception was marked CLOSED",
    )

    # Relationships
    shipment: Mapped["Shipment"] = relationship(
        "Shipment",
        foreign_keys=[shipment_id],
        lazy="selectin",
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_to_user_id],
        lazy="selectin",
    )
    audit_logs: Mapped[List["ExceptionAuditLog"]] = relationship(
        "ExceptionAuditLog",
        back_populates="exception",
        cascade="all, delete-orphan",
        order_by="desc(ExceptionAuditLog.created_at)",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_exceptions_shipment_status", "shipment_id", "status"),
        Index("ix_exceptions_severity_status", "severity", "status"),
        Index("ix_exceptions_sla_breach", "is_sla_breached", "sla_breach_at"),
    )


class ExceptionAuditLog(Base, UUIDPrimaryKeyMixin):
    """Append-only audit trail capturing all state transitions and interactions."""

    __tablename__ = "exception_audit_logs"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipment_exceptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Parent exception ID",
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User ID who performed action (None if automated system)",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Action performed (CREATED, STATUS_CHANGED, ASSIGNED, ESCALATED, RESOLVED, CLOSED, COMMENT_ADDED)",
    )
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot of exception before the action",
    )
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot of exception after the action",
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Explanatory note or justification",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="Audit timestamp",
    )

    # Relationships
    exception: Mapped["ShipmentException"] = relationship(
        "ShipmentException",
        back_populates="audit_logs",
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[actor_id],
        lazy="selectin",
    )
