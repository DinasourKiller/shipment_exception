"""Unit Tests for Delivery Management & e-POD Domain Service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from app.modules.delivery.models import DeliveryAttempt, DeliveryOtp, ProofOfDelivery
from app.modules.delivery.schemas import (
    FailedDeliveryAttemptRequest,
    PodSubmissionRequest,
)
from app.modules.delivery.service import DeliveryService
from app.modules.shipments.models import Shipment


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_shipment():
    return Shipment(
        id=uuid.uuid4(),
        order_number="ORD-TEST-999",
        tracking_number="TRK-999-DELIVERY",
        carrier_code="FEDEX",
        carrier_name="FedEx Freight",
        origin_country="US",
        origin_city="Chicago",
        destination_country="US",
        destination_city="Dallas",
        status="IN_TRANSIT",
        transport_mode="ROAD",
    )


@pytest.mark.asyncio
async def test_generate_otp_success(mock_session, sample_shipment):
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)
    service.repository.create_otp = AsyncMock(side_effect=lambda o: o)

    resp = await service.generate_otp(sample_shipment.id)

    assert resp.shipment_id == sample_shipment.id
    assert len(resp.otp_code) == 6
    assert resp.otp_code.isdigit()
    assert resp.expires_in_minutes == 30
    service.repository.create_otp.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_otp_fails_if_already_delivered(mock_session, sample_shipment):
    sample_shipment.status = "DELIVERED"
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)

    with pytest.raises(ValidationException, match="already delivered"):
        await service.generate_otp(sample_shipment.id)


@pytest.mark.asyncio
async def test_submit_pod_success_without_otp(mock_session, sample_shipment):
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)
    service.repository.get_pod_by_shipment_id = AsyncMock(return_value=None)
    service.repository.count_attempts = AsyncMock(return_value=0)
    service.repository.create_pod = AsyncMock(side_effect=lambda p: p)

    req = PodSubmissionRequest(
        recipient_name="John Doe",
        recipient_signature_svg="data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
        notes="Delivered to front desk receptionist",
    )

    pod_resp = await service.submit_pod(sample_shipment.id, req)

    assert pod_resp.recipient_name == "John Doe"
    assert pod_resp.is_otp_verified is False
    assert sample_shipment.status == "DELIVERED"
    assert sample_shipment.actual_delivery is not None


@pytest.mark.asyncio
async def test_submit_pod_success_with_valid_otp(mock_session, sample_shipment):
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)
    service.repository.get_pod_by_shipment_id = AsyncMock(return_value=None)
    service.repository.count_attempts = AsyncMock(return_value=0)
    service.repository.create_pod = AsyncMock(side_effect=lambda p: p)

    otp_code = "741852"
    otp_hash = service._hash_otp(sample_shipment.id, otp_code)
    active_otp = DeliveryOtp(
        shipment_id=sample_shipment.id,
        otp_hash=otp_hash,
        otp_hint="741852",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        is_used=False,
    )
    service.repository.get_latest_valid_otp = AsyncMock(return_value=active_otp)
    service.repository.mark_otp_used = AsyncMock()

    req = PodSubmissionRequest(
        recipient_name="Alice Smith",
        otp_code=otp_code,
    )

    pod_resp = await service.submit_pod(sample_shipment.id, req)

    assert pod_resp.recipient_name == "Alice Smith"
    assert pod_resp.is_otp_verified is True
    service.repository.mark_otp_used.assert_awaited_once_with(active_otp)


@pytest.mark.asyncio
async def test_submit_pod_invalid_otp_fails(mock_session, sample_shipment):
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)
    service.repository.get_pod_by_shipment_id = AsyncMock(return_value=None)
    service.repository.count_attempts = AsyncMock(return_value=0)

    otp_hash = service._hash_otp(sample_shipment.id, "111111")
    active_otp = DeliveryOtp(
        shipment_id=sample_shipment.id,
        otp_hash=otp_hash,
        otp_hint="111111",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        is_used=False,
    )
    service.repository.get_latest_valid_otp = AsyncMock(return_value=active_otp)

    req = PodSubmissionRequest(
        recipient_name="Alice Smith",
        otp_code="999999",  # Wrong code
    )

    with pytest.raises(ValidationException, match="Invalid delivery verification OTP"):
        await service.submit_pod(sample_shipment.id, req)


@pytest.mark.asyncio
async def test_submit_pod_conflict_if_already_recorded(mock_session, sample_shipment):
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)
    service.repository.get_pod_by_shipment_id = AsyncMock(
        return_value=ProofOfDelivery(
            shipment_id=sample_shipment.id,
            recipient_name="Existing Signer",
            delivered_at=datetime.now(timezone.utc),
        )
    )

    req = PodSubmissionRequest(recipient_name="New Signer")
    with pytest.raises(ConflictException, match="Proof of delivery already recorded"):
        await service.submit_pod(sample_shipment.id, req)


@pytest.mark.asyncio
async def test_record_failed_attempt_escalates_on_repeated_failure(mock_session, sample_shipment):
    service = DeliveryService(session=mock_session)
    service.repository.get_shipment_by_id = AsyncMock(return_value=sample_shipment)
    service.repository.count_attempts = AsyncMock(return_value=1)  # Prior count 1 -> this is attempt 2
    service.repository.create_delivery_attempt = AsyncMock(side_effect=lambda a: a)
    service._trigger_failed_delivery_exception = AsyncMock()

    req = FailedDeliveryAttemptRequest(
        reason_code="RECIPIENT_UNAVAILABLE",
        notes="Security gate locked, recipient not answering intercom.",
        driver_name="Dave Miller",
    )

    attempt_resp = await service.record_failed_attempt(sample_shipment.id, req)

    assert attempt_resp.attempt_number == 2
    assert attempt_resp.reason_code == "RECIPIENT_UNAVAILABLE"
    assert sample_shipment.status == "DELAYED"
    service._trigger_failed_delivery_exception.assert_awaited_once_with(sample_shipment, 2, req)
