"""Unit tests for Real-Time WebSocket Connection Manager and Event Broadcaster."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.modules.realtime.broadcaster import Broadcaster
from app.modules.realtime.connection_manager import ConnectionManager
from app.modules.realtime.schemas import (
    CHANNEL_ALERTS_ALL,
    CHANNEL_AUDIT_LIVE,
    CHANNEL_TELEMETRY_ALL,
    EVENT_EXCEPTION_TRIGGERED,
    EVENT_TELEMETRY_RECORDED,
    RealtimeEvent,
)


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    return ws


@pytest.mark.asyncio
async def test_connection_manager_connect_and_auto_subscribe(mock_ws):
    manager = ConnectionManager()
    user_info = {
        "sub": "user-uuid-1",
        "email": "operator@logistics.com",
        "roles": ["Operations Manager"],
    }

    await manager.connect(mock_ws, user_info)

    mock_ws.accept.assert_awaited_once()
    assert manager.active_connections_count == 1
    stats = manager.get_stats()
    assert stats["active_connections_count"] == 1
    assert CHANNEL_ALERTS_ALL in stats["channels"]
    assert CHANNEL_TELEMETRY_ALL in stats["channels"]
    # Operations manager should not be auto-subscribed to audit:live
    assert CHANNEL_AUDIT_LIVE not in stats["channels"]


@pytest.mark.asyncio
async def test_connection_manager_admin_auto_subscribe_audit(mock_ws):
    manager = ConnectionManager()
    admin_info = {
        "sub": "admin-uuid-1",
        "email": "admin@controltower.com",
        "roles": ["System Administrator"],
    }

    await manager.connect(mock_ws, admin_info)
    stats = manager.get_stats()
    assert CHANNEL_AUDIT_LIVE in stats["channels"]


@pytest.mark.asyncio
async def test_connection_manager_subscribe_and_unsubscribe(mock_ws):
    manager = ConnectionManager()
    user_info = {"sub": "user-1", "email": "test@test.com", "roles": []}
    await manager.connect(mock_ws, user_info)

    test_channel = "telemetry:SHP-001"
    await manager.subscribe(mock_ws, test_channel)
    assert test_channel in manager.get_stats()["channels"]

    await manager.unsubscribe(mock_ws, test_channel)
    assert test_channel not in manager.get_stats()["channels"]


@pytest.mark.asyncio
async def test_connection_manager_broadcast_to_channel(mock_ws):
    manager = ConnectionManager()
    await manager.connect(mock_ws, {"sub": "user-1", "email": "u1@test.com", "roles": []})

    msg = {"event_type": "TEST_EVENT", "data": "hello"}
    sent = await manager.broadcast_to_channel(CHANNEL_ALERTS_ALL, msg)

    assert sent == 1
    mock_ws.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_connection_manager_broadcast_to_user():
    manager = ConnectionManager()
    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()
    ws1.client.host = "127.0.0.1"

    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()
    ws2.client.host = "127.0.0.1"

    await manager.connect(ws1, {"sub": "user-target", "email": "target@test.com", "roles": []})
    await manager.connect(ws2, {"sub": "user-other", "email": "other@test.com", "roles": []})

    msg = {"event_type": "DIRECT_MSG", "content": "secret"}
    sent = await manager.broadcast_to_user("user-target", msg)

    assert sent == 1
    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_connection_manager_handles_failing_socket():
    manager = ConnectionManager()
    failing_ws = MagicMock()
    failing_ws.accept = AsyncMock()
    failing_ws.send_json = AsyncMock(side_effect=RuntimeError("Broken pipe"))
    failing_ws.client.host = "127.0.0.1"

    await manager.connect(failing_ws, {"sub": "user-1", "email": "fail@test.com", "roles": []})
    assert manager.active_connections_count == 1

    # Broadcast should catch the exception and cleanup the dead socket
    sent = await manager.broadcast_to_channel(CHANNEL_ALERTS_ALL, {"test": 1})
    assert sent == 0
    assert manager.active_connections_count == 0


@pytest.mark.asyncio
async def test_broadcaster_publishes_event(mock_ws):
    manager = ConnectionManager()
    await manager.connect(mock_ws, {"sub": "user-1", "email": "b@test.com", "roles": []})

    broadcaster = Broadcaster(manager=manager)
    sent = await broadcaster.broadcast_event(
        channel=CHANNEL_ALERTS_ALL,
        event_type=EVENT_EXCEPTION_TRIGGERED,
        payload={"exception_id": "exc-123", "severity": "CRITICAL"},
    )

    assert sent == 1
    mock_ws.send_json.assert_awaited_once()
    call_args = mock_ws.send_json.await_args[0][0]
    assert call_args["event_type"] == EVENT_EXCEPTION_TRIGGERED
    assert call_args["channel"] == CHANNEL_ALERTS_ALL
    assert call_args["payload"]["severity"] == "CRITICAL"
