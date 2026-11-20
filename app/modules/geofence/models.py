"""Geofencing, Dynamic Corridors & Dwell Anomaly Database Models."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GeofenceZone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Spatial boundary defining authorized terminals, hubs, customer sites, or restricted zones."""

    __tablename__ = "geofence_zones"

    zone_code: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable identifier e.g. GF-ORD-CHICAGO-HUB",
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
        comment="Descriptive zone name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Operational description of the zone",
    )
    zone_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="TRANSIT_CROSSDOCK",
        index=True,
        comment="ORIGIN_FACILITY, TRANSIT_CROSSDOCK, DELIVERY_DESTINATION, RESTRICTED_AREA, REST_STOP, CUSTOMS_PORT",
    )
    geometry_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="CIRCULAR",
        comment="CIRCULAR or POLYGON",
    )
    center_latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Center latitude for circular geofences or centroid",
    )
    center_longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Center longitude for circular geofences or centroid",
    )
    radius_meters: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=500.0,
        comment="Radius in meters for circular geofences",
    )
    polygon_coordinates: Mapped[Optional[List[List[float]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="List of [latitude, longitude] vertex pairs defining the boundary polygon",
    )
    max_permitted_dwell_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=120,
        comment="Maximum permissible stationary dwell time before alert in minutes",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether zone boundary is actively monitored",
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="Arbitrary metadata such as contact person, operating hours, etc.",
    )

    # Relationships
    dwell_events: Mapped[List["ShipmentDwellEvent"]] = relationship(
        "ShipmentDwellEvent",
        back_populates="geofence_zone",
        cascade="all, delete-orphan",
    )


class ShipmentDwellEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks stationary stops, dwell durations, and detention periods for shipments."""

    __tablename__ = "shipment_dwell_events"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Monitored shipment ID",
    )
    geofence_zone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geofence_zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated geofence zone if dwell occurs within a designated perimeter",
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Stationary latitude coordinate",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Stationary longitude coordinate",
    )
    location_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Named location or geocoded address",
    )
    dwell_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp when stationary state commenced",
    )
    dwell_ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when vehicle resumed transit motion",
    )
    dwell_duration_minutes: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Total elapsed stationary dwell duration in minutes",
    )
    stationary_pings_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Consecutive stationary GPS telemetry pings recorded",
    )
    is_authorized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False if stop is outside approved zones or exceeds maximum permitted duration",
    )
    is_alert_dispatched: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag indicating whether an operational exception has been generated",
    )
    exception_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipment_exceptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Linked operational exception if dwell resulted in breach",
    )

    # Relationships
    geofence_zone: Mapped[Optional["GeofenceZone"]] = relationship(
        "GeofenceZone",
        back_populates="dwell_events",
    )
