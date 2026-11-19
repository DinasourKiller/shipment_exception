"""Tracking and Telemetry Database Models.

Defines PostgreSQL entities for tracking events, scan checkpoints, and GPS telemetry.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
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


class TrackingEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational event, GPS telemetry ping, or carrier scan for a shipment."""

    __tablename__ = "tracking_events"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipment_milestones.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    event_code: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="Normalized event code (e.g. PICKUP_SCANNED, HUB_ARRIVED, OUT_FOR_DELIVERY, GPS_PING)",
    )
    event_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable event title",
    )
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        comment="Time the physical event occurred in UTC",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="CARRIER_API",
        nullable=False,
        comment="CARRIER_API, GPS_DEVICE, MANUAL_SCAN, EDI_214",
    )

    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    location_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    carrier_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tracking_events_shipment_time", "shipment_id", "event_timestamp"),
        Index("ix_tracking_events_code_time", "event_code", "event_timestamp"),
    )
