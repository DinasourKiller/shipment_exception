"""Shipment Exception Database Repository.

Provides data access routines, filtering, pagination, and audit logging
for the Exception Management domain.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.exceptions.models import (
    ExceptionAction,
    ExceptionAuditLog,
    ExceptionStatus,
    ShipmentException,
)
from app.modules.shipments.models import Shipment


class ExceptionRepository:
    """Async repository for ShipmentException and ExceptionAuditLog persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, exception_id: uuid.UUID) -> Optional[ShipmentException]:
        """Fetch a single exception with associated shipment, assignee, and audit logs."""
        query = (
            select(ShipmentException)
            .options(
                selectinload(ShipmentException.shipment),
                selectinload(ShipmentException.assigned_to),
                selectinload(ShipmentException.audit_logs).selectinload(ExceptionAuditLog.actor),
            )
            .where(ShipmentException.id == exception_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_shipment_id(self, shipment_id: uuid.UUID) -> List[ShipmentException]:
        """Fetch all exceptions for a given shipment, sorted by created_at descending."""
        query = (
            select(ShipmentException)
            .options(
                selectinload(ShipmentException.shipment),
                selectinload(ShipmentException.assigned_to),
                selectinload(ShipmentException.audit_logs).selectinload(ExceptionAuditLog.actor),
            )
            .where(ShipmentException.shipment_id == shipment_id)
            .order_by(ShipmentException.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_exceptions(
        self,
        page: int = 1,
        page_size: int = 20,
        shipment_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        exception_type: Optional[str] = None,
        assigned_to_user_id: Optional[uuid.UUID] = None,
        is_sla_breached: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[ShipmentException], int]:
        """Query paginated exceptions with multi-dimensional filtering."""
        query = select(ShipmentException).options(
            selectinload(ShipmentException.shipment),
            selectinload(ShipmentException.assigned_to),
            selectinload(ShipmentException.audit_logs).selectinload(ExceptionAuditLog.actor),
        )
        count_query = select(func.count(ShipmentException.id))

        filters = []
        if shipment_id:
            filters.append(ShipmentException.shipment_id == shipment_id)
        if status:
            filters.append(ShipmentException.status == status)
        if severity:
            filters.append(ShipmentException.severity == severity)
        if exception_type:
            filters.append(ShipmentException.exception_type == exception_type)
        if assigned_to_user_id:
            filters.append(ShipmentException.assigned_to_user_id == assigned_to_user_id)
        if is_sla_breached is not None:
            filters.append(ShipmentException.is_sla_breached == is_sla_breached)

        if search:
            search_term = f"%{search.strip()}%"
            # Join with shipment to allow searching on shipment reference/order number
            query = query.join(Shipment, ShipmentException.shipment_id == Shipment.id, isouter=True)
            count_query = count_query.join(Shipment, ShipmentException.shipment_id == Shipment.id, isouter=True)
            search_clause = or_(
                ShipmentException.title.ilike(search_term),
                ShipmentException.description.ilike(search_term),
                Shipment.external_reference.ilike(search_term),
                Shipment.order_number.ilike(search_term),
                Shipment.carrier_code.ilike(search_term),
            )
            filters.append(search_clause)

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        total_result = await self.session.execute(count_query)
        total_count = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(ShipmentException.created_at.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total_count

    async def create(self, exception: ShipmentException) -> ShipmentException:
        """Persist a new exception entity."""
        self.session.add(exception)
        await self.session.flush()
        return exception

    async def update(self, exception: ShipmentException) -> ShipmentException:
        """Mark modified entity for commit."""
        self.session.add(exception)
        await self.session.flush()
        return exception

    async def add_audit_log(
        self,
        exception_id: uuid.UUID,
        action: str,
        actor_id: Optional[uuid.UUID] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ) -> ExceptionAuditLog:
        """Append an audit record to the exception lifecycle history."""
        log = ExceptionAuditLog(
            id=uuid.uuid4(),
            exception_id=exception_id,
            actor_id=actor_id,
            action=action,
            previous_state=previous_state,
            new_state=new_state,
            comment=comment,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def check_and_mark_sla_breaches(self) -> int:
        """Identify overdue unresolved exceptions and mark them as breached."""
        now = datetime.now(timezone.utc)
        active_statuses = [
            ExceptionStatus.OPEN.value,
            ExceptionStatus.INVESTIGATING.value,
            ExceptionStatus.ESCALATED.value,
            ExceptionStatus.RESOLVING.value,
        ]

        query = select(ShipmentException).where(
            ShipmentException.status.in_(active_statuses),
            ShipmentException.is_sla_breached.is_(False),
            ShipmentException.sla_breach_at.is_not(None),
            ShipmentException.sla_breach_at <= now,
        )

        result = await self.session.execute(query)
        breached_exceptions = list(result.scalars().all())

        count = 0
        for exc in breached_exceptions:
            exc.is_sla_breached = True
            await self.add_audit_log(
                exception_id=exc.id,
                action="SLA_BREACHED",
                actor_id=None,
                previous_state={"is_sla_breached": False},
                new_state={"is_sla_breached": True, "breached_at": now.isoformat()},
                comment=f"SLA deadline violated at {exc.sla_breach_at.isoformat()}",
            )
            count += 1

        if count > 0:
            await self.session.flush()

        return count
