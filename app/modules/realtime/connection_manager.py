"""WebSocket Connection Manager and Multi-Channel Pub/Sub Hub.

Manages persistent client sessions, channel subscriptions, authentication contexts,
and thread-safe async broadcasting across operational rooms.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, status

from app.core.logging import get_logger
from app.modules.realtime.schemas import (
    CHANNEL_ALERTS_ALL,
    CHANNEL_AUDIT_LIVE,
    CHANNEL_TELEMETRY_ALL,
)

logger = get_logger("control_tower.realtime.manager")


class ConnectionManager:
    """In-memory pub/sub connection hub and subscription router."""

    def __init__(self) -> None:
        # Mapping: websocket -> client_info dict
        self._active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        # Mapping: channel_name -> Set[WebSocket]
        self._subscriptions: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        return len(self._active_connections)

    async def connect(
        self, websocket: WebSocket, user_info: Dict[str, Any]
    ) -> None:
        """Accept WebSocket handshake and register client session."""
        await websocket.accept()
        async with self._lock:
            self._active_connections[websocket] = {
                "user_id": user_info.get("sub"),
                "email": user_info.get("email"),
                "roles": user_info.get("roles", []),
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "client_ip": websocket.client.host if websocket.client else "unknown",
            }
            # Automatically subscribe to standard global channels
            self._add_subscription_unsafe(websocket, CHANNEL_ALERTS_ALL)
            self._add_subscription_unsafe(websocket, CHANNEL_TELEMETRY_ALL)

            # Auto-subscribe Admins and Auditors to live audit trail
            roles = user_info.get("roles", [])
            if any(r in ["System Administrator", "Compliance Auditor"] for r in roles):
                self._add_subscription_unsafe(websocket, CHANNEL_AUDIT_LIVE)

        logger.info(
            "WebSocket connected: user=%s, ip=%s, active_clients=%d",
            user_info.get("email"),
            websocket.client.host if websocket.client else "unknown",
            len(self._active_connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister client and cleanup all channel bindings."""
        async with self._lock:
            user_info = self._active_connections.pop(websocket, None)
            # Remove from all subscriptions
            for channel, subscribers in list(self._subscriptions.items()):
                subscribers.discard(websocket)
                if not subscribers:
                    self._subscriptions.pop(channel, None)

        user_email = user_info.get("email") if user_info else "anonymous"
        logger.info(
            "WebSocket disconnected: user=%s, remaining_clients=%d",
            user_email,
            len(self._active_connections),
        )

    def _add_subscription_unsafe(self, websocket: WebSocket, channel: str) -> None:
        """Internal helper to add socket to channel without acquiring lock."""
        if channel not in self._subscriptions:
            self._subscriptions[channel] = set()
        self._subscriptions[channel].add(websocket)

    async def subscribe(self, websocket: WebSocket, channel: str) -> None:
        """Subscribe client socket to a specific topic or shipment room."""
        async with self._lock:
            if websocket in self._active_connections:
                self._add_subscription_unsafe(websocket, channel)
                logger.debug(
                    "Client subscribed: user=%s, channel=%s",
                    self._active_connections[websocket].get("email"),
                    channel,
                )

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> None:
        """Unsubscribe client socket from a specific topic."""
        async with self._lock:
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(websocket)
                if not self._subscriptions[channel]:
                    self._subscriptions.pop(channel, None)

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]) -> int:
        """Broadcast event to all subscribers of a specific channel."""
        subscribers: List[WebSocket] = []
        async with self._lock:
            if channel in self._subscriptions:
                subscribers = list(self._subscriptions[channel])

        if not subscribers:
            return 0

        failed_sockets: List[WebSocket] = []
        sent_count = 0

        for ws in subscribers:
            try:
                await ws.send_json(message)
                sent_count += 1
            except Exception as exc:
                logger.warning("Failed to send message to websocket, queueing disconnect: %s", exc)
                failed_sockets.append(ws)

        if failed_sockets:
            for ws in failed_sockets:
                await self.disconnect(ws)

        return sent_count

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """Broadcast message to all active sockets belonging to a specific user ID."""
        target_sockets: List[WebSocket] = []
        async with self._lock:
            for ws, meta in self._active_connections.items():
                if str(meta.get("user_id")) == str(user_id):
                    target_sockets.append(ws)

        sent_count = 0
        for ws in target_sockets:
            try:
                await ws.send_json(message)
                sent_count += 1
            except Exception:
                await self.disconnect(ws)
        return sent_count

    async def broadcast_to_all(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all connected clients regardless of subscription."""
        all_sockets: List[WebSocket] = []
        async with self._lock:
            all_sockets = list(self._active_connections.keys())

        sent_count = 0
        for ws in all_sockets:
            try:
                await ws.send_json(message)
                sent_count += 1
            except Exception:
                await self.disconnect(ws)
        return sent_count

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic statistics on active sessions and channel density."""
        return {
            "active_connections_count": len(self._active_connections),
            "channels_count": len(self._subscriptions),
            "channels": {
                ch: len(sockets) for ch, sockets in self._subscriptions.items()
            },
        }


# Global Manager Singleton
connection_manager = ConnectionManager()
