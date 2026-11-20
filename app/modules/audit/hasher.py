"""Cryptographic SHA-256 Hash Chaining Utilities for Audit Logs."""

import hashlib
import json
from typing import Any, Dict, Optional

GENESIS_PREV_HASH: str = "0" * 64


def canonical_json_dump(data: Any) -> str:
    """Produces deterministic, compact JSON string with sorted keys."""
    if data is None:
        return ""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_audit_hash(
    prev_record_hash: str,
    sequence_number: int,
    actor_email: Optional[str],
    action: str,
    resource_type: str,
    resource_id: str,
    created_at_iso: str,
    diff_summary: Dict[str, Any],
) -> str:
    """Calculates SHA-256 cryptographic signature linking this record to its predecessor."""
    canonical_diff = canonical_json_dump(diff_summary)
    payload_components = [
        prev_record_hash,
        str(sequence_number),
        actor_email or "SYSTEM",
        action,
        resource_type,
        resource_id,
        created_at_iso,
        canonical_diff,
    ]
    raw_payload = "|".join(payload_components)
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
