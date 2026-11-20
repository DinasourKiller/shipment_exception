"""Pydantic Schemas for Analytics, Reporting & Trend Engine."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CarrierPerformanceMetric(BaseModel):
    """Operational KPI scorecard for a freight carrier."""

    carrier_code: str
    carrier_name: str
    total_shipments: int
    exceptions_count: int
    exception_rate_pct: float = Field(..., description="Percentage of shipments with exceptions")
    on_time_delivery_pct: float = Field(..., description="Percentage of shipments delivered on time")
    avg_recovery_hours: float = Field(..., description="Average turnaround duration on recovery plans")
    performance_score: float = Field(..., description="Normalized 0-100 composite scorecard rating")
    rating_grade: str = Field(..., description="Rating tier: A, B, C, or D")


class CarrierPerformanceResponse(BaseModel):
    """Rollup of carrier performance scorecards."""

    carriers: List[CarrierPerformanceMetric]
    total_carriers: int


class RootCauseItem(BaseModel):
    """Categorized exception frequency and monetary impact."""

    exception_type: str
    count: int
    percentage: float
    total_financial_loss_usd: float


class RootCauseDistributionResponse(BaseModel):
    """Pareto distribution breakdown of shipment disruption categories."""

    items: List[RootCauseItem]
    total_exceptions: int
    most_frequent_type: str


class SLAComplianceMetric(BaseModel):
    """SLA resolution performance indicators."""

    total_exceptions: int
    resolved_within_sla: int
    breached_sla: int
    compliance_rate_pct: float
    avg_resolution_hours: float
    critical_compliance_rate_pct: float


class FinancialExposureSummary(BaseModel):
    """Cumulative exposure breakdown across all analyzed disruptions."""

    total_exposure_usd: float
    delay_costs_usd: float
    cargo_damage_usd: float
    contractual_penalties_usd: float
    auto_escalated_exposure_usd: float
    assessments_count: int
