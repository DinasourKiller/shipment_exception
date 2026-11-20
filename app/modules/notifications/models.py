"""Notification & Alerting Database Models.

Defines PostgreSQL entities for user notification feeds, multi-channel dispatch logs,
and notification channel delivery preferences.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.authentication.models import User


class NotificationChannel(str, enum.Enum):
    """Delivery mechanism for operational notifications."""

    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    SMS = "SMS"


class NotificationPriority(str, enum.Enum):
    """Urgency level of notification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class NotificationStatus(str, enum.Enum):
    """Delivery lifecycle state of notification."""

    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    READ = "READ"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational alert / notification record for users and control tower operators."""

    __tablename__ = "notifications"

    recipient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="Recipient user UUID (null for broadcast)",
    )
    recipient_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Destination email address if applicable",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        default=NotificationChannel.IN_APP.value,
        nullable=False,
        comment="IN_APP, EMAIL, WEBHOOK, SMS",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        default=NotificationPriority.MEDIUM.value,
        index=True,
        nullable=False,
        comment="LOW, MEDIUM, HIGH, URGENT",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Brief notification headline",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full notification narrative",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=NotificationStatus.SENT.value,
        index=True,
        nullable=False,
        comment="PENDING, SENT, FAILED, READ",
    )

    # Correlated entity link
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Source entity type (EXCEPTION, RECOVERY, SHIPMENT)",
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Source entity UUID",
    )

    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Additional context, action links, and payload variables",
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    recipient: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[recipient_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_notifications_recipient_status", "recipient_id", "status"),
        Index("ix_notifications_entity", "entity_type", "entity_id"),
    )


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User delivery channel and severity thresholds."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    webhook_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    min_priority: Mapped[str] = mapped_column(
        String(20),
        default=NotificationPriority.LOW.value,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
