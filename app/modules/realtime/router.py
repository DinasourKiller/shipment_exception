"""Real-Time Streaming WebSocket and Event Broadcast Router."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.common.schemas import ApiResponse
from app.core.exceptions import UnauthorizedException
from app.core.jwt import decode_access_token
from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.realtime.broadcaster import broadcaster
from app.modules.realtime.connection_manager import connection_manager
from app.modules.realtime.schemas import (
    CHANNEL_ALERTS_ALL,
    CHANNEL_TELEMETRY_ALL,
    EVENT_PONG,
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SYSTEM_ALERT,
    EVENT_TELEMETRY_RECORDED,
    SimulateTelemetryRequest,
    SystemAlertBroadcastRequest,
)

logger = get_logger("control_tower.realtime.router")

router = APIRouter(prefix="/ws", tags=["Real-Time Streaming"])


@router.websocket("/stream")
@router.websocket("/ws")
@router.websocket("")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
) -> None:
    """Authenticated WebSocket stream delivering real-time telemetry, alerts, and state events.

    Clients must authenticate by providing a valid JWT Bearer token in the `?token=` query parameter.
    """
    # 1. Authenticate connection handshake
    auth_token = token
    if not auth_token:
        # Check Sec-WebSocket-Protocol or Authorization header if provided
        headers = dict(websocket.headers)
        auth_header = headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ", 1)[1]

    if not auth_token:
        logger.warning("WebSocket connection rejected: missing authentication token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    try:
        token_payload = decode_access_token(auth_token)
    except UnauthorizedException as exc:
        logger.warning("WebSocket authentication failed: %s", exc.message)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return
    except Exception as exc:
        logger.error("Unexpected error validating WebSocket token: %s", exc)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token invalid")
        return

    # 2. Accept and bind to multi-channel pub/sub
    await connection_manager.connect(websocket, token_payload)

    # Send initial connection handshake confirmation
    user_email = token_payload.get("email", "unknown")
    roles = token_payload.get("roles", [])
    initial_frame = {
        "event_type": "CONNECTED",
        "channel": "system",
        "payload": {
            "message": "Connected to Shipment Exception Control Tower Real-Time Stream",
            "user": user_email,
            "roles": roles,
            "subscribed_channels": [CHANNEL_ALERTS_ALL, CHANNEL_TELEMETRY_ALL],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": None,
    }
    await websocket.send_json(initial_frame)

    # 3. Message loop handling client commands
    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                continue

            action = data.get("action")

            if action == "ping":
                await websocket.send_json({
                    "event_type": EVENT_PONG,
                    "channel": "system",
                    "payload": {
                        "client_timestamp": data.get("timestamp"),
                        "server_timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": data.get("correlation_id"),
                })

            elif action == "subscribe":
                channel = data.get("channel")
                if channel and isinstance(channel, str):
                    await connection_manager.subscribe(websocket, channel)
                    await websocket.send_json({
                        "event_type": EVENT_SUBSCRIPTION_CONFIRMED,
                        "channel": channel,
                        "payload": {"status": "subscribed", "channel": channel},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": data.get("correlation_id"),
                    })

            elif action == "unsubscribe":
                channel = data.get("channel")
                if channel and isinstance(channel, str):
                    await connection_manager.unsubscribe(websocket, channel)

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception as exc:
        logger.debug("WebSocket session ended: %s", exc)
        await connection_manager.disconnect(websocket)


@router.get("/status", response_model=ApiResponse[Dict[str, Any]])
async def get_stream_status(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[Dict[str, Any]]:
    """Retrieve diagnostic statistics on active WebSocket connections and channel subscriptions."""
    stats = connection_manager.get_stats()
    return ApiResponse(
        success=True,
        data=stats,
        message="Real-time streaming status retrieved.",
    )


@router.post("/simulate/telemetry", response_model=ApiResponse[Dict[str, Any]])
async def simulate_telemetry_event(
    body: SimulateTelemetryRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[Dict[str, Any]]:
    """Inject a synthetic real-time telemetry breadcrumb and broadcast to active subscribers.

    Emits `TELEMETRY_RECORDED` to both `telemetry:{shipment_id}` and `telemetry:all`.
    """
    telemetry_payload = {
        "shipment_id": body.shipment_id,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "speed_mph": body.speed_mph,
        "temperature_c": body.temperature_c,
        "battery_pct": body.battery_pct,
        "status_note": body.status_note,
        "simulated_by": current_user.email,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    # Broadcast to shipment-specific channel and global telemetry channel
    recipients_specific = await broadcaster.broadcast_event(
        channel=f"telemetry:{body.shipment_id}",
        event_type=EVENT_TELEMETRY_RECORDED,
        payload=telemetry_payload,
    )
    recipients_all = await broadcaster.broadcast_event(
        channel=CHANNEL_TELEMETRY_ALL,
        event_type=EVENT_TELEMETRY_RECORDED,
        payload=telemetry_payload,
    )

    return ApiResponse(
        success=True,
        data={
            "telemetry": telemetry_payload,
            "dispatched_recipients": recipients_specific + recipients_all,
        },
        message="Simulated telemetry frame broadcasted successfully.",
    )


@router.post("/broadcast/alert", response_model=ApiResponse[Dict[str, Any]])
async def broadcast_system_alert(
    body: SystemAlertBroadcastRequest,
    current_user: User = Depends(require_roles("System Administrator", "Operations Manager")),
) -> ApiResponse[Dict[str, Any]]:
    """Broadcast an urgent operational banner or toast alert across all connected client consoles."""
    alert_payload = {
        "severity": body.severity,
        "title": body.title,
        "message": body.message,
        "broadcast_by": current_user.email,
        "broadcast_at": datetime.now(timezone.utc).isoformat(),
    }

    recipients = await broadcaster.broadcast_event(
        channel=CHANNEL_ALERTS_ALL,
        event_type=EVENT_SYSTEM_ALERT,
        payload=alert_payload,
    )

    return ApiResponse(
        success=True,
        data={
            "alert": alert_payload,
            "recipients_count": recipients,
        },
        message=f"System alert broadcasted to {recipients} active subscriber(s).",
    )
