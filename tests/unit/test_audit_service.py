"""Unit Tests for Cryptographic Audit Logging, Hash Chaining, and Tamper Detection."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.modules.audit.hasher import GENESIS_PREV_HASH, canonical_json_dump, compute_audit_hash
from app.modules.audit.models import SystemAuditLog
from app.modules.audit.service import AuditService


def test_canonical_json_dump():
    """Verify deterministic JSON formatting regardless of key order."""
    data_1 = {"z": 1, "a": "hello", "b": [3, 2, 1]}
    data_2 = {"a": "hello", "b": [3, 2, 1], "z": 1}
    assert canonical_json_dump(data_1) == canonical_json_dump(data_2)
    assert canonical_json_dump(None) == ""


def test_compute_audit_hash():
    """Verify SHA-256 hash consistency."""
    h1 = compute_audit_hash(
        prev_record_hash=GENESIS_PREV_HASH,
        sequence_number=1,
        actor_email="admin@controltower.corp",
        action="EXCEPTION_CREATED",
        resource_type="EXCEPTION",
        resource_id="EXC-001",
        created_at_iso="2026-11-20T10:00:00Z",
        diff_summary={"status": {"from": None, "to": "OPEN"}},
    )
    h2 = compute_audit_hash(
        prev_record_hash=GENESIS_PREV_HASH,
        sequence_number=1,
        actor_email="admin@controltower.corp",
        action="EXCEPTION_CREATED",
        resource_type="EXCEPTION",
        resource_id="EXC-001",
        created_at_iso="2026-11-20T10:00:00Z",
        diff_summary={"status": {"from": None, "to": "OPEN"}},
    )
    assert len(h1) == 64
    assert h1 == h2


def test_calculate_diff():
    before = {"status": "OPEN", "severity": "MEDIUM", "carrier": "APEX"}
    after = {"status": "ESCALATED", "severity": "CRITICAL", "carrier": "APEX"}
    diff = AuditService.calculate_diff(before, after)
    assert "status" in diff
    assert diff["status"] == {"from": "OPEN", "to": "ESCALATED"}
    assert "severity" in diff
    assert diff["severity"] == {"from": "MEDIUM", "to": "CRITICAL"}
    assert "carrier" not in diff  # Unchanged


@pytest.mark.asyncio
async def test_record_genesis_event():
    """Verify first record links to genesis hash."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # No prior log
    mock_session.execute.return_value = mock_res

    service = AuditService(mock_session)
    entry = await service.record_event(
        action="EXCEPTION_CREATED",
        resource_type="EXCEPTION",
        resource_id="EXC-100",
        state_after={"status": "OPEN"},
        actor_email="dispatcher@controltower.corp",
    )

    assert entry.sequence_number == 1
    assert entry.prev_record_hash == GENESIS_PREV_HASH
    assert len(entry.record_hash) == 64
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_record_consecutive_chained_event():
    """Verify subsequent record links to previous record's hash."""
    mock_session = AsyncMock()
    prior_log = SystemAuditLog(
        id=uuid.uuid4(),
        sequence_number=42,
        record_hash="a" * 64,
        prev_record_hash="b" * 64,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = prior_log
    mock_session.execute.return_value = mock_res

    service = AuditService(mock_session)
    entry = await service.record_event(
        action="RECOVERY_DISPATCHED",
        resource_type="RECOVERY_PLAN",
        resource_id="REC-200",
        actor_email="admin@controltower.corp",
    )

    assert entry.sequence_number == 43
    assert entry.prev_record_hash == "a" * 64
    assert len(entry.record_hash) == 64


@pytest.mark.asyncio
async def test_verify_chain_integrity_valid():
    """Verify valid chain passes integrity inspection."""
    mock_session = AsyncMock()
    now1 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    now2 = datetime(2026, 11, 20, 10, 5, 0, tzinfo=timezone.utc)

    diff1 = {"created": True}
    h1 = compute_audit_hash(GENESIS_PREV_HASH, 1, "admin@corp.com", "ACTION_1", "RES", "1", now1.isoformat(), diff1)

    diff2 = {"status": {"from": "A", "to": "B"}}
    h2 = compute_audit_hash(h1, 2, "admin@corp.com", "ACTION_2", "RES", "1", now2.isoformat(), diff2)

    r1 = SystemAuditLog(
        id=uuid.uuid4(),
        sequence_number=1,
        actor_email="admin@corp.com",
        action="ACTION_1",
        resource_type="RES",
        resource_id="1",
        created_at=now1,
        diff_summary=diff1,
        prev_record_hash=GENESIS_PREV_HASH,
        record_hash=h1,
    )
    r2 = SystemAuditLog(
        id=uuid.uuid4(),
        sequence_number=2,
        actor_email="admin@corp.com",
        action="ACTION_2",
        resource_type="RES",
        resource_id="1",
        created_at=now2,
        diff_summary=diff2,
        prev_record_hash=h1,
        record_hash=h2,
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [r1, r2]
    mock_session.execute.return_value = mock_res

    service = AuditService(mock_session)
    check = await service.verify_chain_integrity()

    assert check.is_valid is True
    assert check.total_records_checked == 2
    assert "Zero tampering detected" in check.message


@pytest.mark.asyncio
async def test_verify_chain_integrity_tampered():
    """Verify corrupted record content is immediately flagged as tamper attempt."""
    mock_session = AsyncMock()
    now1 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    diff1 = {"amount": 100}
    h1 = compute_audit_hash(GENESIS_PREV_HASH, 1, "admin@corp.com", "CREATE", "PAYLOAD", "1", now1.isoformat(), diff1)

    r1 = SystemAuditLog(
        id=uuid.uuid4(),
        sequence_number=1,
        actor_email="admin@corp.com",
        action="CREATE",
        resource_type="PAYLOAD",
        resource_id="1",
        created_at=now1,
        diff_summary=diff1,
        prev_record_hash=GENESIS_PREV_HASH,
        record_hash=h1,
    )

    # Tamper with diff_summary in database
    r1.diff_summary = {"amount": 999999}  # Malicious post-hoc modification!

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [r1]
    mock_session.execute.return_value = mock_res

    service = AuditService(mock_session)
    check = await service.verify_chain_integrity()

    assert check.is_valid is False
    assert check.corrupted_sequence_number == 1
    assert "tampering detected" in check.message
