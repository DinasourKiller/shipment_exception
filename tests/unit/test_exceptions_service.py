"""Unit Tests for Exception Management Service, State Machine, and Anomaly Detection."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import ValidationException
from app.modules.exceptions.models import (
    ExceptionAction,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentException,
)
from app.modules.exceptions.schemas import (
    ExceptionAssignRequest,
    ExceptionCloseRequest,
    ExceptionCreateRequest,
    ExceptionEscalateRequest,
    ExceptionResolveRequest,
    ExceptionStatusUpdateRequest,
)
from app.modules.exceptions.service import (
    ALLOWED_TRANSITIONS,
    DEFAULT_SLA_HOURS,
    ExceptionService,
)
from app.modules.shipments.models import Shipment, ShipmentMilestone
from app.modules.tracking.models import TrackingEvent


def test_calculate_default_sla_deadlines():
    """Verify default SLA hours mapping based on impact severity."""
    now = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
    critical_sla = ExceptionService.calculate_default_sla(ExceptionSeverity.CRITICAL.value, from_time=now)
    high_sla = ExceptionService.calculate_default_sla(ExceptionSeverity.HIGH.value, from_time=now)
    med_sla = ExceptionService.calculate_default_sla(ExceptionSeverity.MEDIUM.value, from_time=now)
    low_sla = ExceptionService.calculate_default_sla(ExceptionSeverity.LOW.value, from_time=now)

    assert critical_sla == now + timedelta(hours=2)
    assert high_sla == now + timedelta(hours=4)
    assert med_sla == now + timedelta(hours=12)
    assert low_sla == now + timedelta(hours=24)


def test_state_machine_allowed_transitions_structure():
    """Verify state machine transition graph integrity."""
    assert ExceptionStatus.INVESTIGATING.value in ALLOWED_TRANSITIONS[ExceptionStatus.OPEN.value]
    assert ExceptionStatus.ESCALATED.value in ALLOWED_TRANSITIONS[ExceptionStatus.OPEN.value]
    assert ExceptionStatus.CLOSED.value in ALLOWED_TRANSITIONS[ExceptionStatus.RESOLVED.value]
    assert len(ALLOWED_TRANSITIONS[ExceptionStatus.CLOSED.value]) == 0


@pytest.mark.asyncio
async def test_create_exception_with_default_sla():
    """Verify exception creation computes default SLA when omitted."""
    shipment_id = uuid.uuid4()
    shipment = Shipment(id=shipment_id, external_reference="MDX-101", source_system="INTERNAL")

    mock_session = MagicMock()
    mock_mendix = MagicMock()
    mock_mendix.push_exception_notification = AsyncMock()

    service = ExceptionService(session=mock_session, mendix_client=mock_mendix)
    service.shipment_repo.get_by_id = AsyncMock(return_value=shipment)
    service.repository.create = AsyncMock()
    service.repository.add_audit_log = AsyncMock()

    created_entity = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.OPEN.value,
        title="Delay alert",
        description="Shipment delayed",
        sla_breach_at=datetime.now(timezone.utc) + timedelta(hours=4),
        metadata_payload={},
    )
    service.repository.get_by_id = AsyncMock(return_value=created_entity)

    req = ExceptionCreateRequest(
        shipment_id=shipment_id,
        exception_type=ExceptionType.DELAY,
        severity=ExceptionSeverity.HIGH,
        title="Delay alert",
        description="Shipment delayed",
    )

    result = await service.create_exception(req, actor_id=uuid.uuid4())

    assert result.severity == ExceptionSeverity.HIGH.value
    assert result.status == ExceptionStatus.OPEN.value
    service.repository.create.assert_called_once()
    service.repository.add_audit_log.assert_called_once()


@pytest.mark.asyncio
async def test_update_status_illegal_transition_raises_validation_exception():
    """Verify state machine strictly rejects illegal transitions."""
    exception_id = uuid.uuid4()
    exception = ShipmentException(
        id=exception_id,
        shipment_id=uuid.uuid4(),
        status=ExceptionStatus.CLOSED.value,
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.LOW.value,
        title="Closed exception",
        description="Already resolved and closed",
    )

    mock_session = MagicMock()
    service = ExceptionService(session=mock_session)
    service.repository.get_by_id = AsyncMock(return_value=exception)

    req = ExceptionStatusUpdateRequest(status=ExceptionStatus.INVESTIGATING)

    with pytest.raises(ValidationException) as exc_info:
        await service.update_status(exception_id, req)

    assert "Illegal exception lifecycle transition" in str(exc_info.value)


@pytest.mark.asyncio
async def test_escalate_exception_tightens_sla():
    """Verify escalating an exception increases severity and tightens resolution SLA."""
    exception_id = uuid.uuid4()
    shipment = Shipment(id=uuid.uuid4(), external_reference="MDX-202", source_system="MENDIX")
    exception = ShipmentException(
        id=exception_id,
        shipment_id=shipment.id,
        shipment=shipment,
        status=ExceptionStatus.OPEN.value,
        severity=ExceptionSeverity.MEDIUM.value,
        exception_type=ExceptionType.VEHICLE_BREAKDOWN.value,
        title="Engine failure",
        description="Truck engine overheated",
        sla_breach_at=datetime.now(timezone.utc) + timedelta(hours=12),
        metadata_payload={},
    )

    mock_session = MagicMock()
    mock_mendix = MagicMock()
    mock_mendix.push_exception_notification = AsyncMock()

    service = ExceptionService(session=mock_session, mendix_client=mock_mendix)
    service.repository.get_by_id = AsyncMock(return_value=exception)
    service.repository.update = AsyncMock()
    service.repository.add_audit_log = AsyncMock()

    req = ExceptionEscalateRequest(
        severity=ExceptionSeverity.CRITICAL,
        reason="Perishable cargo at risk of spoilage",
    )

    await service.escalate_exception(exception_id, req)

    assert exception.severity == ExceptionSeverity.CRITICAL.value
    assert exception.status == ExceptionStatus.ESCALATED.value
    service.repository.update.assert_called_once()
    service.repository.add_audit_log.assert_called_once()
    mock_mendix.push_exception_notification.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_and_close_exception_lifecycle():
    """Verify resolve sets root cause and resolved_at, then close sets closed_at."""
    exception_id = uuid.uuid4()
    exception = ShipmentException(
        id=exception_id,
        shipment_id=uuid.uuid4(),
        status=ExceptionStatus.INVESTIGATING.value,
        severity=ExceptionSeverity.HIGH.value,
        exception_type=ExceptionType.ROUTE_DEVIATION.value,
        title="Route deviation",
        description="Driver took alternate route",
        metadata_payload={},
    )

    mock_session = MagicMock()
    service = ExceptionService(session=mock_session)
    service.repository.get_by_id = AsyncMock(return_value=exception)
    service.repository.update = AsyncMock()
    service.repository.add_audit_log = AsyncMock()
    service._dispatch_upstream_notification = AsyncMock()

    resolve_req = ExceptionResolveRequest(
        root_cause="Highway construction detour",
        resolution_notes="Authorized detour completed; shipment back on designated corridor.",
    )

    await service.resolve_exception(exception_id, resolve_req)
    assert exception.status == ExceptionStatus.RESOLVED.value
    assert exception.root_cause == "Highway construction detour"
    assert exception.resolved_at is not None

    close_req = ExceptionCloseRequest(resolution_notes="Customer notified, delivery confirmed.")
    await service.close_exception(exception_id, close_req)
    assert exception.status == ExceptionStatus.CLOSED.value
    assert exception.closed_at is not None


@pytest.mark.asyncio
async def test_detect_milestone_delay_anomalies_triggers_exception():
    """Verify milestone delay exceeding threshold creates an automated exception."""
    shipment_id = uuid.uuid4()
    planned = datetime(2026, 11, 19, 8, 0, 0, tzinfo=timezone.utc)
    actual = planned + timedelta(minutes=120)  # 120 minutes delay
    delayed_milestone = ShipmentMilestone(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        event_code="HUB_TRANSIT",
        title="Hub Sorting",
        location_name="Chicago Hub",
        planned_time=planned,
        actual_time=actual,
        status="DELAYED",
    )
    shipment = Shipment(
        id=shipment_id,
        external_reference="MDX-999",
        source_system="INTERNAL",
        milestones=[delayed_milestone],
    )

    mock_session = MagicMock()
    service = ExceptionService(session=mock_session)
    service.shipment_repo.get_by_id = AsyncMock(return_value=shipment)
    service.repository.list_by_shipment_id = AsyncMock(return_value=[])  # no existing exceptions
    service.create_exception = AsyncMock(return_value=ShipmentException(id=uuid.uuid4()))

    triggered = await service.detect_milestone_delay_anomalies(shipment_id, delay_threshold_minutes=60)

    assert len(triggered) == 1
    service.create_exception.assert_called_once()


@pytest.mark.asyncio
async def test_detect_milestone_delay_anomalies_avoids_duplicate():
    """Verify milestone delay already flagged is not duplicated."""
    shipment_id = uuid.uuid4()
    milestone_id = uuid.uuid4()
    planned = datetime(2026, 11, 19, 8, 0, 0, tzinfo=timezone.utc)
    actual = planned + timedelta(minutes=120)
    delayed_milestone = ShipmentMilestone(
        id=milestone_id,
        shipment_id=shipment_id,
        event_code="HUB_TRANSIT",
        title="Hub Sorting",
        location_name="Chicago Hub",
        planned_time=planned,
        actual_time=actual,
        status="DELAYED",
    )
    shipment = Shipment(
        id=shipment_id,
        external_reference="MDX-999",
        source_system="INTERNAL",
        milestones=[delayed_milestone],
    )

    existing_exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        exception_type=ExceptionType.DELAY.value,
        status=ExceptionStatus.OPEN.value,
        metadata_payload={"milestone_id": str(milestone_id)},
    )

    mock_session = MagicMock()
    service = ExceptionService(session=mock_session)
    service.shipment_repo.get_by_id = AsyncMock(return_value=shipment)
    service.repository.list_by_shipment_id = AsyncMock(return_value=[existing_exception])
    service.create_exception = AsyncMock()

    triggered = await service.detect_milestone_delay_anomalies(shipment_id, delay_threshold_minutes=60)

    assert len(triggered) == 0
    service.create_exception.assert_not_called()
