"""Pydantic Schemas for Role and Permission management."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    """Public permission representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(..., description="Permission identifier (e.g. shipments:read)")
    resource: str = Field(..., description="Resource name (e.g. shipments)")
    action: str = Field(..., description="Action name (e.g. read)")
    description: Optional[str] = None


class RoleResponse(BaseModel):
    """Public role representation including assigned permissions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(..., description="Role name (e.g. Control Tower Analyst)")
    description: Optional[str] = None
    permissions: List[PermissionResponse] = Field(default_factory=list)


class RoleCreateRequest(BaseModel):
    """Request to create a new role."""

    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    permission_ids: List[uuid.UUID] = Field(default_factory=list, description="Permission IDs to assign")


class RoleAssignRequest(BaseModel):
    """Request to assign roles to a user."""

    role_ids: List[uuid.UUID] = Field(..., description="Role IDs to assign to the user")


class UserWithRolesResponse(BaseModel):
    """User profile with assigned roles."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    roles: List[RoleResponse] = Field(default_factory=list)
