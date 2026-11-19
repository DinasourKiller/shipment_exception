"""Role and Permission Business Logic Service."""

import uuid
from typing import List, Sequence

from app.core.exceptions import ConflictException, EntityNotFoundException
from app.core.logging import get_logger
from app.modules.authentication.models import User
from app.modules.roles.models import Permission, Role
from app.modules.roles.repository import RoleRepository

logger = get_logger("control_tower.role_service")


class RoleService:
    """Service for RBAC operations."""

    def __init__(self, repository: RoleRepository) -> None:
        self.repo = repository

    async def get_all_roles(self) -> Sequence[Role]:
        return await self.repo.get_all_roles()

    async def get_all_permissions(self) -> Sequence[Permission]:
        return await self.repo.get_all_permissions()

    async def create_role(
        self,
        name: str,
        description: str | None = None,
        permission_ids: List[uuid.UUID] | None = None,
    ) -> Role:
        existing = await self.repo.get_role_by_name(name)
        if existing:
            raise ConflictException(f"Role '{name}' already exists.")

        role = Role(name=name, description=description)
        role = await self.repo.create_role(role)

        if permission_ids:
            permissions = await self.repo.get_permissions_by_ids(permission_ids)
            for perm in permissions:
                await self.repo.assign_permission_to_role(role.id, perm.id)

        # Reload with permissions
        loaded_role = await self.repo.get_role_by_id(role.id)
        return loaded_role or role

    async def assign_roles_to_user(self, user: User, role_ids: List[uuid.UUID]) -> User:
        for role_id in role_ids:
            role = await self.repo.get_role_by_id(role_id)
            if not role:
                raise EntityNotFoundException("Role", role_id)
            await self.repo.assign_role_to_user(user.id, role.id)
        return user

    async def remove_role_from_user(self, user: User, role_id: uuid.UUID) -> User:
        role = await self.repo.get_role_by_id(role_id)
        if not role:
            raise EntityNotFoundException("Role", role_id)
        await self.repo.remove_role_from_user(user.id, role.id)
        return user

    async def get_user_permissions(self, user_id: uuid.UUID) -> List[str]:
        return await self.repo.get_user_permissions(user_id)

    async def get_user_role_names(self, user_id: uuid.UUID) -> List[str]:
        return await self.repo.get_user_role_names(user_id)
