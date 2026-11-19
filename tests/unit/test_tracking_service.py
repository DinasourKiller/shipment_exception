"""Unit Tests for Tracking & Milestones Business Logic and ETA Engine."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import ValidationException
from app.modules.shipments.models import Shipment, ShipmentMilestone
from app.modules.tracking.schemas import TrackingEventCreateRequest
from app.modules.tracking.service import TrackingService


@pytest.mark.asyncio
async def test_recalculate_eta_when_on_schedule():
    """Verify recalculate_eta maintains original ETA when milestones are on schedule."""
    shipment_id = uuid.uuid4()
    original_eta = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
    shipment = Shipment(id=shipment_id, estimated_delivery=original_eta)

    # Completed milestone on time (0 delay)
    planned = datetime(2026, 11, 19, 8, 0, 0, tzinfo=timezone.utc)
    actual = datetime(2026, 11, 19, 8, 5, 0, tzinfo=timezone.utc)  # only 5 min difference, within 15m tolerance
    milestone = ShipmentMilestone(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        event_code="PICKUP_COMPLETED",
        planned_time=planned,
        actual_time=actual,
        status="COMPLETED",
    )

    mock_shipment_repo = MagicMock()
    mock_shipment_repo.get_by_id = AsyncMock(return_value=shipment)

    mock_tracking_repo = MagicMock()
    mock_tracking_repo.get_milestones_for_shipment = AsyncMock(return_value=[milestone])
    mock_tracking_repo.update_shipment_estimated_delivery = AsyncMock()

    service = TrackingService(tracking_repo=mock_tracking_repo, shipment_repo=mock_shipment_repo)
    result = await service.recalculate_eta(shipment_id)

    assert result.is_delayed is False
    assert result.accumulated_delay_minutes <= 15
    assert result.updated_estimated_delivery == original_eta
    mock_tracking_repo.update_shipment_estimated_delivery.assert_not_called()


@pytest.mark.asyncio
async def test_recalculate_eta_when_delayed_projects_new_delivery_time():
    """Verify recalculate_eta projects forward delay delta onto estimated_delivery."""
    shipment_id = uuid.uuid4()
    original_eta = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
    shipment = Shipment(id=shipment_id, estimated_delivery=original_eta)

    # Completed milestone delayed by 120 minutes (2 hours)
    planned = datetime(2026, 11, 19, 8, 0, 0, tzinfo=timezone.utc)
    actual = datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc)  # 120 minutes late
    milestone = ShipmentMilestone(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        event_code="HUB_TRANSIT",
        planned_time=planned,
        actual_time=actual,
        status="COMPLETED",
    )

    mock_shipment_repo = MagicMock()
    mock_shipment_repo.get_by_id = AsyncMock(return_value=shipment)

    mock_tracking_repo = MagicMock()
    mock_tracking_repo.get_milestones_for_shipment = AsyncMock(return_value=[milestone])
    mock_tracking_repo.update_shipment_estimated_delivery = AsyncMock()

    service = TrackingService(tracking_repo=mock_tracking_repo, shipment_repo=mock_shipment_repo)
    result = await service.recalculate_eta(shipment_id)

    assert result.is_delayed is True
    assert result.accumulated_delay_minutes == 120
    expected_new_eta = original_eta + timedelta(minutes=120)
    assert result.updated_estimated_delivery == expected_new_eta
    mock_tracking_repo.update_shipment_estimated_delivery.assert_called_once_with(shipment_id, expected_new_eta)


@pytest.mark.asyncio
async def test_update_milestone_status_rejects_invalid_status():
    """Verify milestone status update rejects unsupported status values."""
    mock_tracking_repo = MagicMock()
    mock_tracking_repo.get_milestone_by_id = AsyncMock(return_value=ShipmentMilestone(id=uuid.uuid4()))

    service = TrackingService(tracking_repo=mock_tracking_repo, shipment_repo=MagicMock())

    from app.modules.tracking.schemas import MilestoneUpdateRequest
    req = MilestoneUpdateRequest(status="NOT_A_REAL_STATUS")

    with pytest.raises(ValidationException) as exc_info:
        await service.update_milestone_status(uuid.uuid4(), req)

    assert "Invalid milestone status 'NOT_A_REAL_STATUS'" in str(exc_info.value)
