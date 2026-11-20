"""Geofence, Corridor & Dwell Event Repository."""

import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.geofence.models import GeofenceZone, ShipmentDwellEvent


class GeofenceRepository:
    """Async repository for geofence zones and dwell/detention event records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_zone(self, zone: GeofenceZone) -> GeofenceZone:
        """Persist a new geofence zone definition."""
        self.session.add(zone)
        await self.session.flush()
        await self.session.refresh(zone)
        return zone

    async def get_by_id(self, zone_id: uuid.UUID) -> Optional[GeofenceZone]:
        """Fetch a geofence zone by its primary UUID."""
        stmt = select(GeofenceZone).where(GeofenceZone.id == zone_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, zone_code: str) -> Optional[GeofenceZone]:
        """Fetch a geofence zone by its unique business code."""
        stmt = select(GeofenceZone).where(GeofenceZone.zone_code == zone_code.upper())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active_zones(self) -> List[GeofenceZone]:
        """Retrieve all currently active geofence zones for spatial evaluation."""
        stmt = select(GeofenceZone).where(GeofenceZone.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_zones(
        self,
        active_only: bool = False,
        zone_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[GeofenceZone], int]:
        """List geofence zones with filtering, search, and pagination."""
        stmt = select(GeofenceZone)
        count_stmt = select(func.count(GeofenceZone.id))

        if active_only:
            stmt = stmt.where(GeofenceZone.is_active == True)
            count_stmt = count_stmt.where(GeofenceZone.is_active == True)

        if zone_type:
            stmt = stmt.where(GeofenceZone.zone_type == zone_type.upper())
            count_stmt = count_stmt.where(GeofenceZone.zone_type == zone_type.upper())

        if search:
            search_filter = f"%{search.strip().lower()}%"
            criteria = (
                func.lower(GeofenceZone.zone_code).like(search_filter)
                | func.lower(GeofenceZone.name).like(search_filter)
            )
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(GeofenceZone.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update_zone(self, zone: GeofenceZone) -> GeofenceZone:
        """Commit updates to an existing geofence zone."""
        await self.session.flush()
        await self.session.refresh(zone)
        return zone

    async def delete_zone(self, zone: GeofenceZone) -> None:
        """Remove a geofence zone."""
        await self.session.delete(zone)
        await self.session.flush()

    # --- Dwell Event Operations ---

    async def create_dwell_event(self, event: ShipmentDwellEvent) -> ShipmentDwellEvent:
        """Persist a new dwell event."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_active_dwell_for_shipment(self, shipment_id: uuid.UUID) -> Optional[ShipmentDwellEvent]:
        """Retrieve the currently open (un-ended) dwell event for a shipment, if any."""
        stmt = (
            select(ShipmentDwellEvent)
            .options(selectinload(ShipmentDwellEvent.geofence_zone))
            .where(
                ShipmentDwellEvent.shipment_id == shipment_id,
                ShipmentDwellEvent.dwell_ended_at.is_(None),
            )
            .order_by(ShipmentDwellEvent.dwell_started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_dwell_event(self, event: ShipmentDwellEvent) -> ShipmentDwellEvent:
        """Commit updates to a dwell event."""
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_dwells_for_shipment(self, shipment_id: uuid.UUID) -> List[ShipmentDwellEvent]:
        """List all historical dwell records for a shipment."""
        stmt = (
            select(ShipmentDwellEvent)
            .options(selectinload(ShipmentDwellEvent.geofence_zone))
            .where(ShipmentDwellEvent.shipment_id == shipment_id)
            .order_by(ShipmentDwellEvent.dwell_started_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
