"""Carrier Claims & SLA Penalty Settlement Database Repository."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.claims.models import CarrierClaim, ClaimAuditEvent


class ClaimRepository:
    """Async repository for carrier claims, penalties, and audit event logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, claim_id: uuid.UUID) -> Optional[CarrierClaim]:
        """Fetch a claim by UUID with eager loaded audit timeline."""
        stmt = (
            select(CarrierClaim)
            .options(selectinload(CarrierClaim.audit_events))
            .where(CarrierClaim.id == claim_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_claim_number(self, claim_number: str) -> Optional[CarrierClaim]:
        """Fetch a claim by human-readable claim number."""
        stmt = (
            select(CarrierClaim)
            .options(selectinload(CarrierClaim.audit_events))
            .where(CarrierClaim.claim_number == claim_number)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_claims_for_year(self, year: int) -> int:
        """Count total claims registered in the given year for sequence numbering."""
        stmt = select(func.count(CarrierClaim.id)).where(
            func.extract("year", CarrierClaim.created_at) == year
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def create_claim(self, claim: CarrierClaim) -> CarrierClaim:
        """Persist a new carrier claim record."""
        self.session.add(claim)
        await self.session.flush()
        return claim

    async def add_audit_event(self, event: ClaimAuditEvent) -> ClaimAuditEvent:
        """Record an audit trail milestone event for a claim."""
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_claims(
        self,
        page: int = 1,
        page_size: int = 50,
        carrier_code: Optional[str] = None,
        status: Optional[str] = None,
        claim_type: Optional[str] = None,
        shipment_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[CarrierClaim], int]:
        """Retrieve paginated, filterable carrier claims."""
        stmt = select(CarrierClaim).options(selectinload(CarrierClaim.audit_events))

        if carrier_code:
            stmt = stmt.where(CarrierClaim.carrier_code == carrier_code.upper())
        if status:
            stmt = stmt.where(CarrierClaim.status == status.upper())
        if claim_type:
            stmt = stmt.where(CarrierClaim.claim_type == claim_type.upper())
        if shipment_id:
            stmt = stmt.where(CarrierClaim.shipment_id == shipment_id)

        # Count total matching
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Apply ordering and pagination
        stmt = stmt.order_by(CarrierClaim.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_summary_metrics(self) -> Dict[str, Any]:
        """Aggregate high-level financial claims and settlement metrics."""
        stmt = select(
            func.count(CarrierClaim.id).label("total_count"),
            func.coalesce(func.sum(CarrierClaim.claimed_amount_usd), 0.0).label("total_claimed"),
            func.coalesce(func.sum(CarrierClaim.settled_amount_usd), 0.0).label("total_settled"),
            func.coalesce(
                func.sum(
                    case(
                        (CarrierClaim.status == "CARRIER_DISPUTED", CarrierClaim.claimed_amount_usd),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("total_disputed"),
            func.count(
                case((CarrierClaim.status.in_(["SUBMITTED", "ARBITRATION"]), 1))
            ).label("open_count"),
            func.count(
                case((CarrierClaim.status == "CARRIER_DISPUTED", 1))
            ).label("disputed_count"),
            func.count(
                case((CarrierClaim.status == "SETTLED", 1))
            ).label("settled_count"),
        )
        result = await self.session.execute(stmt)
        row = result.one()

        return {
            "total_claims_count": row.total_count,
            "open_claims_count": row.open_count,
            "disputed_claims_count": row.disputed_count,
            "settled_claims_count": row.settled_count,
            "total_claimed_usd": float(row.total_claimed),
            "total_settled_usd": float(row.total_settled),
            "total_disputed_usd": float(row.total_disputed),
        }
