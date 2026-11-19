"""User Administration API Endpoints.

Protected by RBAC dependencies:
- POST   /api/v1/users
- GET    /api/v1/users
- GET    /api/v1/users/{user_id}
- PUT    /api/v1/users/{user_id}
- PATCH  /api/v1/users/{user_id}/status
- PUT    /api/v1/users/{user_id}/roles
- POST   /api/v1/users/{user_id}/reset-password
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse, PaginatedResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.roles.repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    AdminResetPasswordRequest,
    UserCreateRequest,
    UserDetailResponse,
    UserListItemResponse,
    UserRoleSyncRequest,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.modules.users.service import UserService

router = APIRouter()


def get_user_repo(session: AsyncSession = Depends(get_db_session)) -> UserRepository:
    return UserRepository(session=session)


def get_user_service(
    session: AsyncSession = Depends(get_db_session),
    repo: UserRepository = Depends(get_user_repo),
) -> UserService:
    role_repo = RoleRepository(session=session)
    return UserService(repository=repo, role_repository=role_repo)


@router.post(
    "",
    response_model=ApiResponse[UserDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def create_user(
    payload: UserCreateRequest,
    service: UserService = Depends(get_user_service),
) -> ApiResponse[UserDetailResponse]:
    created = await service.create_user(payload)
    return ApiResponse(
        success=True,
        data=created,
        message=f"User '{created.email}' created successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "",
    response_model=PaginatedResponse[UserListItemResponse],
    summary="List users with search, filtering, and pagination",
    dependencies=[Depends(require_permissions("users:read"))],
)
async def list_users(
    search: Optional[str] = Query(default=None, description="Search by name or email"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    role: Optional[str] = Query(default=None, description="Filter by assigned role name"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    service: UserService = Depends(get_user_service),
) -> PaginatedResponse[UserListItemResponse]:
    paginated = await service.list_users(
        search=search,
        is_active=is_active,
        role_name=role,
        page=page,
        page_size=page_size,
    )
    paginated.correlation_id = get_correlation_id()
    return paginated


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserDetailResponse],
    summary="Get user profile by UUID",
    dependencies=[Depends(require_permissions("users:read"))],
)
async def get_user_by_id(
    user_id: uuid.UUID,
    service: UserService = Depends(get_user_service),
) -> ApiResponse[UserDetailResponse]:
    user = await service.get_user_by_id(user_id)
    return ApiResponse(
        success=True,
        data=user,
        correlation_id=get_correlation_id(),
    )


@router.put(
    "/{user_id}",
    response_model=ApiResponse[UserDetailResponse],
    summary="Update user profile information",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    service: UserService = Depends(get_user_service),
) -> ApiResponse[UserDetailResponse]:
    updated = await service.update_user(user_id, payload)
    return ApiResponse(
        success=True,
        data=updated,
        message="User profile updated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.patch(
    "/{user_id}/status",
    response_model=ApiResponse[UserDetailResponse],
    summary="Activate or deactivate a user account",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def set_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> ApiResponse[UserDetailResponse]:
    updated = await service.set_user_status(
        user_id=user_id,
        is_active=payload.is_active,
        actor_id=current_user.id,
    )
    status_str = "activated" if payload.is_active else "deactivated"
    return ApiResponse(
        success=True,
        data=updated,
        message=f"User account has been {status_str}.",
        correlation_id=get_correlation_id(),
    )


@router.put(
    "/{user_id}/roles",
    response_model=ApiResponse[UserDetailResponse],
    summary="Synchronize assigned roles for a user",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def sync_user_roles(
    user_id: uuid.UUID,
    payload: UserRoleSyncRequest,
    session: AsyncSession = Depends(get_db_session),
    service: UserService = Depends(get_user_service),
) -> ApiResponse[UserDetailResponse]:
    await service.sync_user_roles(user_id, payload.role_ids)
    session.expire_all()
    refreshed = await service.get_user_by_id(user_id)
    return ApiResponse(
        success=True,
        data=refreshed,
        message="User roles synchronized successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/{user_id}/reset-password",
    response_model=ApiResponse[dict],
    summary="Administrative password reset",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def admin_reset_password(
    user_id: uuid.UUID,
    payload: AdminResetPasswordRequest,
    service: UserService = Depends(get_user_service),
) -> ApiResponse[dict]:
    await service.admin_reset_password(user_id, payload.new_password)
    return ApiResponse(
        success=True,
        data={"message": "Password reset successfully. All active sessions terminated."},
        correlation_id=get_correlation_id(),
    )
