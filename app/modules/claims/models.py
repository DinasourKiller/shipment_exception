"""Carrier Claims & SLA Penalty Settlement Database Models."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CarrierClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Financial claim or contractual SLA penalty levied against a carrier."""

    __tablename__ = "carrier_claims"

    claim_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exception_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipment_exceptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    carrier_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    carrier_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    claim_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SLA_DELAY_PENALTY",
    )  # SLA_DELAY_PENALTY, CARGO_DAMAGE, TEMPERATURE_EXCURSION, TOTAL_LOSS
    claimed_amount_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    assessed_penalty_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    settled_amount_usd: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SUBMITTED",
        index=True,
    )  # DRAFT, SUBMITTED, CARRIER_DISPUTED, ARBITRATION, SETTLED, REJECTED
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
    )
    incident_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    dispute_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    counter_offer_amount_usd: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    settlement_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    deadline_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    settled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    settled_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Relationships
    shipment = relationship("Shipment", foreign_keys=[shipment_id])
    exception = relationship("ShipmentException", foreign_keys=[exception_id])
    audit_events = relationship(
        "ClaimAuditEvent",
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="ClaimAuditEvent.created_at.desc()",
    )


class ClaimAuditEvent(Base, UUIDPrimaryKeyMixin):
    """Audit log entry capturing state transitions, disputes, counter-offers, and settlements."""

    __tablename__ = "claim_audit_events"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carrier_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # CREATED, SUBMITTED, DISPUTED, COUNTER_OFFER, ARBITRATION, SETTLED, REJECTED
    actor_email: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )
    actor_role: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    amount_change: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    claim = relationship("CarrierClaim", back_populates="audit_events")
