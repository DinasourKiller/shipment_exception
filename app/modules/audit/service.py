"""Audit Logging & Regulatory Compliance Verification Service."""

import csv
from datetime import datetime, timezone
import io
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id, get_logger
from app.modules.audit.hasher import GENESIS_PREV_HASH, compute_audit_hash
from app.modules.audit.models import SystemAuditLog
from app.modules.audit.schemas import (
    AuditLogResponse,
    ChainIntegrityResponse,
    PaginatedAuditLogsResponse,
)

logger = get_logger("control_tower.modules.audit.service")


class AuditService:
    """Orchestrates immutable audit logging, cryptographic hash verification, and compliance exports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def calculate_diff(before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates granular delta between previous and current entity state."""
        b = before or {}
        a = after or {}
        diff: Dict[str, Any] = {}
        all_keys = set(b.keys()).union(set(a.keys()))
        for k in all_keys:
            v_b = b.get(k)
            v_a = a.get(k)
            if v_b != v_a:
                diff[k] = {"from": v_b, "to": v_a}
        return diff

    async def record_event(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        state_before: Optional[Dict[str, Any]] = None,
        state_after: Optional[Dict[str, Any]] = None,
        diff_summary: Optional[Dict[str, Any]] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SystemAuditLog:
        """Appends an immutable, cryptographically chained audit log record."""
        b = state_before or {}
        a = state_after or {}
        delta = diff_summary if diff_summary is not None else self.calculate_diff(b, a)
        corr_id = correlation_id or get_correlation_id()
        now = datetime.now(timezone.utc)

        # Retrieve the latest audit log entry to establish the cryptographic chain link
        last_log_query = (
            select(SystemAuditLog)
            .order_by(SystemAuditLog.sequence_number.desc())
            .limit(1)
        )
        last_log_res = await self.session.execute(last_log_query)
        last_log = last_log_res.scalar_one_or_none()

        if last_log:
            prev_hash = last_log.record_hash
            next_seq = last_log.sequence_number + 1
        else:
            prev_hash = GENESIS_PREV_HASH
            next_seq = 1

        # Calculate SHA-256 signature
        rec_hash = compute_audit_hash(
            prev_record_hash=prev_hash,
            sequence_number=next_seq,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            created_at_iso=now.isoformat(),
            diff_summary=delta,
        )

        audit_entry = SystemAuditLog(
            sequence_number=next_seq,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            state_before=b,
            state_after=a,
            diff_summary=delta,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=corr_id,
            created_at=now,
            prev_record_hash=prev_hash,
            record_hash=rec_hash,
        )

        self.session.add(audit_entry)
        await self.session.flush()
        logger.info(
            "Recorded audit log block #%d (%s:%s) [Hash: %s...]",
            next_seq,
            resource_type,
            action,
            rec_hash[:12],
        )

        # Broadcast live audit log to auditors & admins
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_AUDIT_LIVE, EVENT_AUDIT_LOG_RECORDED
            broadcaster.publish_nowait(
                channel=CHANNEL_AUDIT_LIVE,
                event_type=EVENT_AUDIT_LOG_RECORDED,
                payload={
                    "audit_sequence_num": audit_entry.audit_sequence_num,
                    "action": audit_entry.action,
                    "resource_type": audit_entry.resource_type,
                    "resource_id": audit_entry.resource_id,
                    "actor_email": audit_entry.actor_email,
                    "created_at": audit_entry.created_at.isoformat() if audit_entry.created_at else None,
                    "record_hash": audit_entry.record_hash,
                    "diff_summary": audit_entry.diff_summary,
                },
            )
        except Exception as b_err:
            logger.debug("Live audit broadcast skipped: %s", b_err)

        return audit_entry

    async def list_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> PaginatedAuditLogsResponse:
        """Returns filtered, paginated audit records ordered chronologically descending."""
        query = select(SystemAuditLog)

        if action:
            query = query.where(SystemAuditLog.action == action)
        if resource_type:
            query = query.where(SystemAuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(SystemAuditLog.resource_id == resource_id)
        if actor_email:
            query = query.where(SystemAuditLog.actor_email.ilike(f"%{actor_email}%"))
        if from_date:
            query = query.where(SystemAuditLog.created_at >= from_date)
        if to_date:
            query = query.where(SystemAuditLog.created_at <= to_date)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar_one()

        offset = (page - 1) * page_size
        paged_query = (
            query.order_by(SystemAuditLog.sequence_number.desc())
            .offset(offset)
            .limit(page_size)
        )
        logs_res = await self.session.execute(paged_query)
        items = list(logs_res.scalars().all())

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedAuditLogsResponse(
            items=[AuditLogResponse.model_validate(it) for it in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def verify_chain_integrity(self) -> ChainIntegrityResponse:
        """Verifies the unbroken cryptographic SHA-256 chain across all historical audit records."""
        query = select(SystemAuditLog).order_by(SystemAuditLog.sequence_number.asc())
        res = await self.session.execute(query)
        records = list(res.scalars().all())

        total_records = len(records)
        if total_records == 0:
            return ChainIntegrityResponse(
                is_valid=True,
                total_records_checked=0,
                message="Audit chain is empty. Genesis block ready.",
            )

        expected_prev = GENESIS_PREV_HASH

        for idx, rec in enumerate(records):
            # Check 1: Predecessor hash linkage
            if rec.prev_record_hash != expected_prev:
                logger.error(
                    "Audit chain broken at seq #%d: expected prev_hash '%s', found '%s'",
                    rec.sequence_number,
                    expected_prev,
                    rec.prev_record_hash,
                )
                return ChainIntegrityResponse(
                    is_valid=False,
                    total_records_checked=idx,
                    corrupted_sequence_number=rec.sequence_number,
                    corrupted_record_id=rec.id,
                    expected_hash=expected_prev,
                    actual_hash=rec.prev_record_hash,
                    message=f"Predecessor hash linkage broken at sequence #{rec.sequence_number}.",
                )

            # Check 2: Content signature recalculation
            calculated_hash = compute_audit_hash(
                prev_record_hash=rec.prev_record_hash,
                sequence_number=rec.sequence_number,
                actor_email=rec.actor_email,
                action=rec.action,
                resource_type=rec.resource_type,
                resource_id=rec.resource_id,
                created_at_iso=rec.created_at.isoformat(),
                diff_summary=rec.diff_summary,
            )

            if calculated_hash != rec.record_hash:
                logger.error(
                    "Audit record content altered at seq #%d: expected hash '%s', stored '%s'",
                    rec.sequence_number,
                    calculated_hash,
                    rec.record_hash,
                )
                return ChainIntegrityResponse(
                    is_valid=False,
                    total_records_checked=idx,
                    corrupted_sequence_number=rec.sequence_number,
                    corrupted_record_id=rec.id,
                    expected_hash=calculated_hash,
                    actual_hash=rec.record_hash,
                    message=f"Record content tampering detected at sequence #{rec.sequence_number}.",
                )

            expected_prev = rec.record_hash

        return ChainIntegrityResponse(
            is_valid=True,
            total_records_checked=total_records,
            message=f"Cryptographic audit chain is 100% intact ({total_records} blocks verified). Zero tampering detected.",
        )

    async def export_compliance_csv(self) -> str:
        """Generates auditor-ready forensic CSV export containing cryptographic verification hashes."""
        query = select(SystemAuditLog).order_by(SystemAuditLog.sequence_number.asc())
        res = await self.session.execute(query)
        records = res.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header compliant with regulatory forensic standards
        writer.writerow([
            "Sequence Number",
            "Event Timestamp (UTC)",
            "Actor Email",
            "Actor Role",
            "Action Category",
            "Resource Type",
            "Resource Identifier",
            "Field Delta (Diff Summary)",
            "Client IP",
            "Correlation ID",
            "Previous Block SHA-256",
            "Cryptographic Record SHA-256",
        ])

        for r in records:
            writer.writerow([
                r.sequence_number,
                r.created_at.isoformat(),
                r.actor_email or "SYSTEM",
                r.actor_role or "SYSTEM_DAEMON",
                r.action,
                r.resource_type,
                r.resource_id,
                str(r.diff_summary),
                r.ip_address or "N/A",
                r.correlation_id or "N/A",
                r.prev_record_hash,
                r.record_hash,
            ])

        return output.getvalue()
