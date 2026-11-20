"""Notification & Alerting Database Repository.

Provides data access methods for notification feeds, preferences, and mark-as-read updates.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import (
    Notification,
    NotificationPreference,
    NotificationPriority,
    NotificationStatus,
)


class NotificationRepository:
    """Encapsulates database operations for notifications and preferences."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, notification: Notification) -> Notification:
        """Persist a newly dispatched notification."""
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        """Fetch notification by primary key."""
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Tuple[List[Notification], int, int]:
        """Fetch notifications visible to user (direct or broadcast) with unread count."""
        # Notifications for this user OR system broadcasts (recipient_id is None)
        base_filter = or_(Notification.recipient_id == user_id, Notification.recipient_id.is_(None))

        query = select(Notification).where(base_filter)
        if status:
            query = query.where(Notification.status == status)
        if channel:
            query = query.where(Notification.channel == channel)
        if priority:
            query = query.where(Notification.priority == priority)

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Count unread
        unread_stmt = select(func.count()).where(
            base_filter,
            Notification.status != NotificationStatus.READ.value,
        )
        unread_count = (await self.session.execute(unread_stmt)).scalar() or 0

        # Pagination & ordering
        query = (
            query.order_by(Notification.sent_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total, unread_count

    async def mark_as_read(
        self,
        notification_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[Notification]:
        """Mark a single notification as read."""
        stmt = select(Notification).where(Notification.id == notification_id)
        if user_id:
            stmt = stmt.where(or_(Notification.recipient_id == user_id, Notification.recipient_id.is_(None)))

        result = await self.session.execute(stmt)
        notification = result.scalar_one_or_none()
        if notification and notification.status != NotificationStatus.READ.value:
            notification.status = NotificationStatus.READ.value
            notification.read_at = datetime.now(timezone.utc)
            await self.session.flush()
            await self.session.refresh(notification)

        return notification

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """Mark all unread notifications for a user as read."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                or_(Notification.recipient_id == user_id, Notification.recipient_id.is_(None)),
                Notification.status != NotificationStatus.READ.value,
            )
            .values(status=NotificationStatus.READ.value, read_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_or_create_preference(self, user_id: uuid.UUID) -> NotificationPreference:
        """Fetch or initialize default notification preferences for a user."""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        result = await self.session.execute(stmt)
        pref = result.scalar_one_or_none()
        if not pref:
            pref = NotificationPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                in_app_enabled=True,
                email_enabled=True,
                webhook_enabled=False,
                min_priority=NotificationPriority.LOW.value,
            )
            self.session.add(pref)
            await self.session.flush()
            await self.session.refresh(pref)
        return pref

    async def update_preference(self, pref: NotificationPreference) -> NotificationPreference:
        """Update notification preference settings."""
        await self.session.flush()
        await self.session.refresh(pref)
        return pref
