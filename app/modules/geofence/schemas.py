"""Geofence, Corridor & Dwell Schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GeofenceZoneCreateRequest(BaseModel):
    """Schema for creating a circular or polygonal geofence zone."""

    zone_code: str = Field(..., max_length=60, description="Unique zone code e.g. GF-ORD-CHICAGO")
    name: str = Field(..., max_length=150, description="Descriptive zone name")
    description: Optional[str] = Field(None, description="Operational notes for the zone")
    zone_type: str = Field(
        default="TRANSIT_CROSSDOCK",
        description="ORIGIN_FACILITY, TRANSIT_CROSSDOCK, DELIVERY_DESTINATION, RESTRICTED_AREA, REST_STOP, CUSTOMS_PORT",
    )
    geometry_type: str = Field(
        default="CIRCULAR",
        description="CIRCULAR or POLYGON",
    )
    center_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Center latitude")
    center_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Center longitude")
    radius_meters: Optional[float] = Field(default=500.0, ge=1.0, description="Radius in meters")
    polygon_coordinates: Optional[List[List[float]]] = Field(
        None,
        description="List of [latitude, longitude] pairs for POLYGON geometry",
    )
    max_permitted_dwell_minutes: int = Field(
        default=120,
        ge=1,
        description="Max permitted dwell time in minutes before alert",
    )
    is_active: bool = Field(default=True, description="Zone active status")
    metadata_json: Optional[Dict[str, Any]] = Field(None, description="Arbitrary zone metadata")


class GeofenceZoneUpdateRequest(BaseModel):
    """Schema for updating an existing geofence zone."""

    name: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = None
    zone_type: Optional[str] = None
    geometry_type: Optional[str] = None
    center_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    center_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    radius_meters: Optional[float] = Field(None, ge=1.0)
    polygon_coordinates: Optional[List[List[float]]] = None
    max_permitted_dwell_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


class GeofenceZoneResponse(BaseModel):
    """Public representation of a geofence zone."""

    id: uuid.UUID
    zone_code: str
    name: str
    description: Optional[str] = None
    zone_type: str
    geometry_type: str
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon_coordinates: Optional[List[List[float]]] = None
    max_permitted_dwell_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedGeofenceResponse(BaseModel):
    """Paginated collection of geofence zones."""

    items: List[GeofenceZoneResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SpatialEvaluationRequest(BaseModel):
    """Telemetry payload for spatial evaluation."""

    shipment_id: uuid.UUID = Field(..., description="Shipment UUID to evaluate")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Current GPS latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Current GPS longitude")
    speed_kmh: float = Field(default=0.0, ge=0.0, description="Current speed in km/h")
    timestamp: Optional[datetime] = Field(None, description="Observation timestamp")
    location_name: Optional[str] = Field(None, description="Optional geocoded name")


class SpatialEvaluationResponse(BaseModel):
    """Result of geospatial fence, corridor, and dwell evaluation."""

    shipment_id: uuid.UUID
    latitude: float
    longitude: float
    speed_kmh: float
    current_geofence_zones: List[str]
    is_inside_restricted_zone: bool
    is_dwell_active: bool
    dwell_duration_minutes: float
    is_unauthorized_dwell: bool
    corridor_deviation_km: Optional[float] = None
    is_corridor_deviated: bool
    generated_exception_id: Optional[uuid.UUID] = None
    generated_exception_type: Optional[str] = None
    evaluation_summary: str


class ShipmentDwellEventResponse(BaseModel):
    """Representation of an active or concluded shipment dwell event."""

    id: uuid.UUID
    shipment_id: uuid.UUID
    geofence_zone_id: Optional[uuid.UUID] = None
    geofence_zone_name: Optional[str] = None
    latitude: float
    longitude: float
    location_name: Optional[str] = None
    dwell_started_at: datetime
    dwell_ended_at: Optional[datetime] = None
    dwell_duration_minutes: float
    stationary_pings_count: int
    is_authorized: bool
    is_alert_dispatched: bool
    exception_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
