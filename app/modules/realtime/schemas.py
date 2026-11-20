"""Real-Time Streaming Schemas and Event Protocol Contracts."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# Event Type Constants
EVENT_TELEMETRY_RECORDED = "TELEMETRY_RECORDED"
EVENT_EXCEPTION_TRIGGERED = "EXCEPTION_TRIGGERED"
EVENT_EXCEPTION_ESCALATED = "EXCEPTION_ESCALATED"
EVENT_EXCEPTION_RESOLVED = "EXCEPTION_RESOLVED"
EVENT_RECOVERY_DISPATCHED = "RECOVERY_DISPATCHED"
EVENT_AUDIT_LOG_RECORDED = "AUDIT_LOG_RECORDED"
EVENT_SYSTEM_ALERT = "SYSTEM_ALERT"
EVENT_PONG = "PONG"
EVENT_SUBSCRIPTION_CONFIRMED = "SUBSCRIPTION_CONFIRMED"

# Default Channels
CHANNEL_ALERTS_ALL = "alerts:all"
CHANNEL_TELEMETRY_ALL = "telemetry:all"
CHANNEL_AUDIT_LIVE = "audit:live"


class RealtimeEvent(BaseModel):
    """Payload contract for all events pushed over WebSockets."""

    event_type: str = Field(..., description="Categorical identifier for the event")
    channel: str = Field(..., description="Target pub/sub topic or stream channel")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific metadata and data payload")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of event generation",
    )
    correlation_id: Optional[str] = Field(default=None, description="Request or process correlation tracking ID")


class WebSocketClientCommand(BaseModel):
    """Client command frame sent from browser/client to server."""

    action: str = Field(..., description="Command verb: subscribe, unsubscribe, or ping")
    channel: Optional[str] = Field(default=None, description="Topic or channel to bind to or unbind from")


class SimulateTelemetryRequest(BaseModel):
    """Input payload to inject synthetic real-time telemetry breadcrumbs."""

    shipment_id: str = Field(..., description="Target shipment UUID or reference")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    speed_mph: Optional[float] = Field(default=55.0, ge=0.0, description="Instantaneous vehicle speed")
    temperature_c: Optional[float] = Field(default=4.2, description="Sensor ambient/cargo temperature in Celsius")
    battery_pct: Optional[float] = Field(default=98.0, ge=0.0, le=100.0, description="Sensor beacon battery level")
    status_note: Optional[str] = Field(default="Normal Highway Transit", description="Live carrier transit note")


class SystemAlertBroadcastRequest(BaseModel):
    """Payload to trigger a global system-wide operational banner."""

    severity: str = Field(default="WARNING", description="INFO, WARNING, CRITICAL, or URGENT")
    title: str = Field(..., description="Short headline for the alert toast")
    message: str = Field(..., description="Detailed message body")
