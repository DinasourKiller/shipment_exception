"""Pydantic schemas for System Audit Logs and Regulatory Compliance Verification."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Forensic audit log record serialized for compliance review."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence_number: int = Field(..., description="Monotonically increasing sequence ID")
    actor_id: Optional[uuid.UUID] = Field(None, description="User UUID or null for system event")
    actor_email: Optional[str] = Field(None, description="Actor email address")
    actor_role: Optional[str] = Field(None, description="Primary role at execution time")
    action: str = Field(..., description="Action tag (e.g. EXCEPTION_CREATED, RECOVERY_DISPATCHED)")
    resource_type: str = Field(..., description="Domain resource (e.g. SHIPMENT, EXCEPTION)")
    resource_id: str = Field(..., description="Identifier of affected resource")
    state_before: Dict[str, Any] = Field(default_factory=dict, description="State before change")
    state_after: Dict[str, Any] = Field(default_factory=dict, description="State after change")
    diff_summary: Dict[str, Any] = Field(default_factory=dict, description="Key delta")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client User-Agent")
    correlation_id: Optional[str] = Field(None, description="Correlation tracing token")
    created_at: datetime = Field(..., description="Immutable event timestamp")
    prev_record_hash: str = Field(..., description="SHA-256 hash of previous block")
    record_hash: str = Field(..., description="SHA-256 hash of this record block")


class PaginatedAuditLogsResponse(BaseModel):
    """Paginated collection of audit log entries."""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ChainIntegrityResponse(BaseModel):
    """Cryptographic hash-chain integrity verification outcome."""
    is_valid: bool = Field(..., description="True if 100% of hash chain links are cryptographically intact")
    total_records_checked: int = Field(..., description="Number of sequential records verified")
    corrupted_sequence_number: Optional[int] = Field(None, description="Sequence of first corrupted record, if any")
    corrupted_record_id: Optional[uuid.UUID] = Field(None, description="UUID of first corrupted record, if any")
    expected_hash: Optional[str] = Field(None, description="Expected SHA-256 hash")
    actual_hash: Optional[str] = Field(None, description="Actual calculated SHA-256 hash")
    verified_at: datetime = Field(default_factory=datetime.utcnow, description="Verification timestamp")
    message: str = Field(..., description="Integrity status summary message")
