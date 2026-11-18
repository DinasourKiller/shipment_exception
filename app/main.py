"""Shipment Exception Control Tower - Main Application Entrypoint.

Initializes FastAPI application with middleware, exception handlers,
lifespan events, and core monitoring endpoints.
"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
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

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME} cleanly.")


def create_application() -> FastAPI:
    """Factory creating and configuring the primary FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Enterprise Shipment Exception Control Tower API. "
            "Monitors shipments, detects operational exceptions, calculates SLA/business impact, "
            "and orchestrates recovery workflows."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
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
        payload = HealthStatus(
            status="healthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            app_name=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT,
            components={
                "api": "healthy",
                "database": "configured",
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
    async def readiness_probe() -> dict[str, str]:
        # Ready checks can inspect database connectivity in Phase 2
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

    return app


app = create_application()
