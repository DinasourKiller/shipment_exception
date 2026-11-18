"""Unit tests for domain exception hierarchy."""

from app.core.exceptions import (
    AppException,
    BusinessRuleViolationException,
    EntityNotFoundException,
    ForbiddenException,
    IntegrationException,
    UnauthorizedException,
)


def test_exception_properties():
    """Verify exception hierarchy, status codes, and error codes."""
    exc1 = EntityNotFoundException("Shipment", "SHP-12345")
    assert exc1.status_code == 404
    assert exc1.code == "ENTITY_NOT_FOUND"
    assert exc1.details["identifier"] == "SHP-12345"

    exc2 = UnauthorizedException()
    assert exc2.status_code == 401
    assert exc2.code == "UNAUTHORIZED"

    exc3 = ForbiddenException()
    assert exc3.status_code == 403
    assert exc3.code == "FORBIDDEN"

    exc4 = BusinessRuleViolationException(
        message="Cannot split an already delivered shipment",
        rule="RULE_DELIVERY_FINALIZED",
    )
    assert exc4.status_code == 400
    assert exc4.details["rule"] == "RULE_DELIVERY_FINALIZED"

    exc5 = IntegrationException(
        integration_name="Mendix",
        message="Endpoint connection timed out",
    )
    assert exc5.status_code == 502
    assert "Mendix" in exc5.message
