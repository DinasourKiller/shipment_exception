"""Pydantic Request & Response Schemas for Tracking & Milestones."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TrackingEventCreateRequest(BaseModel):
    """Payload to record a new physical tracking event or GPS telemetry ping."""

    event_code: str = Field(
        ...,
        description="Event code: PICKUP_SCANNED, HUB_ARRIVED, HUB_DEPARTED, OUT_FOR_DELIVERY, DELIVERED, GPS_PING, DELAY_ALERT",
        examples=["HUB_ARRIVED"],
    )
    event_name: str = Field(
        ...,
        description="Human-readable title describing the event",
        examples=["Arrived at Central Sort Facility"],
    )
    event_timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Time the event occurred in UTC",
    )
    source: str = Field(
        default="CARRIER_API",
        description="Source of the event: CARRIER_API, GPS_DEVICE, MANUAL_SCAN, EDI_214",
    )
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    location_name: Optional[str] = Field(default=None, description="Location description or city")
    carrier_code: Optional[str] = Field(default=None, description="Carrier identifier")
    notes: Optional[str] = Field(default=None, description="Additional context or remarks")
    raw_payload: Optional[Dict[str, Any]] = Field(default=None, description="Optional raw source payload")


class TrackingEventResponse(BaseModel):
    """Response model for tracking event records."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shipment_id: uuid.UUID
    milestone_id: Optional[uuid.UUID] = None
    event_code: str
    event_name: str
    event_timestamp: datetime
    source: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    carrier_code: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class MilestoneProgressItem(BaseModel):
    """Milestone detail with calculated delay indicators."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_code: str
    title: str
    location_name: Optional[str] = None
    planned_time: Optional[datetime] = None
    actual_time: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    is_delayed: bool = False
    delay_minutes: int = 0


class ShipmentTrackingTimelineResponse(BaseModel):
    """Complete chronological tracking timeline and milestone progress for a shipment."""

    shipment_id: uuid.UUID
    external_reference: str
    order_number: str
    tracking_number: Optional[str] = None
    current_status: str
    origin_city: str
    destination_city: str
    estimated_delivery: datetime
    actual_delivery: Optional[datetime] = None
    milestones: List[MilestoneProgressItem] = Field(default_factory=list)
    events: List[TrackingEventResponse] = Field(default_factory=list)
    total_events: int


class MilestoneUpdateRequest(BaseModel):
    """Manual milestone update payload."""

    status: str = Field(..., description="Target status: PENDING, IN_PROGRESS, COMPLETED, DELAYED, SKIPPED")
    actual_time: Optional[datetime] = None
    notes: Optional[str] = None


class EtaRecalculationResponse(BaseModel):
    """Result of dynamic ETA recalculation."""

    shipment_id: uuid.UUID
    previous_estimated_delivery: datetime
    updated_estimated_delivery: datetime
    accumulated_delay_minutes: int
    is_delayed: bool
    message: str
