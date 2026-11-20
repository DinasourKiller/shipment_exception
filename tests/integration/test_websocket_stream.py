"""Integration Tests for Real-Time WebSocket Streaming & Operational Telemetry."""

import uuid
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.roles.repository import RoleRepository


@pytest.fixture
async def realtime_test_user():
    """Create a persistent System Administrator in the test database."""
    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        user = User(
            email=f"ws_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("WsPass123!"),
            full_name="WebSocket Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(user)

        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(user.id, admin_role.id)

        await session.commit()

        token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=["System Administrator"],
        )
        return {"user": user, "token": token}


def test_websocket_missing_token_rejected(client):
    """Clients connecting without an authentication token must be rejected with 1008."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/stream"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_invalid_token_rejected(client):
    """Clients connecting with a malformed/invalid token must be rejected with 1008."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/stream?token=invalid.jwt.token"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_connection_and_handshake(client):
    """Authenticated client receives initial CONNECTED frame and can ping/pong."""
    token = create_access_token(
        user_id=uuid.uuid4(),
        email="operator@test.local",
        roles=["Operations Manager"],
    )

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as websocket:
        # 1. Receive initial welcome frame
        connected_frame = websocket.receive_json()
        assert connected_frame["event_type"] == "CONNECTED"
        assert connected_frame["payload"]["user"] == "operator@test.local"
        assert "alerts:all" in connected_frame["payload"]["subscribed_channels"]

        # 2. Ping-pong handshake
        websocket.send_json({"action": "ping", "timestamp": "2026-11-20T12:00:00Z"})
        pong_frame = websocket.receive_json()
        assert pong_frame["event_type"] == "PONG"
        assert pong_frame["payload"]["client_timestamp"] == "2026-11-20T12:00:00Z"


def test_websocket_channel_subscription(client):
    """Client can subscribe to topic-specific channels and receive confirmation."""
    token = create_access_token(
        user_id=uuid.uuid4(),
        email="auditor@test.local",
        roles=["Compliance Auditor"],
    )

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as websocket:
        # Drain initial welcome
        _ = websocket.receive_json()

        # Subscribe to custom shipment room
        custom_topic = "telemetry:SHP-9999"
        websocket.send_json({"action": "subscribe", "channel": custom_topic})
        sub_frame = websocket.receive_json()
        assert sub_frame["event_type"] == "SUBSCRIPTION_CONFIRMED"
        assert sub_frame["channel"] == custom_topic


@pytest.mark.asyncio
async def test_simulated_telemetry_broadcast_to_websocket(client, realtime_test_user):
    """Simulated telemetry POST triggers live WebSocket frame to connected clients."""
    token = realtime_test_user["token"]

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as websocket:
        # Drain initial connect frame
        _ = websocket.receive_json()

        # Inject simulated telemetry via HTTP POST
        response = client.post(
            "/api/v1/ws/simulate/telemetry",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "shipment_id": "SHP-SIM-001",
                "latitude": 41.8781,
                "longitude": -87.6298,
                "speed_mph": 62.5,
                "temperature_c": -18.2,
                "battery_pct": 94.0,
                "status_note": "Cold chain optimal",
            },
        )
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["success"] is True

        # Client should receive TELEMETRY_RECORDED on telemetry:all
        event_frame = websocket.receive_json()
        assert event_frame["event_type"] == "TELEMETRY_RECORDED"
        assert event_frame["payload"]["shipment_id"] == "SHP-SIM-001"
        assert event_frame["payload"]["latitude"] == 41.8781
        assert event_frame["payload"]["temperature_c"] == -18.2


@pytest.mark.asyncio
async def test_system_alert_broadcast_to_websocket(client, realtime_test_user):
    """System alert POST triggers live alert notification frame on alerts:all."""
    admin_token = realtime_test_user["token"]

    with client.websocket_connect(f"/api/v1/ws/stream?token={admin_token}") as websocket:
        _ = websocket.receive_json()

        response = client.post(
            "/api/v1/ws/broadcast/alert",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "severity": "CRITICAL",
                "title": "Severe Weather Warning",
                "message": "Blizzard in Midwest Hub. Expect ground delays.",
            },
        )
        assert response.status_code == 200

        alert_frame = websocket.receive_json()
        assert alert_frame["event_type"] == "SYSTEM_ALERT"
        assert alert_frame["payload"]["severity"] == "CRITICAL"
        assert alert_frame["payload"]["title"] == "Severe Weather Warning"


@pytest.mark.asyncio
async def test_stream_status_endpoint(client, realtime_test_user):
    """GET /api/v1/ws/status returns connection diagnostics."""
    token = realtime_test_user["token"]

    response = client.get(
        "/api/v1/ws/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "active_connections_count" in data
    assert "channels_count" in data
    assert "channels" in data
