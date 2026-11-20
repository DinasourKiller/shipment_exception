"""Pydantic schemas for AI-powered Root Cause, Recovery, and Customer Communication."""

from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.modules.recovery.models import RecoveryStrategy


class AIRootCauseResponse(BaseModel):
    """Structured AI output for root cause synthesis."""
    model_config = ConfigDict(from_attributes=True)

    exception_id: uuid.UUID = Field(..., description="ID of evaluated shipment exception")
    synthesized_cause: str = Field(..., description="Clear diagnostic explanation of why exception occurred")
    contributing_factors: List[str] = Field(default_factory=list, description="List of primary and secondary factors")
    severity_assessment: str = Field(..., description="Risk and severity evaluation (LOW, MEDIUM, HIGH, CRITICAL)")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence rating between 0.0 and 1.0")
    provider: str = Field(..., description="Model / inference provider that produced analysis")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")


class AIRecoveryRecommendationResponse(BaseModel):
    """Structured AI output for tactical recovery proposal."""
    model_config = ConfigDict(from_attributes=True)

    exception_id: uuid.UUID = Field(..., description="ID of evaluated shipment exception")
    recommended_strategy: RecoveryStrategy = Field(..., description="Optimal tactical recovery strategy")
    suggested_action_type: str = Field(..., description="Action category (e.g. VEHICLE_REPLACEMENT, CROSS_DOCK)")
    rationale: str = Field(..., description="Operational justification for recommended action")
    estimated_cost_usd: float = Field(..., ge=0.0, description="Projected recovery cost")
    estimated_turnaround_hours: float = Field(..., ge=0.0, description="Estimated time to complete recovery")
    risk_tradeoffs: List[str] = Field(default_factory=list, description="Identified risk trade-offs")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence rating")
    provider: str = Field(..., description="Inference engine provider")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")


class AICustomerCommunicationResponse(BaseModel):
    """Structured AI output for proactive customer notification draft."""
    model_config = ConfigDict(from_attributes=True)

    exception_id: uuid.UUID = Field(..., description="ID of evaluated shipment exception")
    customer_email: str = Field(..., description="Recipient email address")
    customer_name: str = Field(..., description="Customer / recipient name")
    email_subject: str = Field(..., description="Polished, transparent email subject line")
    email_body: str = Field(..., description="Empathetic, clear status explanation and mitigation steps")
    tone: str = Field(default="Empathetic & Professional", description="Communication tone")
    estimated_delay_hours: Optional[float] = Field(default=None, description="Projected delay in hours")
    provider: str = Field(..., description="Inference engine provider")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")


class AIHealthResponse(BaseModel):
    """AI Subsystem health and connectivity state."""
    status: str = Field(..., description="online, degraded, or offline")
    model_configured: str = Field(..., description="Configured model name (e.g. gemma2:2b)")
    model_available: bool = Field(default=False, description="Whether configured model is downloaded locally")
    installed_models: List[str] = Field(default_factory=list, description="List of local models in Ollama")
    active_provider: str = Field(..., description="ollama or deterministic_fallback")
