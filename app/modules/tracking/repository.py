"""Tracking Database Repository.

Encapsulates database operations for tracking events and milestone updates.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.shipments.models import Shipment, ShipmentMilestone
from app.modules.tracking.models import TrackingEvent


class TrackingRepository:
    """Async repository for tracking events and milestone queries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_event(self, event: TrackingEvent) -> TrackingEvent:
        """Persists a new tracking event."""
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def get_events_for_shipment(
        self,
        shipment_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[TrackingEvent], int]:
        """Returns paginated tracking events for a shipment ordered chronologically descending."""
        # Total count
        count_query = select(func.count()).where(TrackingEvent.shipment_id == shipment_id)
        count_res = await self.session.execute(count_query)
        total = count_res.scalar_one()

        # Items
        query = (
            select(TrackingEvent)
            .where(TrackingEvent.shipment_id == shipment_id)
            .order_by(TrackingEvent.event_timestamp.desc(), TrackingEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items_res = await self.session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    async def get_latest_event(self, shipment_id: uuid.UUID) -> Optional[TrackingEvent]:
        """Returns the most recent tracking event for a shipment."""
        query = (
            select(TrackingEvent)
            .where(TrackingEvent.shipment_id == shipment_id)
            .order_by(TrackingEvent.event_timestamp.desc(), TrackingEvent.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(query)
        return res.scalars().first()

    async def get_milestone_by_id(self, milestone_id: uuid.UUID) -> Optional[ShipmentMilestone]:
        """Fetches a specific milestone by UUID."""
        query = select(ShipmentMilestone).where(ShipmentMilestone.id == milestone_id)
        res = await self.session.execute(query)
        return res.scalars().first()

    async def get_milestones_for_shipment(self, shipment_id: uuid.UUID) -> List[ShipmentMilestone]:
        """Fetches all milestones for a shipment ordered by planned time."""
        query = (
            select(ShipmentMilestone)
            .where(ShipmentMilestone.shipment_id == shipment_id)
            .order_by(ShipmentMilestone.planned_time.asc())
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def find_matching_milestone(
        self,
        shipment_id: uuid.UUID,
        event_code: str,
    ) -> Optional[ShipmentMilestone]:
        """Attempts to match a tracking event code to a pending or in-progress milestone."""
        query = (
            select(ShipmentMilestone)
            .where(
                ShipmentMilestone.shipment_id == shipment_id,
                func.upper(ShipmentMilestone.event_code) == event_code.upper(),
            )
            .order_by(ShipmentMilestone.planned_time.asc())
        )
        res = await self.session.execute(query)
        return res.scalars().first()

    async def update_milestone(
        self,
        milestone: ShipmentMilestone,
        status: str,
        actual_time: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> ShipmentMilestone:
        """Updates milestone status and completion timestamp."""
        milestone.status = status.upper()
        if actual_time:
            milestone.actual_time = actual_time
        if notes:
            milestone.notes = notes
        await self.session.commit()
        await self.session.refresh(milestone)
        return milestone

    async def update_shipment_estimated_delivery(
        self,
        shipment_id: uuid.UUID,
        new_estimated_delivery: datetime,
    ) -> None:
        """Updates the shipment's estimated delivery timestamp in PostgreSQL."""
        query = select(Shipment).where(Shipment.id == shipment_id)
        res = await self.session.execute(query)
        shipment = res.scalars().first()
        if shipment:
            shipment.estimated_delivery = new_estimated_delivery
            await self.session.commit()
