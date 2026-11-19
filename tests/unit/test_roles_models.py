"""Unit tests for Role and Permission models."""

import uuid
from app.modules.roles.models import Permission, Role


def test_role_model_instantiation():
    """Verify Role entity creation and attributes."""
    role = Role(
        name="Custom Auditor",
        description="Audits exception logs",
    )
    assert role.name == "Custom Auditor"
    assert role.description == "Audits exception logs"
    assert role.id is None or isinstance(role.id, uuid.UUID)


def test_permission_model_instantiation():
    """Verify Permission entity creation and attributes."""
    perm = Permission(
        name="audit:export",
        resource="audit",
        action="export",
        description="Export compliance audit reports",
    )
    assert perm.name == "audit:export"
    assert perm.resource == "audit"
    assert perm.action == "export"
    data = perm.to_dict()
    assert data["name"] == "audit:export"
    assert data["resource"] == "audit"
