"""Shipment Database Repository.

Encapsulates all database operations, complex queries, filtering,
and canonical model upserts for the Shipments module.
"""

import math
import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.integrations.base.canonical import CanonicalParty, CanonicalShipment
from app.modules.shipments.models import CargoItem, Shipment, ShipmentMilestone, ShipmentParty


class ShipmentRepository:
    """Async repository for Shipment persistence and querying."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, shipment_id: uuid.UUID) -> Optional[Shipment]:
        """Loads a single shipment by UUID with all child collections."""
        query = (
            select(Shipment)
            .options(
                selectinload(Shipment.parties),
                selectinload(Shipment.cargo_items),
                selectinload(Shipment.milestones),
            )
            .where(Shipment.id == shipment_id)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_external_reference(self, external_reference: str) -> Optional[Shipment]:
        """Loads a shipment by external source identifier (e.g. Mendix ID)."""
        query = (
            select(Shipment)
            .options(
                selectinload(Shipment.parties),
                selectinload(Shipment.cargo_items),
                selectinload(Shipment.milestones),
            )
            .where(Shipment.external_reference == external_reference)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_tracking_number(self, tracking_number: str) -> Optional[Shipment]:
        """Loads a shipment by carrier tracking number."""
        query = (
            select(Shipment)
            .options(
                selectinload(Shipment.parties),
                selectinload(Shipment.cargo_items),
                selectinload(Shipment.milestones),
            )
            .where(Shipment.tracking_number == tracking_number)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_shipments(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        carrier_code: Optional[str] = None,
        transport_mode: Optional[str] = None,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Shipment], int]:
        """Retrieves paginated shipments matching filter criteria with total record count."""
        base_query = select(Shipment)

        # Filters
        if status:
            base_query = base_query.where(Shipment.status == status.upper())
        if carrier_code:
            base_query = base_query.where(Shipment.carrier_code == carrier_code.upper())
        if transport_mode:
            base_query = base_query.where(Shipment.transport_mode == transport_mode.upper())
        if origin_city:
            base_query = base_query.where(func.lower(Shipment.origin_city) == origin_city.lower())
        if destination_city:
            base_query = base_query.where(func.lower(Shipment.destination_city) == destination_city.lower())
        if start_date:
            base_query = base_query.where(Shipment.estimated_delivery >= start_date)
        if end_date:
            base_query = base_query.where(Shipment.estimated_delivery <= end_date)

        # Full-text / substring search across references
        if search:
            search_pattern = f"%{search.strip()}%"
            base_query = base_query.where(
                or_(
                    Shipment.external_reference.ilike(search_pattern),
                    Shipment.order_number.ilike(search_pattern),
                    Shipment.tracking_number.ilike(search_pattern),
                    Shipment.carrier_name.ilike(search_pattern),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Paginated fetch ordered by estimated_delivery
        offset = (page - 1) * page_size
        items_query = base_query.order_by(Shipment.estimated_delivery.asc()).offset(offset).limit(page_size)
        items_result = await self.session.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total

    async def upsert_canonical_shipment(self, canonical: CanonicalShipment) -> Shipment:
        """Upserts a CanonicalShipment from an integration adapter into the database.

        Updates attributes and recreates child entities if shipment already exists.
        """
        existing = await self.get_by_external_reference(canonical.external_reference)

        origin_city = canonical.origin.city
        origin_country = canonical.origin.country_code
        destination_city = canonical.destination.city
        destination_country = canonical.destination.country_code

        if existing:
            # Update attributes
            existing.order_number = canonical.order_number
            existing.tracking_number = canonical.tracking_number
            existing.source_system = canonical.source_system
            existing.status = canonical.status.value
            existing.transport_mode = canonical.transport_mode.value
            existing.carrier_code = canonical.carrier_code
            existing.carrier_name = canonical.carrier_name
            existing.total_weight_kg = canonical.total_weight_kg
            existing.total_volume_cbm = canonical.total_volume_cbm
            existing.total_packages = canonical.total_packages
            existing.origin_city = origin_city
            existing.origin_country = origin_country
            existing.destination_city = destination_city
            existing.destination_country = destination_country
            existing.pickup_time_planned = canonical.pickup_time_planned
            existing.pickup_time_actual = canonical.pickup_time_actual
            existing.estimated_delivery = canonical.estimated_delivery
            existing.actual_delivery = canonical.actual_delivery
            existing.raw_metadata = canonical.raw_metadata

            # Clear existing child records
            existing.parties.clear()
            existing.cargo_items.clear()
            existing.milestones.clear()

            shipment = existing
        else:
            shipment = Shipment(
                external_reference=canonical.external_reference,
                order_number=canonical.order_number,
                tracking_number=canonical.tracking_number,
                source_system=canonical.source_system,
                status=canonical.status.value,
                transport_mode=canonical.transport_mode.value,
                carrier_code=canonical.carrier_code,
                carrier_name=canonical.carrier_name,
                total_weight_kg=canonical.total_weight_kg,
                total_volume_cbm=canonical.total_volume_cbm,
                total_packages=canonical.total_packages,
                origin_city=origin_city,
                origin_country=origin_country,
                destination_city=destination_city,
                destination_country=destination_country,
                pickup_time_planned=canonical.pickup_time_planned,
                pickup_time_actual=canonical.pickup_time_actual,
                estimated_delivery=canonical.estimated_delivery,
                actual_delivery=canonical.actual_delivery,
                raw_metadata=canonical.raw_metadata,
            )
            self.session.add(shipment)

        # Build parties
        def _build_party(party: CanonicalParty, party_type: str) -> ShipmentParty:
            return ShipmentParty(
                party_type=party_type,
                party_reference=party.party_id,
                name=party.name,
                street=party.address.street,
                city=party.address.city,
                state_province=party.address.state_province,
                postal_code=party.address.postal_code,
                country_code=party.address.country_code,
                latitude=party.address.latitude,
                longitude=party.address.longitude,
                contact_name=party.contact_name,
                contact_email=party.contact_email,
                contact_phone=party.contact_phone,
            )

        shipment.parties.append(_build_party(canonical.shipper, "SHIPPER"))
        shipment.parties.append(_build_party(canonical.consignee, "CONSIGNEE"))

        # Build cargo items
        for item in canonical.line_items:
            shipment.cargo_items.append(
                CargoItem(
                    sku=item.sku,
                    description=item.description,
                    quantity=item.quantity,
                    weight_kg=item.weight_kg,
                    volume_cbm=item.volume_cbm,
                    declared_value=item.declared_value,
                    currency=item.currency or "USD",
                )
            )

        # Build milestones
        for m in canonical.milestones:
            shipment.milestones.append(
                ShipmentMilestone(
                    event_code=m.event_code,
                    title=m.title,
                    location_name=m.location_name,
                    planned_time=m.planned_time,
                    actual_time=m.actual_time,
                    status=m.status,
                    notes=m.notes,
                )
            )

        await self.session.commit()
        await self.session.refresh(shipment)
        return shipment

    async def update_status(
        self,
        shipment: Shipment,
        new_status: str,
        actual_delivery: Optional[datetime] = None,
    ) -> Shipment:
        """Updates shipment operational status."""
        shipment.status = new_status
        if actual_delivery:
            shipment.actual_delivery = actual_delivery
        await self.session.commit()
        await self.session.refresh(shipment)
        return shipment
