"""Integration Tests for Notification & Alerting REST API.

Tests user notification feed, unread counters, mark-as-read, preference management,
operational alert broadcasts, and RBAC authorization guards.
"""

import uuid
import httpx
import pytest

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.database.connection import get_db_session
from app.main import create_application
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.notifications.models import Notification, NotificationPriority, NotificationStatus
from app.modules.roles.repository import RoleRepository


@pytest.fixture
async def notification_test_setup():
    """Sets up FastAPI test app with database entities and authenticated RBAC credentials."""
    app = create_application()
    transport = httpx.ASGITransport(app=app)

    async for session in get_db_session():
        auth_repo = AuthenticationRepository(session)
        role_repo = RoleRepository(session)

        # 1. Admin (has notifications:read, exceptions:manage)
        admin = User(
            email=f"notif_admin_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Notification Admin",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(admin)
        admin_role = await role_repo.get_role_by_name("System Administrator")
        assert admin_role is not None
        await role_repo.assign_role_to_user(admin.id, admin_role.id)

        # 2. Analyst (has notifications:read)
        analyst = User(
            email=f"notif_analyst_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("AnalystPass123!"),
            full_name="Notification Analyst",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(analyst)
        analyst_role = await role_repo.get_role_by_name("Control Tower Analyst")
        assert analyst_role is not None
        await role_repo.assign_role_to_user(analyst.id, analyst_role.id)

        # 3. Carrier Rep (lacks notifications:read)
        carrier_user = User(
            email=f"notif_carrier_{uuid.uuid4().hex[:6]}@controltower.corp",
            hashed_password=hash_password("CarrierPass123!"),
            full_name="Notification Carrier",
            is_active=True,
            is_verified=True,
        )
        await auth_repo.create_user(carrier_user)
        carrier_role = await role_repo.get_role_by_name("Carrier")
        assert carrier_role is not None
        await role_repo.assign_role_to_user(carrier_user.id, carrier_role.id)

        # Pre-seed notifications for admin
        n1 = Notification(
            id=uuid.uuid4(),
            recipient_id=admin.id,
            title="Cold chain breach",
            message="Temperature excursion logged on container ABC",
            priority=NotificationPriority.URGENT.value,
            status=NotificationStatus.SENT.value,
        )
        n2 = Notification(
            id=uuid.uuid4(),
            recipient_id=None,  # Broadcast
            title="System Maintenance Notice",
            message="Nightly database re-indexing at 02:00 UTC",
            priority=NotificationPriority.LOW.value,
            status=NotificationStatus.SENT.value,
        )
        session.add_all([n1, n2])
        await session.commit()

        admin_token = create_access_token(admin.id, admin.email, roles=["System Administrator"])
        analyst_token = create_access_token(analyst.id, analyst.email, roles=["Control Tower Analyst"])
        carrier_token = create_access_token(carrier_user.id, carrier_user.email, roles=["Carrier"])

        return {
            "app": app,
            "transport": transport,
            "admin_user": admin,
            "n1_id": n1.id,
            "n2_id": n2.id,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "analyst_headers": {"Authorization": f"Bearer {analyst_token}"},
            "carrier_headers": {"Authorization": f"Bearer {carrier_token}"},
        }


@pytest.mark.asyncio
async def test_list_notifications_feed(notification_test_setup):
    """Verify listing notifications returns user direct and broadcast alerts with unread count."""
    env = notification_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        resp = await client.get("/api/v1/notifications", headers=env["admin_headers"])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "items" in data
        assert data["total"] >= 2
        assert data["unread_count"] >= 2


@pytest.mark.asyncio
async def test_mark_as_read_and_mark_all(notification_test_setup):
    """Verify marking single notification as read and marking all as read."""
    env = notification_test_setup
    n1_id = env["n1_id"]

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Mark single notification as read
        read_resp = await client.patch(
            f"/api/v1/notifications/{n1_id}/read",
            headers=env["admin_headers"],
        )
        assert read_resp.status_code == 200
        assert read_resp.json()["data"]["status"] == "READ"
        assert read_resp.json()["data"]["read_at"] is not None

        # Mark all remaining notifications as read
        mark_all_resp = await client.post(
            "/api/v1/notifications/mark-all-read",
            headers=env["admin_headers"],
        )
        assert mark_all_resp.status_code == 200
        assert mark_all_resp.json()["data"]["marked_read_count"] >= 1


@pytest.mark.asyncio
async def test_notification_preferences_crud(notification_test_setup):
    """Verify retrieving and updating user delivery preferences."""
    env = notification_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Get defaults
        get_resp = await client.get("/api/v1/notifications/preferences", headers=env["admin_headers"])
        assert get_resp.status_code == 200
        pref = get_resp.json()["data"]
        assert pref["in_app_enabled"] is True
        assert pref["email_enabled"] is True

        # Update preferences
        update_resp = await client.put(
            "/api/v1/notifications/preferences",
            headers=env["admin_headers"],
            json={
                "email_enabled": False,
                "webhook_enabled": True,
                "webhook_url": "https://company.slack.com/services/hook/123",
                "min_priority": "HIGH",
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()["data"]
        assert updated["email_enabled"] is False
        assert updated["webhook_enabled"] is True
        assert updated["webhook_url"] == "https://company.slack.com/services/hook/123"
        assert updated["min_priority"] == "HIGH"


@pytest.mark.asyncio
async def test_broadcast_alert_endpoint(notification_test_setup):
    """Verify operators can broadcast operational alerts."""
    env = notification_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        broadcast_res = await client.post(
            "/api/v1/notifications/broadcast",
            headers=env["admin_headers"],
            json={
                "title": "Severe Weather Warning: Blizzard Alert",
                "message": "Heavy snowfall affecting Midwest transit corridor I-80. Expect 12+ hour delays.",
                "priority": "URGENT",
                "channel": "IN_APP",
            },
        )
        assert broadcast_res.status_code == 201
        alert = broadcast_res.json()["data"]
        assert alert["title"] == "Severe Weather Warning: Blizzard Alert"
        assert alert["recipient_id"] is None


@pytest.mark.asyncio
async def test_notification_rbac_enforcement(notification_test_setup):
    """Verify RBAC authorization prevents unauthorized actions."""
    env = notification_test_setup

    async with httpx.AsyncClient(transport=env["transport"], base_url="http://testserver") as client:
        # Carrier has notifications:read, so reading feed succeeds
        get_res = await client.get("/api/v1/notifications", headers=env["carrier_headers"])
        assert get_res.status_code == 200

        # Carrier lacks exceptions:manage -> 403 Forbidden on broadcast
        post_res = await client.post(
            "/api/v1/notifications/broadcast",
            headers=env["carrier_headers"],
            json={"title": "Unauthorized Alert", "message": "Broadcast attempt", "priority": "LOW"},
        )
        assert post_res.status_code == 403

        # Unauthenticated request -> 401 Unauthorized
        unauth_res = await client.get("/api/v1/notifications")
        assert unauth_res.status_code == 401
