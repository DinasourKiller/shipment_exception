"""AI Service orchestrating Ollama LLM inference with deterministic heuristic fallback."""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException
from app.core.logging import get_logger
from app.integrations.ollama.client import OllamaClient
from app.modules.ai.prompts import (
    SYSTEM_PROMPT_JSON,
    build_customer_communication_prompt,
    build_recovery_recommendation_prompt,
    build_root_cause_prompt,
)
from app.modules.ai.schemas import (
    AICustomerCommunicationResponse,
    AIHealthResponse,
    AIRecoveryRecommendationResponse,
    AIRootCauseResponse,
)
from app.modules.exceptions.models import ExceptionSeverity, ExceptionType, ShipmentException
from app.modules.impact.models import ImpactAssessment
from app.modules.recovery.models import RecoveryPlan, RecoveryStrategy
from app.modules.shipments.models import Shipment

logger = get_logger("control_tower.modules.ai.service")


class AIService:
    """Provides generative AI root cause synthesis, tactical recovery recommendations,

    and customer communications with full deterministic fallback.
    """

    def __init__(
        self,
        db: AsyncSession,
        ollama_client: Optional[OllamaClient] = None,
    ) -> None:
        self.db = db
        self.ollama = ollama_client or OllamaClient()

    async def check_health(self) -> AIHealthResponse:
        """Inspects status of local Ollama runtime."""
        res = await self.ollama.check_health()
        status = res.get("status", "offline")
        provider = f"ollama ({self.ollama.model})" if status == "online" else "deterministic_fallback"
        return AIHealthResponse(
            status=status,
            model_configured=self.ollama.model,
            model_available=res.get("model_available", False),
            installed_models=res.get("installed_models", []),
            active_provider=provider,
        )

    async def _get_exception_and_context(self, exception_id: uuid.UUID) -> Dict[str, Any]:
        """Loads exception, associated shipment, impact assessment, and recent recovery plans."""
        query = select(ShipmentException).where(ShipmentException.id == exception_id)
        result = await self.db.execute(query)
        exc = result.scalar_one_or_none()
        if not exc:
            raise EntityNotFoundException("ShipmentException", exception_id)

        # Load impact assessment if available
        impact_query = select(ImpactAssessment).where(ImpactAssessment.exception_id == exception_id)
        impact_res = await self.db.execute(impact_query)
        impact = impact_res.scalar_one_or_none()

        shipment: Shipment = exc.shipment
        cargo_items = shipment.cargo_items if shipment else []
        primary_cargo = cargo_items[0] if cargo_items else None
        raw_meta = shipment.raw_metadata if shipment and shipment.raw_metadata else {}
        is_temp = (
            raw_meta.get("is_temperature_sensitive", False)
            or exc.exception_type == ExceptionType.TEMPERATURE_EXCURSION.value
        )
        temp_min = raw_meta.get("temp_min_c", 2.0 if is_temp else None)
        temp_max = raw_meta.get("temp_max_c", 8.0 if is_temp else None)

        # Determine parties
        customer_name = "Valued Logistics Client"
        customer_email = "customer.service@logistics-client.com"
        customer_tier = impact.customer_tier if impact else "STANDARD"

        if shipment and shipment.parties:
            for party in shipment.parties:
                if party.party_type in ["CONSIGNEE", "SHIPPER", "CUSTOMER"]:
                    customer_name = party.name or party.contact_name or customer_name
                    if party.contact_email:
                        customer_email = party.contact_email
                    break

        context = {
            "exception_id": str(exc.id),
            "shipment_id": str(exc.shipment_id),
            "shipment_reference": shipment.external_reference if shipment else "UNKNOWN-REF",
            "carrier_code": shipment.carrier_code if shipment else "UNKNOWN-CARRIER",
            "origin": f"{shipment.origin_city}, {shipment.origin_country}" if shipment else "Unknown",
            "destination": f"{shipment.destination_city}, {shipment.destination_country}" if shipment else "Unknown",
            "cargo_type": primary_cargo.description if primary_cargo else "General Freight",
            "is_temp_sensitive": is_temp,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "exception_type": exc.exception_type,
            "severity": exc.severity,
            "title": exc.title,
            "description": exc.description,
            "exception_status": exc.status,
            "metadata": exc.metadata_payload,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_tier": customer_tier,
            "estimated_financial_impact": impact.total_financial_impact_usd if impact else 0.0,
            "priority_score": impact.composite_priority_score if impact else 50.0,
            "delay_hours": impact.delay_hours if impact else 4.0,
        }
        return context

    @staticmethod
    def _extract_json_from_llm(raw_text: str) -> Optional[Dict[str, Any]]:
        """Cleans and extracts JSON object from raw LLM output."""
        if not raw_text:
            return None
        # Strip potential markdown fences
        cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            # Fallback regex search for JSON object {}
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return None

    # -------------------------------------------------------------------------
    # 1. Root Cause Synthesis
    # -------------------------------------------------------------------------
    async def analyze_root_cause(self, exception_id: uuid.UUID) -> AIRootCauseResponse:
        """Performs AI diagnostic root cause analysis using Ollama with deterministic fallback."""
        context = await self._get_exception_and_context(exception_id)
        prompt = build_root_cause_prompt(context)

        raw_response = await self.ollama.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_JSON,
            format_json=True,
        )

        if raw_response:
            data = self._extract_json_from_llm(raw_response)
            if data and "synthesized_cause" in data:
                try:
                    return AIRootCauseResponse(
                        exception_id=exception_id,
                        synthesized_cause=data.get("synthesized_cause", ""),
                        contributing_factors=data.get("contributing_factors", []),
                        severity_assessment=data.get("severity_assessment", context["severity"]),
                        confidence_score=min(max(float(data.get("confidence_score", 0.88)), 0.0), 1.0),
                        provider=f"ollama ({self.ollama.model})",
                    )
                except Exception as parse_err:
                    logger.warning("Failed parsing Ollama JSON response: %s", parse_err)

        # Fallback heuristic
        return self._fallback_root_cause(exception_id, context)

    def _fallback_root_cause(self, exception_id: uuid.UUID, context: Dict[str, Any]) -> AIRootCauseResponse:
        """High-fidelity deterministic root cause synthesis based on domain rules."""
        exc_type = context.get("exception_type", "OTHER")
        desc = context.get("description", "")
        cargo = context.get("cargo_type", "General Cargo")
        is_temp = context.get("is_temp_sensitive", False)

        if exc_type == ExceptionType.TEMPERATURE_EXCURSION.value or is_temp:
            cause = (
                f"Active refrigeration telemetry breach identified on {context.get('carrier_code')}. "
                f"Sustained ambient temperature exceeded the validated target corridor "
                f"({context.get('temp_min')}°C to {context.get('temp_max')}°C) due to compressor cycle shutdown "
                f"or door seal failure during mid-transit dwell."
            )
            factors = [
                "Reefer cooling unit power failure / alternator cutout",
                "Prolonged dock or staging door dwell without shore power",
                "Telemetry probe calibration drift under elevated ambient humidity",
            ]
            sev = ExceptionSeverity.CRITICAL.value if context["severity"] in ["HIGH", "CRITICAL"] else ExceptionSeverity.HIGH.value
            confidence = 0.94
        elif exc_type == ExceptionType.VEHICLE_BREAKDOWN.value:
            cause = (
                f"Mechanical prime-mover failure encountered along transit corridor from {context.get('origin')} "
                f"to {context.get('destination')}. Powertrain or pneumatic braking diagnostic codes forced "
                f"an immediate emergency roadside stoppage."
            )
            factors = [
                "Transmission fluid pressure threshold drop",
                "Unscheduled roadside tractor immobilization",
                "Secondary dispatch relay required to recover active trailer",
            ]
            sev = ExceptionSeverity.HIGH.value
            confidence = 0.91
        elif exc_type == ExceptionType.ROUTE_DEVIATION.value:
            cause = (
                f"Corridor geofence boundary violation detected. Shipment diverged by >25km from the scheduled "
                f"interstate corridor, indicating dynamic driver detour or detour around civil infrastructure repairs."
            )
            factors = [
                "Unplanned highway lane closure or toll bypass",
                "Driver navigational override without control tower dispatch clearance",
                "Telemetry timestamp jitter during cellular handover",
            ]
            sev = ExceptionSeverity.MEDIUM.value
            confidence = 0.89
        elif exc_type == ExceptionType.WEATHER_DISRUPTION.value:
            cause = (
                f"Severe meteorological hazard (icing / flash flooding / blizzard) along the regional arterial route, "
                f"triggering mandatory Department of Transportation (DOT) speed reductions and highway closures."
            )
            factors = [
                "Severe regional weather advisory / winter storm warning",
                "Mandatory highway chain controls or closure of mountain passes",
                "Upstream port or interchange yard backlog",
            ]
            sev = ExceptionSeverity.HIGH.value
            confidence = 0.92
        elif exc_type == ExceptionType.COMMUNICATION_LOSS.value:
            cause = (
                f"Telematics black-out: continuous missing GPS/ELD pings exceeding SLA threshold (60 minutes). "
                f"Primary cellular telemetry gateway lost connectivity in rural corridor dead-zone."
            )
            factors = [
                "Remote terrain cellular blindspot",
                "On-board telematics unit battery depletion or wiring harness disconnect",
                "Satellite backhaul failover failure",
            ]
            sev = ExceptionSeverity.MEDIUM.value
            confidence = 0.86
        else:
            cause = (
                f"Transit schedule anomaly and milestone checkpoint delay on {context.get('carrier_code')}. "
                f"Cumulative queuing at interchange hubs impacted the projected delivery ETA for {cargo}."
            )
            factors = [
                "Chokepoint dwell at intermediate cross-dock terminal",
                "Regional traffic volume peak / interstate congestion",
                "Driver hours-of-service (HOS) rest period compliance",
            ]
            sev = context.get("severity", ExceptionSeverity.MEDIUM.value)
            confidence = 0.85

        return AIRootCauseResponse(
            exception_id=exception_id,
            synthesized_cause=cause,
            contributing_factors=factors,
            severity_assessment=sev,
            confidence_score=confidence,
            provider="deterministic_fallback (gemma2:2b)",
        )

    # -------------------------------------------------------------------------
    # 2. Recovery Recommendation
    # -------------------------------------------------------------------------
    async def recommend_recovery(self, exception_id: uuid.UUID) -> AIRecoveryRecommendationResponse:
        """Recommends tactical recovery action using Ollama with deterministic fallback."""
        context = await self._get_exception_and_context(exception_id)
        prompt = build_recovery_recommendation_prompt(context)

        raw_response = await self.ollama.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_JSON,
            format_json=True,
        )

        if raw_response:
            data = self._extract_json_from_llm(raw_response)
            if data and "recommended_strategy" in data:
                try:
                    strat_str = str(data.get("recommended_strategy", "")).upper()
                    # Validate strategy is in RecoveryStrategy enum
                    if strat_str in RecoveryStrategy.__members__:
                        strategy = RecoveryStrategy[strat_str]
                    else:
                        strategy = RecoveryStrategy.ROUTE_REDIRECT

                    return AIRecoveryRecommendationResponse(
                        exception_id=exception_id,
                        recommended_strategy=strategy,
                        suggested_action_type=data.get("suggested_action_type", strategy.value),
                        rationale=data.get("rationale", "AI tactical optimization proposal"),
                        estimated_cost_usd=float(data.get("estimated_cost_usd", 650.0)),
                        estimated_turnaround_hours=float(data.get("estimated_turnaround_hours", 4.0)),
                        risk_tradeoffs=data.get("risk_tradeoffs", []),
                        confidence_score=min(max(float(data.get("confidence_score", 0.88)), 0.0), 1.0),
                        provider=f"ollama ({self.ollama.model})",
                    )
                except Exception as parse_err:
                    logger.warning("Failed parsing recovery JSON response: %s", parse_err)

        # Fallback heuristic
        return self._fallback_recovery(exception_id, context)

    def _fallback_recovery(self, exception_id: uuid.UUID, context: Dict[str, Any]) -> AIRecoveryRecommendationResponse:
        """Deterministic heuristic recovery recommendations based on supply chain logic."""
        exc_type = context.get("exception_type", "OTHER")
        is_temp = context.get("is_temp_sensitive", False)
        customer_tier = context.get("customer_tier", "STANDARD")
        priority_score = context.get("priority_score", 50.0)

        if is_temp or exc_type == ExceptionType.TEMPERATURE_EXCURSION.value:
            strategy = RecoveryStrategy.CROSS_DOCK
            action = "Emergency Cold-Chain Cross-Dock & Reefer Transfer"
            rationale = (
                "Immediate thermal stabilization required. Reroute shipment to the nearest certified cold storage "
                "cross-dock facility to inspect payload integrity, re-chill, and transfer cargo to a verified backup reefer."
            )
            cost = 1450.0
            turnaround = 3.5
            risks = [
                "Short handling dwell during pallet transfer between trailers",
                "Dock door scheduling lead time at receiving cold-storage facility",
            ]
            confidence = 0.95
        elif exc_type == ExceptionType.VEHICLE_BREAKDOWN.value:
            strategy = RecoveryStrategy.VEHICLE_REPLACEMENT
            action = "Secondary Power Unit & Driver Dispatch"
            rationale = (
                "Dispatch replacement bobtail tractor to the breakdown milepost to hitch the immobilized trailer "
                "and resume linehaul transit with minimal dwell."
            )
            cost = 850.0
            turnaround = 4.0
            risks = [
                "Highway shoulder safety clearance during coupling operation",
                "Tow-truck availability for defective tractor recovery",
            ]
            confidence = 0.93
        elif priority_score >= 85.0 or customer_tier == "VIP":
            strategy = RecoveryStrategy.AIR_EXPEDITE
            action = "Next-Flight-Out Air Freight Expedite"
            rationale = (
                f"Critical SLA penalty and high priority score ({priority_score}/100) for VIP account. "
                "Transfer cargo to nearest cargo airport terminal for immediate next-flight-out direct dispatch."
            )
            cost = 2800.0
            turnaround = 6.0
            risks = [
                "Higher transportation budget expenditure",
                "Flight cutoff times and TSA cargo screening throughput",
            ]
            confidence = 0.91
        elif exc_type == ExceptionType.WEATHER_DISRUPTION.value:
            strategy = RecoveryStrategy.WAREHOUSE_HOLD
            action = "Weather Staging Bay Secure Hold"
            rationale = (
                "Mandatory DOT highway closures make continued transit unsafe. Direct driver into nearest "
                "partner logistics staging hub until storm warning is lifted."
            )
            cost = 250.0
            turnaround = 12.0
            risks = [
                "Delivery ETA delayed by weather duration",
                "Staging bay yard storage capacity",
            ]
            confidence = 0.88
        else:
            strategy = RecoveryStrategy.ROUTE_REDIRECT
            action = "Dynamic Bypass Route Re-routing"
            rationale = (
                "Recalculate route corridor around chokepoints and construction zones to bypass bottleneck "
                "and regain transit schedule adherence."
            )
            cost = 380.0
            turnaround = 2.0
            risks = [
                "Incremental toll expenditure on detour highway",
                "Driver hours-of-service compliance limits",
            ]
            confidence = 0.89

        return AIRecoveryRecommendationResponse(
            exception_id=exception_id,
            recommended_strategy=strategy,
            suggested_action_type=action,
            rationale=rationale,
            estimated_cost_usd=cost,
            estimated_turnaround_hours=turnaround,
            risk_tradeoffs=risks,
            confidence_score=confidence,
            provider="deterministic_fallback (gemma2:2b)",
        )

    # -------------------------------------------------------------------------
    # 3. Customer Communication Drafting
    # -------------------------------------------------------------------------
    async def draft_customer_communication(self, exception_id: uuid.UUID) -> AICustomerCommunicationResponse:
        """Drafts empathetic, transparent customer update email via Ollama with deterministic fallback."""
        context = await self._get_exception_and_context(exception_id)
        prompt = build_customer_communication_prompt(context)

        raw_response = await self.ollama.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_JSON,
            format_json=True,
        )

        if raw_response:
            data = self._extract_json_from_llm(raw_response)
            if data and "email_subject" in data and "email_body" in data:
                try:
                    return AICustomerCommunicationResponse(
                        exception_id=exception_id,
                        customer_email=context["customer_email"],
                        customer_name=context["customer_name"],
                        email_subject=data.get("email_subject", ""),
                        email_body=data.get("email_body", ""),
                        tone=data.get("tone", "Empathetic & Professional"),
                        estimated_delay_hours=context.get("delay_hours"),
                        provider=f"ollama ({self.ollama.model})",
                    )
                except Exception as parse_err:
                    logger.warning("Failed parsing customer email JSON response: %s", parse_err)

        # Fallback heuristic
        return self._fallback_customer_communication(exception_id, context)

    def _fallback_customer_communication(
        self,
        exception_id: uuid.UUID,
        context: Dict[str, Any],
    ) -> AICustomerCommunicationResponse:
        """Deterministic customer notification draft maintaining brand trust and transparency."""
        shipment_ref = context.get("shipment_reference", "SHP-UNKNOWN")
        customer_name = context.get("customer_name", "Valued Partner")
        customer_email = context.get("customer_email", "customer@client.com")
        exc_type = context.get("exception_type", "Operational Disruption").replace("_", " ").title()
        delay_hrs = context.get("delay_hours", 4.0)

        subject = f"Shipment Advisory: Transit Update for Order {shipment_ref} ({exc_type})"
        body = (
            f"Dear {customer_name},\n\n"
            f"We are writing to provide you with a transparent update regarding shipment {shipment_ref} "
            f"en route from {context.get('origin')} to {context.get('destination')}.\n\n"
            f"During linehaul transit, our automated Control Tower telemetry identified an operational disruption "
            f"({exc_type}). To safeguard your cargo integrity and prevent prolonged schedule slippage, our "
            f"specialized incident response team has already initiated mitigation procedures, including carrier "
            f"coordination and active rerouting.\n\n"
            f"At this stage, our predictive ETA engine estimates an adjusted delivery window of approximately "
            f"{delay_hrs:.1f} hours beyond the original schedule. You can track live telemetry milestones directly "
            f"through our client portal.\n\n"
            f"We sincerely apologize for this unexpected delay and remain committed to delivering your shipment safely. "
            f"Please reach out to your dedicated account manager with any immediate inquiries.\n\n"
            f"Warm regards,\n"
            f"Global Control Tower Operations Team\n"
            f"support@controltower.corp | 1-800-555-TOWER"
        )

        return AICustomerCommunicationResponse(
            exception_id=exception_id,
            customer_email=customer_email,
            customer_name=customer_name,
            email_subject=subject,
            email_body=body,
            tone="Empathetic & Professional",
            estimated_delay_hours=delay_hrs,
            provider="deterministic_fallback (gemma2:2b)",
        )
