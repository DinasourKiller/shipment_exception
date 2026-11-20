"""Unit Tests for AI Service, Prompts, and Local Ollama Fallback Engine."""

import json
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.core.exceptions import EntityNotFoundException
from app.integrations.ollama.client import OllamaClient
from app.modules.ai.prompts import (
    build_customer_communication_prompt,
    build_recovery_recommendation_prompt,
    build_root_cause_prompt,
)
from app.modules.ai.schemas import (
    AICustomerCommunicationResponse,
    AIHealthResponse,
    AIRecoveryRecommendationResponse,
    AIRootCauseResponse,
)
from app.modules.ai.service import AIService
from app.modules.exceptions.models import ExceptionSeverity, ExceptionType, ShipmentException
from app.modules.recovery.models import RecoveryStrategy
from app.modules.shipments.models import CargoItem, Shipment, ShipmentParty


@pytest.fixture
def mock_db_session():
    """Mock async SQLAlchemy session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient."""
    client = MagicMock(spec=OllamaClient)
    client.model = "gemma2:2b"
    client.base_url = "http://localhost:11434"
    client.check_health = AsyncMock()
    client.generate = AsyncMock()
    return client


def _create_mock_exception(
    exc_type: str = ExceptionType.TEMPERATURE_EXCURSION.value,
    severity: str = ExceptionSeverity.CRITICAL.value,
    is_temp: bool = True,
    customer_tier: str = "VIP",
) -> ShipmentException:
    exc_id = uuid.uuid4()
    shipment_id = uuid.uuid4()

    cargo = CargoItem(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        description="Pharmaceutical Biologics & Vaccines",
        weight_kg=120.0,
        declared_value=50000.0,
    )
    party = ShipmentParty(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        party_type="CONSIGNEE",
        name="BioPharma Health Inc.",
        contact_name="Dr. Sarah Johnson",
        contact_email="s.johnson@biopharma.org",
        city="Boston",
        country_code="US",
    )
    shipment = Shipment(
        id=shipment_id,
        external_reference="MDX-SHP-AI-01",
        order_number="ORD-AI-101",
        carrier_code="APEX",
        carrier_name="Apex Logistics",
        origin_city="Chicago",
        origin_country="US",
        destination_city="Boston",
        destination_country="US",
        raw_metadata={"is_temperature_sensitive": is_temp, "temp_min_c": 2.0, "temp_max_c": 8.0},
        cargo_items=[cargo],
        parties=[party],
        milestones=[],
    )
    exc = ShipmentException(
        id=exc_id,
        shipment_id=shipment_id,
        exception_type=exc_type,
        severity=severity,
        title="Active Temperature Excursion Alert",
        description="Reefer sensor reading at 14.5C for over 45 minutes",
        metadata_payload={"telemetry_excursion_duration_min": 45, "ambient_temp_c": 14.5},
    )
    exc.shipment = shipment
    return exc


# -----------------------------------------------------------------------------
# Prompt Builders Tests
# -----------------------------------------------------------------------------
def test_build_root_cause_prompt():
    """Verify prompt templates inject contextual variables correctly."""
    context = {
        "shipment_reference": "REF-001",
        "carrier_code": "DHL",
        "origin": "Dallas, US",
        "destination": "Miami, US",
        "cargo_type": "Electronics",
        "is_temp_sensitive": False,
        "exception_type": "DELAY",
        "severity": "HIGH",
        "description": "Port dwell delay",
        "recent_events": [],
        "estimated_financial_impact": 4500.0,
    }
    prompt = build_root_cause_prompt(context)
    assert "REF-001" in prompt
    assert "Port dwell delay" in prompt
    assert "$4,500.00" in prompt
    assert "synthesized_cause" in prompt


def test_build_recovery_recommendation_prompt():
    context = {
        "exception_type": "VEHICLE_BREAKDOWN",
        "severity": "HIGH",
        "cargo_type": "Dry Goods",
        "is_temp_sensitive": False,
        "customer_tier": "VIP",
        "origin": "Atlanta, US",
        "destination": "Charlotte, US",
        "root_cause_summary": "Engine failure",
        "delay_hours": 6.0,
        "priority_score": 85.0,
    }
    prompt = build_recovery_recommendation_prompt(context)
    assert "VEHICLE_REPLACEMENT" in prompt
    assert "CROSS_DOCK" in prompt
    assert "VIP" in prompt


def test_build_customer_communication_prompt():
    context = {
        "customer_name": "Acme Corp",
        "customer_email": "acme@example.com",
        "shipment_reference": "SHP-999",
        "origin": "Seattle",
        "destination": "Portland",
        "exception_type": "DELAY",
        "exception_status": "OPEN",
        "recovery_action": "Rerouted to express corridor",
        "delay_hours": 3.5,
    }
    prompt = build_customer_communication_prompt(context)
    assert "Acme Corp" in prompt
    assert "SHP-999" in prompt
    assert "Empathetic & Professional" in prompt


# -----------------------------------------------------------------------------
# Health Check Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ai_health_offline(mock_db_session, mock_ollama_client):
    mock_ollama_client.check_health.return_value = {
        "status": "offline",
        "model_configured": "gemma2:2b",
        "reason": "Connection refused",
    }
    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.check_health()

    assert isinstance(res, AIHealthResponse)
    assert res.status == "offline"
    assert res.active_provider == "deterministic_fallback"
    assert res.model_configured == "gemma2:2b"


@pytest.mark.asyncio
async def test_ai_health_online(mock_db_session, mock_ollama_client):
    mock_ollama_client.check_health.return_value = {
        "status": "online",
        "model_configured": "gemma2:2b",
        "model_available": True,
        "installed_models": ["gemma2:2b", "llama3.1:8b"],
    }
    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.check_health()

    assert res.status == "online"
    assert res.model_available is True
    assert "ollama" in res.active_provider


# -----------------------------------------------------------------------------
# Root Cause Analysis Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_root_cause_with_ollama(mock_db_session, mock_ollama_client):
    """Verify successful parsing when Ollama returns valid JSON."""
    exc = _create_mock_exception()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]  # Exception, then Impact
    mock_db_session.execute.return_value = mock_db_result

    ollama_output = {
        "synthesized_cause": "Compressor unit failed due to blown fuse in auxiliary refrigeration generator.",
        "contributing_factors": ["High ambient heat 38C", "Auxiliary generator fuse failure"],
        "severity_assessment": "CRITICAL",
        "confidence_score": 0.96,
    }
    mock_ollama_client.generate.return_value = json.dumps(ollama_output)

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.analyze_root_cause(exc.id)

    assert isinstance(res, AIRootCauseResponse)
    assert res.exception_id == exc.id
    assert "Compressor unit failed" in res.synthesized_cause
    assert len(res.contributing_factors) == 2
    assert res.severity_assessment == "CRITICAL"
    assert res.confidence_score == 0.96
    assert "ollama (gemma2:2b)" in res.provider


@pytest.mark.asyncio
async def test_analyze_root_cause_fallback_temperature_excursion(mock_db_session, mock_ollama_client):
    """Verify deterministic fallback when Ollama is offline or returns None."""
    exc = _create_mock_exception(exc_type=ExceptionType.TEMPERATURE_EXCURSION.value)
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]
    mock_db_session.execute.return_value = mock_db_result

    mock_ollama_client.generate.return_value = None  # Simulates Ollama offline

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.analyze_root_cause(exc.id)

    assert isinstance(res, AIRootCauseResponse)
    assert "Active refrigeration telemetry breach" in res.synthesized_cause
    assert "Reefer cooling unit" in res.contributing_factors[0]
    assert "deterministic_fallback" in res.provider
    assert res.confidence_score >= 0.85


@pytest.mark.asyncio
async def test_analyze_root_cause_fallback_vehicle_breakdown(mock_db_session, mock_ollama_client):
    exc = _create_mock_exception(
        exc_type=ExceptionType.VEHICLE_BREAKDOWN.value,
        severity=ExceptionSeverity.HIGH.value,
        is_temp=False,
    )
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]
    mock_db_session.execute.return_value = mock_db_result
    mock_ollama_client.generate.return_value = None

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.analyze_root_cause(exc.id)

    assert "Mechanical prime-mover failure" in res.synthesized_cause
    assert "Transmission fluid" in res.contributing_factors[0]


# -----------------------------------------------------------------------------
# Recovery Recommendation Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recommend_recovery_with_ollama(mock_db_session, mock_ollama_client):
    exc = _create_mock_exception()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]
    mock_db_session.execute.return_value = mock_db_result

    ollama_output = {
        "recommended_strategy": "CROSS_DOCK",
        "suggested_action_type": "Emergency Cross-Dock Transfer",
        "rationale": "Transfer cargo to certified cold storage hub to salvage vaccine batch.",
        "estimated_cost_usd": 1250.0,
        "estimated_turnaround_hours": 3.0,
        "risk_tradeoffs": ["Transfer temperature breach during unload"],
        "confidence_score": 0.92,
    }
    mock_ollama_client.generate.return_value = f"```json\n{json.dumps(ollama_output)}\n```"

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.recommend_recovery(exc.id)

    assert isinstance(res, AIRecoveryRecommendationResponse)
    assert res.recommended_strategy == RecoveryStrategy.CROSS_DOCK
    assert res.estimated_cost_usd == 1250.0
    assert res.estimated_turnaround_hours == 3.0
    assert "ollama (gemma2:2b)" in res.provider


@pytest.mark.asyncio
async def test_recommend_recovery_fallback_cold_chain(mock_db_session, mock_ollama_client):
    exc = _create_mock_exception(is_temp=True)
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]
    mock_db_session.execute.return_value = mock_db_result
    mock_ollama_client.generate.return_value = None

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.recommend_recovery(exc.id)

    assert res.recommended_strategy == RecoveryStrategy.CROSS_DOCK
    assert res.estimated_cost_usd > 1000.0
    assert "deterministic_fallback" in res.provider


# -----------------------------------------------------------------------------
# Customer Communication Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_draft_customer_communication_with_ollama(mock_db_session, mock_ollama_client):
    exc = _create_mock_exception()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]
    mock_db_session.execute.return_value = mock_db_result

    ollama_output = {
        "email_subject": "Urgent Shipment Advisory: MDX-SHP-AI-01 Temperature Alert",
        "email_body": "Dear BioPharma Health,\n\nWe detected a temporary temperature excursion and have dispatched a relief team.",
        "tone": "Empathetic & Professional",
    }
    mock_ollama_client.generate.return_value = json.dumps(ollama_output)

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.draft_customer_communication(exc.id)

    assert isinstance(res, AICustomerCommunicationResponse)
    assert "MDX-SHP-AI-01" in res.email_subject
    assert res.customer_email == "s.johnson@biopharma.org"
    assert "ollama (gemma2:2b)" in res.provider


@pytest.mark.asyncio
async def test_draft_customer_communication_fallback(mock_db_session, mock_ollama_client):
    exc = _create_mock_exception()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.side_effect = [exc, None]
    mock_db_session.execute.return_value = mock_db_result
    mock_ollama_client.generate.return_value = None

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    res = await service.draft_customer_communication(exc.id)

    assert isinstance(res, AICustomerCommunicationResponse)
    assert "MDX-SHP-AI-01" in res.email_subject
    assert "Dear BioPharma Health Inc." in res.email_body
    assert "Global Control Tower Operations Team" in res.email_body
    assert "deterministic_fallback" in res.provider


@pytest.mark.asyncio
async def test_exception_not_found(mock_db_session, mock_ollama_client):
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_db_result

    service = AIService(db=mock_db_session, ollama_client=mock_ollama_client)
    with pytest.raises(EntityNotFoundException):
        await service.analyze_root_cause(uuid.uuid4())
