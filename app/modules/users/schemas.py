"""Pydantic Schemas for User Management Domain."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.roles.schemas import RoleResponse


class UserCreateRequest(BaseModel):
    """Payload to create a new user account."""

    email: EmailStr = Field(..., description="User's unique email address")
    password: str = Field(..., min_length=8, description="Initial plaintext password (min 8 chars)")
    full_name: str = Field(..., min_length=2, max_length=255, description="User's full name")
    is_active: bool = Field(default=True, description="Account active status")
    is_verified: bool = Field(default=True, description="Account email verification status")
    role_ids: List[uuid.UUID] = Field(default_factory=list, description="Initial role IDs to assign")


class UserUpdateRequest(BaseModel):
    """Payload to update an existing user's profile."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    email: Optional[EmailStr] = Field(default=None)


class UserStatusUpdateRequest(BaseModel):
    """Payload to activate or deactivate a user account."""

    is_active: bool = Field(..., description="New active status")
    reason: Optional[str] = Field(default=None, description="Optional administrative justification")


class UserRoleSyncRequest(BaseModel):
    """Payload to bulk-assign / synchronize roles for a user."""

    role_ids: List[uuid.UUID] = Field(..., description="Complete list of role IDs to associate with this user")


class AdminResetPasswordRequest(BaseModel):
    """Payload for an administrator to reset a user's password."""

    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class UserDetailResponse(BaseModel):
    """Comprehensive user profile response including assigned roles."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    failed_login_attempts: int
    locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleResponse] = Field(default_factory=list)


class UserListItemResponse(BaseModel):
    """Compact user representation for paginated lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    roles: List[RoleResponse] = Field(default_factory=list)
