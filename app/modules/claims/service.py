"""Carrier Claims & SLA Penalty Settlement Domain Service."""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.claims.models import CarrierClaim, ClaimAuditEvent
from app.modules.claims.repository import ClaimRepository
from app.modules.claims.schemas import (
    AutoClaimFromExceptionRequest,
    CarrierClaimResponse,
    ClaimCreateRequest,
    ClaimDisputeRequest,
    ClaimRejectRequest,
    ClaimSettleRequest,
    ClaimsSummaryResponse,
    PaginatedClaimsResponse,
)

logger = get_logger("control_tower.claims.service")

SEVERITY_DEFAULT_PENALTIES = {
    "CRITICAL": 2500.0,
    "HIGH": 1200.0,
    "MEDIUM": 500.0,
    "LOW": 150.0,
}


class ClaimService:
    """Core domain service for carrier claims, SLA penalty assessment, and settlement."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ClaimRepository(session)

    async def create_claim(
        self,
        request: ClaimCreateRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CarrierClaimResponse:
        """Lodge a new contractual claim against a carrier."""
        now_utc = datetime.now(timezone.utc)
        year = now_utc.year
        count = await self.repository.count_claims_for_year(year)
        claim_number = f"CLM-{year}-{(count + 1):04d}"

        deadline_date = now_utc + timedelta(days=request.deadline_days)

        claim = CarrierClaim(
            id=uuid.uuid4(),
            claim_number=claim_number,
            shipment_id=request.shipment_id,
            exception_id=request.exception_id,
            carrier_code=request.carrier_code.upper(),
            carrier_name=request.carrier_name,
            claim_type=request.claim_type.upper(),
            claimed_amount_usd=round(request.claimed_amount_usd, 2),
            assessed_penalty_usd=round(request.claimed_amount_usd, 2),
            settled_amount_usd=None,
            status="SUBMITTED",
            currency="USD",
            incident_description=request.incident_description,
            deadline_date=deadline_date,
            created_by_user_id=actor_id,
            created_at=now_utc,
            updated_at=now_utc,
        )
        saved_claim = await self.repository.create_claim(claim)

        # Initial audit timeline event
        audit_event = ClaimAuditEvent(
            id=uuid.uuid4(),
            claim_id=saved_claim.id,
            action="SUBMITTED",
            actor_email=actor_email or "SYSTEM",
            actor_role=actor_role or "Operations",
            previous_status=None,
            new_status="SUBMITTED",
            comment=f"Claim initialized with gross amount ${saved_claim.claimed_amount_usd:,.2f}. Carrier notified.",
            amount_change=saved_claim.claimed_amount_usd,
            created_at=now_utc,
        )
        await self.repository.add_audit_event(audit_event)

        # Hook 1: Record cryptographically hash-chained system audit log (Phase 15)
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="CARRIER_CLAIM_FILED",
                resource_type="CARRIER_CLAIM",
                resource_id=str(saved_claim.id),
                actor_id=actor_id,
                diff_summary={
                    "claim_number": claim_number,
                    "carrier_code": saved_claim.carrier_code,
                    "claimed_amount_usd": saved_claim.claimed_amount_usd,
                    "claim_type": saved_claim.claim_type,
                },
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped for claim: %s", audit_err)

        # Hook 2: Broadcast real-time event (Phase 16)
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_ALERTS_ALL
            broadcaster.publish_nowait(
                channel=CHANNEL_ALERTS_ALL,
                event_type="CLAIM_FILED",
                payload={
                    "claim_id": str(saved_claim.id),
                    "claim_number": claim_number,
                    "carrier_code": saved_claim.carrier_code,
                    "carrier_name": saved_claim.carrier_name,
                    "claimed_amount_usd": saved_claim.claimed_amount_usd,
                    "claim_type": saved_claim.claim_type,
                },
            )
        except Exception as ws_err:
            logger.debug("Real-time broadcast skipped for claim: %s", ws_err)

        logger.info(
            "Filed claim %s against carrier %s for $%.2f",
            claim_number,
            saved_claim.carrier_code,
            saved_claim.claimed_amount_usd,
        )

        return await self.get_claim(saved_claim.id)

    async def auto_create_from_exception(
        self,
        request: AutoClaimFromExceptionRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CarrierClaimResponse:
        """Derive an automated carrier SLA penalty claim from an operational exception and impact assessment."""
        from app.modules.exceptions.models import ShipmentException
        from app.modules.impact.models import ImpactAssessment
        from app.modules.shipments.models import Shipment
        from sqlalchemy import select

        # 1. Fetch exception
        stmt_exc = select(ShipmentException).where(ShipmentException.id == request.exception_id)
        res_exc = await self.session.execute(stmt_exc)
        exc = res_exc.scalar_one_or_none()
        if not exc:
            raise EntityNotFoundException("ShipmentException", str(request.exception_id))

        # 2. Fetch shipment
        stmt_shp = select(Shipment).where(Shipment.id == exc.shipment_id)
        res_shp = await self.session.execute(stmt_shp)
        shipment = res_shp.scalar_one_or_none()
        if not shipment:
            raise EntityNotFoundException("Shipment", str(exc.shipment_id))

        # 3. Check for existing ImpactAssessment (select latest if multiple exist)
        stmt_imp = (
            select(ImpactAssessment)
            .where(ImpactAssessment.exception_id == exc.id)
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
        res_imp = await self.session.execute(stmt_imp)
        impact = res_imp.scalars().first()

        if impact and impact.financial_impact > 0:
            claimed_amount = float(impact.financial_impact)
            justification = (
                f"Automated contractual SLA breach penalty derived from Impact Assessment. "
                f"Financial exposure: ${claimed_amount:,.2f}. Composite score: {impact.composite_score:.1f}. "
                f"Exception: {exc.title}."
            )
        else:
            claimed_amount = SEVERITY_DEFAULT_PENALTIES.get(exc.severity.upper(), 500.0)
            justification = (
                f"Standard contractual penalty levied for {exc.severity} severity incident: {exc.title}. "
                f"Carrier failed to adhere to transit milestone commitment."
            )

        claim_type = request.claim_type or (
            "SLA_DELAY_PENALTY" if "DELAY" in exc.exception_type.upper() else exc.exception_type
        )

        create_req = ClaimCreateRequest(
            shipment_id=shipment.id,
            exception_id=exc.id,
            carrier_code=shipment.carrier_code or "UNKNOWN",
            carrier_name=shipment.carrier_name or "Carrier Logistics",
            claim_type=claim_type,
            claimed_amount_usd=claimed_amount,
            incident_description=justification,
            deadline_days=14,
        )

        return await self.create_claim(
            request=create_req,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
        )

    async def submit_dispute(
        self,
        claim_id: uuid.UUID,
        request: ClaimDisputeRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CarrierClaimResponse:
        """Lodge a carrier dispute and optional counter-offer against a pending claim."""
        claim = await self.repository.get_by_id(claim_id)
        if not claim:
            raise EntityNotFoundException("CarrierClaim", str(claim_id))

        if claim.status in ("SETTLED", "REJECTED"):
            raise ValidationException(f"Cannot dispute a claim that is already {claim.status}.")

        old_status = claim.status
        now_utc = datetime.now(timezone.utc)

        claim.status = "CARRIER_DISPUTED"
        claim.dispute_reason = request.dispute_reason.strip()
        claim.counter_offer_amount_usd = (
            round(request.counter_offer_amount_usd, 2)
            if request.counter_offer_amount_usd is not None
            else None
        )
        claim.updated_at = now_utc
        await self.session.flush()

        counter_text = (
            f" Counter-offer: ${claim.counter_offer_amount_usd:,.2f}."
            if claim.counter_offer_amount_usd is not None
            else ""
        )
        audit_event = ClaimAuditEvent(
            id=uuid.uuid4(),
            claim_id=claim.id,
            action="DISPUTED",
            actor_email=actor_email or "Carrier Representative",
            actor_role=actor_role or "Carrier",
            previous_status=old_status,
            new_status="CARRIER_DISPUTED",
            comment=f"Carrier disputed claim: {request.dispute_reason}.{counter_text}",
            amount_change=claim.counter_offer_amount_usd,
            created_at=now_utc,
        )
        await self.repository.add_audit_event(audit_event)

        # Hook 1: System audit log (Phase 15)
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="CARRIER_CLAIM_DISPUTED",
                resource_type="CARRIER_CLAIM",
                resource_id=str(claim.id),
                actor_id=actor_id,
                diff_summary={
                    "status": {"from": old_status, "to": "CARRIER_DISPUTED"},
                    "dispute_reason": claim.dispute_reason,
                    "counter_offer_usd": claim.counter_offer_amount_usd,
                },
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped for dispute: %s", audit_err)

        # Hook 2: WebSocket broadcast (Phase 16)
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_ALERTS_ALL
            broadcaster.publish_nowait(
                channel=CHANNEL_ALERTS_ALL,
                event_type="CLAIM_DISPUTED",
                payload={
                    "claim_id": str(claim.id),
                    "claim_number": claim.claim_number,
                    "carrier_code": claim.carrier_code,
                    "counter_offer_usd": claim.counter_offer_amount_usd,
                    "reason": claim.dispute_reason,
                },
            )
        except Exception as ws_err:
            logger.debug("Real-time broadcast skipped for dispute: %s", ws_err)

        return await self.get_claim(claim.id)

    async def settle_claim(
        self,
        claim_id: uuid.UUID,
        request: ClaimSettleRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CarrierClaimResponse:
        """Finalize and reconcile agreed claim settlement."""
        claim = await self.repository.get_by_id(claim_id)
        if not claim:
            raise EntityNotFoundException("CarrierClaim", str(claim_id))

        if claim.status == "SETTLED":
            raise ValidationException("Claim is already settled.")

        old_status = claim.status
        now_utc = datetime.now(timezone.utc)
        settled_amt = round(request.settled_amount_usd, 2)

        claim.status = "SETTLED"
        claim.settled_amount_usd = settled_amt
        claim.settlement_notes = f"[{request.settlement_method}] {request.settlement_notes or 'Agreed final reconciliation.'}".strip()
        claim.settled_at = now_utc
        claim.settled_by_user_id = actor_id
        claim.updated_at = now_utc
        await self.session.flush()

        audit_event = ClaimAuditEvent(
            id=uuid.uuid4(),
            claim_id=claim.id,
            action="SETTLED",
            actor_email=actor_email or "SYSTEM",
            actor_role=actor_role or "Manager",
            previous_status=old_status,
            new_status="SETTLED",
            comment=f"Claim settled for ${settled_amt:,.2f} via {request.settlement_method}.",
            amount_change=settled_amt,
            created_at=now_utc,
        )
        await self.repository.add_audit_event(audit_event)

        # Hook 1: Record cryptographically hash-chained system audit log (Phase 15)
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="CARRIER_CLAIM_SETTLED",
                resource_type="CARRIER_CLAIM",
                resource_id=str(claim.id),
                actor_id=actor_id,
                diff_summary={
                    "status": {"from": old_status, "to": "SETTLED"},
                    "claimed_usd": claim.claimed_amount_usd,
                    "settled_usd": settled_amt,
                    "method": request.settlement_method,
                },
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped for settlement: %s", audit_err)

        # Hook 2: Broadcast real-time event (Phase 16)
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_ALERTS_ALL
            broadcaster.publish_nowait(
                channel=CHANNEL_ALERTS_ALL,
                event_type="CLAIM_SETTLED",
                payload={
                    "claim_id": str(claim.id),
                    "claim_number": claim.claim_number,
                    "carrier_code": claim.carrier_code,
                    "settled_amount_usd": settled_amt,
                    "settlement_method": request.settlement_method,
                },
            )
        except Exception as ws_err:
            logger.debug("Real-time broadcast skipped for settlement: %s", ws_err)

        logger.info(
            "Settled claim %s with carrier %s for $%.2f via %s",
            claim.claim_number,
            claim.carrier_code,
            settled_amt,
            request.settlement_method,
        )

        return await self.get_claim(claim.id)

    async def reject_claim(
        self,
        claim_id: uuid.UUID,
        request: ClaimRejectRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CarrierClaimResponse:
        """Deny and close a carrier claim."""
        claim = await self.repository.get_by_id(claim_id)
        if not claim:
            raise EntityNotFoundException("CarrierClaim", str(claim_id))

        if claim.status in ("SETTLED", "REJECTED"):
            raise ValidationException(f"Cannot reject a claim that is already {claim.status}.")

        old_status = claim.status
        now_utc = datetime.now(timezone.utc)

        claim.status = "REJECTED"
        claim.settlement_notes = f"[REJECTED] {request.rejection_reason}"
        claim.updated_at = now_utc
        await self.session.flush()

        audit_event = ClaimAuditEvent(
            id=uuid.uuid4(),
            claim_id=claim.id,
            action="REJECTED",
            actor_email=actor_email or "SYSTEM",
            actor_role=actor_role or "Manager",
            previous_status=old_status,
            new_status="REJECTED",
            comment=f"Claim rejected: {request.rejection_reason}",
            amount_change=0.0,
            created_at=now_utc,
        )
        await self.repository.add_audit_event(audit_event)

        return await self.get_claim(claim.id)

    async def get_claim(self, claim_id: uuid.UUID) -> CarrierClaimResponse:
        """Retrieve full claim record by primary key."""
        claim = await self.repository.get_by_id(claim_id)
        if not claim:
            raise EntityNotFoundException("CarrierClaim", str(claim_id))
        return CarrierClaimResponse.model_validate(claim)

    async def list_claims(
        self,
        page: int = 1,
        page_size: int = 50,
        carrier_code: Optional[str] = None,
        status: Optional[str] = None,
        claim_type: Optional[str] = None,
        shipment_id: Optional[uuid.UUID] = None,
    ) -> PaginatedClaimsResponse:
        """Retrieve paginated and filtered carrier claims."""
        items, total = await self.repository.list_claims(
            page=page,
            page_size=page_size,
            carrier_code=carrier_code,
            status=status,
            claim_type=claim_type,
            shipment_id=shipment_id,
        )
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedClaimsResponse(
            items=[CarrierClaimResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_summary(self) -> ClaimsSummaryResponse:
        """Retrieve executive claims and recovery KPI totals."""
        metrics = await self.repository.get_summary_metrics()
        return ClaimsSummaryResponse(**metrics)

    async def export_claims_csv(self) -> str:
        """Export claims ledger to RFC-4180 CSV format for corporate financial reconciliation."""
        items, _ = await self.repository.list_claims(page=1, page_size=5000)

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "Claim Number",
            "Carrier Code",
            "Carrier Name",
            "Claim Type",
            "Status",
            "Claimed USD",
            "Assessed Penalty USD",
            "Settled USD",
            "Disputed Reason",
            "Counter-Offer USD",
            "Created Date",
            "Deadline Date",
            "Settled Date",
        ])

        for c in items:
            writer.writerow([
                c.claim_number,
                c.carrier_code,
                c.carrier_name,
                c.claim_type,
                c.status,
                f"{c.claimed_amount_usd:.2f}",
                f"{c.assessed_penalty_usd:.2f}",
                f"{c.settled_amount_usd:.2f}" if c.settled_amount_usd is not None else "",
                c.dispute_reason or "",
                f"{c.counter_offer_amount_usd:.2f}" if c.counter_offer_amount_usd is not None else "",
                c.created_at.isoformat() if c.created_at else "",
                c.deadline_date.isoformat() if c.deadline_date else "",
                c.settled_at.isoformat() if c.settled_at else "",
            ])

        return output.getvalue()
