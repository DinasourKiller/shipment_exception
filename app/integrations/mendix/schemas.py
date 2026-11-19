"""Mendix External System REST Data Schemas.

Represents raw external data models received from or sent to Mendix REST APIs.
Follows Mendix JSON naming conventions (camelCase).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MendixAddressModel(BaseModel):
    street: Optional[str] = None
    city: str
    state: Optional[str] = None
    postalCode: Optional[str] = None
    countryCode: str = Field(min_length=2, max_length=3)
    lat: Optional[float] = None
    lng: Optional[float] = None


class MendixPartyModel(BaseModel):
    partyId: Optional[str] = None
    companyName: str
    contactPerson: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: MendixAddressModel


class MendixCarrierModel(BaseModel):
    code: str
    name: str


class MendixCargoItemModel(BaseModel):
    itemSku: Optional[str] = None
    itemDescription: str
    quantity: int = 1
    weightKg: float = 0.0
    volumeCbm: Optional[float] = None
    declaredValue: Optional[float] = None
    currency: Optional[str] = "USD"


class MendixMilestoneModel(BaseModel):
    id: Optional[str] = None
    code: str
    description: str
    location: Optional[str] = None
    targetTime: Optional[str] = None
    completedTime: Optional[str] = None
    status: str = "PENDING"
    notes: Optional[str] = None


class MendixShipmentPayload(BaseModel):
    """Raw Mendix JSON shipment payload."""

    mendixId: str = Field(..., description="Unique Mendix entity identifier")
    orderNumber: str
    trackingNumber: Optional[str] = None
    statusCode: str
    transportType: str = "ROAD"

    carrier: MendixCarrierModel
    shipper: MendixPartyModel
    consignee: MendixPartyModel
    originLocation: Optional[MendixAddressModel] = None
    destinationLocation: Optional[MendixAddressModel] = None

    cargoItems: List[MendixCargoItemModel] = Field(default_factory=list)
    milestones: List[MendixMilestoneModel] = Field(default_factory=list)

    plannedDeparture: Optional[str] = None
    actualDeparture: Optional[str] = None
    expectedDelivery: str
    actualDelivery: Optional[str] = None

    customAttributes: Dict[str, Any] = Field(default_factory=dict)


class MendixShipmentListResponse(BaseModel):
    """Mendix pagination list response."""

    totalCount: int
    items: List[MendixShipmentPayload]


class MendixExceptionSyncRequest(BaseModel):
    """Payload pushed to Mendix when an exception or recovery action is registered."""

    mendixId: str
    exceptionType: str
    severity: str
    status: str
    impactDelayMinutes: Optional[int] = None
    summary: str
    recommendedAction: Optional[str] = None
