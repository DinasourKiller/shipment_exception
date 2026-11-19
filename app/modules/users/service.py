"""User Management Business Logic Service.

Implements business operations and rules:
- Unique email enforcement.
- Safe password hashing with Argon2id.
- Pagination calculation and metadata.
- Account deactivation rules (prevents deactivating the last active System Administrator).
- Session revocation on deactivation and administrative password resets.
"""

import math
import uuid
from typing import List, Optional

from app.common.schemas import PaginatedResponse, PaginationMetadata
from app.core.exceptions import (
    BusinessRuleViolationException,
    ConflictException,
    EntityNotFoundException,
)
from app.core.logging import get_logger
from app.core.security import hash_password
from app.modules.authentication.models import User
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleResponse
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    UserCreateRequest,
    UserDetailResponse,
    UserListItemResponse,
    UserUpdateRequest,
)

logger = get_logger("control_tower.user_service")


class UserService:
    """Service handling user administration business logic."""

    def __init__(self, repository: UserRepository, role_repository: RoleRepository) -> None:
        self.repo = repository
        self.role_repo = role_repository

    async def create_user(self, payload: UserCreateRequest) -> UserDetailResponse:
        """Create a new user account with initial role assignments."""
        existing = await self.repo.get_by_email(payload.email)
        if existing:
            raise ConflictException(f"User with email '{payload.email}' already exists.")

        # Hash initial password with Argon2id
        hashed_pwd = hash_password(payload.password)

        user = User(
            email=payload.email.lower().strip(),
            hashed_password=hashed_pwd,
            full_name=payload.full_name.strip(),
            is_active=payload.is_active,
            is_verified=payload.is_verified,
        )
        user = await self.repo.create(user)

        # Assign initial roles if provided
        if payload.role_ids:
            for role_id in payload.role_ids:
                role = await self.role_repo.get_role_by_id(role_id)
                if not role:
                    raise EntityNotFoundException("Role", role_id)
            await self.repo.sync_roles(user.id, payload.role_ids)

        # Refresh and return detailed user
        created_user = await self.repo.get_by_id(user.id)
        return self._to_detail_response(created_user or user)

    async def list_users(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        role_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[UserListItemResponse]:
        """Retrieve paginated, filtered list of users."""
        users, total_items = await self.repo.list_users_paginated(
            search=search,
            is_active=is_active,
            role_name=role_name,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        items = [
            UserListItemResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                roles=[RoleResponse.model_validate(r) for r in u.roles],
            )
            for u in users
        ]

        pagination = PaginationMetadata(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

        return PaginatedResponse(data=items, pagination=pagination)

    async def get_user_by_id(self, user_id: uuid.UUID) -> UserDetailResponse:
        """Fetch user by unique UUID."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)
        return self._to_detail_response(user)

    async def update_user(self, user_id: uuid.UUID, payload: UserUpdateRequest) -> UserDetailResponse:
        """Update user profile information."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)

        if payload.email and payload.email.lower().strip() != user.email:
            existing = await self.repo.get_by_email(payload.email)
            if existing and existing.id != user_id:
                raise ConflictException(f"Email '{payload.email}' is already in use by another user.")
            user.email = payload.email.lower().strip()

        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()

        await self.repo.update(user)
        updated_user = await self.repo.get_by_id(user_id)
        return self._to_detail_response(updated_user or user)

    async def set_user_status(
        self,
        user_id: uuid.UUID,
        is_active: bool,
        actor_id: uuid.UUID,
    ) -> UserDetailResponse:
        """Activate or deactivate a user account with safety checks."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)

        # Safety Check: Prevent deactivating the last active System Administrator
        if not is_active and user.is_active:
            user_roles_names = [r.name for r in user.roles]
            if "System Administrator" in user_roles_names:
                active_admins = await self.repo.count_active_admins()
                if active_admins <= 1:
                    raise BusinessRuleViolationException(
                        message="Cannot deactivate the last active System Administrator.",
                        rule="RULE_PREVENT_ADMIN_LOCKOUT",
                    )

            # Invalidate all active user sessions upon deactivation
            await self.repo.revoke_all_user_sessions(user_id)
            logger.info(f"User {user.email} deactivated by {actor_id}; all active sessions terminated.")

        user.is_active = is_active
        await self.repo.update(user)
        updated_user = await self.repo.get_by_id(user_id)
        return self._to_detail_response(updated_user or user)

    async def sync_user_roles(self, user_id: uuid.UUID, role_ids: List[uuid.UUID]) -> UserDetailResponse:
        """Synchronize assigned roles for a user."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)

        # Validate that all role IDs exist
        for role_id in role_ids:
            role = await self.role_repo.get_role_by_id(role_id)
            if not role:
                raise EntityNotFoundException("Role", role_id)

        await self.repo.sync_roles(user_id, role_ids)

        # Revoke user sessions so JWT reflects updated role claims on next login
        await self.repo.revoke_all_user_sessions(user_id)

        updated_user = await self.repo.get_by_id(user_id)
        return self._to_detail_response(updated_user or user)

    async def admin_reset_password(self, user_id: uuid.UUID, new_password: str) -> None:
        """Administrator resets user password and revokes all active sessions."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)

        user.hashed_password = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.repo.update(user)

        # Revoke all active sessions
        await self.repo.revoke_all_user_sessions(user_id)
        logger.info(f"Password reset by admin for user {user.email}; all existing sessions terminated.")

    def _to_detail_response(self, user: User) -> UserDetailResponse:
        """Helper to convert User model to UserDetailResponse."""
        return UserDetailResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[RoleResponse.model_validate(r) for r in user.roles],
        )
