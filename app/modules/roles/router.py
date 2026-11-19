"""Role and Permission Management API Endpoints.

Protected by RBAC dependencies:
- GET  /api/v1/roles
- GET  /api/v1/permissions
- POST /api/v1/roles
- POST /api/v1/roles/assign/{user_id}
- DELETE /api/v1/roles/assign/{user_id}/{role_id}
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status

from app.common.schemas import ApiResponse
from app.core.exceptions import EntityNotFoundException
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions, require_roles
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.roles.models import Permission, Role
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import (
    PermissionResponse,
    RoleAssignRequest,
    RoleCreateRequest,
    RoleResponse,
    UserWithRolesResponse,
)
from app.modules.roles.service import RoleService

router = APIRouter()


def get_role_repository(session=Depends(lambda: None)):
    pass  # Defined dynamically with DB session injection below


from app.database.connection import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession


def get_role_repo(session: AsyncSession = Depends(get_db_session)) -> RoleRepository:
    return RoleRepository(session=session)


def get_role_service(repo: RoleRepository = Depends(get_role_repo)) -> RoleService:
    return RoleService(repository=repo)


@router.get(
    "",
    response_model=ApiResponse[List[RoleResponse]],
    summary="List all application roles",
    dependencies=[Depends(require_permissions("roles:read"))],
)
async def list_roles(
    service: RoleService = Depends(get_role_service),
) -> ApiResponse[List[RoleResponse]]:
    roles = await service.get_all_roles()
    return ApiResponse(
        success=True,
        data=[RoleResponse.model_validate(r) for r in roles],
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/permissions",
    response_model=ApiResponse[List[PermissionResponse]],
    summary="List all available granular permissions",
    dependencies=[Depends(require_permissions("roles:read"))],
)
async def list_permissions(
    service: RoleService = Depends(get_role_service),
) -> ApiResponse[List[PermissionResponse]]:
    permissions = await service.get_all_permissions()
    return ApiResponse(
        success=True,
        data=[PermissionResponse.model_validate(p) for p in permissions],
        correlation_id=get_correlation_id(),
    )


@router.post(
    "",
    response_model=ApiResponse[RoleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new custom role",
    dependencies=[Depends(require_permissions("roles:manage"))],
)
async def create_role(
    payload: RoleCreateRequest,
    service: RoleService = Depends(get_role_service),
) -> ApiResponse[RoleResponse]:
    role = await service.create_role(
        name=payload.name,
        description=payload.description,
        permission_ids=payload.permission_ids,
    )
    return ApiResponse(
        success=True,
        data=RoleResponse.model_validate(role),
        message=f"Role '{role.name}' created successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/assign/{user_id}",
    response_model=ApiResponse[UserWithRolesResponse],
    summary="Assign roles to a user",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def assign_roles_to_user(
    user_id: uuid.UUID,
    payload: RoleAssignRequest,
    session: AsyncSession = Depends(get_db_session),
    service: RoleService = Depends(get_role_service),
) -> ApiResponse[UserWithRolesResponse]:
    auth_repo = AuthenticationRepository(session)
    user = await auth_repo.get_user_by_id(user_id)
    if not user:
        raise EntityNotFoundException("User", user_id)

    await service.assign_roles_to_user(user, payload.role_ids)

    # Expire identity map cache so fresh relationships are fetched
    session.expire_all()
    updated_user = await service.repo.get_user_with_roles(user_id)
    return ApiResponse(
        success=True,
        data=UserWithRolesResponse.model_validate(updated_user),
        message="Roles assigned successfully.",
        correlation_id=get_correlation_id(),
    )


@router.delete(
    "/assign/{user_id}/{role_id}",
    response_model=ApiResponse[UserWithRolesResponse],
    summary="Remove a role from a user",
    dependencies=[Depends(require_permissions("users:manage"))],
)
async def remove_role_from_user(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    service: RoleService = Depends(get_role_service),
) -> ApiResponse[UserWithRolesResponse]:
    auth_repo = AuthenticationRepository(session)
    user = await auth_repo.get_user_by_id(user_id)
    if not user:
        raise EntityNotFoundException("User", user_id)

    await service.remove_role_from_user(user, role_id)

    session.expire_all()
    updated_user = await service.repo.get_user_with_roles(user_id)
    return ApiResponse(
        success=True,
        data=UserWithRolesResponse.model_validate(updated_user),
        message="Role removed successfully.",
        correlation_id=get_correlation_id(),
    )
