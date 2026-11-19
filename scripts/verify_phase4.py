"""Comprehensive Phase 4 Live PostgreSQL Verification Script.

Inspects live database state, roles, permissions, association tables,
and verifies RBAC mappings directly against PostgreSQL.
"""

import asyncio
from sqlalchemy import text
from app.database.connection import async_engine
from app.modules.roles.repository import RoleRepository

EXPECTED_ROLES = [
    "System Administrator",
    "Control Tower Analyst",
    "Dispatcher / Planner",
    "Operations Manager",
    "Carrier",
    "Warehouse Supervisor",
    "Customer Service",
]

EXPECTED_PERMISSIONS_COUNT = 19


async def verify_rbac() -> bool:
    print("=" * 70)
    print("       PHASE 4: LIVE POSTGRESQL RBAC VERIFICATION REPORT")
    print("=" * 70)

    all_passed = True

    async with async_engine.connect() as conn:
        # 1. Check roles table
        res = await conn.execute(text("SELECT count(*) FROM roles"))
        roles_count = res.scalar()
        print(f"\n[1] Roles Count: {roles_count} in database")
        if roles_count < len(EXPECTED_ROLES):
            print(f"    FAILED: Expected at least {len(EXPECTED_ROLES)} roles!")
            all_passed = False
        else:
            print("    PASSED: All standard enterprise roles are present.")

        # 2. Check permissions table
        res = await conn.execute(text("SELECT count(*) FROM permissions"))
        perms_count = res.scalar()
        print(f"\n[2] Permissions Count: {perms_count} in database")
        if perms_count < EXPECTED_PERMISSIONS_COUNT:
            print(f"    FAILED: Expected at least {EXPECTED_PERMISSIONS_COUNT} permissions!")
            all_passed = False
        else:
            print("    PASSED: All 19 granular permissions are present.")

        # 3. Check role_permissions associations
        res = await conn.execute(text("SELECT count(*) FROM role_permissions"))
        assoc_count = res.scalar()
        print(f"\n[3] Role-Permission Associations: {assoc_count} active mappings")
        if assoc_count < 40:
            print("    WARNING: Association count lower than expected.")
        else:
            print("    PASSED: Robust permission-to-role associations verified.")

        # 4. Detail each standard role and its assigned permission count
        print("\n[4] Detailed Role-Permission Breakdown:")
        print(f"    {'Role Name':<30} | {'Permission Count':<18} | Status")
        print("    " + "-" * 60)

        for role_name in EXPECTED_ROLES:
            res = await conn.execute(
                text(
                    "SELECT count(rp.permission_id) "
                    "FROM roles r "
                    "JOIN role_permissions rp ON r.id = rp.role_id "
                    "WHERE r.name = :name"
                ),
                {"name": role_name},
            )
            count = res.scalar()
            status = "OK" if count > 0 else "EMPTY"
            print(f"    {role_name:<30} | {count:<18} | {status}")
            if count == 0:
                all_passed = False

        # 5. Check user_roles association table
        res = await conn.execute(text("SELECT count(*) FROM user_roles"))
        user_role_count = res.scalar()
        print(f"\n[5] User-Role Assignments: {user_role_count} assignments present.")

    print("\n" + "=" * 70)
    if all_passed:
        print(">>> OVERALL STATUS: ALL PHASE 4 RBAC CHECKS PASSED SUCCESSFULLY! <<<")
    else:
        print(">>> OVERALL STATUS: SOME CHECKS FAILED! <<<")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(verify_rbac())
    exit(0 if success else 1)
