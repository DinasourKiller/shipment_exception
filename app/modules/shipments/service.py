"""Shipment Domain Service.

Orchestrates business logic for Shipment Management:
- Status lifecycle state machine validation
- External Mendix ingestion pipeline execution
- Shipment querying and filtering
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.integrations.base.canonical import CanonicalShipmentStatus
from app.integrations.mendix.client import MendixClient
from app.modules.shipments.models import Shipment
from app.modules.shipments.repository import ShipmentRepository

logger = get_logger("control_tower.shipments.service")

# State transition matrix defining permitted status transitions
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "CREATED": {"BOOKED", "CANCELLED", "DELAYED", "EXCEPTION"},
    "BOOKED": {"PICKED_UP", "DELAYED", "EXCEPTION", "CANCELLED"},
    "PICKED_UP": {"IN_TRANSIT", "DELAYED", "EXCEPTION", "CANCELLED"},
    "IN_TRANSIT": {"OUT_FOR_DELIVERY", "DELIVERED", "DELAYED", "EXCEPTION"},
    "OUT_FOR_DELIVERY": {"DELIVERED", "DELAYED", "EXCEPTION"},
    "DELAYED": {"IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION", "CANCELLED"},
    "EXCEPTION": {"IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "DELAYED", "CANCELLED"},
    "DELIVERED": set(),  # Terminal state
    "CANCELLED": set(),  # Terminal state
}


class ShipmentService:
    """Core domain service for Shipment Management."""

    def __init__(
        self,
        repository: ShipmentRepository,
        mendix_client: Optional[MendixClient] = None,
    ):
        self.repo = repository
        self.mendix = mendix_client or MendixClient()

    async def get_shipment_by_id(self, shipment_id: uuid.UUID) -> Shipment:
        """Retrieves single shipment by UUID or raises EntityNotFoundException."""
        shipment = await self.repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))
        return shipment

    async def get_shipment_by_reference(self, external_reference: str) -> Shipment:
        """Retrieves single shipment by external reference or raises EntityNotFoundException."""
        shipment = await self.repo.get_by_external_reference(external_reference)
        if not shipment:
            raise EntityNotFoundException("Shipment", external_reference)
        return shipment

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
    ) -> Tuple[List[Shipment], int, int]:
        """Lists shipments with pagination and filters. Returns (items, total, total_pages)."""
        items, total = await self.repo.list_shipments(
            page=page,
            page_size=page_size,
            status=status,
            carrier_code=carrier_code,
            transport_mode=transport_mode,
            origin_city=origin_city,
            destination_city=destination_city,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return items, total, total_pages

    async def ingest_from_mendix(self, external_reference: str) -> Shipment:
        """Ingests or updates a single shipment from Mendix into the local database."""
        logger.info(f"Ingesting shipment '{external_reference}' from Mendix")
        canonical = await self.mendix.fetch_shipment(external_reference)
        shipment = await self.repo.upsert_canonical_shipment(canonical)
        logger.info(f"Successfully ingested and persisted shipment {shipment.id} ({shipment.external_reference})")
        return shipment

    async def sync_batch_from_mendix(
        self,
        since: datetime,
        limit: int = 50,
    ) -> List[Shipment]:
        """Polls batch of modified shipments from Mendix and upserts each into local database."""
        logger.info(f"Triggering batch sync from Mendix since {since.isoformat()} (limit={limit})")
        canonical_list = await self.mendix.fetch_updated_shipments(since=since, limit=limit)

        persisted: List[Shipment] = []
        for canonical in canonical_list:
            try:
                shipment = await self.repo.upsert_canonical_shipment(canonical)
                persisted.append(shipment)
            except Exception as exc:
                logger.error(
                    f"Failed to upsert canonical shipment {canonical.external_reference}: {exc}"
                )
                continue

        logger.info(f"Batch sync complete: {len(persisted)} shipments upserted")
        return persisted

    def validate_status_transition(self, current_status: str, target_status: str) -> None:
        """Validates that status transition follows operational state machine rules."""
        cur = current_status.upper()
        tgt = target_status.upper()

        if cur == tgt:
            return

        if cur in ("DELIVERED", "CANCELLED"):
            raise ValidationException(
                f"Cannot transition shipment from terminal state '{cur}' to '{tgt}'"
            )

        allowed = ALLOWED_TRANSITIONS.get(cur, set())
        if tgt not in allowed:
            raise ValidationException(
                f"Invalid status transition from '{cur}' to '{tgt}'. "
                f"Permitted transitions from '{cur}': {sorted(list(allowed))}"
            )

    async def update_status(
        self,
        shipment_id: uuid.UUID,
        target_status: str,
        notes: Optional[str] = None,
        actual_delivery: Optional[datetime] = None,
    ) -> Shipment:
        """Transitions shipment status with state machine enforcement."""
        shipment = await self.get_shipment_by_id(shipment_id)
        target_status = target_status.upper()

        self.validate_status_transition(shipment.status, target_status)

        delivery_dt = actual_delivery
        if target_status == "DELIVERED" and not delivery_dt:
            delivery_dt = datetime.now(timezone.utc)

        updated = await self.repo.update_status(
            shipment=shipment,
            new_status=target_status,
            actual_delivery=delivery_dt,
        )

        logger.info(
            f"Shipment {shipment_id} transitioned from {shipment.status} to {target_status}"
        )
        return updated
