"""Shipment Exception Control Tower - Main Application Entrypoint.

Initializes FastAPI application with middleware, exception handlers,
lifespan events, and core monitoring endpoints.
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.common.constants import CORRELATION_ID_HEADER
from app.common.schemas import ApiResponse, HealthStatus
from app.config import get_settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import (
    get_correlation_id,
    get_logger,
    set_correlation_id,
    setup_logging,
)
from app.database.connection import check_database_health
from app.integrations.mendix.sandbox import sandbox_router
from app.modules.authentication.router import router as auth_router
from app.modules.roles.router import router as roles_router
from app.modules.shipments.router import router as shipments_router
from app.modules.tracking.router import router as tracking_router
from app.modules.users.router import router as users_router

settings = get_settings()
logger = get_logger("control_tower.main")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to inject or propagate request correlation IDs and measure request latency."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract existing correlation ID or generate new UUID4
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or uuid.uuid4().hex
        set_correlation_id(correlation_id)

        start_time = time.perf_counter()

        response = await call_next(request)

        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        response.headers["X-Response-Time-Ms"] = str(process_time_ms)

        # Do not log healthcheck polling in access log to keep logs clean
        if not request.url.path.startswith("/health"):
            logger.info(
                f"{request.method} {request.url.path} returned {response.status_code} in {process_time_ms}ms"
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    # Startup
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} "
        f"[Environment: {settings.ENVIRONMENT}, Debug: {settings.DEBUG}]"
    )

    # Test database connectivity
    db_healthy, db_detail = await check_database_health()
    if db_healthy:
        logger.info("Database connection established successfully.")
    else:
        logger.warning(f"Database connection warning on startup: {db_detail}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME} cleanly.")


OPENAPI_TAGS = [
    {
        "name": "System Diagnostics",
        "description": "Liveness probes, readiness probes, and comprehensive system health diagnostics.",
    },
    {
        "name": "Authentication",
        "description": "User authentication, RS256 JWT access tokens, HttpOnly refresh cookies with reuse detection, and session management.",
    },
    {
        "name": "Roles & RBAC",
        "description": "Role-Based Access Control: enterprise roles, granular permissions, and dynamic role assignments.",
    },
    {
        "name": "User Management",
        "description": "User CRUD, paginated search and filtering, status toggling with immediate session invalidation, and password resets.",
    },
    {
        "name": "Shipment Management",
        "description": "Shipment operational records, Mendix ingestion pipeline, tracking milestones, and status lifecycle management.",
    },
    {
        "name": "Tracking & Milestones",
        "description": "Real-time physical scan events, GPS telemetry pings, automated milestone progression, and dynamic delivery ETA recalculation.",
    },
    {
        "name": "Mendix Sandbox",
        "description": "Simulated Mendix REST API endpoints for external shipment ingestion and operational exception synchronization.",
    },
]

SWAGGER_DESCRIPTION = """
### Enterprise Shipment Exception Control Tower API

The Central Operations Platform for multi-modal logistics tracking, real-time exception detection, 
SLA/financial impact assessment, and automated recovery orchestration.

---

### Demo User Accounts for Interactive Testing
Authenticate via `POST /api/v1/auth/login` using any of the seeded enterprise accounts:

| Role | Email | Password | Scope |
|---|---|---|---|
| **System Administrator** | `admin@controltower.corp` | `Password123!` | Full unrestricted access |
| **Control Tower Analyst** | `analyst@controltower.corp` | `Password123!` | Shipments, Exceptions, Recovery |
| **Dispatcher / Planner** | `dispatcher@controltower.corp` | `Password123!` | Shipments, Dispatch, Resource Allocation |
| **Operations Manager** | `manager@controltower.corp` | `Password123!` | Management, Escalations, Approvals |
| **Carrier** | `carrier@controltower.corp` | `Password123!` | Carrier Recovery Responses |

#### How to Authorize in Swagger UI:
1. Call `POST /api/v1/auth/login` with your desired role credentials.
2. Copy the `access_token` from the response.
3. Click the green **Authorize** button (top right of this page).
4. Enter `Bearer <your_access_token>` in the dialog and click **Authorize**.
5. Your authorization token is automatically persisted in your browser (`persistAuthorization: true`).
"""


def create_application() -> FastAPI:
    """Factory creating and configuring the primary FastAPI application."""
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description=SWAGGER_DESCRIPTION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
            "docExpansion": "list",
            "defaultModelsExpandDepth": 1,
        },
        lifespan=lifespan,
    )

    # Middleware Configuration
    app.add_middleware(CorrelationIdMiddleware)

    # Configure CORS
    allowed_origins = (
        settings.ALLOWED_ORIGINS
        if isinstance(settings.ALLOWED_ORIGINS, list)
        else [settings.ALLOWED_ORIGINS]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Health & Diagnostics Endpoints
    @app.get(
        "/health",
        response_model=ApiResponse[HealthStatus],
        tags=["System Diagnostics"],
        summary="Comprehensive system health check",
    )
    async def health_check() -> ApiResponse[HealthStatus]:
        db_healthy, db_detail = await check_database_health()
        overall_status = "healthy" if db_healthy else "degraded"

        payload = HealthStatus(
            status=overall_status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            app_name=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT,
            components={
                "api": "healthy",
                "database": "healthy" if db_healthy else f"unhealthy: {db_detail}",
                "mendix_adapter": "configured",
                "ai_provider": "configured",
            },
        )
        return ApiResponse(
            success=True,
            data=payload,
            correlation_id=get_correlation_id(),
        )

    @app.get(
        "/health/live",
        status_code=status.HTTP_200_OK,
        tags=["System Diagnostics"],
        summary="Kubernetes / Docker Liveness probe",
    )
    async def liveness_probe() -> dict[str, str]:
        return {"status": "live"}

    @app.get(
        "/health/ready",
        status_code=status.HTTP_200_OK,
        tags=["System Diagnostics"],
        summary="Kubernetes / Docker Readiness probe",
    )
    async def readiness_probe(response: Response) -> dict[str, str]:
        db_healthy, db_detail = await check_database_health()
        if not db_healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unhealthy", "reason": f"Database unavailable: {db_detail}"}
        return {"status": "ready"}

    @app.get(
        f"{settings.API_V1_PREFIX}/ping",
        response_model=ApiResponse[dict[str, str]],
        tags=["System Diagnostics"],
        summary="Sanity ping endpoint",
    )
    async def ping() -> ApiResponse[dict[str, str]]:
        return ApiResponse(
            success=True,
            data={"message": "pong"},
            correlation_id=get_correlation_id(),
        )

    # Register Business Domain Routers
    app.include_router(
        auth_router,
        prefix=f"{settings.API_V1_PREFIX}/auth",
        tags=["Authentication"],
    )
    app.include_router(
        roles_router,
        prefix=f"{settings.API_V1_PREFIX}/roles",
        tags=["Roles & RBAC"],
    )
    app.include_router(
        users_router,
        prefix=f"{settings.API_V1_PREFIX}/users",
        tags=["User Management"],
    )
    app.include_router(
        shipments_router,
        prefix=f"{settings.API_V1_PREFIX}/shipments",
        tags=["Shipment Management"],
    )
    app.include_router(
        tracking_router,
        prefix=f"{settings.API_V1_PREFIX}/tracking",
        tags=["Tracking & Milestones"],
    )
    app.include_router(
        sandbox_router,
        prefix=settings.API_V1_PREFIX,
    )

    # Web Testing Console routes
    @app.get("/console", response_class=FileResponse, include_in_schema=False)
    @app.get("/ui", response_class=FileResponse, include_in_schema=False)
    @app.get("/test", response_class=FileResponse, include_in_schema=False)
    async def serve_testing_console():
        index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
        return FileResponse(index_path)

    # Convenience Redirects to Swagger UI
    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/console")

    @app.get("/docs", include_in_schema=False)
    async def docs_redirect():
        return RedirectResponse(url=f"{settings.API_V1_PREFIX}/docs")

    @app.get("/redoc", include_in_schema=False)
    async def redoc_redirect():
        return RedirectResponse(url=f"{settings.API_V1_PREFIX}/redoc")

    return app


app = create_application()
