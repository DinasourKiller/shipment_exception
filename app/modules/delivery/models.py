"""Delivery Management & Electronic Proof of Delivery (e-POD) Database Models."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProofOfDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Electronic Proof of Delivery (e-POD) record for completed cargo handovers."""

    __tablename__ = "proof_of_deliveries"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    delivery_attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    recipient_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    recipient_signature_svg: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    photo_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    photo_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    otp_code_hash: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    is_otp_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    handover_latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    handover_longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    delivery_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="CONFIRMED",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    submitted_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Relationships
    shipment = relationship("Shipment", foreign_keys=[shipment_id])


class DeliveryAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Record of failed or deferred delivery attempts triggering anomaly workflows."""

    __tablename__ = "delivery_attempts"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # RECIPIENT_UNAVAILABLE, PREMISES_CLOSED, REFUSED, ACCESS_DENIED, INCORRECT_ADDRESS
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    driver_name: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Relationships
    shipment = relationship("Shipment", foreign_keys=[shipment_id])


class DeliveryOtp(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Time-bound cryptographic One-Time Password (OTP) for secure delivery handoff."""

    __tablename__ = "delivery_otps"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    otp_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    otp_hint: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    shipment = relationship("Shipment", foreign_keys=[shipment_id])
