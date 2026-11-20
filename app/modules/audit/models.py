"""Audit Logging Database Models with Cryptographic SHA-256 Hash Chaining.

Provides immutable non-repudiation and forensic traceability across all system operations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Sequence,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin
from app.modules.authentication.models import User

# Sequence for strict monotonically increasing audit numbers
audit_seq = Sequence("audit_sequence_num", start=1, increment=1)


class SystemAuditLog(Base, UUIDPrimaryKeyMixin):
    """Immutable forensic audit event chained with SHA-256 signatures."""

    __tablename__ = "system_audit_logs"

    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        audit_seq,
        server_default=audit_seq.next_value(),
        unique=True,
        index=True,
        nullable=False,
        comment="Monotonically increasing sequence number",
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who triggered action, null if automated system event",
    )
    actor_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="User email address at time of event",
    )
    actor_role: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Primary enterprise role active when action executed",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Categorical action identifier (e.g. EXCEPTION_CREATED, RECOVERY_DISPATCHED)",
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Domain entity category (e.g. SHIPMENT, EXCEPTION, RECOVERY_PLAN)",
    )
    resource_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="ID of affected entity",
    )
    state_before: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Entity state prior to mutation",
    )
    state_after: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Entity state following mutation",
    )
    diff_summary: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Key-by-key delta of changes",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Originating client IP address",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Client User-Agent",
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Request tracing correlation ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
        comment="Cryptographically immutable timestamp",
    )

    # Cryptographic Chain Linkage
    prev_record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of immediately preceding audit record",
    )
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash calculated over current record and prev_record_hash",
    )

    # Relationships
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[actor_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_audit_action_resource", "action", "resource_type"),
        Index("ix_audit_created_actor", "created_at", "actor_id"),
    )
