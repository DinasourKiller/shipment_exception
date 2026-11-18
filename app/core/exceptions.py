"""Core Exceptions and Global Exception Handlers.

Defines the enterprise exception hierarchy and FastAPI exception handlers
to ensure all error responses follow a standardized, predictable format.
"""

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_correlation_id, get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """Base application exception for domain and business logic errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class EntityNotFoundException(AppException):
    """Raised when an entity is not found in the database."""

    def __init__(self, entity_name: str, identifier: Any) -> None:
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="ENTITY_NOT_FOUND",
            details={"entity": entity_name, "identifier": str(identifier)},
        )


class UnauthorizedException(AppException):
    """Raised when authentication fails or is missing."""

    def __init__(self, message: str = "Authentication required or invalid credentials.") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
        )


class ForbiddenException(AppException):
    """Raised when authenticated user lacks required permissions."""

    def __init__(self, message: str = "Access forbidden for current user permissions.") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )


class ConflictException(AppException):
    """Raised on unique constraint or state conflict."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            details=details,
        )


class BusinessRuleViolationException(AppException):
    """Raised when an operation violates an explicit operational/business rule."""

    def __init__(self, message: str, rule: str, details: Optional[Dict[str, Any]] = None) -> None:
        payload = details or {}
        payload["rule"] = rule
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BUSINESS_RULE_VIOLATION",
            details=payload,
        )


class IntegrationException(AppException):
    """Raised when an external integration (e.g. Mendix, SAP) fails or times out."""

    def __init__(self, integration_name: str, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(
            message=f"Integration error ({integration_name}): {message}",
            status_code=status_code,
            code="INTEGRATION_ERROR",
            details={"integration": integration_name},
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    correlation_id = get_correlation_id()
    logger.warning(
        f"Application exception: {exc.code} - {exc.message}",
        extra={"status_code": exc.status_code, "code": exc.code, "details": exc.details},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "correlation_id": correlation_id,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic request validation errors."""
    correlation_id = get_correlation_id()
    formatted_errors = []
    for error in exc.errors():
        formatted_errors.append(
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )

    logger.info("Request validation failed", extra={"errors": formatted_errors})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": {"errors": formatted_errors},
            },
            "correlation_id": correlation_id,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled server exceptions."""
    correlation_id = get_correlation_id()
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact system support.",
                "details": {},
            },
            "correlation_id": correlation_id,
        },
    )
