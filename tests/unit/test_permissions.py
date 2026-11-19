"""Unit tests for RBAC Authorization Guard factories (require_permissions, require_roles)."""

import uuid
import pytest
from app.core.exceptions import ForbiddenException
from app.core.permissions import require_permissions, require_roles
from app.database.connection import AsyncSessionLocal
from app.modules.authentication.models import User
from app.modules.roles.models import Permission, Role
from app.modules.roles.repository import RoleRepository


@pytest.fixture
async def sample_rbac_entities():
    """Setup roles and permissions for unit testing."""
    async with AsyncSessionLocal() as session:
        role_repo = RoleRepository(session)

        # Create permissions
        perm_a = Permission(name=f"test:read_{uuid.uuid4().hex[:6]}", resource="test", action="read")
        perm_b = Permission(name=f"test:write_{uuid.uuid4().hex[:6]}", resource="test", action="write")
        await role_repo.create_permission(perm_a)
        await role_repo.create_permission(perm_b)

        # Create role with perm_a only
        role_reader = Role(name=f"Test Reader {uuid.uuid4().hex[:6]}")
        await role_repo.create_role(role_reader)
        await role_repo.assign_permission_to_role(role_reader.id, perm_a.id)

        # Create role with both perm_a and perm_b
        role_writer = Role(name=f"Test Writer {uuid.uuid4().hex[:6]}")
        await role_repo.create_role(role_writer)
        await role_repo.assign_permission_to_role(role_writer.id, perm_a.id)
        await role_repo.assign_permission_to_role(role_writer.id, perm_b.id)

        # Create users
        user_reader = User(
            email=f"reader_{uuid.uuid4().hex[:6]}@test.corp",
            hashed_password="hashed_pwd",
            full_name="Reader User",
            is_active=True,
            is_verified=True,
        )
        session.add(user_reader)
        await session.flush()
        await role_repo.assign_role_to_user(user_reader.id, role_reader.id)

        user_writer = User(
            email=f"writer_{uuid.uuid4().hex[:6]}@test.corp",
            hashed_password="hashed_pwd",
            full_name="Writer User",
            is_active=True,
            is_verified=True,
        )
        session.add(user_writer)
        await session.flush()
        await role_repo.assign_role_to_user(user_writer.id, role_writer.id)

        user_admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.corp",
            hashed_password="hashed_pwd",
            full_name="Admin User",
            is_active=True,
            is_verified=True,
        )
        session.add(user_admin)
        await session.flush()
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(user_admin.id, admin_role.id)

        await session.commit()

        yield {
            "session": session,
            "perm_a": perm_a.name,
            "perm_b": perm_b.name,
            "role_reader": role_reader.name,
            "role_writer": role_writer.name,
            "user_reader": user_reader,
            "user_writer": user_writer,
            "user_admin": user_admin,
        }


async def test_require_permissions_granted(sample_rbac_entities):
    """User with perm_a accesses endpoint requiring perm_a."""
    checker = require_permissions(sample_rbac_entities["perm_a"])
    result = await checker(
        current_user=sample_rbac_entities["user_reader"],
        session=sample_rbac_entities["session"],
    )
    assert result.id == sample_rbac_entities["user_reader"].id


async def test_require_permissions_denied_missing_one(sample_rbac_entities):
    """User with only perm_a tries to access endpoint requiring perm_a AND perm_b."""
    checker = require_permissions(
        sample_rbac_entities["perm_a"],
        sample_rbac_entities["perm_b"],
    )
    with pytest.raises(ForbiddenException) as exc_info:
        await checker(
            current_user=sample_rbac_entities["user_reader"],
            session=sample_rbac_entities["session"],
        )
    assert "missing" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


async def test_require_permissions_admin_bypass(sample_rbac_entities):
    """System Administrator bypasses all permission requirements even arbitrary ones."""
    checker = require_permissions("non_existent:permission_xyz")
    result = await checker(
        current_user=sample_rbac_entities["user_admin"],
        session=sample_rbac_entities["session"],
    )
    assert result.id == sample_rbac_entities["user_admin"].id


async def test_require_roles_granted(sample_rbac_entities):
    """User holding role matches requirement."""
    checker = require_roles(sample_rbac_entities["role_reader"])
    result = await checker(
        current_user=sample_rbac_entities["user_reader"],
        session=sample_rbac_entities["session"],
    )
    assert result.id == sample_rbac_entities["user_reader"].id


async def test_require_roles_or_logic_granted(sample_rbac_entities):
    """User holding one of multiple accepted roles passes (OR logic)."""
    checker = require_roles("NonExistentRole", sample_rbac_entities["role_reader"])
    result = await checker(
        current_user=sample_rbac_entities["user_reader"],
        session=sample_rbac_entities["session"],
    )
    assert result.id == sample_rbac_entities["user_reader"].id


async def test_require_roles_denied(sample_rbac_entities):
    """User holding reader role fails requirement for writer role."""
    checker = require_roles(sample_rbac_entities["role_writer"])
    with pytest.raises(ForbiddenException):
        await checker(
            current_user=sample_rbac_entities["user_reader"],
            session=sample_rbac_entities["session"],
        )
