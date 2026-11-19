"""Impact Assessment Database Repository.

Provides data access methods for impact analysis records and aggregated executive summaries.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.impact.models import ImpactAssessment


class ImpactRepository:
    """Encapsulates database operations for impact assessment records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, assessment: ImpactAssessment) -> ImpactAssessment:
        """Persist a new impact assessment evaluation."""
        self.session.add(assessment)
        await self.session.flush()
        await self.session.refresh(assessment)
        return assessment

    async def get_by_id(self, assessment_id: uuid.UUID) -> Optional[ImpactAssessment]:
        """Fetch impact assessment by primary key."""
        stmt = select(ImpactAssessment).where(ImpactAssessment.id == assessment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_by_exception_id(self, exception_id: uuid.UUID) -> Optional[ImpactAssessment]:
        """Fetch the most recent assessment for a specific shipment exception."""
        stmt = (
            select(ImpactAssessment)
            .where(ImpactAssessment.exception_id == exception_id)
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_assessments(
        self,
        page: int = 1,
        page_size: int = 20,
        min_score: Optional[float] = None,
        is_auto_escalated: Optional[bool] = None,
        exception_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[ImpactAssessment], int]:
        """List impact assessments with filtering and pagination."""
        stmt = select(ImpactAssessment)

        if min_score is not None:
            stmt = stmt.where(ImpactAssessment.composite_score >= min_score)
        if is_auto_escalated is not None:
            stmt = stmt.where(ImpactAssessment.is_auto_escalated == is_auto_escalated)
        if exception_id is not None:
            stmt = stmt.where(ImpactAssessment.exception_id == exception_id)

        # Count total matching
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Apply ordering and pagination
        stmt = (
            stmt.order_by(ImpactAssessment.composite_score.desc(), ImpactAssessment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_summary_stats(self) -> Dict[str, Any]:
        """Calculate aggregate impact exposure across all assessed exceptions."""
        stmt = select(
            func.count(ImpactAssessment.id).label("total_assessed"),
            func.coalesce(func.sum(ImpactAssessment.financial_impact), 0.0).label("total_financial"),
            func.count(
                func.nullif(
                    ImpactAssessment.composite_score < 75.0,
                    True,
                )
            ).label("critical_count"),
            func.count(
                func.nullif(
                    ImpactAssessment.is_auto_escalated == False,  # noqa: E712
                    True,
                )
            ).label("auto_escalated_count"),
            func.coalesce(func.avg(ImpactAssessment.composite_score), 0.0).label("avg_score"),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_assessed": row.total_assessed,
            "total_financial_exposure_usd": round(float(row.total_financial), 2),
            "critical_count": row.critical_count,
            "auto_escalated_count": row.auto_escalated_count,
            "average_composite_score": round(float(row.avg_score), 1),
        }
