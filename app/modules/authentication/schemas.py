"""Pydantic Schemas for Authentication Request and Response Models."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials required to authenticate."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User plaintext password")


class TokenResponse(BaseModel):
    """Response returned upon successful authentication or token refresh."""

    access_token: str = Field(..., description="Short-lived RS256 JWT access token")
    token_type: str = Field(default="Bearer", description="Token schema type")
    expires_in: int = Field(..., description="Access token expiration window in seconds")


class UserResponse(BaseModel):
    """Public user profile information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., description="Full legal name")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Email verification status")
    created_at: datetime = Field(..., description="Account creation timestamp")


class ChangePasswordRequest(BaseModel):
    """Payload to update an authenticated user's password."""

    current_password: str = Field(..., min_length=8, description="Existing plaintext password")
    new_password: str = Field(..., min_length=8, description="New plaintext password (min 8 characters)")


class ForgotPasswordRequest(BaseModel):
    """Payload to initiate a password reset flow."""

    email: EmailStr = Field(..., description="Registered user email address")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Informational message")
