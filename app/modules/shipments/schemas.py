"""Pydantic Request & Response Schemas for Shipment Management."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ShipmentPartySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[uuid.UUID] = None
    party_type: str
    party_reference: Optional[str] = None
    name: str
    street: Optional[str] = None
    city: str
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class CargoItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[uuid.UUID] = None
    sku: Optional[str] = None
    description: str
    quantity: int = 1
    weight_kg: float = 0.0
    volume_cbm: Optional[float] = None
    declared_value: Optional[float] = None
    currency: str = "USD"


class ShipmentMilestoneSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[uuid.UUID] = None
    event_code: str
    title: str
    location_name: Optional[str] = None
    planned_time: Optional[datetime] = None
    actual_time: Optional[datetime] = None
    status: str = "PENDING"
    notes: Optional[str] = None


class ShipmentSummaryResponse(BaseModel):
    """Compact summary response for high-performance paginated listings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_reference: str
    order_number: str
    tracking_number: Optional[str] = None
    source_system: str
    status: str
    transport_mode: str
    carrier_code: str
    carrier_name: str
    origin_city: str
    origin_country: str
    destination_city: str
    destination_country: str
    total_weight_kg: float
    total_packages: int
    estimated_delivery: datetime
    actual_delivery: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ShipmentDetailResponse(BaseModel):
    """Full detail shipment response including parties, cargo items, and milestones."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_reference: str
    order_number: str
    tracking_number: Optional[str] = None
    source_system: str
    status: str
    transport_mode: str
    carrier_code: str
    carrier_name: str
    total_weight_kg: float
    total_volume_cbm: Optional[float] = None
    total_packages: int
    origin_city: str
    origin_country: str
    destination_city: str
    destination_country: str
    pickup_time_planned: Optional[datetime] = None
    pickup_time_actual: Optional[datetime] = None
    estimated_delivery: datetime
    actual_delivery: Optional[datetime] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    parties: List[ShipmentPartySchema] = Field(default_factory=list)
    cargo_items: List[CargoItemSchema] = Field(default_factory=list)
    milestones: List[ShipmentMilestoneSchema] = Field(default_factory=list)


class ShipmentListResponse(BaseModel):
    items: List[ShipmentSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ShipmentStatusUpdateRequest(BaseModel):
    """Request to transition shipment status."""

    status: str = Field(..., description="Target status: IN_TRANSIT, DELIVERED, EXCEPTION, DELAYED, etc.")
    notes: Optional[str] = None
    actual_delivery: Optional[datetime] = None


class ShipmentSyncResponse(BaseModel):
    """Result of an on-demand or batch sync from Mendix."""

    synced_count: int
    message: str
    shipment_ids: List[uuid.UUID] = Field(default_factory=list)
