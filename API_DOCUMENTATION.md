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

*Domain endpoints will be documented as their respective phases are implemented.*
