"""Pydantic Request and Response Schemas for Notification & Alerting Engine."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.modules.notifications.models import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)


class NotificationCreateRequest(BaseModel):
    """Payload to create or dispatch an operational notification."""

    recipient_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Target user UUID (null for broadcast to all operators)",
    )
    recipient_email: Optional[str] = Field(
        default=None,
        description="Optional explicit recipient email address",
    )
    channel: NotificationChannel = Field(
        default=NotificationChannel.IN_APP,
        description="Delivery mechanism",
    )
    priority: NotificationPriority = Field(
        default=NotificationPriority.MEDIUM,
        description="Alert urgency",
    )
    title: str = Field(..., min_length=2, max_length=255, description="Notification summary headline")
    message: str = Field(..., min_length=2, description="Full notification message narrative")
    entity_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Correlated business entity (e.g. EXCEPTION, RECOVERY, SHIPMENT)",
    )
    entity_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Correlated business entity UUID",
    )
    metadata_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary action links and context variables",
    )


class NotificationResponse(BaseModel):
    """Operational representation of a delivered notification."""

    id: uuid.UUID
    recipient_id: Optional[uuid.UUID] = None
    recipient_email: Optional[str] = None
    channel: str
    priority: str
    title: str
    message: str
    status: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    metadata_payload: Dict[str, Any] = {}
    sent_at: datetime
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceUpdateRequest(BaseModel):
    """Payload to configure delivery channels and priority filtering."""

    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    min_priority: Optional[NotificationPriority] = None


class NotificationPreferenceResponse(BaseModel):
    """User delivery channel preferences."""

    id: uuid.UUID
    user_id: uuid.UUID
    in_app_enabled: bool
    email_enabled: bool
    webhook_enabled: bool
    webhook_url: Optional[str] = None
    min_priority: str

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotificationResponse(BaseModel):
    """Paginated notification feed with unread count indicator."""

    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int
