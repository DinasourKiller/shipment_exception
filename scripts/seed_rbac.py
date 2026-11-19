"""Seed Script for Enterprise RBAC Roles and Permissions.

Populates PostgreSQL database with predefined enterprise roles and granular permissions
as defined in the Master System Prompt (Section 7).
"""

import asyncio
from typing import Dict, List, Tuple
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_engine
from app.modules.authentication.models import User
from app.modules.roles.models import Permission, Role, role_permissions

# Definition of granular permissions (name, resource, action, description)
DEFAULT_PERMISSIONS: List[Tuple[str, str, str, str]] = [
    # Shipments
    ("shipments:read", "shipments", "read", "View shipment records, tracking, and milestones"),
    ("shipments:write", "shipments", "write", "Create and update shipment data"),
    # Exceptions
    ("exceptions:read", "exceptions", "read", "View operational exceptions and impact analysis"),
    ("exceptions:manage", "exceptions", "manage", "Create, update, and manage exceptions"),
    ("exceptions:escalate", "exceptions", "escalate", "Escalate critical high-severity exceptions"),
    ("exceptions:close", "exceptions", "close", "Close exceptions upon delivery confirmation"),
    # Recovery
    ("recovery:read", "recovery", "read", "View recovery requests, proposals, and history"),
    ("recovery:request", "recovery", "request", "Initiate recovery requests to carriers"),
    ("recovery:approve", "recovery", "approve", "Approve high-severity recovery plans"),
    ("recovery:dispatch", "recovery", "dispatch", "Confirm recovery dispatch, vehicles, and drivers"),
    # Carriers & Resources
    ("carriers:read", "carriers", "read", "View carrier directory and performance"),
    ("carriers:respond", "carriers", "respond", "Accept or reject recovery requests as a carrier"),
    ("resources:allocate", "resources", "allocate", "Assign vehicles and drivers to recoveries"),
    # Users & Roles
    ("users:read", "users", "read", "View user accounts and profiles"),
    ("users:manage", "users", "manage", "Create, update, and deactivate user accounts"),
    ("roles:read", "roles", "read", "View roles and permissions configuration"),
    ("roles:manage", "roles", "manage", "Create and configure roles and permissions"),
    # Notifications & Reporting
    ("notifications:read", "notifications", "read", "View notification alerts"),
    ("reporting:read", "reporting", "read", "Access operational reports and trend metrics"),
]

# Mapping of standard enterprise roles to their allowed permissions
ROLE_PERMISSIONS_MAPPING: Dict[str, List[str]] = {
    "System Administrator": [p[0] for p in DEFAULT_PERMISSIONS],
    "Control Tower Analyst": [
        "shipments:read",
        "exceptions:read",
        "exceptions:manage",
        "recovery:read",
        "recovery:request",
        "notifications:read",
        "reporting:read",
        "roles:read",
    ],
    "Dispatcher / Planner": [
        "shipments:read",
        "shipments:write",
        "exceptions:read",
        "exceptions:manage",
        "recovery:read",
        "recovery:request",
        "recovery:dispatch",
        "resources:allocate",
        "notifications:read",
    ],
    "Operations Manager": [
        "shipments:read",
        "shipments:write",
        "exceptions:read",
        "exceptions:manage",
        "exceptions:escalate",
        "exceptions:close",
        "recovery:read",
        "recovery:request",
        "recovery:approve",
        "recovery:dispatch",
        "resources:allocate",
        "notifications:read",
        "reporting:read",
        "roles:read",
    ],
    "Carrier": [
        "recovery:read",
        "carriers:respond",
        "resources:allocate",
        "notifications:read",
    ],
    "Warehouse Supervisor": [
        "shipments:read",
        "exceptions:read",
        "notifications:read",
    ],
    "Customer Service": [
        "shipments:read",
        "exceptions:read",
        "notifications:read",
    ],
}


async def seed_rbac() -> None:
    """Seed permissions and roles into PostgreSQL."""
    print("Starting RBAC seeding...")
    async with AsyncSession(async_engine) as session:
        # 1. Seed Permissions
        perm_map: Dict[str, Permission] = {}
        for name, resource, action, desc in DEFAULT_PERMISSIONS:
            stmt = select(Permission).where(Permission.name == name)
            res = await session.execute(stmt)
            perm = res.scalar_one_or_none()
            if not perm:
                perm = Permission(name=name, resource=resource, action=action, description=desc)
                session.add(perm)
                await session.flush()
                print(f"  Created permission: {name}")
            perm_map[name] = perm

        # 2. Seed Roles and map permissions
        for role_name, allowed_perms in ROLE_PERMISSIONS_MAPPING.items():
            stmt = select(Role).where(Role.name == role_name)
            res = await session.execute(stmt)
            role = res.scalar_one_or_none()
            if not role:
                role = Role(
                    name=role_name,
                    description=f"Standard enterprise role: {role_name}",
                )
                session.add(role)
                await session.flush()
                print(f"  Created role: {role_name}")

            # Assign permissions via association table
            for perm_name in allowed_perms:
                target_perm = perm_map[perm_name]
                check_stmt = select(role_permissions).where(
                    role_permissions.c.role_id == role.id,
                    role_permissions.c.permission_id == target_perm.id,
                )
                check_res = await session.execute(check_stmt)
                if not check_res.first():
                    await session.execute(
                        insert(role_permissions).values(
                            role_id=role.id,
                            permission_id=target_perm.id,
                        )
                    )

        await session.commit()
        print("RBAC seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_rbac())
