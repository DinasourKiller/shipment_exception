"""Tracking & Milestone Domain Service.

Orchestrates tracking event ingestion, automated milestone state progression,
dynamic ETA recalculation, and timeline generation.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.shipments.models import Shipment, ShipmentMilestone
from app.modules.shipments.repository import ShipmentRepository
from app.modules.tracking.models import TrackingEvent
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import (
    EtaRecalculationResponse,
    MilestoneProgressItem,
    MilestoneUpdateRequest,
    ShipmentTrackingTimelineResponse,
    TrackingEventCreateRequest,
    TrackingEventResponse,
)

logger = get_logger("control_tower.tracking.service")

# Event codes mapped to major operational lifecycle transitions
COMPLETION_EVENT_CODES = {
    "PICKUP_COMPLETED",
    "HUB_DEPARTED",
    "CUSTOMS_CLEARED",
    "DELIVERED",
    "OUT_FOR_DELIVERY",
}


class TrackingService:
    """Core domain service for tracking events and milestones."""

    def __init__(
        self,
        tracking_repo: TrackingRepository,
        shipment_repo: ShipmentRepository,
    ):
        self.tracking_repo = tracking_repo
        self.shipment_repo = shipment_repo

    async def record_event(
        self,
        shipment_id: uuid.UUID,
        request: TrackingEventCreateRequest,
    ) -> TrackingEventResponse:
        """Ingests a new tracking telemetry event, links to milestone, and evaluates state progression."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        event_time = request.event_timestamp or datetime.now(timezone.utc)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        # 1. Match with milestone if applicable
        matching_milestone = await self.tracking_repo.find_matching_milestone(
            shipment_id=shipment_id,
            event_code=request.event_code,
        )

        milestone_id = None
        if matching_milestone:
            milestone_id = matching_milestone.id
            target_status = (
                "IN_PROGRESS"
                if "IN_PROGRESS" in request.event_code.upper() or "START" in request.event_code.upper()
                else "COMPLETED"
            )
            await self.tracking_repo.update_milestone(
                milestone=matching_milestone,
                status=target_status,
                actual_time=event_time,
                notes=request.notes,
            )
            logger.info(
                f"Updated milestone {matching_milestone.id} ({matching_milestone.event_code}) "
                f"to {target_status} for shipment {shipment_id}"
            )

        # 2. Persist Tracking Event
        event = TrackingEvent(
            shipment_id=shipment_id,
            milestone_id=milestone_id,
            event_code=request.event_code.upper(),
            event_name=request.event_name,
            event_timestamp=event_time,
            source=request.source.upper(),
            latitude=request.latitude,
            longitude=request.longitude,
            location_name=request.location_name,
            carrier_code=request.carrier_code or shipment.carrier_code,
            notes=request.notes,
            raw_payload=request.raw_payload or {},
        )
        saved_event = await self.tracking_repo.create_event(event)

        # 3. Automated parent shipment state progression
        await self._evaluate_shipment_progression(shipment, request.event_code.upper(), event_time)

        # 4. Trigger ETA recalculation if milestone had planned time and experienced delay
        if matching_milestone and matching_milestone.planned_time:
            await self.recalculate_eta(shipment_id)

        # 5. Broadcast real-time telemetry update to WebSocket subscribers
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_TELEMETRY_ALL, EVENT_TELEMETRY_RECORDED
            broadcaster.publish_nowait(
                channel=f"telemetry:{shipment_id}",
                event_type=EVENT_TELEMETRY_RECORDED,
                payload={
                    "shipment_id": str(shipment_id),
                    "tracking_number": shipment.tracking_number,
                    "event_code": saved_event.event_code,
                    "event_type": saved_event.event_type,
                    "latitude": saved_event.latitude,
                    "longitude": saved_event.longitude,
                    "location_name": saved_event.location_name,
                    "event_timestamp": saved_event.event_timestamp.isoformat() if saved_event.event_timestamp else None,
                    "description": saved_event.description,
                },
            )
            broadcaster.publish_nowait(
                channel=CHANNEL_TELEMETRY_ALL,
                event_type=EVENT_TELEMETRY_RECORDED,
                payload={
                    "shipment_id": str(shipment_id),
                    "tracking_number": shipment.tracking_number,
                    "event_code": saved_event.event_code,
                    "latitude": saved_event.latitude,
                    "longitude": saved_event.longitude,
                    "location_name": saved_event.location_name,
                    "event_timestamp": saved_event.event_timestamp.isoformat() if saved_event.event_timestamp else None,
                },
            )
        except Exception as b_err:
            logger.debug("Real-time broadcast skipped: %s", b_err)

        return TrackingEventResponse.model_validate(saved_event)

    async def _evaluate_shipment_progression(
        self,
        shipment: Shipment,
        event_code: str,
        event_time: datetime,
    ) -> None:
        """Advances shipment lifecycle status based on major scan milestones."""
        cur_status = shipment.status.upper()

        if event_code in ("PICKUP_COMPLETED", "DEPARTED_ORIGIN", "LOADED"):
            if cur_status in ("CREATED", "BOOKED"):
                await self.shipment_repo.update_status(shipment, "IN_TRANSIT")
        elif event_code in ("OUT_FOR_DELIVERY", "FINAL_MILE_DISPATCH"):
            if cur_status in ("IN_TRANSIT", "DELAYED"):
                await self.shipment_repo.update_status(shipment, "OUT_FOR_DELIVERY")
        elif event_code in ("DELIVERED", "POD_RECEIVED", "SIGNATURE_OBTAINED"):
            if cur_status != "DELIVERED":
                await self.shipment_repo.update_status(shipment, "DELIVERED", actual_delivery=event_time)

    async def recalculate_eta(self, shipment_id: uuid.UUID) -> EtaRecalculationResponse:
        """Calculates dynamic delivery ETA based on milestone progress and transit delays."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        milestones = await self.tracking_repo.get_milestones_for_shipment(shipment_id)
        accumulated_delay_minutes = 0

        # Scan milestones for delay
        for m in milestones:
            if m.planned_time and m.actual_time:
                # Milestone already reached: calculate actual delay delta
                planned_utc = m.planned_time.astimezone(timezone.utc)
                actual_utc = m.actual_time.astimezone(timezone.utc)
                diff = int((actual_utc - planned_utc).total_seconds() / 60)
                if diff > 0:
                    accumulated_delay_minutes = max(accumulated_delay_minutes, diff)
            elif m.planned_time and not m.actual_time:
                # Milestone not yet reached: check if current time has already exceeded planned time
                planned_utc = m.planned_time.astimezone(timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc > planned_utc:
                    overdue = int((now_utc - planned_utc).total_seconds() / 60)
                    accumulated_delay_minutes = max(accumulated_delay_minutes, overdue)

        previous_eta = shipment.estimated_delivery
        is_delayed = accumulated_delay_minutes > 15  # 15-minute tolerance buffer

        if is_delayed:
            updated_eta = previous_eta + timedelta(minutes=accumulated_delay_minutes)
            await self.tracking_repo.update_shipment_estimated_delivery(shipment_id, updated_eta)
            message = (
                f"ETA delayed by {accumulated_delay_minutes} minutes. "
                f"New projected delivery: {updated_eta.isoformat()}"
            )
            logger.warning(f"Shipment {shipment_id} ETA updated: {previous_eta} -> {updated_eta}")
        else:
            updated_eta = previous_eta
            message = "Shipment is operating on schedule."

        return EtaRecalculationResponse(
            shipment_id=shipment_id,
            previous_estimated_delivery=previous_eta,
            updated_estimated_delivery=updated_eta,
            accumulated_delay_minutes=accumulated_delay_minutes,
            is_delayed=is_delayed,
            message=message,
        )

    async def get_shipment_timeline(
        self,
        shipment_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> ShipmentTrackingTimelineResponse:
        """Aggregates all tracking events and milestones into a chronological timeline."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        events, total_events = await self.tracking_repo.get_events_for_shipment(
            shipment_id=shipment_id,
            limit=limit,
            offset=offset,
        )
        milestones = await self.tracking_repo.get_milestones_for_shipment(shipment_id)

        # Build milestone progress items with computed delay metadata
        milestone_items: List[MilestoneProgressItem] = []
        for m in milestones:
            delay_mins = 0
            is_delayed = False
            if m.planned_time and m.actual_time:
                diff = int((m.actual_time - m.planned_time).total_seconds() / 60)
                if diff > 15:
                    delay_mins = diff
                    is_delayed = True
            elif m.planned_time and not m.actual_time:
                now_utc = datetime.now(timezone.utc)
                planned_utc = m.planned_time.astimezone(timezone.utc)
                if now_utc > planned_utc:
                    diff = int((now_utc - planned_utc).total_seconds() / 60)
                    if diff > 15:
                        delay_mins = diff
                        is_delayed = True

            milestone_items.append(
                MilestoneProgressItem(
                    id=m.id,
                    event_code=m.event_code,
                    title=m.title,
                    location_name=m.location_name,
                    planned_time=m.planned_time,
                    actual_time=m.actual_time,
                    status=m.status,
                    notes=m.notes,
                    is_delayed=is_delayed,
                    delay_minutes=delay_mins,
                )
            )

        event_responses = [TrackingEventResponse.model_validate(e) for e in events]

        return ShipmentTrackingTimelineResponse(
            shipment_id=shipment.id,
            external_reference=shipment.external_reference,
            order_number=shipment.order_number,
            tracking_number=shipment.tracking_number,
            current_status=shipment.status,
            origin_city=shipment.origin_city,
            destination_city=shipment.destination_city,
            estimated_delivery=shipment.estimated_delivery,
            actual_delivery=shipment.actual_delivery,
            milestones=milestone_items,
            events=event_responses,
            total_events=total_events,
        )

    async def get_latest_event(self, shipment_id: uuid.UUID) -> Optional[TrackingEventResponse]:
        """Fetches the latest tracking event recorded for a shipment."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        latest = await self.tracking_repo.get_latest_event(shipment_id)
        return TrackingEventResponse.model_validate(latest) if latest else None

    async def update_milestone_status(
        self,
        milestone_id: uuid.UUID,
        request: MilestoneUpdateRequest,
    ) -> MilestoneProgressItem:
        """Manually updates milestone status and completion time."""
        milestone = await self.tracking_repo.get_milestone_by_id(milestone_id)
        if not milestone:
            raise EntityNotFoundException("Milestone", str(milestone_id))

        valid_statuses = {"PENDING", "IN_PROGRESS", "COMPLETED", "DELAYED", "SKIPPED"}
        status_upper = request.status.upper()
        if status_upper not in valid_statuses:
            raise ValidationException(
                f"Invalid milestone status '{request.status}'. Allowed: {sorted(list(valid_statuses))}"
            )

        actual_time = request.actual_time
        if status_upper == "COMPLETED" and not actual_time:
            actual_time = datetime.now(timezone.utc)

        updated = await self.tracking_repo.update_milestone(
            milestone=milestone,
            status=status_upper,
            actual_time=actual_time,
            notes=request.notes,
        )

        # Recalculate ETA for the parent shipment
        await self.recalculate_eta(updated.shipment_id)

        return MilestoneProgressItem.model_validate(updated)
