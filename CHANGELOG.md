# Changelog

All notable changes to the Shipment Exception Control Tower project will be documented here.

## [Unreleased]

## [0.4.0] - 2026-11-19
### Added
- **PHASE 4 - Authorization & Role-Based Access Control (RBAC):**
  - Implemented `app/modules/roles/models.py`: `Role`, `Permission`, and association tables `user_roles` and `role_permissions` with CASCADE foreign keys and unique constraints.
  - Linked `User.roles` relationship in `app/modules/authentication/models.py`.
  - Generated and applied Alembic migration `fbe3df102447_create_rbac_tables.py` creating RBAC tables in PostgreSQL.
  - Created `scripts/seed_rbac.py` seeding 19 granular permissions and 7 standard enterprise roles (`System Administrator`, `Control Tower Analyst`, `Dispatcher / Planner`, `Operations Manager`, `Carrier`, `Warehouse Supervisor`, `Customer Service`).
  - Implemented `app/core/permissions.py`:
    - `require_permissions(*permissions)`: Enforces user permissions with automatic `System Administrator` bypass.
    - `require_roles(*roles)`: Enforces role membership.
  - Updated JWT token issuance to embed user roles in token claims.
  - Implemented `app/modules/roles/router.py`:
    - `GET /api/v1/roles` (List all roles)
    - `GET /api/v1/roles/permissions` (List all permissions)
    - `POST /api/v1/roles` (Create custom role)
    - `POST /api/v1/roles/assign/{user_id}` (Assign roles to user)
    - `DELETE /api/v1/roles/assign/{user_id}/{role_id}` (Revoke role from user)
  - Added unit tests for RBAC models (`tests/unit/test_roles_models.py`).
  - Added security integration tests covering authorization, forbidden access (403), admin bypass, and role assignment lifecycle (`tests/security/test_rbac_api.py`).
  - Verified 35/35 automated tests passing across the entire test suite.

## [0.3.0] - 2026-11-19
### Added
- **PHASE 3 - Authentication & Session Security:**
  - Implemented `app/core/security.py` with Argon2id password hashing, verification, rehashing check, and cryptographic opaque token generation with SHA-256 digest hashing.
  - Implemented `scripts/generate_keys.py` for asymmetric 2048-bit RSA key generation (`keys/jwt-private.pem` & `keys/jwt-public.pem`).
  - Implemented `app/core/jwt.py` providing short-lived (15 min) RS256 JWT access token generation and strict claim validation (`iss`, `aud`, `exp`, `jti`, `sub`, `type`).
  - Implemented database models in `app/modules/authentication/models.py`: `User`, `RefreshToken`, and `LoginAttempt`.
  - Created and applied Alembic migration `6b3639b97799_create_auth_tables.py`, creating `users`, `refresh_tokens`, and `login_attempts` tables in PostgreSQL.
  - Implemented `app/modules/authentication/repository.py` for encapsulated database access.
  - Implemented `app/modules/authentication/service.py` with lockout rules after 5 failed attempts, single-use refresh token rotation, and automatic token reuse attack detection (revoking all sessions).
  - Implemented authentication endpoints in `app/modules/authentication/router.py`:
    - `POST /api/v1/auth/login` (sets HttpOnly, SameSite, Secure refresh cookie)
    - `POST /api/v1/auth/refresh` (single-use rotation)
    - `POST /api/v1/auth/logout` (session revocation & cookie clearing)
    - `GET /api/v1/auth/me` (current authenticated user profile)
    - `POST /api/v1/auth/change-password`
    - `POST /api/v1/auth/forgot-password`
  - Added unit tests for Argon2id and JWT verification (`tests/unit/test_security.py`, `tests/unit/test_jwt.py`).
  - Added security integration tests covering login, token verification, rotation, replay attack reuse detection, and logout (`tests/security/test_auth_api.py`).
  - Verified 27/27 automated tests passing across entire test suite.

## [0.2.0] - 2026-11-19
### Added
- **PHASE 2 - Database Foundation:**
  - Configured SQLAlchemy 2.x asynchronous engine with connection pooling and `pool_pre_ping`.
  - Implemented `app/database/connection.py` providing `get_db_session()` async generator and `check_database_health()`.
  - Implemented `app/database/base.py` declarative `Base`, `UUIDPrimaryKeyMixin` (UUIDv4), and `TimestampMixin` (timezone-aware UTC `created_at` and `updated_at`).
  - Configured Alembic with `alembic.ini` and `app/database/migrations/env.py` for asynchronous migrations.
  - Updated `/health` and `/health/ready` endpoints in `app/main.py` with live PostgreSQL health checks and readiness probes.
  - Added unit tests for database base and mixins (`tests/unit/test_database_base.py`).
  - Added integration tests for async session lifecycle, queries, and rollbacks (`tests/integration/test_database_session.py`).
  - Verified 16/16 automated tests passing against live PostgreSQL database.

## [0.1.0] - 2026-11-18
### Added
- **PHASE 1 - Project Foundation:**
  - Initialized FastAPI modular architecture with custom lifespan manager.
  - Implemented environment-driven configuration management via `pydantic-settings` (`app/config.py`).
  - Implemented structured JSON and text logging with correlation ID tracing (`app/core/logging.py`).
  - Added enterprise custom exception hierarchy and standardized FastAPI error handlers (`app/core/exceptions.py`).
  - Added request correlation ID middleware (`X-Correlation-ID`) and performance timing header (`X-Response-Time-Ms`).
  - Added health diagnostics endpoints (`/health`, `/health/live`, `/health/ready`, `/api/v1/ping`).
  - Added common enums, schemas, and API response wrappers (`app/common/`).
  - Created multi-stage `Dockerfile`, `.dockerignore`, and `docker-compose.yml` for PostgreSQL and API services.
  - Created initial documentation files: `README.md`, `ARCHITECTURE.md`, `DATABASE_DESIGN.md`, `API_DOCUMENTATION.md`, `IMPLEMENTATION_PROGRESS.md`, `CHANGELOG.md`.
  - Added comprehensive automated test suite for Phase 1.
