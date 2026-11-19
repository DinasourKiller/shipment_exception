"""Unit Tests for Impact Analysis Engine Service and Risk Scoring Algorithms."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import EntityNotFoundException
from app.modules.exceptions.models import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentException,
)
from app.modules.impact.models import (
    CustomerImpactLevel,
    ImpactAssessment,
    SupplyChainImpactLevel,
)
from app.modules.impact.schemas import ImpactAssessRequest
from app.modules.impact.service import ImpactService
from app.modules.shipments.models import CargoItem, Shipment


@pytest.fixture
def mock_session():
    """Mock async SQLAlchemy session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def test_compute_delay_hours_custom_override(mock_session):
    """Verify custom delay hours takes top precedence."""
    service = ImpactService(mock_session)
    shipment = Shipment(id=uuid.uuid4(), external_reference="MDX-1", raw_metadata={})
    exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment.id,
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.MEDIUM.value,
        status=ExceptionStatus.OPEN.value,
        title="Delay test",
        description="Delay test description",
        metadata_payload={"delay_minutes": 120},
    )

    hours = service._compute_delay_hours(exception, shipment, custom_delay_hours=7.5)
    assert hours == 7.5


def test_compute_delay_hours_from_metadata(mock_session):
    """Verify delay minutes in exception metadata converts to hours."""
    service = ImpactService(mock_session)
    shipment = Shipment(id=uuid.uuid4(), external_reference="MDX-2", raw_metadata={})
    exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment.id,
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.OPEN.value,
        title="Delay test 2",
        description="Delay test description 2",
        metadata_payload={"delay_minutes": 180},
    )

    hours = service._compute_delay_hours(exception, shipment, custom_delay_hours=None)
    assert hours == 3.0


def test_compute_cargo_risk_temperature_excursion(mock_session):
    """Verify temperature excursion computes high cargo spoilage on critical severity."""
    service = ImpactService(mock_session)
    cargo1 = CargoItem(id=uuid.uuid4(), description="Vaccines", declared_value=5000.0, quantity=2)
    cargo2 = CargoItem(id=uuid.uuid4(), description="Supplies", declared_value=2000.0, quantity=1)
    shipment = Shipment(
        id=uuid.uuid4(),
        external_reference="MDX-COLD",
        cargo_items=[cargo1, cargo2],
        raw_metadata={},
    )
    # Total cargo value: (5000 * 2) + 2000 = 12,000 USD
    exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment.id,
        exception_type=ExceptionType.TEMPERATURE_EXCURSION.value,
        severity=ExceptionSeverity.CRITICAL.value,
        status=ExceptionStatus.OPEN.value,
    )

    cargo_val, damage_cost, ratio = service._compute_cargo_risk(
        exception, shipment, custom_cargo_loss_pct=None
    )
    assert cargo_val == 12000.0
    assert ratio == 0.85
    assert damage_cost == 10200.0


def test_compute_contractual_penalties_sla_breach(mock_session):
    """Verify SLA breach adds contractual penalty according to severity."""
    service = ImpactService(mock_session)
    exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=uuid.uuid4(),
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.CRITICAL.value,
        status=ExceptionStatus.OPEN.value,
        is_sla_breached=True,
    )

    penalty = service._compute_contractual_penalties(exception, custom_contractual_penalty=None)
    assert penalty == 2500.0


def test_compute_customer_impact_vip(mock_session):
    """Verify VIP customer tier receives elevated impact scoring."""
    service = ImpactService(mock_session)
    shipment = Shipment(
        id=uuid.uuid4(),
        external_reference="MDX-VIP",
        raw_metadata={"customer_tier": "VIP"},
    )
    exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment.id,
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.OPEN.value,
    )

    tier, level, score = service._compute_customer_impact(
        exception, shipment, delay_hours=8.0, custom_tier=None
    )
    assert tier == "VIP"
    assert level == CustomerImpactLevel.CRITICAL
    assert score >= 20.0


def test_composite_score_bounds_and_components(mock_session):
    """Verify composite priority score remains clamped between 0 and 100."""
    service = ImpactService(mock_session)
    # Extreme high values
    score_high, factors_high = service._compute_composite_score(
        total_financial_impact=50000.0,
        customer_score=25.0,
        exception_severity=ExceptionSeverity.CRITICAL.value,
        is_sla_breached=True,
        sc_score=15.0,
    )
    assert 0.0 <= score_high <= 100.0
    assert score_high == 100.0
    assert factors_high["sla_points"] == 10.0

    # Low values
    score_low, factors_low = service._compute_composite_score(
        total_financial_impact=0.0,
        customer_score=3.0,
        exception_severity=ExceptionSeverity.LOW.value,
        is_sla_breached=False,
        sc_score=2.0,
    )
    assert 0.0 <= score_low <= 100.0
    assert score_low < 20.0
    assert factors_low["sla_points"] == 0.0


@pytest.mark.asyncio
async def test_assess_exception_triggers_auto_escalation(mock_session):
    """Verify assess_exception_impact auto-escalates when score breaches threshold."""
    service = ImpactService(mock_session)

    shipment_id = uuid.uuid4()
    exception_id = uuid.uuid4()
    shipment = Shipment(
        id=shipment_id,
        external_reference="MDX-AUTO-ESC",
        raw_metadata={"customer_tier": "VIP", "hourly_penalty_rate": 300.0},
        cargo_items=[CargoItem(id=uuid.uuid4(), description="Microchips", declared_value=50000.0, quantity=1)],
        transport_mode="AIR",
    )
    exception = ShipmentException(
        id=exception_id,
        shipment_id=shipment_id,
        exception_type=ExceptionType.TEMPERATURE_EXCURSION.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.OPEN.value,
        title="High loss excursion",
        description="Temp excursion description",
        is_sla_breached=True,
        metadata_payload={"delay_minutes": 600},  # 10 hours delay
    )

    # Mock repositories
    service.exception_repo.get_by_id = AsyncMock(return_value=exception)
    service.shipment_repo.get_by_id = AsyncMock(return_value=shipment)
    service.impact_repo.create = AsyncMock(side_effect=lambda a: a)
    service.exception_service.escalate_exception = AsyncMock()

    request = ImpactAssessRequest(auto_escalate_threshold=70.0)
    result = await service.assess_exception_impact(exception_id, request=request)

    assert result.composite_score >= 70.0
    assert result.is_auto_escalated is True
    assert "Automated risk escalation" in result.escalation_reason
    assert result.financial_impact > 10000.0
    # Verified that escalate_exception was triggered
    service.exception_service.escalate_exception.assert_awaited_once()


@pytest.mark.asyncio
async def test_assess_nonexistent_exception_raises_error(mock_session):
    """Verify entity not found exception raised when exception does not exist."""
    service = ImpactService(mock_session)
    service.exception_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(EntityNotFoundException):
        await service.assess_exception_impact(uuid.uuid4())
