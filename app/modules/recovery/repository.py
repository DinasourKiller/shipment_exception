"""Carrier Recovery Database Repository.

Provides data access methods for recovery plans and their audit trail.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.recovery.models import RecoveryAuditLog, RecoveryPlan


class RecoveryRepository:
    """Encapsulates database operations for recovery plans and audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, plan: RecoveryPlan) -> RecoveryPlan:
        """Persist a new recovery plan."""
        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def update(self, plan: RecoveryPlan) -> RecoveryPlan:
        """Update an existing recovery plan."""
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def get_by_id(self, plan_id: uuid.UUID) -> Optional[RecoveryPlan]:
        """Fetch recovery plan by primary key."""
        stmt = select(RecoveryPlan).where(RecoveryPlan.id == plan_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_exception_id(self, exception_id: uuid.UUID) -> List[RecoveryPlan]:
        """Fetch all recovery plans associated with a shipment exception."""
        stmt = (
            select(RecoveryPlan)
            .where(RecoveryPlan.exception_id == exception_id)
            .order_by(RecoveryPlan.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_plans(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        carrier_code: Optional[str] = None,
        plan_type: Optional[str] = None,
        exception_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[RecoveryPlan], int]:
        """List recovery plans with filtering and pagination."""
        stmt = select(RecoveryPlan)

        if status:
            stmt = stmt.where(RecoveryPlan.status == status)
        if carrier_code:
            stmt = stmt.where(RecoveryPlan.carrier_code == carrier_code)
        if plan_type:
            stmt = stmt.where(RecoveryPlan.plan_type == plan_type)
        if exception_id:
            stmt = stmt.where(RecoveryPlan.exception_id == exception_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            stmt.order_by(RecoveryPlan.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def add_audit_log(
        self,
        recovery_plan_id: uuid.UUID,
        action: str,
        actor_id: Optional[uuid.UUID] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ) -> RecoveryAuditLog:
        """Append an audit record to the recovery lifecycle journal."""
        log = RecoveryAuditLog(
            id=uuid.uuid4(),
            recovery_plan_id=recovery_plan_id,
            action=action,
            actor_id=actor_id,
            previous_state=previous_state or {},
            new_state=new_state or {},
            comment=comment,
        )
        self.session.add(log)
        await self.session.flush()
        return log
