"""Unit tests for User Management Pydantic schemas."""

import uuid
import pytest
from pydantic import ValidationError

from app.modules.users.schemas import (
    AdminResetPasswordRequest,
    UserCreateRequest,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)


def test_user_create_request_valid():
    """Verify valid UserCreateRequest instantiation."""
    role_id = uuid.uuid4()
    req = UserCreateRequest(
        email="operator@controltower.corp",
        password="SuperPassword123!",
        full_name="Operations Operator",
        is_active=True,
        is_verified=True,
        role_ids=[role_id],
    )
    assert req.email == "operator@controltower.corp"
    assert req.full_name == "Operations Operator"
    assert len(req.role_ids) == 1


def test_user_create_request_short_password():
    """Verify validation error when password is under 8 characters."""
    with pytest.raises(ValidationError):
        UserCreateRequest(
            email="short@corp.local",
            password="short",
            full_name="Valid Name",
        )


def test_user_create_request_invalid_email():
    """Verify validation error for invalid email formats."""
    with pytest.raises(ValidationError):
        UserCreateRequest(
            email="not-an-email",
            password="ValidPassword123!",
            full_name="Valid Name",
        )


def test_user_status_update_request():
    """Verify UserStatusUpdateRequest attributes."""
    req = UserStatusUpdateRequest(is_active=False, reason="Seasonal employee departure")
    assert req.is_active is False
    assert req.reason == "Seasonal employee departure"


def test_admin_reset_password_request():
    """Verify AdminResetPasswordRequest validation."""
    req = AdminResetPasswordRequest(new_password="NewSecurePassword123!")
    assert req.new_password == "NewSecurePassword123!"

    with pytest.raises(ValidationError):
        AdminResetPasswordRequest(new_password="tiny")
