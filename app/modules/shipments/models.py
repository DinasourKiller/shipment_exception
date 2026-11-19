"""Shipment Management Database Models.

Defines PostgreSQL entities for Shipments, Parties, Cargo Items, and Milestones.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Shipment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Primary Shipment operational record ingested from upstream systems (Mendix)."""

    __tablename__ = "shipments"

    external_reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="Upstream source reference (e.g. Mendix ID)",
    )
    order_number: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="Commercial order reference",
    )
    tracking_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
        nullable=True,
        comment="Master carrier tracking number",
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        default="MENDIX",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="CREATED",
        index=True,
        nullable=False,
        comment="Current lifecycle status (CREATED, BOOKED, IN_TRANSIT, DELIVERED, etc.)",
    )
    transport_mode: Mapped[str] = mapped_column(
        String(50),
        default="ROAD",
        index=True,
        nullable=False,
        comment="ROAD, AIR, OCEAN, RAIL, MULTIMODAL",
    )
    carrier_code: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    carrier_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    total_weight_kg: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    total_volume_cbm: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    total_packages: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    origin_city: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    origin_country: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    destination_city: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    destination_country: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    pickup_time_planned: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    pickup_time_actual: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estimated_delivery: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    actual_delivery: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    raw_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    parties: Mapped[List["ShipmentParty"]] = relationship(
        "ShipmentParty",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    cargo_items: Mapped[List["CargoItem"]] = relationship(
        "CargoItem",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    milestones: Mapped[List["ShipmentMilestone"]] = relationship(
        "ShipmentMilestone",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentMilestone.planned_time",
        lazy="selectin",
    )
    exceptions: Mapped[List["ShipmentException"]] = relationship(
        "ShipmentException",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_shipments_status_mode", "status", "transport_mode"),
        Index("ix_shipments_est_delivery", "estimated_delivery"),
    )


class ShipmentParty(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Parties associated with a shipment (Shipper, Consignee, etc.)."""

    __tablename__ = "shipment_parties"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    party_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="SHIPPER, CONSIGNEE, NOTIFY_PARTY",
    )
    party_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    street: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    state_province: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    postal_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    country_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    contact_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    shipment: Mapped["Shipment"] = relationship(
        "Shipment",
        back_populates="parties",
    )


class CargoItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Individual cargo or parcel line items within a shipment."""

    __tablename__ = "cargo_items"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sku: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    weight_kg: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    volume_cbm: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    declared_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    shipment: Mapped["Shipment"] = relationship(
        "Shipment",
        back_populates="cargo_items",
    )


class ShipmentMilestone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational milestone / tracking checkpoint for a shipment."""

    __tablename__ = "shipment_milestones"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g. PICKUP_COMPLETED, DEPARTED_HUB, OUT_FOR_DELIVERY",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    location_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    planned_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        comment="PENDING, IN_PROGRESS, COMPLETED, DELAYED, SKIPPED",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    shipment: Mapped["Shipment"] = relationship(
        "Shipment",
        back_populates="milestones",
    )
