# Changelog

All notable changes to the Shipment Exception Control Tower project will be documented here.

## [Unreleased]

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
