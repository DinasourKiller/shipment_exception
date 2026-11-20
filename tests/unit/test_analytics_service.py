"""Unit Tests for Analytics, Reporting & Trend Engine Service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.modules.analytics.service import AnalyticsService
from app.modules.exceptions.models import ExceptionSeverity, ExceptionStatus, ExceptionType, ShipmentException
from app.modules.shipments.models import Shipment


@pytest.fixture
def mock_session():
    """Mock async SQLAlchemy session."""
    session = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_carrier_performance_score_and_grades(mock_session):
    """Verify carrier scorecard calculates on-time rate, exception rate, composite score, and grade."""
    service = AnalyticsService(mock_session)
    mock_data = [
        {
            "carrier_code": "APEX",
            "carrier_name": "Apex Logistics",
            "total_shipments": 20,
            "on_time_count": 19,
            "exceptions_count": 1,
            "avg_recovery_hours": 2.0,
        },
        {
            "carrier_code": "SLOW",
            "carrier_name": "Slow Freight Inc",
            "total_shipments": 10,
            "on_time_count": 4,
            "exceptions_count": 6,
            "avg_recovery_hours": 9.0,
        },
    ]
    service.repository.get_carrier_scorecard_data = AsyncMock(return_value=mock_data)

    response = await service.get_carrier_performance()
    assert response.total_carriers == 2

    # High performing carrier
    apex = next(c for c in response.carriers if c.carrier_code == "APEX")
    assert apex.exception_rate_pct == 5.0
    assert apex.on_time_delivery_pct == 95.0
    assert apex.performance_score >= 90.0
    assert apex.rating_grade == "A"

    # Underperforming carrier
    slow = next(c for c in response.carriers if c.carrier_code == "SLOW")
    assert slow.exception_rate_pct == 60.0
    assert slow.on_time_delivery_pct == 40.0
    assert slow.performance_score < 65.0
    assert slow.rating_grade in ("C", "D")


@pytest.mark.asyncio
async def test_get_root_cause_distribution_pareto(mock_session):
    """Verify root cause distribution calculates percentage weights and most frequent type."""
    service = AnalyticsService(mock_session)
    mock_items = [
        {"exception_type": "DELAY", "count": 15, "total_loss": 4500.0},
        {"exception_type": "TEMPERATURE_EXCURSION", "count": 5, "total_loss": 25000.0},
    ]
    service.repository.get_root_cause_distribution_data = AsyncMock(return_value=mock_items)

    response = await service.get_root_cause_distribution()
    assert response.total_exceptions == 20
    assert response.most_frequent_type == "DELAY"
    assert response.items[0].percentage == 75.0
    assert response.items[1].percentage == 25.0
    assert response.items[1].total_financial_loss_usd == 25000.0


@pytest.mark.asyncio
async def test_get_sla_compliance_percentages(mock_session):
    """Verify SLA compliance calculation formula."""
    service = AnalyticsService(mock_session)
    mock_data = {
        "total_exceptions": 20,
        "breached_count": 3,
        "resolved_within_sla": 15,
        "critical_adherent": 4,
        "critical_total": 5,
    }
    service.repository.get_sla_compliance_data = AsyncMock(return_value=mock_data)

    metric = await service.get_sla_compliance()
    assert metric.total_exceptions == 20
    assert metric.breached_sla == 3
    # Compliance rate: (20 - 3) / 20 = 85.0%
    assert metric.compliance_rate_pct == 85.0
    # Critical compliance rate: 4 / 5 = 80.0%
    assert metric.critical_compliance_rate_pct == 80.0


@pytest.mark.asyncio
async def test_get_financial_exposure_summary(mock_session):
    """Verify financial exposure metrics mapping."""
    service = AnalyticsService(mock_session)
    mock_data = {
        "assessments_count": 8,
        "total_exposure_usd": 42500.0,
        "delay_costs_usd": 7500.0,
        "cargo_damage_usd": 30000.0,
        "contractual_penalties_usd": 5000.0,
        "auto_escalated_exposure_usd": 35000.0,
    }
    service.repository.get_financial_exposure_data = AsyncMock(return_value=mock_data)

    result = await service.get_financial_exposure()
    assert result.assessments_count == 8
    assert result.total_exposure_usd == 42500.0
    assert result.cargo_damage_usd == 30000.0


@pytest.mark.asyncio
async def test_generate_exceptions_csv(mock_session):
    """Verify CSV export compiles valid CSV text with headers and row values."""
    service = AnalyticsService(mock_session)

    shipment = Shipment(
        id=uuid.uuid4(),
        external_reference="MDX-CSV-100",
        order_number="ORD-991",
        carrier_code="APEX",
        carrier_name="Apex Logistics",
        transport_mode="ROAD",
        origin_city="Chicago",
        destination_city="Dallas",
    )
    exception = ShipmentException(
        id=uuid.uuid4(),
        shipment_id=shipment.id,
        exception_type=ExceptionType.DELAY.value,
        severity=ExceptionSeverity.HIGH.value,
        status=ExceptionStatus.RESOLVED.value,
        title="Traffic Gridlock",
        is_sla_breached=False,
    )

    service.repository.get_exceptions_for_export = AsyncMock(return_value=[(exception, shipment)])

    csv_text = await service.generate_exceptions_csv()
    assert "Exception_ID,Shipment_Ref,Order_Number" in csv_text
    assert "MDX-CSV-100" in csv_text
    assert "APEX" in csv_text
    assert "DELAY" in csv_text
    assert "HIGH" in csv_text
