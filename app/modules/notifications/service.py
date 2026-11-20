"""Notification & Alerting Engine Service.

Orchestrates multi-channel alert delivery (in-app, email, webhook), user preference filtering,
automated operational trigger hooks for exceptions, and mark-as-read tracking.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationPriority,
    NotificationStatus,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import (
    NotificationCreateRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    PaginatedNotificationResponse,
)

logger = get_logger("control_tower.notifications.service")


class NotificationService:
    """Core domain service for notification dispatching and alert lifecycle management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = NotificationRepository(session)

    async def send_notification(self, request: NotificationCreateRequest) -> Notification:
        """Dispatches an operational notification checking recipient preferences."""
        # Preference check if user is targeted directly
        if request.recipient_id:
            pref = await self.repository.get_or_create_preference(request.recipient_id)
            if request.channel == NotificationChannel.IN_APP and not pref.in_app_enabled:
                logger.debug("In-app notifications disabled for user %s; skipping", request.recipient_id)
            if request.channel == NotificationChannel.EMAIL and not pref.email_enabled:
                logger.debug("Email notifications disabled for user %s; skipping", request.recipient_id)

        notification = Notification(
            id=uuid.uuid4(),
            recipient_id=request.recipient_id,
            recipient_email=request.recipient_email,
            channel=request.channel.value,
            priority=request.priority.value,
            title=request.title.strip(),
            message=request.message.strip(),
            status=NotificationStatus.SENT.value,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            metadata_payload=request.metadata_payload,
            sent_at=datetime.now(timezone.utc),
        )

        saved = await self.repository.create(notification)
        logger.info(
            "Dispatched notification %s: [%s] '%s' -> %s",
            saved.id,
            saved.priority,
            saved.title,
            saved.recipient_id or "BROADCAST",
        )
        return saved

    async def trigger_exception_alert(
        self,
        exception_id: uuid.UUID,
        title: str,
        severity: str,
        shipment_ref: Optional[str] = None,
        recipient_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Automated trigger when a critical or high exception is logged."""
        priority_map = {
            "CRITICAL": NotificationPriority.URGENT,
            "HIGH": NotificationPriority.HIGH,
            "MEDIUM": NotificationPriority.MEDIUM,
            "LOW": NotificationPriority.LOW,
        }
        priority = priority_map.get(severity, NotificationPriority.MEDIUM)

        ref_str = f" on shipment {shipment_ref}" if shipment_ref else ""
        return await self.send_notification(
            NotificationCreateRequest(
                recipient_id=recipient_id,
                channel=NotificationChannel.IN_APP,
                priority=priority,
                title=f"🚨 New Exception: {title}",
                message=f"Disruption detected{ref_str}. Urgency: {severity}.",
                entity_type="EXCEPTION",
                entity_id=exception_id,
                metadata_payload={"severity": severity, "shipment_ref": shipment_ref},
            )
        )

    async def trigger_sla_breach_alert(
        self,
        exception_id: uuid.UUID,
        title: str,
        shipment_ref: Optional[str] = None,
        recipient_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Automated trigger when an exception breaches resolution SLA."""
        return await self.send_notification(
            NotificationCreateRequest(
                recipient_id=recipient_id,
                channel=NotificationChannel.IN_APP,
                priority=NotificationPriority.URGENT,
                title=f"⚠️ SLA BREACH: {title}",
                message=f"Guaranteed resolution SLA expired for exception on {shipment_ref or 'shipment'}. Escalation required.",
                entity_type="EXCEPTION",
                entity_id=exception_id,
                metadata_payload={"sla_breached": True, "shipment_ref": shipment_ref},
            )
        )

    async def trigger_impact_escalation_alert(
        self,
        exception_id: uuid.UUID,
        composite_score: float,
        financial_impact: float,
        recipient_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Automated trigger when Phase 10 auto-escalates an exception."""
        return await self.send_notification(
            NotificationCreateRequest(
                recipient_id=recipient_id,
                channel=NotificationChannel.IN_APP,
                priority=NotificationPriority.URGENT,
                title=f"⚡ Auto-Escalation: Risk Score {composite_score:.1f}/100",
                message=f"Critical exposure detected: Total financial impact estimated at ${financial_impact:,.2f}.",
                entity_type="EXCEPTION",
                entity_id=exception_id,
                metadata_payload={"composite_score": composite_score, "financial_impact": financial_impact},
            )
        )

    async def trigger_recovery_dispatch_alert(
        self,
        plan_id: uuid.UUID,
        exception_id: uuid.UUID,
        carrier_name: str,
        driver_name: str,
        vehicle_plate: str,
        recipient_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Automated trigger when Phase 11 dispatches recovery resources."""
        return await self.send_notification(
            NotificationCreateRequest(
                recipient_id=recipient_id,
                channel=NotificationChannel.IN_APP,
                priority=NotificationPriority.HIGH,
                title="🚚 Recovery Resources Dispatched",
                message=f"{carrier_name} dispatched driver {driver_name} (Plate: {vehicle_plate}).",
                entity_type="RECOVERY",
                entity_id=plan_id,
                metadata_payload={"exception_id": str(exception_id), "driver": driver_name, "plate": vehicle_plate},
            )
        )

    async def list_user_notifications(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> PaginatedNotificationResponse:
        """Retrieve paginated notification feed for user with unread counter."""
        items, total, unread_count = await self.repository.list_for_user(
            user_id=user_id,
            page=page,
            page_size=page_size,
            status=status,
            channel=channel,
            priority=priority,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedNotificationResponse(
            items=[NotificationResponse.model_validate(n) for n in items],
            total=total,
            unread_count=unread_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def mark_as_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        """Mark a notification as read."""
        notification = await self.repository.mark_as_read(notification_id, user_id=user_id)
        if not notification:
            raise EntityNotFoundException("Notification", notification_id)
        return notification

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """Mark all unread notifications for a user as read."""
        return await self.repository.mark_all_as_read(user_id=user_id)

    async def get_preferences(self, user_id: uuid.UUID) -> NotificationPreferenceResponse:
        """Get user delivery preferences."""
        pref = await self.repository.get_or_create_preference(user_id)
        return NotificationPreferenceResponse.model_validate(pref)

    async def update_preferences(
        self,
        user_id: uuid.UUID,
        request: NotificationPreferenceUpdateRequest,
    ) -> NotificationPreferenceResponse:
        """Update user delivery channel settings."""
        pref = await self.repository.get_or_create_preference(user_id)

        if request.in_app_enabled is not None:
            pref.in_app_enabled = request.in_app_enabled
        if request.email_enabled is not None:
            pref.email_enabled = request.email_enabled
        if request.webhook_enabled is not None:
            pref.webhook_enabled = request.webhook_enabled
        if request.webhook_url is not None:
            pref.webhook_url = request.webhook_url
        if request.min_priority is not None:
            pref.min_priority = request.min_priority.value

        updated = await self.repository.update_preference(pref)
        return NotificationPreferenceResponse.model_validate(updated)
