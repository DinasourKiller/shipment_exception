"""Seed Standard Demo Users for Shipment Exception Control Tower.

Creates clean, standard demo user accounts for each of the 7 enterprise roles
with predefined, easy-to-use credentials for Swagger UI and local testing.
"""

import asyncio
from typing import Dict, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.connection import async_engine
from app.core.security import hash_password
from app.modules.authentication.models import User
from app.modules.roles.models import Role, user_roles

DEMO_USERS: List[Dict[str, str]] = [
    {
        "email": "admin@controltower.corp",
        "full_name": "Sarah Connor (System Admin)",
        "role_name": "System Administrator",
        "phone": "+1-555-0101",
    },
    {
        "email": "analyst@controltower.corp",
        "full_name": "Alex Mercer (Tower Analyst)",
        "role_name": "Control Tower Analyst",
        "phone": "+1-555-0102",
    },
    {
        "email": "dispatcher@controltower.corp",
        "full_name": "Marcus Vance (Dispatcher)",
        "role_name": "Dispatcher / Planner",
        "phone": "+1-555-0103",
    },
    {
        "email": "manager@controltower.corp",
        "full_name": "Elena Rostova (Operations Manager)",
        "role_name": "Operations Manager",
        "phone": "+1-555-0104",
    },
    {
        "email": "carrier@controltower.corp",
        "full_name": "Dave Batista (Apex Logistics Carrier)",
        "role_name": "Carrier",
        "phone": "+1-555-0105",
    },
    {
        "email": "warehouse@controltower.corp",
        "full_name": "John Miller (Hub Supervisor)",
        "role_name": "Warehouse Supervisor",
        "phone": "+1-555-0106",
    },
    {
        "email": "support@controltower.corp",
        "full_name": "Emily Clark (Customer Service Rep)",
        "role_name": "Customer Service",
        "phone": "+1-555-0107",
    },
]

DEMO_PASSWORD = "Password123!"


async def seed_demo_users():
    """Seeds or refreshes the standard demo user accounts."""
    password_hash = hash_password(DEMO_PASSWORD)

    async with AsyncSession(async_engine) as session:
        # Load all existing roles
        roles_result = await session.execute(select(Role))
        role_map = {r.name: r for r in roles_result.scalars().all()}

        print(f"Loaded {len(role_map)} existing enterprise roles from database.")

        for user_data in DEMO_USERS:
            email = user_data["email"]
            role_name = user_data["role_name"]
            role = role_map.get(role_name)

            if not role:
                print(f"[WARN] Role '{role_name}' not found. Skipping {email}.")
                continue

            # Check if user already exists
            user_result = await session.execute(
                select(User).options(selectinload(User.roles)).where(User.email == email)
            )
            existing_user = user_result.scalars().first()

            if existing_user:
                # Update password, status, profile, and roles
                existing_user.full_name = user_data["full_name"]
                existing_user.phone_number = user_data["phone"]
                existing_user.password_hash = password_hash
                existing_user.is_active = True
                existing_user.is_verified = True
                existing_user.roles = [role]
                print(f"[UPDATED] Demo user: {email} ({role_name})")
            else:
                new_user = User(
                    email=email,
                    password_hash=password_hash,
                    full_name=user_data["full_name"],
                    phone_number=user_data["phone"],
                    is_active=True,
                    is_verified=True,
                )
                new_user.roles.append(role)
                session.add(new_user)
                print(f"[CREATED] Demo user: {email} ({role_name})")

        await session.commit()
        print("\nAll standard demo user accounts seeded successfully!")
        print(f"Default Password for all demo accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed_demo_users())
