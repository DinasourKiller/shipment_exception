# Database Design

## Overview
The application uses **PostgreSQL** with **SQLAlchemy 2.x** and **Alembic** for schema migrations.

## Core Rules & Conventions
1. **Primary Keys:** UUID v4 for business entities to prevent enumeration attacks and support distributed generation.
2. **Timestamps:** Timezone-aware UTC timestamps (`created_at`, `updated_at`) on all persistent records.
3. **Foreign Keys & Indices:** Explicit foreign keys with appropriate cascading rules and indexes on lookup columns (e.g., `shipment_id`, `status`, `tracking_number`).
4. **Audit History:** Critical state changes (exceptions, recovery decisions, dispatch updates) maintain historical log tables.
5. **Domain Separation:** Each module owns its tables. Cross-module data integrity is managed at the service and transaction boundary layer.

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
