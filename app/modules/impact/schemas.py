"""Pydantic Request and Response Schemas for Impact Analysis Engine."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.modules.impact.models import CustomerImpactLevel, SupplyChainImpactLevel


class ImpactAssessRequest(BaseModel):
    """Optional overrides and parameters when triggering impact evaluation."""

    custom_delay_hours: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Override delay hours (defaults to milestone delay or SLA diff)",
    )
    custom_hourly_penalty_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Override carrier hourly delay penalty in USD (default $150/hr)",
    )
    custom_cargo_loss_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override cargo loss ratio (0.0 to 1.0, e.g., 0.5 = 50% loss)",
    )
    custom_contractual_penalty: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Direct fixed contractual penalty in USD",
    )
    customer_tier: Optional[str] = Field(
        default=None,
        description="Customer tier override: 'VIP', 'ENTERPRISE', or 'STANDARD'",
    )
    auto_escalate_threshold: Optional[float] = Field(
        default=75.0,
        ge=0.0,
        le=100.0,
        description="Composite score threshold triggering automatic supervisor escalation",
    )


class ImpactAssessmentResponse(BaseModel):
    """Detailed quantitative impact analysis evaluation record."""

    id: uuid.UUID
    exception_id: uuid.UUID
    financial_impact: float = Field(..., description="Total financial loss estimate in USD")
    delay_cost: float = Field(..., description="Estimated cost of shipment delay")
    cargo_damage_cost: float = Field(..., description="Estimated cargo spoilage/damage value")
    contractual_penalty_cost: float = Field(..., description="Contractual or demurrage SLA penalty")
    customer_impact: str
    supply_chain_impact: str
    composite_score: float = Field(..., description="0-100 normalized risk priority score")
    is_auto_escalated: bool
    escalation_reason: Optional[str] = None
    calculation_factors: Dict[str, Any]
    assessed_by_id: Optional[uuid.UUID] = None
    assessed_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImpactSummaryStatsResponse(BaseModel):
    """Aggregated impact metrics for operational control tower dashboards."""

    total_assessed: int
    total_financial_exposure_usd: float
    critical_count: int
    auto_escalated_count: int
    average_composite_score: float


class PaginatedImpactResponse(BaseModel):
    """Paginated collection of impact assessments."""

    items: List[ImpactAssessmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
