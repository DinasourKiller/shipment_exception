"""Integration Exceptions Hierarchy.

Standardized exceptions raised across all external system integration adapters
(Mendix, SAP, TMS, GPS, Carriers).
"""

from typing import Any, Dict, Optional
from app.core.exceptions import AppException


class IntegrationException(AppException):
    """Base exception for all external integration failures."""

    def __init__(
        self,
        message: str,
        system_name: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 502,
    ):
        super().__init__(
            message=f"[{system_name}] {message}",
            status_code=status_code,
            details={"system": system_name, **(details or {})},
        )
        self.system_name = system_name


class IntegrationConnectionException(IntegrationException):
    """Raised when an external system is unreachable or drops connection."""

    def __init__(self, system_name: str, message: str = "Connection failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            system_name=system_name,
            details=details,
            status_code=503,
        )


class IntegrationTimeoutException(IntegrationException):
    """Raised when an external system request exceeds configured timeout threshold."""

    def __init__(self, system_name: str, timeout_seconds: float, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Request timed out after {timeout_seconds}s",
            system_name=system_name,
            details={"timeout_seconds": timeout_seconds, **(details or {})},
            status_code=504,
        )


class IntegrationAuthenticationException(IntegrationException):
    """Raised when credentials (API Key, OAuth token) are rejected by external system."""

    def __init__(self, system_name: str, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            system_name=system_name,
            details=details,
            status_code=502,
        )


class IntegrationDataMappingException(IntegrationException):
    """Raised when payload from external system cannot be transformed into canonical domain model."""

    def __init__(self, system_name: str, message: str, raw_payload: Optional[Any] = None):
        super().__init__(
            message=f"Data transformation error: {message}",
            system_name=system_name,
            details={"raw_payload_preview": str(raw_payload)[:300] if raw_payload is not None else None},
            status_code=422,
        )
