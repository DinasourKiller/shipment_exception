# Database Design

## Overview
The application uses **PostgreSQL** with **SQLAlchemy 2.x** and **Alembic** for schema migrations.

## Core Rules & Conventions
1. **Primary Keys:** UUID v4 for business entities to prevent enumeration attacks and support distributed generation.
2. **Timestamps:** Timezone-aware UTC timestamps (`created_at`, `updated_at`) on all persistent records.
3. **Foreign Keys & Indices:** Explicit foreign keys with appropriate cascading rules and indexes on lookup columns (e.g., `shipment_id`, `status`, `tracking_number`).
4. **Audit History:** Critical state changes (exceptions, recovery decisions, dispatch updates) maintain historical log tables.
5. **Domain Separation:** Each module owns its tables. Cross-module data integrity is managed at the service and transaction boundary layer.

## Base Mixins & ORM Specification (`app/database/base.py`)
- **`Base`**: Root `DeclarativeBase` generating lowercased table names by default with `.to_dict()` helper.
- **`UUIDPrimaryKeyMixin`**: Defines `id: Mapped[uuid.UUID]` with default `uuid.uuid4`, primary key, and indexed.
- **`TimestampMixin`**: Defines `created_at` and `updated_at` as timezone-aware `DateTime(timezone=True)` using UTC timestamps.

## Database Connection & Session Lifecycle (`app/database/connection.py`)
- Asynchronous SQLAlchemy 2.x engine initialized with `postgresql+asyncpg://`.
- Connection pooling with `pool_size`, `max_overflow`, `pool_timeout`, and `pool_pre_ping=True`.
- `get_db_session()` FastAPI dependency: commits transaction on success, rolls back on exception, and closes session on completion.
- `check_database_health()` executes lightweight `SELECT 1` with transaction rollback to continuously verify connectivity for container orchestrators.

## Implemented Tables & Schemas

### 1. `users` Table (Phase 3)
- `id`: UUID (Primary Key, default uuid.uuid4)
- `email`: VARCHAR(255), UNIQUE, NOT NULL, INDEXED
- `hashed_password`: VARCHAR(255), NOT NULL (Argon2id format)
- `full_name`: VARCHAR(255), NOT NULL
- `is_active`: BOOLEAN, NOT NULL, default TRUE
- `is_verified`: BOOLEAN, NOT NULL, default FALSE
- `failed_login_attempts`: INTEGER, NOT NULL, default 0
- `locked_until`: TIMESTAMP WITH TIME ZONE, NULLABLE
- `created_at`: TIMESTAMP WITH TIME ZONE, NOT NULL
- `updated_at`: TIMESTAMP WITH TIME ZONE, NOT NULL

### 2. `refresh_tokens` Table (Phase 3)
- `id`: UUID (Primary Key, default uuid.uuid4)
- `user_id`: UUID, FOREIGN KEY (`users.id`, ON DELETE CASCADE), NOT NULL, INDEXED
- `token_hash`: VARCHAR(64), UNIQUE, NOT NULL, INDEXED (SHA-256 digest of raw 64-char token)
- `expires_at`: TIMESTAMP WITH TIME ZONE, NOT NULL
- `is_revoked`: BOOLEAN, NOT NULL, default FALSE
- `revoked_at`: TIMESTAMP WITH TIME ZONE, NULLABLE
- `replaced_by_token_id`: UUID, NULLABLE (pointer to replacement token for reuse detection)
- `created_at`: TIMESTAMP WITH TIME ZONE, NOT NULL
- `updated_at`: TIMESTAMP WITH TIME ZONE, NOT NULL

### 3. `login_attempts` Table (Phase 3)
- `id`: UUID (Primary Key, default uuid.uuid4)
- `email`: VARCHAR(255), NOT NULL, INDEXED
- `ip_address`: VARCHAR(45), NULLABLE
- `user_agent`: VARCHAR(500), NULLABLE
- `success`: BOOLEAN, NOT NULL
- `failure_reason`: VARCHAR(255), NULLABLE
- `attempted_at`: TIMESTAMP WITH TIME ZONE, NOT NULL

### 4. `roles` Table (Phase 4)
- `id`: UUID (Primary Key, default uuid.uuid4)
- `name`: VARCHAR(100), UNIQUE, NOT NULL, INDEXED
- `description`: TEXT, NULLABLE
- `created_at`: TIMESTAMP WITH TIME ZONE, NOT NULL
- `updated_at`: TIMESTAMP WITH TIME ZONE, NOT NULL

### 5. `permissions` Table (Phase 4)
- `id`: UUID (Primary Key, default uuid.uuid4)
- `name`: VARCHAR(100), UNIQUE, NOT NULL, INDEXED
- `resource`: VARCHAR(50), NOT NULL, INDEXED
- `action`: VARCHAR(50), NOT NULL
- `description`: TEXT, NULLABLE
- `created_at`: TIMESTAMP WITH TIME ZONE, NOT NULL
- `updated_at`: TIMESTAMP WITH TIME ZONE, NOT NULL

### 6. `user_roles` Association Table (Phase 4)
- `user_id`: UUID, FOREIGN KEY (`users.id`, ON DELETE CASCADE), PRIMARY KEY
- `role_id`: UUID, FOREIGN KEY (`roles.id`, ON DELETE CASCADE), PRIMARY KEY

### 7. `role_permissions` Association Table (Phase 4)
- `role_id`: UUID, FOREIGN KEY (`roles.id`, ON DELETE CASCADE), PRIMARY KEY
- `permission_id`: UUID, FOREIGN KEY (`permissions.id`, ON DELETE CASCADE), PRIMARY KEY

## Migrations Engine (`app/database/migrations/`)
- Alembic configured for async migrations via `async_engine_from_config` in `app/database/migrations/env.py`.
- Migration templates output formatted revisions in UTC (`YYYYMMDD_HHMM_<rev>_<slug>.py`).

## Domain Entity Map

```mermaid
erDiagram
    USERS ||--o{ REFRESH_TOKENS : has
    USERS }o--o{ ROLES : assigned
    ROLES }o--o{ PERMISSIONS : contains
    
    SHIPMENTS ||--o{ SHIPMENT_TRACKING : logs
    SHIPMENTS ||--o{ EXCEPTIONS : incurs
    
    EXCEPTIONS ||--o{ IMPACT_ANALYSIS : evaluated_by
    EXCEPTIONS ||--o{ RECOVERY_REQUESTS : triggers
    EXCEPTIONS ||--o{ EXCEPTION_HISTORY : tracks
    
    RECOVERY_REQUESTS ||--o{ RECOVERY_ACTIONS : executes
    RECOVERY_REQUESTS }o--|| CARRIERS : routed_to
    
    CARRIERS ||--o{ VEHICLES : manages
    CARRIERS ||--o{ DRIVERS : employs
    
    SHIPMENTS ||--o{ SHIPMENT_PARTS : split_into
    SHIPMENTS ||--o{ DELIVERY_CONFIRMATIONS : concluded_by
```

*Detailed entity specifications and Alembic migrations will be generated systematically during Phase 2 and subsequent domain phases.*
