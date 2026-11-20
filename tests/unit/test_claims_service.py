"""Unit Tests for Carrier Claims & SLA Penalty Settlement Domain Service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.modules.claims.models import CarrierClaim, ClaimAuditEvent
from app.modules.claims.schemas import (
    AutoClaimFromExceptionRequest,
    ClaimCreateRequest,
    ClaimDisputeRequest,
    ClaimRejectRequest,
    ClaimSettleRequest,
)
from app.modules.claims.service import ClaimService
from app.modules.exceptions.models import ShipmentException
from app.modules.impact.models import ImpactAssessment
from app.modules.shipments.models import Shipment


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_claim():
    return CarrierClaim(
        id=uuid.uuid4(),
        claim_number="CLM-2026-0001",
        shipment_id=uuid.uuid4(),
        carrier_code="APEX",
        carrier_name="Apex Logistics",
        claim_type="SLA_DELAY_PENALTY",
        claimed_amount_usd=1250.0,
        assessed_penalty_usd=1250.0,
        settled_amount_usd=None,
        status="SUBMITTED",
        currency="USD",
        incident_description="Transit SLA exceeded by 24 hours.",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        audit_events=[],
    )


@pytest.mark.asyncio
async def test_create_claim_manual(mock_session):
    service = ClaimService(session=mock_session)
    service.repository.count_claims_for_year = AsyncMock(return_value=0)
    service.repository.create_claim = AsyncMock(side_effect=lambda c: c)
    service.repository.add_audit_event = AsyncMock()
    service.get_claim = AsyncMock(
        side_effect=lambda cid: service.repository.create_claim.call_args[0][0]
    )

    req = ClaimCreateRequest(
        shipment_id=uuid.uuid4(),
        carrier_code="APEX",
        carrier_name="Apex Logistics",
        claim_type="SLA_DELAY_PENALTY",
        claimed_amount_usd=750.50,
        incident_description="Major hub delay exceeding agreed SLA",
        deadline_days=14,
    )

    resp = await service.create_claim(req, actor_email="operator@test.local")

    assert resp.claim_number.startswith("CLM-")
    assert resp.claimed_amount_usd == 750.50
    assert resp.assessed_penalty_usd == 750.50
    assert resp.status == "SUBMITTED"
    assert resp.carrier_code == "APEX"
    service.repository.add_audit_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_dispute_success(mock_session, sample_claim):
    service = ClaimService(session=mock_session)
    service.repository.get_by_id = AsyncMock(return_value=sample_claim)
    service.repository.add_audit_event = AsyncMock()
    service.get_claim = AsyncMock(return_value=sample_claim)

    req = ClaimDisputeRequest(
        dispute_reason="Interstate closure was due to declared civil emergency (Force Majeure)",
        counter_offer_amount_usd=350.0,
    )

    resp = await service.submit_dispute(sample_claim.id, req, actor_role="Carrier")

    assert resp.status == "CARRIER_DISPUTED"
    assert resp.counter_offer_amount_usd == 350.0
    assert "Force Majeure" in resp.dispute_reason
    service.repository.add_audit_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_dispute_fails_if_already_settled(mock_session, sample_claim):
    sample_claim.status = "SETTLED"
    service = ClaimService(session=mock_session)
    service.repository.get_by_id = AsyncMock(return_value=sample_claim)

    req = ClaimDisputeRequest(dispute_reason="Rebuttal on closed case")
    with pytest.raises(ValidationException, match="already SETTLED"):
        await service.submit_dispute(sample_claim.id, req)


@pytest.mark.asyncio
async def test_settle_claim_success(mock_session, sample_claim):
    service = ClaimService(session=mock_session)
    service.repository.get_by_id = AsyncMock(return_value=sample_claim)
    service.repository.add_audit_event = AsyncMock()
    service.get_claim = AsyncMock(return_value=sample_claim)

    req = ClaimSettleRequest(
        settled_amount_usd=900.0,
        settlement_method="INVOICE_OFFSET",
        settlement_notes="Agreed compromise after carrier dispute review",
    )

    resp = await service.settle_claim(sample_claim.id, req, actor_role="Operations Manager")

    assert resp.status == "SETTLED"
    assert resp.settled_amount_usd == 900.0
    assert "INVOICE_OFFSET" in resp.settlement_notes
    assert resp.settled_at is not None
    service.repository.add_audit_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_reject_claim_success(mock_session, sample_claim):
    service = ClaimService(session=mock_session)
    service.repository.get_by_id = AsyncMock(return_value=sample_claim)
    service.repository.add_audit_event = AsyncMock()
    service.get_claim = AsyncMock(return_value=sample_claim)

    req = ClaimRejectRequest(rejection_reason="Carrier provided GPS telemetry proving no driver negligence")
    resp = await service.reject_claim(sample_claim.id, req)

    assert resp.status == "REJECTED"
    assert "REJECTED" in resp.settlement_notes
    service.repository.add_audit_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_claims_csv(mock_session, sample_claim):
    service = ClaimService(session=mock_session)
    service.repository.list_claims = AsyncMock(return_value=([sample_claim], 1))

    csv_data = await service.export_claims_csv()

    assert "Claim Number,Carrier Code,Carrier Name" in csv_data
    assert "CLM-2026-0001" in csv_data
    assert "APEX" in csv_data
    assert "1250.00" in csv_data
