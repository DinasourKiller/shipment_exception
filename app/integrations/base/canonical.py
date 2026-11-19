"""Canonical Logistics Domain Models for Integrations.

Internal standard data structures that decouple the core Shipment Exception
Control Tower domain logic from external schemas (Mendix, SAP, TMS, etc.).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CanonicalShipmentStatus(str, Enum):
    """Normalized shipment status enum."""

    CREATED = "CREATED"
    BOOKED = "BOOKED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    DELAYED = "DELAYED"
    EXCEPTION = "EXCEPTION"
    CANCELLED = "CANCELLED"


class CanonicalTransportMode(str, Enum):
    """Normalized transportation mode enum."""

    ROAD = "ROAD"
    AIR = "AIR"
    OCEAN = "OCEAN"
    RAIL = "RAIL"
    MULTIMODAL = "MULTIMODAL"


class CanonicalAddress(BaseModel):
    """Normalized physical address structure."""

    street: Optional[str] = None
    city: str
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str = Field(min_length=2, max_length=3)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CanonicalParty(BaseModel):
    """Normalized party/entity details (Shipper, Consignee, Carrier)."""

    party_id: Optional[str] = None
    name: str
    address: CanonicalAddress
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class CanonicalLineItem(BaseModel):
    """Normalized package or cargo line item."""

    sku: Optional[str] = None
    description: str
    quantity: int = Field(default=1, ge=1)
    weight_kg: float = Field(default=0.0, ge=0.0)
    volume_cbm: Optional[float] = Field(default=None, ge=0.0)
    declared_value: Optional[float] = Field(default=None, ge=0.0)
    currency: Optional[str] = Field(default="USD", max_length=3)


class CanonicalMilestone(BaseModel):
    """Normalized transit checkpoint or status milestone."""

    milestone_id: Optional[str] = None
    event_code: str
    title: str
    location_name: Optional[str] = None
    planned_time: Optional[datetime] = None
    actual_time: Optional[datetime] = None
    status: str = "PENDING"
    notes: Optional[str] = None


class CanonicalShipment(BaseModel):
    """Canonical shipment representation produced by all external system adapters."""

    external_reference: str = Field(..., description="Primary identifier in source system (e.g., Mendix ID)")
    order_number: str = Field(..., description="Associated commercial order number")
    tracking_number: Optional[str] = Field(default=None, description="Carrier master tracking number")
    source_system: str = Field(default="MENDIX", description="Originating system identifier")

    status: CanonicalShipmentStatus = CanonicalShipmentStatus.CREATED
    transport_mode: CanonicalTransportMode = CanonicalTransportMode.ROAD

    shipper: CanonicalParty
    consignee: CanonicalParty
    origin: CanonicalAddress
    destination: CanonicalAddress

    carrier_code: str
    carrier_name: str

    total_weight_kg: float = 0.0
    total_volume_cbm: Optional[float] = None
    total_packages: int = 1

    line_items: List[CanonicalLineItem] = Field(default_factory=list)
    milestones: List[CanonicalMilestone] = Field(default_factory=list)

    pickup_time_planned: Optional[datetime] = None
    pickup_time_actual: Optional[datetime] = None
    estimated_delivery: datetime
    actual_delivery: Optional[datetime] = None

    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
