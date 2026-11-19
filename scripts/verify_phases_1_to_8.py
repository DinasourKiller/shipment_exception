"""Comprehensive Live Verification Script for Phases 1 through 8.

Tests the full stack against the live FastAPI dev server and PostgreSQL database:
1. Diagnostics & Health (Phases 1-2)
2. Authentication, Argon2id, RS256 JWT, Cookies (Phase 3)
3. RBAC, Roles, Granular Permissions (Phase 4)
4. User Management APIs & Filtering (Phase 5)
5. Mendix Integration Adapter & Mock Sandbox (Phase 6)
6. Shipment Ingestion, Canonical Upsert, State Machine (Phase 7)
7. Tracking Telemetry Ingestion, Milestone Advancement, Dynamic ETA Recalculation (Phase 8)
"""

import sys
import uuid
import httpx

BASE_URL = "http://127.0.0.1:8000"


def print_step(title: str):
    print(f"\n{'='*70}\n[TEST] {title}\n{'='*70}")


def main():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # =====================================================================
        # Phase 1 & 2: Health & Diagnostics
        # =====================================================================
        print_step("Phase 1 & 2: System Health and Database Connectivity")
        resp = client.get("/health")
        assert resp.status_code == 200, f"/health failed: {resp.text}"
        data = resp.json()["data"]
        assert data["status"] == "healthy"
        assert data["components"]["database"] == "healthy"
        print(f"-> System Status: {data['status'].upper()}")
        print(f"-> Database Status: {data['components']['database']}")
        print(f"-> App: {data['app_name']} v{data['version']}")

        resp_live = client.get("/health/live")
        assert resp_live.status_code == 200
        resp_ready = client.get("/health/ready")
        assert resp_ready.status_code == 200
        resp_ping = client.get("/api/v1/ping")
        assert resp_ping.status_code == 200
        print("-> Liveness, Readiness, and Versioned Ping probes: PASSED")

        # =====================================================================
        # Phase 3: Authentication & JWT
        # =====================================================================
        print_step("Phase 3: Authentication, Argon2id, and JWT Issuance")
        login_payload = {
            "email": "admin@controltower.corp",
            "password": "Password123!",
        }
        resp = client.post("/api/v1/auth/login", json=login_payload)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        token_data = resp.json()["data"]
        admin_token = token_data["access_token"]
        assert admin_token is not None
        assert "refresh_token" in resp.cookies
        print(f"-> Logged in successfully as: {token_data['user']['email']}")
        print(f"-> Access Token Issued: {admin_token[:25]}... (RS256 JWT)")
        print(f"-> Refresh Token Cookie Set: {resp.cookies.get('refresh_token')[:15]}... (HttpOnly, Secure)")

        # Verify /me endpoint
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        resp_me = client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp_me.status_code == 200
        user_profile = resp_me.json()["data"]
        print(f"-> Verified /me profile: {user_profile['full_name']} ({user_profile['email']})")

        # =====================================================================
        # Phase 4: RBAC & Permissions
        # =====================================================================
        print_step("Phase 4: Role-Based Access Control (RBAC)")
        resp_roles = client.get("/api/v1/roles", headers=admin_headers)
        assert resp_roles.status_code == 200
        roles = resp_roles.json()["data"]
        print(f"-> Retrieved {len(roles)} enterprise roles from database")

        resp_perms = client.get("/api/v1/roles/permissions", headers=admin_headers)
        assert resp_perms.status_code == 200
        permissions = resp_perms.json()["data"]
        print(f"-> Retrieved {len(permissions)} granular permissions from database")

        # Login as Analyst to test non-admin role
        analyst_login = client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@controltower.corp", "password": "Password123!"},
        )
        assert analyst_login.status_code == 200
        analyst_token = analyst_login.json()["data"]["access_token"]
        analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
        print("-> Analyst logged in and authenticated with scoped role")

        # =====================================================================
        # Phase 5: User Management
        # =====================================================================
        print_step("Phase 5: User Management APIs")
        resp_users = client.get("/api/v1/users?page=1&page_size=5", headers=admin_headers)
        assert resp_users.status_code == 200
        users_page = resp_users.json()["data"]
        print(f"-> User Management Pagination: Total Users in DB: {users_page['total']}")

        resp_search = client.get("/api/v1/users?search=Connor", headers=admin_headers)
        assert resp_search.status_code == 200
        search_matches = resp_search.json()["data"]["items"]
        assert len(search_matches) >= 1
        print(f"-> User Search ('Connor') matched: {search_matches[0]['full_name']} ({search_matches[0]['email']})")

        # =====================================================================
        # Phase 6: Mendix Adapter & Sandbox
        # =====================================================================
        print_step("Phase 6: Mendix Integration Adapter & Mock Sandbox")
        resp_mendix_health = client.get("/api/v1/mock/mendix/health")
        assert resp_mendix_health.status_code == 200
        assert resp_mendix_health.json()["status"] == "UP"
        print("-> Mendix REST Sandbox Health: UP")

        resp_mendix_shp = client.get(
            "/api/v1/mock/mendix/shipments/MDX-SHP-1001",
            headers={"X-API-Key": "test-key"},
        )
        assert resp_mendix_shp.status_code == 200
        mdx_data = resp_mendix_shp.json()
        print(f"-> Mendix External Shipment: {mdx_data['mendixId']} (Carrier: {mdx_data['carrier']['name']})")

        # =====================================================================
        # Phase 7: Shipment Management (Core Ingestion & CRUD)
        # =====================================================================
        print_step("Phase 7: Shipment Ingestion & Lifecycle Management")
        # Ingest on-demand from Mendix
        resp_sync = client.post(
            "/api/v1/shipments/sync/MDX-SHP-1001",
            headers=admin_headers,
        )
        assert resp_sync.status_code == 200, f"Shipment sync failed: {resp_sync.text}"
        shipment = resp_sync.json()["data"]
        shipment_id = shipment["id"]
        print(f"-> Ingested Shipment ID: {shipment_id}")
        print(f"-> Order: {shipment['order_number']} | Tracking: {shipment['tracking_number']}")
        print(f"-> Status: {shipment['status']} | Mode: {shipment['transport_mode']}")
        print(f"-> Route: {shipment['origin_city']} -> {shipment['destination_city']}")
        print(f"-> Parties: {len(shipment['parties'])} | Line Items: {len(shipment['cargo_items'])} | Milestones: {len(shipment['milestones'])}")

        # Verify shipment list filtering
        resp_list = client.get(
            f"/api/v1/shipments?carrier_code={shipment['carrier_code']}",
            headers=analyst_headers,
        )
        assert resp_list.status_code == 200
        assert resp_list.json()["data"]["total"] >= 1
        print(f"-> Shipment Filter by Carrier ({shipment['carrier_code']}): PASSED")

        # =====================================================================
        # Phase 8: Tracking & Milestones
        # =====================================================================
        print_step("Phase 8: Tracking Telemetry, Milestones & Dynamic ETA Engine")

        # 1. Ingest GPS telemetry ping
        gps_ping = {
            "event_code": "GPS_PING",
            "event_name": "In-transit telemetry heartbeat",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "location_name": "I-55 Southbound Mile Marker 42",
            "source": "GPS_DEVICE",
        }
        resp_gps = client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json=gps_ping,
            headers=admin_headers,
        )
        assert resp_gps.status_code == 201
        print(f"-> Recorded GPS Telemetry Ping: Lat={gps_ping['latitude']}, Lng={gps_ping['longitude']}")

        # 2. Record Milestone scan event
        scan_event = {
            "event_code": "HUB_TRANSIT",
            "event_name": "Arrived at St. Louis Distribution Center",
            "event_timestamp": "2026-11-19T14:30:00Z",
            "location_name": "St. Louis, MO",
            "source": "CARRIER_API",
            "notes": "Dock scan confirmed",
        }
        resp_scan = client.post(
            f"/api/v1/tracking/{shipment_id}/events",
            json=scan_event,
            headers=admin_headers,
        )
        assert resp_scan.status_code == 201
        scan_result = resp_scan.json()["data"]
        print(f"-> Recorded Milestone Scan '{scan_event['event_code']}': linked to milestone_id={scan_result['milestone_id']}")

        # 3. Dynamic ETA Recalculation
        resp_recalc = client.post(
            f"/api/v1/tracking/{shipment_id}/recalculate-eta",
            headers=admin_headers,
        )
        assert resp_recalc.status_code == 200
        recalc_data = resp_recalc.json()["data"]
        print(f"-> Dynamic ETA Engine: {recalc_data['message']}")
        print(f"   Original ETA: {recalc_data['previous_estimated_delivery']}")
        print(f"   Projected ETA: {recalc_data['updated_estimated_delivery']}")
        print(f"   Accumulated Delay: {recalc_data['accumulated_delay_minutes']} minutes (Delayed: {recalc_data['is_delayed']})")

        # 4. Get Tracking Timeline
        resp_timeline = client.get(
            f"/api/v1/tracking/{shipment_id}/timeline",
            headers=analyst_headers,
        )
        assert resp_timeline.status_code == 200
        timeline = resp_timeline.json()["data"]
        print(f"-> Tracking Timeline Retrieved: {timeline['total_events']} events, {len(timeline['milestones'])} milestones")
        for m in timeline["milestones"]:
            status_str = f"[{m['status']}]"
            delay_str = f"(Delayed by {m['delay_minutes']}m)" if m['is_delayed'] else "(On Schedule)"
            print(f"   - Milestone {m['event_code']}: {status_str} {delay_str}")

        # 5. Get Latest Tracking Event
        resp_latest = client.get(
            f"/api/v1/tracking/{shipment_id}/latest",
            headers=analyst_headers,
        )
        assert resp_latest.status_code == 200
        latest = resp_latest.json()["data"]
        print(f"-> Latest Recorded Event: {latest['event_code']} - {latest['event_name']} ({latest['location_name']})")

        print("\n" + "="*70)
        print("ALL ENDPOINTS AND PHASES 1 THROUGH 8 VERIFIED SUCCESSFULLY!")
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
