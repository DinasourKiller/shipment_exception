"""Event Broadcaster utility for publishing real-time telemetry and operational alerts.

Provides decoupled publishing methods usable across services and background tasks.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.modules.realtime.connection_manager import connection_manager
from app.modules.realtime.schemas import RealtimeEvent

logger = get_logger("control_tower.realtime.broadcaster")


class Broadcaster:
    """Publishing gateway routing events to connected WebSocket clients."""

    def __init__(self, manager=connection_manager) -> None:
        self.manager = manager

    async def broadcast_event(
        self,
        channel: str,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> int:
        """Construct a standardized event frame and dispatch to channel subscribers."""
        event = RealtimeEvent(
            event_type=event_type,
            channel=channel,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
        )
        msg_dict = event.model_dump()
        try:
            sent = await self.manager.broadcast_to_channel(channel, msg_dict)
            logger.debug(
                "Broadcasted event %s to channel %s (recipients: %d)",
                event_type,
                channel,
                sent,
            )
            return sent
        except Exception as exc:
            logger.error("Failed to broadcast event %s to %s: %s", event_type, channel, exc)
            return 0

    def publish_nowait(
        self,
        channel: str,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        """Fire-and-forget publishing helper that schedules broadcast without blocking."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self.broadcast_event(
                    channel=channel,
                    event_type=event_type,
                    payload=payload,
                    correlation_id=correlation_id,
                )
            )
        except RuntimeError:
            logger.debug("No running asyncio event loop; skipped live broadcast for %s", event_type)


# Global Broadcaster Singleton
broadcaster = Broadcaster()
