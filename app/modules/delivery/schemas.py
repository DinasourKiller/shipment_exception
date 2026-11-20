"""Delivery Management & Proof of Delivery (e-POD) Pydantic Schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeliveryOtpGenerateResponse(BaseModel):
    """Response payload containing generated delivery release OTP."""

    shipment_id: uuid.UUID
    otp_code: str = Field(..., description="6-digit plain OTP for delivery recipient verification")
    expires_at: datetime
    expires_in_minutes: int = 30


class PodSubmissionRequest(BaseModel):
    """Payload to record an electronic Proof of Delivery (e-POD) handover."""

    recipient_name: str = Field(..., min_length=2, max_length=150, description="Full legal name of the person receiving cargo")
    recipient_signature_svg: Optional[str] = Field(default=None, description="SVG vector or Base64 string of the digital signature")
    photo_url: Optional[str] = Field(default=None, max_length=500, description="URL of photo proof of drop-off or doorstep delivery")
    photo_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Camera, EXIF, or device metadata")
    otp_code: Optional[str] = Field(default=None, min_length=6, max_length=6, description="6-digit recipient release code")
    handover_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="GPS Latitude coordinate at handover point")
    handover_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="GPS Longitude coordinate at handover point")
    notes: Optional[str] = Field(default=None, max_length=1000, description="Delivery handover remarks or access codes")


class ProofOfDeliveryResponse(BaseModel):
    """Detailed Proof of Delivery certificate payload."""

    id: uuid.UUID
    shipment_id: uuid.UUID
    delivery_attempt_number: int
    recipient_name: str
    recipient_signature_svg: Optional[str] = None
    photo_url: Optional[str] = None
    photo_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_otp_verified: bool
    handover_latitude: Optional[float] = None
    handover_longitude: Optional[float] = None
    delivered_at: datetime
    delivery_status: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FailedDeliveryAttemptRequest(BaseModel):
    """Payload to log an unsuccessful delivery attempt."""

    reason_code: str = Field(
        ...,
        description="Reason code: RECIPIENT_UNAVAILABLE, PREMISES_CLOSED, REFUSED, ACCESS_DENIED, INCORRECT_ADDRESS, WEATHER_BLOCKED",
    )
    notes: Optional[str] = Field(default=None, max_length=1000, description="Specific driver notes on what occurred")
    driver_name: Optional[str] = Field(default=None, max_length=120, description="Name of the courier or driver")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="GPS Latitude at attempt location")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="GPS Longitude at attempt location")


class DeliveryAttemptResponse(BaseModel):
    """Details of a recorded delivery attempt."""

    id: uuid.UUID
    shipment_id: uuid.UUID
    attempt_number: int
    reason_code: str
    notes: Optional[str] = None
    driver_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    attempted_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class DeliveryHistoryResponse(BaseModel):
    """Aggregate lifecycle delivery status and verification history."""

    shipment_id: uuid.UUID
    tracking_number: str
    shipment_status: str
    actual_delivery_date: Optional[datetime] = None
    is_delivered: bool
    attempts: List[DeliveryAttemptResponse] = Field(default_factory=list)
    proof_of_delivery: Optional[ProofOfDeliveryResponse] = None
