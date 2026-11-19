"""Authorization Guard Dependencies.

Provides reusable FastAPI dependency factories for RBAC enforcement:
- require_permissions("shipments:read", "exceptions:manage")
- require_roles("System Administrator", "Operations Manager")

Usage in routers:
    @router.get("/shipments", dependencies=[Depends(require_permissions("shipments:read"))])
    async def list_shipments(...):
        ...
"""

from typing import List
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException
from app.core.logging import get_logger
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.roles.repository import RoleRepository

logger = get_logger("control_tower.permissions")


def require_permissions(*required_permissions: str):
    """Factory producing a FastAPI dependency that enforces permission-based authorization.

    Raises ForbiddenException if the current user lacks ANY of the required permissions.
    System Administrators bypass all permission checks.
    """

    async def permission_checker(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        repo = RoleRepository(session)
        role_names = await repo.get_user_role_names(current_user.id)

        # System Administrator bypasses all permission checks
        if "System Administrator" in role_names:
            return current_user

        user_permissions = await repo.get_user_permissions(current_user.id)

        missing = [p for p in required_permissions if p not in user_permissions]
        if missing:
            logger.warning(
                f"Authorization denied for user {current_user.email}: "
                f"missing permissions {missing}"
            )
            raise ForbiddenException(
                f"You do not have the required permissions: {', '.join(missing)}"
            )

        return current_user

    return permission_checker


def require_roles(*required_roles: str):
    """Factory producing a FastAPI dependency that enforces role-based authorization.

    Raises ForbiddenException if the current user holds NONE of the required roles.
    At least one matching role is sufficient (OR logic).
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        repo = RoleRepository(session)
        user_role_names = await repo.get_user_role_names(current_user.id)

        if not any(r in user_role_names for r in required_roles):
            logger.warning(
                f"Authorization denied for user {current_user.email}: "
                f"requires one of {list(required_roles)}, has {user_role_names}"
            )
            raise ForbiddenException(
                f"You must hold one of these roles: {', '.join(required_roles)}"
            )

        return current_user

    return role_checker
