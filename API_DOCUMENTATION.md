# API Documentation Standards

## General Conventions

- **Base Path:** `/api/v1`
- **Content Type:** `application/json`
- **Correlation ID:** Every request receives or generates an `X-Correlation-ID` header, returned in response headers and inside standard JSON envelopes.

## Standard Response Format

### Success Response Envelope
```json
{
  "success": true,
  "data": { ... },
  "message": "Optional human-readable notification",
  "correlation_id": "a93df7c01b..."
}
```

### Error Response Envelope
```json
{
  "success": false,
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Shipment with identifier 'SHP-90210' was not found.",
    "details": {
      "entity": "Shipment",
      "identifier": "SHP-90210"
    }
  },
  "correlation_id": "a93df7c01b..."
}
```

## Health & Diagnostic Endpoints (Phase 1)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Comprehensive system health and subsystem status |
| `GET` | `/health/live` | Liveness check for Kubernetes/Docker container monitoring |
| `GET` | `/health/ready` | Readiness check (verifies database & external dependencies) |
| `GET` | `/api/v1/ping` | Versioned sanity ping |

## Authentication Endpoints (Phase 3)

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | None | Authenticates user; returns RS256 JWT access token in JSON body and sets `refresh_token` in an HttpOnly, Secure, SameSite cookie. |
| `POST` | `/api/v1/auth/refresh` | Cookie (`refresh_token`) | Rotates opaque refresh token; detects token reuse attacks and revokes all active sessions if an already rotated token is replayed. |
| `POST` | `/api/v1/auth/logout` | Cookie (`refresh_token`) | Revokes the refresh token record in PostgreSQL and clears the cookie. |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Returns current authenticated user profile (`id`, `email`, `full_name`, `is_active`, `is_verified`). |
| `POST` | `/api/v1/auth/change-password` | Bearer JWT | Changes password (Argon2id) and terminates all active sessions. |
| `POST` | `/api/v1/auth/forgot-password` | None | Generic endpoint initiating password reset without user enumeration. |

## Roles & Permissions Endpoints (Phase 4)

| Method | Endpoint | Required Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/roles` | `roles:read` | Lists all roles with assigned permissions. |
| `GET` | `/api/v1/roles/permissions` | `roles:read` | Lists all available granular system permissions. |
| `POST` | `/api/v1/roles` | `roles:manage` | Creates a new role with assigned permissions. |
| `POST` | `/api/v1/roles/assign/{user_id}` | `users:manage` | Assigns roles to an existing user. |
| `DELETE` | `/api/v1/roles/assign/{user_id}/{role_id}` | `users:manage` | Revokes a role assignment from an existing user. |

## User Management Endpoints (Phase 5)

| Method | Endpoint | Required Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/users` | `users:read` | Lists users with pagination (`page`, `page_size`), search filter (`search` by name or email), active status (`is_active`), and role name filter (`role`). |
| `POST` | `/api/v1/users` | `users:manage` | Creates a new user with optional role assignments, phone number, and Argon2id hashed password. |
| `GET` | `/api/v1/users/{user_id}` | `users:read` | Retrieves full profile and assigned roles for a specific user. |
| `PUT` | `/api/v1/users/{user_id}` | `users:manage` | Updates profile details (full name, phone number). |
| `PATCH` | `/api/v1/users/{user_id}/status` | `users:manage` | Activates or deactivates user account. Deactivation immediately invalidates all active sessions/refresh tokens. |
| `PUT` | `/api/v1/users/{user_id}/roles` | `users:manage` | Synchronizes user roles (replaces existing assignments with provided set). |
| `POST` | `/api/v1/users/{user_id}/reset-password` | `users:manage` | Administrative password reset. Updates password and revokes all active user sessions. |

## Mendix Sandbox & Integration Simulation Endpoints (Phase 6)

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| `GET` | `/api/v1/mock/mendix/health` | None | Simulates Mendix REST API health check. |
| `GET` | `/api/v1/mock/mendix/shipments/{ref}` | `X-API-Key` | Simulates Mendix single shipment retrieval by external reference ID. |
| `GET` | `/api/v1/mock/mendix/shipments` | `X-API-Key` | Simulates Mendix batch shipment polling (`updatedSince`, `limit`). |
| `POST` | `/api/v1/mock/mendix/shipments/{ref}/exceptions` | `X-API-Key` | Simulates Mendix receiving operational exception notifications and recovery actions. |

## Shipment Management Endpoints (Phase 7)

| Method | Endpoint | Required Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/shipments` | `shipments:read` | Paginated list of shipments with search (`search`), filters (`status`, `carrier_code`, `transport_mode`, `origin_city`, `destination_city`, date range). |
| `GET` | `/api/v1/shipments/{shipment_id}` | `shipments:read` | Full detailed shipment profile including parties, cargo items, and milestones. |
| `POST` | `/api/v1/shipments/sync/{external_reference}` | `shipments:write` | Ingests or synchronizes a single shipment on-demand from Mendix into PostgreSQL. |
| `POST` | `/api/v1/shipments/sync` | `shipments:write` | Triggers batch polling synchronization of updated shipments from Mendix. |
| `PATCH` | `/api/v1/shipments/{shipment_id}/status` | `shipments:write` | Transitions operational lifecycle status with state machine enforcement. |

*Domain endpoints will be documented as their respective phases are implemented.*
