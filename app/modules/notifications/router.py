"""Notification & Alerting API Endpoints.

Provides REST endpoints for user notification feeds, mark-as-read operations,
channel delivery preferences, and manual operational broadcasts with RBAC authorization.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.notifications.schemas import (
    NotificationCreateRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    PaginatedNotificationResponse,
)
from app.modules.notifications.service import NotificationService

router = APIRouter()


def get_notification_service(session: AsyncSession = Depends(get_db_session)) -> NotificationService:
    """Dependency producing initialized NotificationService."""
    return NotificationService(session=session)


@router.get(
    "",
    response_model=ApiResponse[PaginatedNotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="List notifications for current user",
    description="Returns user's notification feed including unread count, with filtering by status and priority.",
)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(require_permissions("notifications:read")),
) -> ApiResponse[PaginatedNotificationResponse]:
    result = await service.list_user_notifications(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        channel=channel,
        priority=priority,
    )
    return ApiResponse(
        success=True,
        data=result,
        message=f"Retrieved {len(result.items)} notifications ({result.unread_count} unread).",
        correlation_id=get_correlation_id(),
    )


@router.patch(
    "/{notification_id}/read",
    response_model=ApiResponse[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Updates notification status to READ.",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(require_permissions("notifications:read")),
) -> ApiResponse[NotificationResponse]:
    notification = await service.mark_as_read(notification_id=notification_id, user_id=current_user.id)
    return ApiResponse(
        success=True,
        data=NotificationResponse.model_validate(notification),
        message="Notification marked as read.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/mark-all-read",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Marks all unread notifications visible to current user as READ.",
)
async def mark_all_notifications_read(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(require_permissions("notifications:read")),
) -> ApiResponse[dict]:
    count = await service.mark_all_as_read(user_id=current_user.id)
    return ApiResponse(
        success=True,
        data={"marked_read_count": count},
        message=f"Marked {count} notifications as read.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/preferences",
    response_model=ApiResponse[NotificationPreferenceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get user notification preferences",
    description="Retrieves current user's delivery channel settings and minimum priority thresholds.",
)
async def get_preferences(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(require_permissions("notifications:read")),
) -> ApiResponse[NotificationPreferenceResponse]:
    pref = await service.get_preferences(user_id=current_user.id)
    return ApiResponse(
        success=True,
        data=pref,
        message="Notification preferences retrieved.",
        correlation_id=get_correlation_id(),
    )


@router.put(
    "/preferences",
    response_model=ApiResponse[NotificationPreferenceResponse],
    status_code=status.HTTP_200_OK,
    summary="Update notification preferences",
    description="Configures user's active delivery channels and notification thresholds.",
)
async def update_preferences(
    payload: NotificationPreferenceUpdateRequest,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(require_permissions("notifications:read")),
) -> ApiResponse[NotificationPreferenceResponse]:
    pref = await service.update_preferences(user_id=current_user.id, request=payload)
    return ApiResponse(
        success=True,
        data=pref,
        message="Notification preferences updated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/broadcast",
    response_model=ApiResponse[NotificationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Broadcast operational alert",
    description="Sends a broadcast notification to all control tower operators.",
)
async def broadcast_alert(
    payload: NotificationCreateRequest,
    service: NotificationService = Depends(get_notification_service),
    _: User = Depends(require_permissions("exceptions:manage")),
) -> ApiResponse[NotificationResponse]:
    notification = await service.send_notification(payload)
    return ApiResponse(
        success=True,
        data=NotificationResponse.model_validate(notification),
        message="Alert broadcast dispatched successfully.",
        correlation_id=get_correlation_id(),
    )
