"""Carrier Claims & SLA Penalty Settlement Pydantic Schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClaimCreateRequest(BaseModel):
    """Payload to lodge a new financial claim or contractual penalty."""

    shipment_id: uuid.UUID
    exception_id: Optional[uuid.UUID] = None
    carrier_code: str = Field(..., max_length=50)
    carrier_name: str = Field(..., max_length=150)
    claim_type: str = Field(
        default="SLA_DELAY_PENALTY",
        description="SLA_DELAY_PENALTY, CARGO_DAMAGE, TEMPERATURE_EXCURSION, TOTAL_LOSS",
    )
    claimed_amount_usd: float = Field(..., ge=0.0, description="Gross claimed compensation in USD")
    incident_description: str = Field(..., min_length=5, description="Factual justification for the claim")
    deadline_days: int = Field(default=14, ge=1, le=90, description="Carrier dispute/settlement response window in days")


class AutoClaimFromExceptionRequest(BaseModel):
    """Payload to automatically construct a claim based on assessed financial exposure."""

    exception_id: uuid.UUID
    claim_type: Optional[str] = Field(default=None, description="Optional override for claim type")


class ClaimDisputeRequest(BaseModel):
    """Carrier dispute or counter-offer submission."""

    dispute_reason: str = Field(..., min_length=5, max_length=1500, description="Contractual or operational rebuttal")
    counter_offer_amount_usd: Optional[float] = Field(default=None, ge=0.0, description="Proposed compromise settlement in USD")


class ClaimSettleRequest(BaseModel):
    """Final claim settlement authorization."""

    settled_amount_usd: float = Field(..., ge=0.0, description="Agreed payout / deduction amount in USD")
    settlement_method: str = Field(
        default="INVOICE_OFFSET",
        description="INVOICE_OFFSET, DIRECT_CREDIT, INSURANCE_PAYOUT, ESCALATION_WAIVER",
    )
    settlement_notes: Optional[str] = Field(default=None, max_length=1000, description="Closing financial remarks")


class ClaimRejectRequest(BaseModel):
    """Claim rejection payload."""

    rejection_reason: str = Field(..., min_length=5, max_length=1500, description="Justification for denying the claim")


class ClaimAuditEventResponse(BaseModel):
    """Audit log entry capturing state transitions, disputes, counter-offers, and settlements."""

    id: uuid.UUID
    claim_id: uuid.UUID
    action: str
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: str
    comment: Optional[str] = None
    amount_change: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CarrierClaimResponse(BaseModel):
    """Detailed carrier claim and penalty record."""

    id: uuid.UUID
    claim_number: str
    shipment_id: uuid.UUID
    exception_id: Optional[uuid.UUID] = None
    carrier_code: str
    carrier_name: str
    claim_type: str
    claimed_amount_usd: float
    assessed_penalty_usd: float
    settled_amount_usd: Optional[float] = None
    status: str
    currency: str
    incident_description: str
    dispute_reason: Optional[str] = None
    counter_offer_amount_usd: Optional[float] = None
    settlement_notes: Optional[str] = None
    deadline_date: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    audit_events: List[ClaimAuditEventResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PaginatedClaimsResponse(BaseModel):
    """Paginated collection of carrier claims."""

    items: List[CarrierClaimResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClaimsSummaryResponse(BaseModel):
    """Executive financial summary of carrier claims, penalties, and recoveries."""

    total_claims_count: int
    open_claims_count: int
    disputed_claims_count: int
    settled_claims_count: int
    total_claimed_usd: float
    total_settled_usd: float
    total_disputed_usd: float
