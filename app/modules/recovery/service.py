"""Carrier Recovery & Resource Dispatch Service.

Coordinates recovery plan creation, carrier quote/proposal acceptance,
vehicle/driver resource dispatching, and synchronization with exception lifecycle.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.exceptions.models import (
    ExceptionAction,
    ExceptionStatus,
    ShipmentException,
)
from app.modules.exceptions.repository import ExceptionRepository
from app.modules.exceptions.schemas import (
    ExceptionResolveRequest,
    ExceptionStatusUpdateRequest,
)
from app.modules.exceptions.service import ExceptionService
from app.modules.recovery.models import (
    RecoveryAction,
    RecoveryPlan,
    RecoveryPlanType,
    RecoveryStatus,
)
from app.modules.recovery.repository import RecoveryRepository
from app.modules.recovery.schemas import (
    PaginatedRecoveryResponse,
    RecoveryPlanCarrierResponseRequest,
    RecoveryPlanCompleteRequest,
    RecoveryPlanCreateRequest,
    RecoveryPlanDispatchRequest,
    RecoveryPlanResponse,
)

logger = get_logger("control_tower.recovery.service")

# Permitted recovery lifecycle transitions
RECOVERY_ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    RecoveryStatus.DRAFT.value: {
        RecoveryStatus.REQUESTED.value,
        RecoveryStatus.CANCELLED.value,
    },
    RecoveryStatus.REQUESTED.value: {
        RecoveryStatus.ACCEPTED.value,
        RecoveryStatus.REJECTED.value,
        RecoveryStatus.DISPATCHED.value,  # Direct expedite override
        RecoveryStatus.CANCELLED.value,
    },
    RecoveryStatus.ACCEPTED.value: {
        RecoveryStatus.DISPATCHED.value,
        RecoveryStatus.CANCELLED.value,
    },
    RecoveryStatus.REJECTED.value: {
        RecoveryStatus.REQUESTED.value,  # Re-request with revised terms
        RecoveryStatus.CANCELLED.value,
    },
    RecoveryStatus.DISPATCHED.value: {
        RecoveryStatus.COMPLETED.value,
        RecoveryStatus.CANCELLED.value,
    },
    RecoveryStatus.COMPLETED.value: set(),
    RecoveryStatus.CANCELLED.value: set(),
}


class RecoveryService:
    """Core domain service for orchestrating carrier recovery and resource dispatch."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.recovery_repo = RecoveryRepository(session)
        self.exception_repo = ExceptionRepository(session)
        self.exception_service = ExceptionService(session)

    async def create_plan(
        self,
        request: RecoveryPlanCreateRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RecoveryPlan:
        """Draft a new recovery plan linked to an active exception."""
        exception = await self.exception_repo.get_by_id(request.exception_id)
        if not exception:
            raise EntityNotFoundException("ShipmentException", request.exception_id)

        if exception.status == ExceptionStatus.CLOSED.value:
            raise ValidationException("Cannot initiate recovery for a closed exception.")

        plan = RecoveryPlan(
            id=uuid.uuid4(),
            exception_id=exception.id,
            plan_type=request.plan_type.value,
            status=RecoveryStatus.DRAFT.value,
            carrier_code=request.carrier_code.strip().upper(),
            carrier_name=request.carrier_name.strip(),
            estimated_cost=round(float(request.estimated_cost), 2),
            estimated_recovery_hours=round(float(request.estimated_recovery_hours), 2),
            instructions=request.instructions,
            created_by_id=actor_id,
        )

        saved = await self.recovery_repo.create(plan)

        await self.recovery_repo.add_audit_log(
            recovery_plan_id=saved.id,
            action=RecoveryAction.CREATED.value,
            actor_id=actor_id,
            previous_state={},
            new_state={
                "status": saved.status,
                "plan_type": saved.plan_type,
                "carrier_code": saved.carrier_code,
                "estimated_cost": saved.estimated_cost,
            },
            comment=f"Drafted recovery plan ({saved.plan_type}) with carrier {saved.carrier_name}",
        )

        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="RECOVERY_PLAN_CREATED",
                resource_type="RECOVERY_PLAN",
                resource_id=str(saved.id),
                actor_id=actor_id,
                state_after={
                    "status": saved.status,
                    "plan_type": saved.plan_type,
                    "carrier_code": saved.carrier_code,
                    "estimated_cost": saved.estimated_cost,
                },
                diff_summary={"created": True, "plan_type": saved.plan_type, "carrier": saved.carrier_code},
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped: %s", audit_err)

        logger.info("Created recovery plan %s for exception %s", saved.id, exception.id)
        return saved

    async def request_carrier(
        self,
        plan_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RecoveryPlan:
        """Transmit recovery request proposal to assigned carrier."""
        plan = await self.get_plan(plan_id)
        self._validate_transition(plan.status, RecoveryStatus.REQUESTED.value)

        old_status = plan.status
        plan.status = RecoveryStatus.REQUESTED.value
        plan.requested_at = datetime.now(timezone.utc)
        await self.recovery_repo.update(plan)

        await self.recovery_repo.add_audit_log(
            recovery_plan_id=plan.id,
            action=RecoveryAction.REQUESTED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={"status": plan.status, "requested_at": plan.requested_at.isoformat()},
            comment=f"Transmitted recovery dispatch request to {plan.carrier_name} ({plan.carrier_code})",
        )
        return plan

    async def carrier_respond(
        self,
        plan_id: uuid.UUID,
        request: RecoveryPlanCarrierResponseRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RecoveryPlan:
        """Record carrier acceptance or rejection with optional revised terms."""
        plan = await self.get_plan(plan_id)
        target_status = RecoveryStatus.ACCEPTED.value if request.accepted else RecoveryStatus.REJECTED.value
        self._validate_transition(plan.status, target_status)

        old_status = plan.status
        plan.status = target_status
        plan.responded_at = datetime.now(timezone.utc)

        if request.carrier_notes:
            plan.carrier_notes = request.carrier_notes

        action = RecoveryAction.CARRIER_ACCEPTED.value if request.accepted else RecoveryAction.CARRIER_REJECTED.value
        comment = ""

        if request.accepted:
            if request.revised_estimated_cost is not None:
                plan.estimated_cost = round(float(request.revised_estimated_cost), 2)
            if request.revised_recovery_hours is not None:
                plan.estimated_recovery_hours = round(float(request.revised_recovery_hours), 2)
            comment = f"Carrier {plan.carrier_name} accepted recovery request."
        else:
            plan.rejection_reason = request.rejection_reason or "Carrier unable to fulfill recovery SLA."
            comment = f"Carrier {plan.carrier_name} rejected request: {plan.rejection_reason}"

        await self.recovery_repo.update(plan)

        await self.recovery_repo.add_audit_log(
            recovery_plan_id=plan.id,
            action=action,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={
                "status": plan.status,
                "accepted": request.accepted,
                "estimated_cost": plan.estimated_cost,
                "rejection_reason": plan.rejection_reason,
            },
            comment=comment,
        )
        return plan

    async def dispatch_resources(
        self,
        plan_id: uuid.UUID,
        request: RecoveryPlanDispatchRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RecoveryPlan:
        """Confirm driver/vehicle resources and dispatch recovery action."""
        plan = await self.get_plan(plan_id)
        self._validate_transition(plan.status, RecoveryStatus.DISPATCHED.value)

        old_status = plan.status
        plan.status = RecoveryStatus.DISPATCHED.value
        plan.driver_name = request.driver_name.strip()
        plan.driver_phone = request.driver_phone.strip()
        plan.vehicle_plate = request.vehicle_plate.strip().upper()
        plan.dispatched_at = datetime.now(timezone.utc)

        await self.recovery_repo.update(plan)

        await self.recovery_repo.add_audit_log(
            recovery_plan_id=plan.id,
            action=RecoveryAction.DISPATCHED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={
                "status": plan.status,
                "driver_name": plan.driver_name,
                "vehicle_plate": plan.vehicle_plate,
                "dispatched_at": plan.dispatched_at.isoformat(),
            },
            comment=f"Dispatched driver {plan.driver_name} (Plate: {plan.vehicle_plate})",
        )

        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="RECOVERY_DISPATCHED",
                resource_type="RECOVERY_PLAN",
                resource_id=str(plan.id),
                actor_id=actor_id,
                state_before={"status": old_status},
                state_after={"status": plan.status, "driver": plan.driver_name, "plate": plan.vehicle_plate},
                diff_summary={"status": {"from": old_status, "to": plan.status}, "driver": plan.driver_name},
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped: %s", audit_err)

        # Hook: Advance underlying exception to RESOLVING
        try:
            exception = await self.exception_repo.get_by_id(plan.exception_id)
            if exception and exception.status in (
                ExceptionStatus.OPEN.value,
                ExceptionStatus.INVESTIGATING.value,
                ExceptionStatus.ESCALATED.value,
            ):
                await self.exception_service.update_status(
                    exception_id=exception.id,
                    request=ExceptionStatusUpdateRequest(
                        status=ExceptionStatus.RESOLVING,
                        comment=f"Recovery plan {plan.id} dispatched: driver {plan.driver_name}, plate {plan.vehicle_plate}",
                    ),
                    actor_id=actor_id,
                )
                logger.info("Exception %s automatically transitioned to RESOLVING upon recovery dispatch", exception.id)
        except Exception as err:
            logger.warning("Failed to auto-update exception status on dispatch: %s", err)

        return plan

    async def complete_recovery(
        self,
        plan_id: uuid.UUID,
        request: RecoveryPlanCompleteRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RecoveryPlan:
        """Mark recovery completed and optionally resolve the associated exception."""
        plan = await self.get_plan(plan_id)
        self._validate_transition(plan.status, RecoveryStatus.COMPLETED.value)

        old_status = plan.status
        plan.status = RecoveryStatus.COMPLETED.value
        plan.completed_at = datetime.now(timezone.utc)
        plan.approved_by_id = actor_id

        await self.recovery_repo.update(plan)

        await self.recovery_repo.add_audit_log(
            recovery_plan_id=plan.id,
            action=RecoveryAction.COMPLETED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={"status": plan.status, "completed_at": plan.completed_at.isoformat()},
            comment=request.completion_notes or "Recovery operation completed and confirmed.",
        )

        # Option: Auto-resolve underlying exception
        if request.resolve_exception:
            try:
                exception = await self.exception_repo.get_by_id(plan.exception_id)
                if exception and exception.status != ExceptionStatus.CLOSED.value:
                    await self.exception_service.resolve_exception(
                        exception_id=exception.id,
                        request=ExceptionResolveRequest(
                            root_cause=f"Resolved via {plan.plan_type} recovery dispatch.",
                            resolution_notes=request.completion_notes or "Driver handover and delivery completed.",
                        ),
                        actor_id=actor_id,
                    )
            except Exception as err:
                logger.warning("Failed to auto-resolve exception on recovery completion: %s", err)

        return plan

    async def cancel_plan(
        self,
        plan_id: uuid.UUID,
        reason: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RecoveryPlan:
        """Cancel an in-flight or drafted recovery plan."""
        plan = await self.get_plan(plan_id)
        self._validate_transition(plan.status, RecoveryStatus.CANCELLED.value)

        old_status = plan.status
        plan.status = RecoveryStatus.CANCELLED.value
        plan.cancelled_at = datetime.now(timezone.utc)

        await self.recovery_repo.update(plan)

        await self.recovery_repo.add_audit_log(
            recovery_plan_id=plan.id,
            action=RecoveryAction.CANCELLED.value,
            actor_id=actor_id,
            previous_state={"status": old_status},
            new_state={"status": plan.status},
            comment=reason or "Recovery plan cancelled by operator.",
        )
        return plan

    async def get_plan(self, plan_id: uuid.UUID) -> RecoveryPlan:
        """Fetch recovery plan by ID or raise 404."""
        plan = await self.recovery_repo.get_by_id(plan_id)
        if not plan:
            raise EntityNotFoundException("RecoveryPlan", plan_id)
        return plan

    async def list_by_exception(self, exception_id: uuid.UUID) -> List[RecoveryPlan]:
        """Fetch all recovery plans associated with an exception."""
        return await self.recovery_repo.list_by_exception_id(exception_id)

    async def list_plans(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        carrier_code: Optional[str] = None,
        plan_type: Optional[str] = None,
        exception_id: Optional[uuid.UUID] = None,
    ) -> PaginatedRecoveryResponse:
        """List recovery plans with filtering and pagination."""
        items, total = await self.recovery_repo.list_plans(
            page=page,
            page_size=page_size,
            status=status,
            carrier_code=carrier_code,
            plan_type=plan_type,
            exception_id=exception_id,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedRecoveryResponse(
            items=[RecoveryPlanResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -------------------------------------------------------------------------
    # Helper Validation
    # -------------------------------------------------------------------------

    def _validate_transition(self, current_status: str, target_status: str) -> None:
        """Enforce recovery state machine transitions."""
        if current_status == target_status:
            return

        allowed = RECOVERY_ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ValidationException(
                f"Illegal recovery lifecycle transition from '{current_status}' to '{target_status}'. "
                f"Allowed transitions: {sorted(list(allowed)) or 'None (Terminal state)'}"
            )
