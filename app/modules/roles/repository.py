"""Role and Permission Data Access Repository."""

import uuid
from typing import List, Optional, Sequence
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.authentication.models import User
from app.modules.roles.models import Permission, Role, role_permissions, user_roles


class RoleRepository:
    """Repository for Role, Permission, and assignment database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ================= Role Operations =================

    async def get_role_by_id(self, role_id: uuid.UUID) -> Optional[Role]:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == role_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.name == name)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_roles(self) -> Sequence[Role]:
        stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_role(self, role: Role) -> Role:
        self.session.add(role)
        await self.session.flush()
        return role

    # ================= Permission Operations =================

    async def get_permission_by_id(self, perm_id: uuid.UUID) -> Optional[Permission]:
        stmt = select(Permission).where(Permission.id == perm_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_permission_by_name(self, name: str) -> Optional[Permission]:
        stmt = select(Permission).where(Permission.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_permissions(self) -> Sequence[Permission]:
        stmt = select(Permission).order_by(Permission.resource, Permission.action)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_permission(self, permission: Permission) -> Permission:
        self.session.add(permission)
        await self.session.flush()
        return permission

    async def get_permissions_by_ids(self, perm_ids: List[uuid.UUID]) -> Sequence[Permission]:
        stmt = select(Permission).where(Permission.id.in_(perm_ids))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # ================= Assignment Operations =================

    async def assign_role_to_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        check_stmt = select(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role_id,
        )
        res = await self.session.execute(check_stmt)
        if not res.first():
            await self.session.execute(
                insert(user_roles).values(user_id=user_id, role_id=role_id)
            )
            await self.session.flush()

    async def remove_role_from_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        stmt = delete(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role_id,
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def assign_permission_to_role(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> None:
        check_stmt = select(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id,
        )
        res = await self.session.execute(check_stmt)
        if not res.first():
            await self.session.execute(
                insert(role_permissions).values(role_id=role_id, permission_id=permission_id)
            )
            await self.session.flush()

    async def get_user_with_roles(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_permissions(self, user_id: uuid.UUID) -> List[str]:
        """Get flat list of permission names for a user across all assigned roles."""
        user = await self.get_user_with_roles(user_id)
        if not user:
            return []
        permissions: set[str] = set()
        for role in user.roles:
            for perm in role.permissions:
                permissions.add(perm.name)
        return sorted(permissions)

    async def get_user_role_names(self, user_id: uuid.UUID) -> List[str]:
        """Get list of role names assigned to a user."""
        user = await self.get_user_with_roles(user_id)
        if not user:
            return []
        return sorted([r.name for r in user.roles])
