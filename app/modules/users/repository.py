"""User Management Data Access Repository.

Encapsulates all database operations for querying, filtering, updating,
and assigning roles to users.
"""

import uuid
from typing import List, Optional, Sequence, Tuple
from sqlalchemy import and_, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.authentication.models import RefreshToken, User
from app.modules.roles.models import Role, role_permissions, user_roles


class UserRepository:
    """Repository handling database operations for user administration."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.email == email.lower().strip())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user: User) -> User:
        await self.session.flush()
        return user

    async def count_active_admins(self) -> int:
        """Count active users with 'System Administrator' role to prevent self-lockout."""
        stmt = (
            select(func.count(func.distinct(User.id)))
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(
                and_(
                    Role.name == "System Administrator",
                    User.is_active == True,  # noqa: E712
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_users_paginated(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        role_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[Sequence[User], int]:
        """Query users with dynamic filtering, search, pagination, and total count."""
        base_query = select(User).distinct()

        # Join roles if filtering by role name
        if role_name:
            base_query = base_query.join(user_roles, User.id == user_roles.c.user_id).join(
                Role, user_roles.c.role_id == Role.id
            )

        # Build filter predicates
        filters = []
        if search:
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                )
            )

        if is_active is not None:
            filters.append(User.is_active == is_active)

        if role_name:
            filters.append(Role.name == role_name.strip())

        if filters:
            base_query = base_query.where(and_(*filters))

        # Count total matching records
        count_query = select(func.count()).select_from(base_query.subquery())
        total_res = await self.session.execute(count_query)
        total_items = total_res.scalar() or 0

        # Execute paginated query with eager loading
        offset = (page - 1) * page_size
        stmt = (
            base_query.options(selectinload(User.roles).selectinload(Role.permissions))
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        users = result.scalars().all()

        return users, total_items

    async def sync_roles(self, user_id: uuid.UUID, role_ids: List[uuid.UUID]) -> None:
        """Replace existing user roles with the provided role IDs."""
        # 1. Delete all existing user roles
        del_stmt = delete(user_roles).where(user_roles.c.user_id == user_id)
        await self.session.execute(del_stmt)

        # 2. Insert new role associations
        if role_ids:
            for role_id in role_ids:
                await self.session.execute(
                    insert(user_roles).values(user_id=user_id, role_id=role_id)
                )

        await self.session.flush()

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke all active refresh token sessions for the given user."""
        from datetime import datetime, timezone
        from sqlalchemy import update as sa_update

        now = datetime.now(timezone.utc)
        update_stmt = (
            sa_update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True, revoked_at=now)
        )
        res = await self.session.execute(update_stmt)
        await self.session.flush()
        return res.rowcount
