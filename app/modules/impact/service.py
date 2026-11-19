"""Impact Analysis Engine Service.

Evaluates multi-variable financial risk, customer satisfaction impact, and supply chain ripple
effects for shipment exceptions, calculating a normalized composite priority score (0-100)
and automating operational escalations.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.exceptions.models import (
    ExceptionAction,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentException,
)
from app.modules.exceptions.repository import ExceptionRepository
from app.modules.exceptions.schemas import ExceptionEscalateRequest
from app.modules.exceptions.service import ExceptionService
from app.modules.impact.models import (
    CustomerImpactLevel,
    ImpactAssessment,
    SupplyChainImpactLevel,
)
from app.modules.impact.repository import ImpactRepository
from app.modules.impact.schemas import (
    ImpactAssessRequest,
    ImpactAssessmentResponse,
    ImpactSummaryStatsResponse,
    PaginatedImpactResponse,
)
from app.modules.shipments.models import Shipment
from app.modules.shipments.repository import ShipmentRepository

logger = get_logger("control_tower.impact.service")


class ImpactService:
    """Core domain service for quantitative impact analysis and risk scoring."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.impact_repo = ImpactRepository(session)
        self.exception_repo = ExceptionRepository(session)
        self.shipment_repo = ShipmentRepository(session)
        self.exception_service = ExceptionService(session)

    async def assess_exception_impact(
        self,
        exception_id: uuid.UUID,
        request: Optional[ImpactAssessRequest] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ImpactAssessment:
        """Calculates multi-dimensional financial, customer, and operational impact for an exception."""
        req = request or ImpactAssessRequest()

        exception = await self.exception_repo.get_by_id(exception_id)
        if not exception:
            raise EntityNotFoundException("ShipmentException", exception_id)

        shipment = await self.shipment_repo.get_by_id(exception.shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", exception.shipment_id)

        # 1. Delay Hours Determination
        delay_hours = self._compute_delay_hours(exception, shipment, req.custom_delay_hours)

        # 2. Financial Penalty & Hourly Rate
        hourly_rate = (
            req.custom_hourly_penalty_rate
            if req.custom_hourly_penalty_rate is not None
            else float(shipment.raw_metadata.get("hourly_penalty_rate", 150.0))
        )
        delay_cost = round(delay_hours * hourly_rate, 2)

        # 3. Cargo Damage / Spoilage Valuation
        cargo_value, cargo_damage_cost, spoilage_ratio = self._compute_cargo_risk(
            exception, shipment, req.custom_cargo_loss_pct
        )

        # 4. Contractual & Demurrage Penalties
        contractual_penalty_cost = self._compute_contractual_penalties(
            exception, req.custom_contractual_penalty
        )

        total_financial_impact = round(delay_cost + cargo_damage_cost + contractual_penalty_cost, 2)

        # 5. Customer Tier & Customer Impact Rating
        customer_tier, customer_impact_level, customer_score = self._compute_customer_impact(
            exception, shipment, delay_hours, req.customer_tier
        )

        # 6. Supply Chain Disruption Level
        supply_chain_impact_level, sc_score = self._compute_supply_chain_impact(
            exception, shipment, delay_hours
        )

        # 7. Composite Risk Priority Score (0 - 100)
        composite_score, score_factors = self._compute_composite_score(
            total_financial_impact=total_financial_impact,
            customer_score=customer_score,
            exception_severity=exception.severity,
            is_sla_breached=exception.is_sla_breached,
            sc_score=sc_score,
        )

        # 8. Automated Escalation Check
        threshold = req.auto_escalate_threshold if req.auto_escalate_threshold is not None else 75.0
        is_auto_escalated = False
        escalation_reason = None

        if composite_score >= threshold or total_financial_impact >= 10000.0:
            is_auto_escalated = True
            escalation_reason = (
                f"Automated risk escalation: Composite score {composite_score:.1f}/100 "
                f"(threshold: {threshold}) | Total financial exposure: ${total_financial_impact:,.2f}"
            )

            # Auto-escalate underlying exception if not closed or already escalated
            if exception.status in (ExceptionStatus.OPEN.value, ExceptionStatus.INVESTIGATING.value):
                try:
                    await self.exception_service.escalate_exception(
                        exception_id=exception.id,
                        request=ExceptionEscalateRequest(
                            reason=escalation_reason,
                            severity=ExceptionSeverity.CRITICAL,
                        ),
                        actor_id=actor_id,
                    )
                    logger.info(
                        "Exception %s automatically escalated due to critical impact assessment",
                        exception.id,
                    )
                except Exception as err:
                    logger.warning(
                        "Auto-escalation status update failed for %s: %s",
                        exception.id,
                        err,
                    )

        calculation_factors = {
            "delay_hours": round(delay_hours, 2),
            "hourly_penalty_rate": hourly_rate,
            "total_cargo_value": cargo_value,
            "cargo_spoilage_ratio": spoilage_ratio,
            "customer_tier": customer_tier,
            "customer_score_component": customer_score,
            "supply_chain_score_component": sc_score,
            "financial_score_component": score_factors.get("financial_score", 0.0),
            "severity_score_component": score_factors.get("severity_score", 0.0),
            "sla_breach_points": score_factors.get("sla_points", 0.0),
            "auto_escalate_threshold": threshold,
        }

        assessment = ImpactAssessment(
            id=uuid.uuid4(),
            exception_id=exception.id,
            financial_impact=total_financial_impact,
            delay_cost=delay_cost,
            cargo_damage_cost=cargo_damage_cost,
            contractual_penalty_cost=contractual_penalty_cost,
            customer_impact=customer_impact_level.value,
            supply_chain_impact=supply_chain_impact_level.value,
            composite_score=round(composite_score, 1),
            is_auto_escalated=is_auto_escalated,
            escalation_reason=escalation_reason,
            calculation_factors=calculation_factors,
            assessed_by_id=actor_id,
            assessed_at=datetime.now(timezone.utc),
        )

        saved = await self.impact_repo.create(assessment)
        logger.info(
            "Completed impact assessment %s for exception %s: score=%s, financial=$%s",
            saved.id,
            exception.id,
            saved.composite_score,
            saved.financial_impact,
        )
        return saved

    async def get_assessment(self, assessment_id: uuid.UUID) -> ImpactAssessment:
        """Fetch impact assessment by ID."""
        assessment = await self.impact_repo.get_by_id(assessment_id)
        if not assessment:
            raise EntityNotFoundException("ImpactAssessment", assessment_id)
        return assessment

    async def get_latest_by_exception(self, exception_id: uuid.UUID) -> Optional[ImpactAssessment]:
        """Fetch most recent assessment for a shipment exception."""
        return await self.impact_repo.get_latest_by_exception_id(exception_id)

    async def list_assessments(
        self,
        page: int = 1,
        page_size: int = 20,
        min_score: Optional[float] = None,
        is_auto_escalated: Optional[bool] = None,
        exception_id: Optional[uuid.UUID] = None,
    ) -> PaginatedImpactResponse:
        """List impact assessments with pagination and filters."""
        items, total = await self.impact_repo.list_assessments(
            page=page,
            page_size=page_size,
            min_score=min_score,
            is_auto_escalated=is_auto_escalated,
            exception_id=exception_id,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedImpactResponse(
            items=[ImpactAssessmentResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_summary_statistics(self) -> ImpactSummaryStatsResponse:
        """Retrieve executive summary of impact exposure across all exceptions."""
        stats = await self.impact_repo.get_summary_stats()
        return ImpactSummaryStatsResponse(**stats)

    # -------------------------------------------------------------------------
    # Internal Calculation Logic
    # -------------------------------------------------------------------------

    def _compute_delay_hours(
        self,
        exception: ShipmentException,
        shipment: Shipment,
        custom_delay_hours: Optional[float],
    ) -> float:
        """Determine estimated delay hours from custom input, exception metadata, or milestone lag."""
        if custom_delay_hours is not None:
            return max(0.0, float(custom_delay_hours))

        # Check exception metadata for delay_minutes
        meta = getattr(exception, "metadata_payload", None) or {}
        if "delay_minutes" in meta:
            try:
                return float(meta["delay_minutes"]) / 60.0
            except (ValueError, TypeError):
                pass

        # Check delayed milestones on shipment
        for milestone in getattr(shipment, "milestones", []):
            if milestone.actual_time and milestone.planned_time and milestone.actual_time > milestone.planned_time:
                diff_hours = (milestone.actual_time - milestone.planned_time).total_seconds() / 3600.0
                return max(0.0, diff_hours)

        # Baseline delay estimates based on exception severity
        severity_defaults = {
            ExceptionSeverity.LOW.value: 1.5,
            ExceptionSeverity.MEDIUM.value: 3.5,
            ExceptionSeverity.HIGH.value: 8.0,
            ExceptionSeverity.CRITICAL.value: 24.0,
        }
        return severity_defaults.get(exception.severity, 2.0)

    def _compute_cargo_risk(
        self,
        exception: ShipmentException,
        shipment: Shipment,
        custom_cargo_loss_pct: Optional[float],
    ) -> Tuple[float, float, float]:
        """Calculates total cargo value and estimated spoilage/damage loss."""
        # Sum cargo value across all cargo items
        total_cargo_val = sum(
            float(item.declared_value or 0.0) * float(item.quantity or 1)
            for item in getattr(shipment, "cargo_items", [])
        )
        if total_cargo_val <= 0.0:
            total_cargo_val = float(shipment.raw_metadata.get("declared_cargo_value", 5000.0))

        if custom_cargo_loss_pct is not None:
            ratio = min(1.0, max(0.0, float(custom_cargo_loss_pct)))
            return total_cargo_val, round(total_cargo_val * ratio, 2), ratio

        # Determine spoilage/damage risk from exception type and severity
        ratio = 0.0
        if exception.exception_type == ExceptionType.TEMPERATURE_EXCURSION.value:
            if exception.severity == ExceptionSeverity.CRITICAL.value:
                ratio = 0.85  # 85% spoilage on critical temp excursion
            elif exception.severity == ExceptionSeverity.HIGH.value:
                ratio = 0.50
            else:
                ratio = 0.20
        elif exception.exception_type in (
            ExceptionType.VEHICLE_BREAKDOWN.value,
            ExceptionType.WEATHER_DISRUPTION.value,
        ):
            if exception.severity == ExceptionSeverity.CRITICAL.value:
                ratio = 0.25
            elif exception.severity == ExceptionSeverity.HIGH.value:
                ratio = 0.10
        elif exception.exception_type == ExceptionType.CUSTOMS_HOLD.value:
            # Perishable goods on customs hold
            if shipment.raw_metadata.get("perishable") is True:
                ratio = 0.40

        cargo_damage_cost = round(total_cargo_val * ratio, 2)
        return total_cargo_val, cargo_damage_cost, ratio

    def _compute_contractual_penalties(
        self,
        exception: ShipmentException,
        custom_contractual_penalty: Optional[float],
    ) -> float:
        """Determines contractual SLA breach charges and carrier demurrage fines."""
        if custom_contractual_penalty is not None:
            return max(0.0, float(custom_contractual_penalty))

        penalty = 0.0
        if exception.is_sla_breached:
            sla_penalties = {
                ExceptionSeverity.LOW.value: 200.0,
                ExceptionSeverity.MEDIUM.value: 500.0,
                ExceptionSeverity.HIGH.value: 1200.0,
                ExceptionSeverity.CRITICAL.value: 2500.0,
            }
            penalty += sla_penalties.get(exception.severity, 500.0)

        if exception.exception_type == ExceptionType.CUSTOMS_HOLD.value:
            penalty += 450.0  # standard port/terminal demurrage surcharge

        return round(penalty, 2)

    def _compute_customer_impact(
        self,
        exception: ShipmentException,
        shipment: Shipment,
        delay_hours: float,
        custom_tier: Optional[str],
    ) -> Tuple[str, CustomerImpactLevel, float]:
        """Calculates customer impact level and score component based on customer SLA tier."""
        tier = (
            custom_tier.upper()
            if custom_tier
            else str(shipment.raw_metadata.get("customer_tier", "STANDARD")).upper()
        )

        tier_multipliers = {
            "VIP": 1.5,
            "ENTERPRISE": 1.25,
            "STANDARD": 1.0,
        }
        multiplier = tier_multipliers.get(tier, 1.0)

        # Baseline customer impact points (0 - 25)
        if exception.severity == ExceptionSeverity.CRITICAL.value or delay_hours >= 12.0:
            level = CustomerImpactLevel.CRITICAL
            base_points = 25.0
        elif exception.severity == ExceptionSeverity.HIGH.value or delay_hours >= 6.0:
            level = CustomerImpactLevel.HIGH
            base_points = 18.0
        elif exception.severity == ExceptionSeverity.MEDIUM.value or delay_hours >= 2.0:
            level = CustomerImpactLevel.MEDIUM
            base_points = 10.0
        else:
            level = CustomerImpactLevel.LOW
            base_points = 4.0

        customer_score = min(25.0, round(base_points * multiplier, 1))

        # Elevate level if VIP has elevated points
        if tier == "VIP" and customer_score >= 20.0:
            level = CustomerImpactLevel.CRITICAL

        return tier, level, customer_score

    def _compute_supply_chain_impact(
        self,
        exception: ShipmentException,
        shipment: Shipment,
        delay_hours: float,
    ) -> Tuple[SupplyChainImpactLevel, float]:
        """Calculates network cascade disruption severity and component score (0 - 15)."""
        mode = getattr(shipment, "transport_mode", "ROAD").upper()

        if mode in ("AIR", "OCEAN") and delay_hours >= 8.0:
            level = SupplyChainImpactLevel.CRITICAL
            score = 15.0
        elif delay_hours >= 10.0 or exception.exception_type in (
            ExceptionType.CUSTOMS_HOLD.value,
            ExceptionType.WEATHER_DISRUPTION.value,
        ):
            level = SupplyChainImpactLevel.SEVERE
            score = 12.0
        elif delay_hours >= 4.0 or exception.exception_type == ExceptionType.VEHICLE_BREAKDOWN.value:
            level = SupplyChainImpactLevel.MODERATE
            score = 8.0
        else:
            level = SupplyChainImpactLevel.MINIMAL
            score = 2.0

        return level, score

    def _compute_composite_score(
        self,
        total_financial_impact: float,
        customer_score: float,
        exception_severity: str,
        is_sla_breached: bool,
        sc_score: float,
    ) -> Tuple[float, Dict[str, float]]:
        """Calculates normalized composite risk score (0 - 100).

        Components:
        - Financial exposure: up to 35 points (scaled against $10,000 baseline)
        - Customer impact: up to 25 points
        - Exception severity: up to 20 points
        - Supply chain disruption: up to 10 points
        - SLA breach penalty: 10 points
        """
        # Financial component: 35 points max (reaches 35 at $10,000+ loss)
        fin_score = min(35.0, round((total_financial_impact / 10000.0) * 35.0, 1))

        # Severity component: 20 points max
        severity_points_map = {
            ExceptionSeverity.LOW.value: 4.0,
            ExceptionSeverity.MEDIUM.value: 9.0,
            ExceptionSeverity.HIGH.value: 15.0,
            ExceptionSeverity.CRITICAL.value: 20.0,
        }
        sev_score = severity_points_map.get(exception_severity, 8.0)

        # SLA breach penalty
        sla_points = 10.0 if is_sla_breached else 0.0

        # Supply chain score: scaled to 10 max
        sc_scaled = min(10.0, round(sc_score * (10.0 / 15.0), 1))

        composite = fin_score + customer_score + sev_score + sc_scaled + sla_points
        composite = min(100.0, max(0.0, round(composite, 1)))

        factors = {
            "financial_score": fin_score,
            "customer_score": customer_score,
            "severity_score": sev_score,
            "supply_chain_score": sc_scaled,
            "sla_points": sla_points,
        }
        return composite, factors
