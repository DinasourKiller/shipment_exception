"""Shipment Exception Management Service.

Coordinates anomaly detection rules, SLA deadline tracking,
exception lifecycle state transitions, and upstream Mendix synchronization.
"""

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.integrations.mendix.client import MendixClient
from app.modules.exceptions.models import (
    ExceptionAction,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentException,
)
from app.modules.exceptions.repository import ExceptionRepository
from app.modules.exceptions.schemas import (
    ExceptionAssignRequest,
    ExceptionCloseRequest,
    ExceptionCreateRequest,
    ExceptionEscalateRequest,
    ExceptionResolveRequest,
    ExceptionResponse,
    ExceptionStatusUpdateRequest,
    PaginatedExceptionResponse,
)
from app.modules.shipments.models import Shipment
from app.modules.shipments.repository import ShipmentRepository
from app.modules.tracking.repository import TrackingRepository

logger = get_logger("control_tower.exceptions.service")

# Permitted state machine transitions
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    ExceptionStatus.OPEN.value: {
        ExceptionStatus.INVESTIGATING.value,
        ExceptionStatus.ESCALATED.value,
        ExceptionStatus.RESOLVING.value,
        ExceptionStatus.RESOLVED.value,
        ExceptionStatus.CLOSED.value,
    },
    ExceptionStatus.INVESTIGATING.value: {
        ExceptionStatus.ESCALATED.value,
        ExceptionStatus.RESOLVING.value,
        ExceptionStatus.RESOLVED.value,
        ExceptionStatus.CLOSED.value,
    },
    ExceptionStatus.ESCALATED.value: {
        ExceptionStatus.INVESTIGATING.value,
        ExceptionStatus.RESOLVING.value,
        ExceptionStatus.RESOLVED.value,
        ExceptionStatus.CLOSED.value,
    },
    ExceptionStatus.RESOLVING.value: {
        ExceptionStatus.INVESTIGATING.value,
        ExceptionStatus.ESCALATED.value,
        ExceptionStatus.RESOLVED.value,
        ExceptionStatus.CLOSED.value,
    },
    ExceptionStatus.RESOLVED.value: {
        ExceptionStatus.CLOSED.value,
        ExceptionStatus.INVESTIGATING.value,  # Reopening for investigation
    },
    ExceptionStatus.CLOSED.value: set(),  # Terminal state
}

# SLA resolution windows in hours based on severity
DEFAULT_SLA_HOURS: Dict[str, int] = {
    ExceptionSeverity.CRITICAL.value: 2,
    ExceptionSeverity.HIGH.value: 4,
    ExceptionSeverity.MEDIUM.value: 12,
    ExceptionSeverity.LOW.value: 24,
}


class ExceptionService:
    """Domain service managing shipment exception life cycle and anomaly detection."""

    def __init__(self, session: AsyncSession, mendix_client: Optional[MendixClient] = None):
        self.session = session
        self.repository = ExceptionRepository(session)
        self.shipment_repo = ShipmentRepository(session)
        self.tracking_repo = TrackingRepository(session)
        self.mendix_client = mendix_client or MendixClient()

    @staticmethod
    def calculate_default_sla(severity: str, from_time: Optional[datetime] = None) -> datetime:
        """Calculate SLA deadline based on urgency severity."""
        base_time = from_time or datetime.now(timezone.utc)
        hours = DEFAULT_SLA_HOURS.get(severity, 12)
        return base_time + timedelta(hours=hours)

    async def create_exception(
        self,
        request: ExceptionCreateRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ShipmentException:
        """Creates a new operational exception and logs audit trail."""
        shipment = await self.shipment_repo.get_by_id(request.shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", request.shipment_id)

        sla_deadline = request.sla_breach_at or self.calculate_default_sla(request.severity.value)

        exception = ShipmentException(
            id=uuid.uuid4(),
            shipment_id=request.shipment_id,
            exception_type=request.exception_type.value,
            severity=request.severity.value,
            status=ExceptionStatus.OPEN.value,
            title=request.title,
            description=request.description,
            assigned_to_user_id=None,
            sla_breach_at=sla_deadline,
            is_sla_breached=False,
            metadata_payload=request.metadata_payload or {},
        )

        await self.repository.create(exception)

        await self.repository.add_audit_log(
            exception_id=exception.id,
            action=ExceptionAction.CREATED.value,
            actor_id=actor_id,
            new_state={
                "status": exception.status,
                "severity": exception.severity,
                "type": exception.exception_type,
                "title": exception.title,
                "sla_breach_at": sla_deadline.isoformat(),
            },
            comment="Exception initialized",
        )

        # Record cryptographically hash-chained system audit log (Phase 15)
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="EXCEPTION_CREATED",
                resource_type="EXCEPTION",
                resource_id=str(exception.id),
                actor_id=actor_id,
                state_after={
                    "status": exception.status,
                    "severity": exception.severity,
                    "type": exception.exception_type,
                    "title": exception.title,
                },
                diff_summary={"created": True, "type": exception.exception_type, "severity": exception.severity},
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped: %s", audit_err)

        # Notify Mendix upstream if applicable
        await self._dispatch_upstream_notification(shipment, exception)

        # Reload with all relationship data
        return await self.repository.get_by_id(exception.id)

    async def get_exception(self, exception_id: uuid.UUID) -> ShipmentException:
        """Retrieve exception by ID with full audit logs and shipment context."""
        exception = await self.repository.get_by_id(exception_id)
        if not exception:
            raise EntityNotFoundException("ShipmentException", exception_id)
        return exception

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
    ) -> PaginatedExceptionResponse:
        """Query paginated exceptions with multi-dimensional filtering."""
        # Check and update any newly breached SLAs
        await self.repository.check_and_mark_sla_breaches()

        items, total = await self.repository.list_exceptions(
            page=page,
            page_size=page_size,
            shipment_id=shipment_id,
            status=status,
            severity=severity,
            exception_type=exception_type,
            assigned_to_user_id=assigned_to_user_id,
            is_sla_breached=is_sla_breached,
            search=search,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return PaginatedExceptionResponse(
            items=[ExceptionResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def list_by_shipment(self, shipment_id: uuid.UUID) -> List[ShipmentException]:
        """Fetch all exceptions for a given shipment."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", shipment_id)
        return await self.repository.list_by_shipment_id(shipment_id)

    async def update_status(
        self,
        exception_id: uuid.UUID,
        request: ExceptionStatusUpdateRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ShipmentException:
        """Transitions exception lifecycle status enforcing state machine integrity."""
        exception = await self.get_exception(exception_id)
        old_status = exception.status
        new_status = request.status.value

        if old_status == new_status:
            return exception

        allowed = ALLOWED_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            raise ValidationException(
                f"Illegal exception lifecycle transition from '{old_status}' to '{new_status}'. "
                f"Permitted transitions: {sorted(list(allowed)) or 'None (Terminal state)'}"
            )

        now = datetime.now(timezone.utc)
        exception.status = new_status
        if new_status == ExceptionStatus.RESOLVED.value and not exception.resolved_at:
            exception.resolved_at = now
        elif new_status == ExceptionStatus.CLOSED.value and not exception.closed_at:
            exception.closed_at = now

        await self.repository.update(exception)

        await self.repository.add_audit_log(
            exception_id=exception.id,
            action=ExceptionAction.STATUS_CHANGED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={"status": new_status},
            comment=request.comment or f"Status changed from {old_status} to {new_status}",
        )

        # Notify upstream if resolved or closed
        if new_status in (ExceptionStatus.RESOLVED.value, ExceptionStatus.CLOSED.value):
            await self._dispatch_upstream_notification(exception.shipment, exception)

        return await self.repository.get_by_id(exception.id)

    async def assign_exception(
        self,
        exception_id: uuid.UUID,
        request: ExceptionAssignRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ShipmentException:
        """Assign or reassign an exception to an operator user."""
        exception = await self.get_exception(exception_id)
        old_assignee = exception.assigned_to_user_id

        exception.assigned_to_user_id = request.assigned_to_user_id
        if exception.status == ExceptionStatus.OPEN.value:
            exception.status = ExceptionStatus.INVESTIGATING.value

        await self.repository.update(exception)

        await self.repository.add_audit_log(
            exception_id=exception.id,
            action=ExceptionAction.ASSIGNED.value,
            actor_id=actor_id,
            previous_state={"assigned_to_user_id": str(old_assignee) if old_assignee else None},
            new_state={
                "assigned_to_user_id": str(request.assigned_to_user_id) if request.assigned_to_user_id else None,
                "status": exception.status,
            },
            comment=request.comment or "Exception reassigned",
        )

        return await self.repository.get_by_id(exception.id)

    async def escalate_exception(
        self,
        exception_id: uuid.UUID,
        request: ExceptionEscalateRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ShipmentException:
        """Escalate an exception to a higher severity and update status."""
        exception = await self.get_exception(exception_id)
        if exception.status == ExceptionStatus.CLOSED.value:
            raise ValidationException("Cannot escalate a closed exception.")

        old_severity = exception.severity
        new_severity = request.severity.value if request.severity else ExceptionSeverity.CRITICAL.value

        old_status = exception.status
        exception.severity = new_severity
        exception.status = ExceptionStatus.ESCALATED.value

        # Tighten SLA if newly elevated to CRITICAL
        now = datetime.now(timezone.utc)
        if new_severity == ExceptionSeverity.CRITICAL.value:
            exception.sla_breach_at = min(
                exception.sla_breach_at or (now + timedelta(hours=2)),
                now + timedelta(hours=2),
            )

        await self.repository.update(exception)

        await self.repository.add_audit_log(
            exception_id=exception.id,
            action=ExceptionAction.ESCALATED.value,
            actor_id=actor_id,
            previous_state={"severity": old_severity, "status": old_status},
            new_state={"severity": new_severity, "status": exception.status, "reason": request.reason},
            comment=f"Escalated: {request.reason}",
        )

        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="EXCEPTION_ESCALATED",
                resource_type="EXCEPTION",
                resource_id=str(exception.id),
                actor_id=actor_id,
                state_before={"severity": old_severity, "status": old_status},
                state_after={"severity": new_severity, "status": exception.status, "reason": request.reason},
                diff_summary={
                    "severity": {"from": old_severity, "to": new_severity},
                    "status": {"from": old_status, "to": exception.status},
                },
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped: %s", audit_err)

        await self._dispatch_upstream_notification(exception.shipment, exception)

        return await self.repository.get_by_id(exception.id)

    async def resolve_exception(
        self,
        exception_id: uuid.UUID,
        request: ExceptionResolveRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ShipmentException:
        """Mark an exception RESOLVED and document root cause and resolution actions."""
        exception = await self.get_exception(exception_id)
        if exception.status == ExceptionStatus.CLOSED.value:
            raise ValidationException("Exception is already closed.")

        old_status = exception.status
        now = datetime.now(timezone.utc)

        exception.status = ExceptionStatus.RESOLVED.value
        exception.root_cause = request.root_cause
        exception.resolution_notes = request.resolution_notes
        exception.resolved_at = now

        await self.repository.update(exception)

        await self.repository.add_audit_log(
            exception_id=exception.id,
            action=ExceptionAction.RESOLVED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={
                "status": exception.status,
                "root_cause": exception.root_cause,
                "resolution_notes": exception.resolution_notes,
                "resolved_at": now.isoformat(),
            },
            comment=f"Resolved with root cause: {request.root_cause}",
        )

        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="EXCEPTION_RESOLVED",
                resource_type="EXCEPTION",
                resource_id=str(exception.id),
                actor_id=actor_id,
                state_before={"status": old_status},
                state_after={"status": exception.status, "root_cause": exception.root_cause},
                diff_summary={"status": {"from": old_status, "to": exception.status}},
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped: %s", audit_err)

        await self._dispatch_upstream_notification(exception.shipment, exception)

        return await self.repository.get_by_id(exception.id)

    async def close_exception(
        self,
        exception_id: uuid.UUID,
        request: ExceptionCloseRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ShipmentException:
        """Formally close an exception."""
        exception = await self.get_exception(exception_id)
        old_status = exception.status
        now = datetime.now(timezone.utc)

        exception.status = ExceptionStatus.CLOSED.value
        exception.closed_at = now
        if request.resolution_notes:
            exception.resolution_notes = (
                f"{exception.resolution_notes or ''}\nClosing Note: {request.resolution_notes}".strip()
            )

        await self.repository.update(exception)

        await self.repository.add_audit_log(
            exception_id=exception.id,
            action=ExceptionAction.CLOSED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={"status": exception.status, "closed_at": now.isoformat()},
            comment=request.resolution_notes or "Exception closed permanently",
        )

        return await self.repository.get_by_id(exception.id)

    # --------------------------------------------------------------------------
    # ANOMALY DETECTION ENGINE
    # --------------------------------------------------------------------------

    async def detect_milestone_delay_anomalies(
        self,
        shipment_id: uuid.UUID,
        delay_threshold_minutes: int = 60,
    ) -> List[ShipmentException]:
        """Examines shipment milestones and triggers automated DELAY exceptions for delays exceeding threshold."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", shipment_id)

        # Check existing active delay exceptions
        existing = await self.repository.list_by_shipment_id(shipment_id)
        active_delays = [
            e for e in existing
            if e.exception_type == ExceptionType.DELAY.value
            and e.status not in (ExceptionStatus.RESOLVED.value, ExceptionStatus.CLOSED.value)
        ]

        created_exceptions: List[ShipmentException] = []
        for milestone in shipment.milestones:
            delay_minutes = 0
            if milestone.planned_time and milestone.actual_time:
                planned_utc = milestone.planned_time.astimezone(timezone.utc) if milestone.planned_time.tzinfo else milestone.planned_time.replace(tzinfo=timezone.utc)
                actual_utc = milestone.actual_time.astimezone(timezone.utc) if milestone.actual_time.tzinfo else milestone.actual_time.replace(tzinfo=timezone.utc)
                diff = int((actual_utc - planned_utc).total_seconds() / 60)
                if diff > 0:
                    delay_minutes = diff
            elif milestone.planned_time and not milestone.actual_time:
                planned_utc = milestone.planned_time.astimezone(timezone.utc) if milestone.planned_time.tzinfo else milestone.planned_time.replace(tzinfo=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc > planned_utc:
                    delay_minutes = int((now_utc - planned_utc).total_seconds() / 60)
            elif getattr(milestone, "status", None) == "DELAYED":
                delay_minutes = delay_threshold_minutes

            if delay_minutes >= delay_threshold_minutes:
                # Check if this specific milestone delay is already recorded
                already_flagged = any(
                    e.metadata_payload.get("milestone_id") == str(milestone.id)
                    for e in active_delays
                )
                if already_flagged:
                    continue

                severity = ExceptionSeverity.HIGH if delay_minutes >= 180 else ExceptionSeverity.MEDIUM
                exc = await self.create_exception(
                    ExceptionCreateRequest(
                        shipment_id=shipment.id,
                        exception_type=ExceptionType.DELAY,
                        severity=severity,
                        title=f"Milestone Delay: {milestone.title} (+{delay_minutes}m)",
                        description=(
                            f"Milestone '{milestone.title}' ({milestone.event_code}) at '{milestone.location_name}' "
                            f"is delayed by {delay_minutes} minutes. Planned: {milestone.planned_time}, "
                            f"Actual/Estimated: {milestone.actual_time or 'Pending'}."
                        ),
                        metadata_payload={
                            "milestone_id": str(milestone.id),
                            "event_code": milestone.event_code,
                            "delay_minutes": delay_minutes,
                            "detection_rule": "MILESTONE_DELAY_THRESHOLD",
                        },
                    ),
                    actor_id=None,  # Automated rule trigger
                )
                created_exceptions.append(exc)

        return created_exceptions

    async def detect_telemetry_silence_anomalies(
        self,
        shipment_id: uuid.UUID,
        max_silence_hours: float = 4.0,
    ) -> Optional[ShipmentException]:
        """Detects if an active IN_TRANSIT shipment has stopped broadcasting telemetry pings."""
        shipment = await self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", shipment_id)

        if shipment.status not in ("PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"):
            return None

        # Check existing active communication loss exceptions
        existing = await self.repository.list_by_shipment_id(shipment_id)
        active_comm_loss = any(
            e.exception_type == ExceptionType.COMMUNICATION_LOSS.value
            and e.status not in (ExceptionStatus.RESOLVED.value, ExceptionStatus.CLOSED.value)
            for e in existing
        )
        if active_comm_loss:
            return None

        latest_event = await self.tracking_repo.get_latest_event(shipment_id)
        now = datetime.now(timezone.utc)

        last_ping_time = latest_event.event_timestamp if latest_event else shipment.updated_at
        if last_ping_time.tzinfo is None:
            last_ping_time = last_ping_time.replace(tzinfo=timezone.utc)

        silence_hours = (now - last_ping_time).total_seconds() / 3600.0
        if silence_hours >= max_silence_hours:
            exc = await self.create_exception(
                ExceptionCreateRequest(
                    shipment_id=shipment.id,
                    exception_type=ExceptionType.COMMUNICATION_LOSS,
                    severity=ExceptionSeverity.HIGH,
                    title=f"Telemetry Silence: Carrier Ping Missing ({round(silence_hours, 1)}h)",
                    description=(
                        f"Shipment {shipment.external_reference} has received no GPS or checkpoint "
                        f"updates for {round(silence_hours, 1)} hours. Last contact: {last_ping_time.isoformat()}."
                    ),
                    metadata_payload={
                        "silence_hours": round(silence_hours, 2),
                        "last_ping_time": last_ping_time.isoformat(),
                        "detection_rule": "TELEMETRY_SILENCE_THRESHOLD",
                    },
                ),
                actor_id=None,
            )
            return exc

        return None

    # --------------------------------------------------------------------------
    # UPSTREAM MENDIX DISPATCH
    # --------------------------------------------------------------------------

    async def _dispatch_upstream_notification(
        self,
        shipment: Optional[Shipment],
        exception: ShipmentException,
    ) -> None:
        """Dispatches an asynchronous exception notification to Mendix adapter."""
        if not shipment or shipment.source_system != "MENDIX":
            return

        try:
            delay_minutes = exception.metadata_payload.get("delay_minutes")
            await self.mendix_client.push_exception_notification(
                external_reference=shipment.external_reference,
                exception_data={
                    "type": exception.exception_type,
                    "severity": exception.severity,
                    "status": exception.status,
                    "delay_minutes": delay_minutes,
                    "summary": exception.title,
                    "recommended_action": exception.resolution_notes or "Review in Control Tower",
                },
            )
            logger.info(
                f"Successfully synced exception {exception.id} to Mendix for shipment {shipment.external_reference}"
            )
        except Exception as exc:
            # Integration notification failure must never crash core transaction
            logger.warning(
                f"Upstream Mendix exception sync failed for {shipment.external_reference}: {exc}"
            )
