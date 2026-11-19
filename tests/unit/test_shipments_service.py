"""Unit Tests for Shipment Service and State Machine Rules."""

import pytest
from app.core.exceptions import ValidationException
from app.modules.shipments.schemas import ShipmentStatusUpdateRequest
from app.modules.shipments.service import ALLOWED_TRANSITIONS, ShipmentService


def test_shipment_status_update_schema():
    """Verify validation of status update request payload."""
    req = ShipmentStatusUpdateRequest(status="IN_TRANSIT", notes="En route to Chicago hub")
    assert req.status == "IN_TRANSIT"
    assert req.notes == "En route to Chicago hub"
    assert req.actual_delivery is None


def test_state_machine_allowed_transitions():
    """Verify valid transitions execute without exception."""
    service = ShipmentService(repository=None, mendix_client=None)

    # CREATED -> BOOKED
    service.validate_status_transition("CREATED", "BOOKED")
    # BOOKED -> PICKED_UP
    service.validate_status_transition("BOOKED", "PICKED_UP")
    # PICKED_UP -> IN_TRANSIT
    service.validate_status_transition("PICKED_UP", "IN_TRANSIT")
    # IN_TRANSIT -> OUT_FOR_DELIVERY
    service.validate_status_transition("IN_TRANSIT", "OUT_FOR_DELIVERY")
    # OUT_FOR_DELIVERY -> DELIVERED
    service.validate_status_transition("OUT_FOR_DELIVERY", "DELIVERED")
    # IN_TRANSIT -> DELAYED
    service.validate_status_transition("IN_TRANSIT", "DELAYED")
    # DELAYED -> IN_TRANSIT
    service.validate_status_transition("DELAYED", "IN_TRANSIT")
    # Same state is a no-op
    service.validate_status_transition("IN_TRANSIT", "IN_TRANSIT")


def test_state_machine_illegal_transition_raises_validation_exception():
    """Verify skipping mandatory lifecycle states raises ValidationException."""
    service = ShipmentService(repository=None, mendix_client=None)

    # CREATED directly to DELIVERED is illegal
    with pytest.raises(ValidationException) as exc_info:
        service.validate_status_transition("CREATED", "DELIVERED")
    assert "Invalid status transition from 'CREATED' to 'DELIVERED'" in str(exc_info.value)

    # BOOKED directly to IN_TRANSIT is illegal (must be picked up first)
    with pytest.raises(ValidationException) as exc_info:
        service.validate_status_transition("BOOKED", "IN_TRANSIT")
    assert "Invalid status transition from 'BOOKED' to 'IN_TRANSIT'" in str(exc_info.value)


def test_state_machine_terminal_states():
    """Verify that DELIVERED and CANCELLED cannot transition to any other status."""
    service = ShipmentService(repository=None, mendix_client=None)

    # DELIVERED cannot transition
    with pytest.raises(ValidationException) as exc_info:
        service.validate_status_transition("DELIVERED", "IN_TRANSIT")
    assert "Cannot transition shipment from terminal state 'DELIVERED'" in str(exc_info.value)

    # CANCELLED cannot transition
    with pytest.raises(ValidationException) as exc_info:
        service.validate_status_transition("CANCELLED", "CREATED")
    assert "Cannot transition shipment from terminal state 'CANCELLED'" in str(exc_info.value)
