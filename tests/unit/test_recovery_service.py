"""Unit Tests for Carrier Recovery & Resource Dispatch Service and State Machine."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.modules.exceptions.models import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentException,
)
from app.modules.recovery.models import (
    RecoveryAction,
    RecoveryPlan,
    RecoveryPlanType,
    RecoveryStatus,
)
from app.modules.recovery.schemas import (
    RecoveryPlanCarrierResponseRequest,
    RecoveryPlanCompleteRequest,
    RecoveryPlanCreateRequest,
    RecoveryPlanDispatchRequest,
)
from app.modules.recovery.service import RECOVERY_ALLOWED_TRANSITIONS, RecoveryService


@pytest.fixture
def mock_session():
    """Mock async SQLAlchemy session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def test_recovery_state_machine_transition_graph():
    """Verify validity of recovery lifecycle transition map."""
    assert RecoveryStatus.REQUESTED.value in RECOVERY_ALLOWED_TRANSITIONS[RecoveryStatus.DRAFT.value]
    assert RecoveryStatus.ACCEPTED.value in RECOVERY_ALLOWED_TRANSITIONS[RecoveryStatus.REQUESTED.value]
    assert RecoveryStatus.REJECTED.value in RECOVERY_ALLOWED_TRANSITIONS[RecoveryStatus.REQUESTED.value]
    assert RecoveryStatus.DISPATCHED.value in RECOVERY_ALLOWED_TRANSITIONS[RecoveryStatus.ACCEPTED.value]
    assert RecoveryStatus.COMPLETED.value in RECOVERY_ALLOWED_TRANSITIONS[RecoveryStatus.DISPATCHED.value]
    assert len(RECOVERY_ALLOWED_TRANSITIONS[RecoveryStatus.COMPLETED.value]) == 0


@pytest.mark.asyncio
async def test_create_recovery_plan(mock_session):
    """Verify drafting a new recovery plan."""
    service = RecoveryService(mock_session)
    exception_id = uuid.uuid4()
    exception = ShipmentException(
        id=exception_id,
        shipment_id=uuid.uuid4(),
        exception_type=ExceptionType.VEHICLE_BREAKDOWN.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.OPEN.value,
        title="Breakdown",
        description="Stranded truck",
    )
    service.exception_repo.get_by_id = AsyncMock(return_value=exception)
    service.recovery_repo.create = AsyncMock(side_effect=lambda p: p)
    service.recovery_repo.add_audit_log = AsyncMock()

    request = RecoveryPlanCreateRequest(
        exception_id=exception_id,
        plan_type=RecoveryPlanType.VEHICLE_REPLACEMENT,
        carrier_code="APEX",
        carrier_name="Apex Logistics",
        estimated_cost=1500.0,
        estimated_recovery_hours=3.5,
        instructions="Relay tractor to mile marker 45",
    )

    plan = await service.create_plan(request)
    assert plan.status == RecoveryStatus.DRAFT.value
    assert plan.carrier_code == "APEX"
    assert plan.estimated_cost == 1500.0
    service.recovery_repo.add_audit_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_carrier_accepts_and_revises_proposal(mock_session):
    """Verify carrier acceptance updates status and accepts revised quote."""
    service = RecoveryService(mock_session)
    plan_id = uuid.uuid4()
    plan = RecoveryPlan(
        id=plan_id,
        exception_id=uuid.uuid4(),
        plan_type=RecoveryPlanType.CROSS_DOCK.value,
        status=RecoveryStatus.REQUESTED.value,
        carrier_code="APEX",
        carrier_name="Apex Logistics",
        estimated_cost=1000.0,
        estimated_recovery_hours=4.0,
    )
    service.recovery_repo.get_by_id = AsyncMock(return_value=plan)
    service.recovery_repo.update = AsyncMock()
    service.recovery_repo.add_audit_log = AsyncMock()

    response_req = RecoveryPlanCarrierResponseRequest(
        accepted=True,
        carrier_notes="Driver standing by at Chicago terminal.",
        revised_estimated_cost=1200.0,
        revised_recovery_hours=3.0,
    )

    updated = await service.carrier_respond(plan_id, response_req)
    assert updated.status == RecoveryStatus.ACCEPTED.value
    assert updated.estimated_cost == 1200.0
    assert updated.estimated_recovery_hours == 3.0
    assert updated.carrier_notes == "Driver standing by at Chicago terminal."


@pytest.mark.asyncio
async def test_carrier_rejects_proposal(mock_session):
    """Verify carrier rejection logs rejection reason and marks plan REJECTED."""
    service = RecoveryService(mock_session)
    plan_id = uuid.uuid4()
    plan = RecoveryPlan(
        id=plan_id,
        exception_id=uuid.uuid4(),
        plan_type=RecoveryPlanType.VEHICLE_REPLACEMENT.value,
        status=RecoveryStatus.REQUESTED.value,
        carrier_code="FEDX",
        carrier_name="FedEx Freight",
        estimated_cost=800.0,
    )
    service.recovery_repo.get_by_id = AsyncMock(return_value=plan)
    service.recovery_repo.update = AsyncMock()
    service.recovery_repo.add_audit_log = AsyncMock()

    response_req = RecoveryPlanCarrierResponseRequest(
        accepted=False,
        rejection_reason="No available refrigerated trailers within 50 miles.",
    )

    updated = await service.carrier_respond(plan_id, response_req)
    assert updated.status == RecoveryStatus.REJECTED.value
    assert updated.rejection_reason == "No available refrigerated trailers within 50 miles."


@pytest.mark.asyncio
async def test_dispatch_resources_advances_exception_status(mock_session):
    """Verify dispatching driver and vehicle transitions exception to RESOLVING."""
    service = RecoveryService(mock_session)
    exception_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    plan = RecoveryPlan(
        id=plan_id,
        exception_id=exception_id,
        plan_type=RecoveryPlanType.VEHICLE_REPLACEMENT.value,
        status=RecoveryStatus.ACCEPTED.value,
        carrier_code="APEX",
        carrier_name="Apex Logistics",
    )
    exception = ShipmentException(
        id=exception_id,
        shipment_id=uuid.uuid4(),
        exception_type=ExceptionType.VEHICLE_BREAKDOWN.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.ESCALATED.value,
        title="Breakdown",
        description="Stranded truck",
    )

    service.recovery_repo.get_by_id = AsyncMock(return_value=plan)
    service.recovery_repo.update = AsyncMock()
    service.recovery_repo.add_audit_log = AsyncMock()
    service.exception_repo.get_by_id = AsyncMock(return_value=exception)
    service.exception_service.update_status = AsyncMock()

    dispatch_req = RecoveryPlanDispatchRequest(
        driver_name="Marcus Vance",
        driver_phone="+1-555-987-6543",
        vehicle_plate="IL-TX-8821",
    )

    dispatched = await service.dispatch_resources(plan_id, dispatch_req)
    assert dispatched.status == RecoveryStatus.DISPATCHED.value
    assert dispatched.driver_name == "Marcus Vance"
    assert dispatched.vehicle_plate == "IL-TX-8821"
    # Verify exception status update called with RESOLVING
    service.exception_service.update_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_recovery_resolves_exception(mock_session):
    """Verify completing recovery plan triggers exception resolution."""
    service = RecoveryService(mock_session)
    exception_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    plan = RecoveryPlan(
        id=plan_id,
        exception_id=exception_id,
        plan_type=RecoveryPlanType.VEHICLE_REPLACEMENT.value,
        status=RecoveryStatus.DISPATCHED.value,
        carrier_code="APEX",
        carrier_name="Apex Logistics",
    )
    exception = ShipmentException(
        id=exception_id,
        shipment_id=uuid.uuid4(),
        exception_type=ExceptionType.VEHICLE_BREAKDOWN.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.RESOLVING.value,
        title="Breakdown",
        description="Stranded truck",
    )

    service.recovery_repo.get_by_id = AsyncMock(return_value=plan)
    service.recovery_repo.update = AsyncMock()
    service.recovery_repo.add_audit_log = AsyncMock()
    service.exception_repo.get_by_id = AsyncMock(return_value=exception)
    service.exception_service.resolve_exception = AsyncMock()

    complete_req = RecoveryPlanCompleteRequest(
        completion_notes="Cargo transferred and delivery completed successfully.",
        resolve_exception=True,
    )

    completed = await service.complete_recovery(plan_id, complete_req)
    assert completed.status == RecoveryStatus.COMPLETED.value
    service.exception_service.resolve_exception.assert_awaited_once()


@pytest.mark.asyncio
async def test_illegal_state_transition_raises_validation_exception(mock_session):
    """Verify attempting an illegal transition (e.g. DRAFT -> DISPATCHED) raises ValidationException."""
    service = RecoveryService(mock_session)
    plan_id = uuid.uuid4()
    plan = RecoveryPlan(
        id=plan_id,
        exception_id=uuid.uuid4(),
        plan_type=RecoveryPlanType.CROSS_DOCK.value,
        status=RecoveryStatus.DRAFT.value,
        carrier_code="APEX",
        carrier_name="Apex Logistics",
    )
    service.recovery_repo.get_by_id = AsyncMock(return_value=plan)

    dispatch_req = RecoveryPlanDispatchRequest(
        driver_name="Jane Doe",
        driver_phone="+1-555-111-2222",
        vehicle_plate="NY-991",
    )

    with pytest.raises(ValidationException):
        await service.dispatch_resources(plan_id, dispatch_req)
