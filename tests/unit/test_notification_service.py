"""Unit Tests for Notification & Alerting Engine Service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import EntityNotFoundException
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationPriority,
    NotificationStatus,
)
from app.modules.notifications.schemas import (
    NotificationCreateRequest,
    NotificationPreferenceUpdateRequest,
)
from app.modules.notifications.service import NotificationService


@pytest.fixture
def mock_session():
    """Mock async SQLAlchemy session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_send_notification(mock_session):
    """Verify sending direct user notification."""
    service = NotificationService(mock_session)
    user_id = uuid.uuid4()

    pref = NotificationPreference(
        id=uuid.uuid4(),
        user_id=user_id,
        in_app_enabled=True,
        email_enabled=True,
    )
    service.repository.get_or_create_preference = AsyncMock(return_value=pref)
    service.repository.create = AsyncMock(side_effect=lambda n: n)

    req = NotificationCreateRequest(
        recipient_id=user_id,
        channel=NotificationChannel.IN_APP,
        priority=NotificationPriority.HIGH,
        title="Test Alert",
        message="Vehicle delay reported",
    )

    result = await service.send_notification(req)
    assert result.title == "Test Alert"
    assert result.priority == "HIGH"
    assert result.status == "SENT"
    assert result.recipient_id == user_id


@pytest.mark.asyncio
async def test_trigger_exception_alert(mock_session):
    """Verify automated trigger formats exception alert properly."""
    service = NotificationService(mock_session)
    service.repository.get_or_create_preference = AsyncMock(return_value=MagicMock(in_app_enabled=True))
    service.repository.create = AsyncMock(side_effect=lambda n: n)

    exception_id = uuid.uuid4()
    alert = await service.trigger_exception_alert(
        exception_id=exception_id,
        title="Reefer Temp Spike",
        severity="CRITICAL",
        shipment_ref="MDX-SHP-1002",
    )
    assert alert.priority == "URGENT"
    assert "🚨 New Exception" in alert.title
    assert alert.entity_type == "EXCEPTION"
    assert alert.entity_id == exception_id


@pytest.mark.asyncio
async def test_trigger_sla_breach_alert(mock_session):
    """Verify automated trigger formats SLA breach alert."""
    service = NotificationService(mock_session)
    service.repository.get_or_create_preference = AsyncMock(return_value=MagicMock(in_app_enabled=True))
    service.repository.create = AsyncMock(side_effect=lambda n: n)

    exception_id = uuid.uuid4()
    alert = await service.trigger_sla_breach_alert(
        exception_id=exception_id,
        title="Delivery Overdue",
        shipment_ref="MDX-SHP-1001",
    )
    assert alert.priority == "URGENT"
    assert "⚠️ SLA BREACH" in alert.title
    assert alert.metadata_payload.get("sla_breached") is True


@pytest.mark.asyncio
async def test_trigger_impact_escalation_alert(mock_session):
    """Verify automated trigger formats Phase 10 impact escalation alert."""
    service = NotificationService(mock_session)
    service.repository.get_or_create_preference = AsyncMock(return_value=MagicMock(in_app_enabled=True))
    service.repository.create = AsyncMock(side_effect=lambda n: n)

    exception_id = uuid.uuid4()
    alert = await service.trigger_impact_escalation_alert(
        exception_id=exception_id,
        composite_score=84.5,
        financial_impact=18500.0,
    )
    assert "Auto-Escalation" in alert.title
    assert "84.5" in alert.title
    assert "$18,500.00" in alert.message


@pytest.mark.asyncio
async def test_trigger_recovery_dispatch_alert(mock_session):
    """Verify automated trigger formats Phase 11 recovery dispatch alert."""
    service = NotificationService(mock_session)
    service.repository.get_or_create_preference = AsyncMock(return_value=MagicMock(in_app_enabled=True))
    service.repository.create = AsyncMock(side_effect=lambda n: n)

    plan_id = uuid.uuid4()
    exception_id = uuid.uuid4()
    alert = await service.trigger_recovery_dispatch_alert(
        plan_id=plan_id,
        exception_id=exception_id,
        carrier_name="Apex Logistics",
        driver_name="Marcus Vance",
        vehicle_plate="IL-TX-7788",
    )
    assert alert.priority == "HIGH"
    assert "Recovery Resources Dispatched" in alert.title
    assert "Marcus Vance" in alert.message
    assert "IL-TX-7788" in alert.message


@pytest.mark.asyncio
async def test_mark_as_read(mock_session):
    """Verify marking notification as read updates status and timestamp."""
    service = NotificationService(mock_session)
    notif_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_notif = Notification(
        id=notif_id,
        recipient_id=user_id,
        title="Test",
        message="Msg",
        status="READ",
        read_at=datetime.now(timezone.utc),
    )
    service.repository.mark_as_read = AsyncMock(return_value=mock_notif)

    result = await service.mark_as_read(notif_id, user_id=user_id)
    assert result.status == "READ"
    assert result.read_at is not None


@pytest.mark.asyncio
async def test_update_user_preferences(mock_session):
    """Verify updating delivery channel preferences."""
    service = NotificationService(mock_session)
    user_id = uuid.uuid4()

    pref = NotificationPreference(
        id=uuid.uuid4(),
        user_id=user_id,
        in_app_enabled=True,
        email_enabled=True,
        webhook_enabled=False,
    )
    service.repository.get_or_create_preference = AsyncMock(return_value=pref)
    service.repository.update_preference = AsyncMock(side_effect=lambda p: p)

    update_req = NotificationPreferenceUpdateRequest(
        email_enabled=False,
        webhook_enabled=True,
        webhook_url="https://hooks.controltower.corp/alerts",
        min_priority=NotificationPriority.HIGH,
    )

    updated = await service.update_preferences(user_id, update_req)
    assert updated.email_enabled is False
    assert updated.webhook_enabled is True
    assert updated.webhook_url == "https://hooks.controltower.corp/alerts"
    assert updated.min_priority == "HIGH"
