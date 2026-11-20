"""Delivery Management Domain Service.

Orchestrates Proof of Delivery (e-POD) verification, digital signatures,
time-bound OTP handshakes, delivery failure tracking, and exception auto-resolution.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.delivery.models import DeliveryAttempt, DeliveryOtp, ProofOfDelivery
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.schemas import (
    DeliveryAttemptResponse,
    DeliveryHistoryResponse,
    DeliveryOtpGenerateResponse,
    FailedDeliveryAttemptRequest,
    PodSubmissionRequest,
    ProofOfDeliveryResponse,
)

logger = get_logger("control_tower.delivery.service")


class DeliveryService:
    """Core domain service for delivery management and e-POD reconciliation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DeliveryRepository(session)

    @staticmethod
    def _hash_otp(shipment_id: uuid.UUID, otp_code: str) -> str:
        """Hash OTP with shipment_id as domain-specific cryptographic salt."""
        return hashlib.sha256(f"{shipment_id}:{otp_code}".encode("utf-8")).hexdigest()

    async def generate_otp(self, shipment_id: uuid.UUID) -> DeliveryOtpGenerateResponse:
        """Issue a 6-digit delivery release OTP valid for 30 minutes."""
        shipment = await self.repository.get_shipment_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        if shipment.status == "DELIVERED":
            raise ValidationException("Shipment is already delivered; cannot issue new OTP.")

        # Generate 6-digit cryptographically secure numerical token
        plain_code = f"{secrets.randbelow(900000) + 100000}"
        otp_hash = self._hash_otp(shipment_id, plain_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        otp = DeliveryOtp(
            id=uuid.uuid4(),
            shipment_id=shipment.id,
            otp_hash=otp_hash,
            otp_hint=plain_code,
            expires_at=expires_at,
            is_used=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        await self.repository.create_otp(otp)

        logger.info(
            "Generated delivery verification OTP for shipment %s (Expires: %s)",
            shipment.tracking_number,
            expires_at.isoformat(),
        )

        return DeliveryOtpGenerateResponse(
            shipment_id=shipment.id,
            otp_code=plain_code,
            expires_at=expires_at,
            expires_in_minutes=30,
        )

    async def submit_pod(
        self,
        shipment_id: uuid.UUID,
        request: PodSubmissionRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
    ) -> ProofOfDeliveryResponse:
        """Submit electronic Proof of Delivery (e-POD), advance shipment, and resolve exceptions."""
        shipment = await self.repository.get_shipment_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        if shipment.status == "DELIVERED":
            raise ValidationException("Shipment is already delivered.")

        existing_pod = await self.repository.get_pod_by_shipment_id(shipment_id)
        if existing_pod:
            raise ConflictException("Proof of delivery already recorded for this shipment.")

        is_otp_verified = False
        otp_hash = None

        # Validate OTP if provided
        if request.otp_code:
            active_otp = await self.repository.get_latest_valid_otp(shipment_id)
            if not active_otp:
                raise ValidationException("Invalid or expired delivery verification OTP.")

            computed_hash = self._hash_otp(shipment_id, request.otp_code)
            if active_otp.otp_hash != computed_hash:
                raise ValidationException("Invalid delivery verification OTP.")

            await self.repository.mark_otp_used(active_otp)
            is_otp_verified = True
            otp_hash = computed_hash

        attempt_count = await self.repository.count_attempts(shipment_id)
        now_utc = datetime.now(timezone.utc)
        old_status = shipment.status

        pod = ProofOfDelivery(
            id=uuid.uuid4(),
            shipment_id=shipment.id,
            delivery_attempt_number=attempt_count + 1,
            recipient_name=request.recipient_name.strip(),
            recipient_signature_svg=request.recipient_signature_svg,
            photo_url=request.photo_url,
            photo_metadata=request.photo_metadata or {},
            otp_code_hash=otp_hash,
            is_otp_verified=is_otp_verified,
            handover_latitude=request.handover_latitude,
            handover_longitude=request.handover_longitude,
            delivered_at=now_utc,
            delivery_status="CONFIRMED",
            notes=request.notes,
            submitted_by_user_id=actor_id,
            created_at=now_utc,
            updated_at=now_utc,
        )
        saved_pod = await self.repository.create_pod(pod)

        # Update shipment lifecycle status
        shipment.status = "DELIVERED"
        shipment.actual_delivery = now_utc
        await self.session.flush()

        # Hook 1: Automatically auto-resolve any open exceptions on this shipment
        await self._auto_resolve_shipment_exceptions(shipment.id, actor_id, request.recipient_name)

        # Hook 2: Record cryptographically hash-chained system audit log (Phase 15)
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="DELIVERY_CONFIRMED_EPOD",
                resource_type="SHIPMENT",
                resource_id=str(shipment.id),
                actor_id=actor_id,
                state_before={"status": old_status},
                state_after={"status": "DELIVERED", "delivered_at": now_utc.isoformat()},
                diff_summary={
                    "status": {"from": old_status, "to": "DELIVERED"},
                    "recipient": request.recipient_name,
                    "otp_verified": is_otp_verified,
                    "attempt_number": pod.delivery_attempt_number,
                },
            )
        except Exception as audit_err:
            logger.debug("System audit recording skipped for delivery: %s", audit_err)

        # Hook 3: Broadcast real-time delivery event (Phase 16)
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_ALERTS_ALL
            broadcaster.publish_nowait(
                channel=CHANNEL_ALERTS_ALL,
                event_type="DELIVERY_COMPLETED",
                payload={
                    "shipment_id": str(shipment.id),
                    "tracking_number": shipment.tracking_number,
                    "recipient_name": request.recipient_name,
                    "is_otp_verified": is_otp_verified,
                    "delivered_at": now_utc.isoformat(),
                    "delivery_attempts": pod.delivery_attempt_number,
                },
            )
            broadcaster.publish_nowait(
                channel=f"telemetry:{shipment.id}",
                event_type="DELIVERY_COMPLETED",
                payload={"status": "DELIVERED", "delivered_at": now_utc.isoformat()},
            )
        except Exception as ws_err:
            logger.debug("Real-time broadcast skipped for delivery: %s", ws_err)

        logger.info(
            "e-POD successfully recorded for shipment %s (Recipient: %s, OTP Verified: %s)",
            shipment.tracking_number,
            request.recipient_name,
            is_otp_verified,
        )

        return ProofOfDeliveryResponse.model_validate(saved_pod)

    async def _auto_resolve_shipment_exceptions(
        self,
        shipment_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
        recipient_name: str,
    ) -> None:
        """Auto-resolve open exceptions once cargo is confirmed delivered."""
        try:
            from app.modules.exceptions.models import ShipmentException
            from sqlalchemy import select

            stmt = select(ShipmentException).where(
                ShipmentException.shipment_id == shipment_id,
                ShipmentException.status.in_(["OPEN", "INVESTIGATING", "ESCALATED", "RESOLVING"]),
            )
            result = await self.session.execute(stmt)
            open_exceptions = list(result.scalars().all())

            now_utc = datetime.now(timezone.utc)
            for exc in open_exceptions:
                exc.status = "RESOLVED"
                exc.root_cause = "CARGO_DELIVERED_POD_CONFIRMED"
                exc.resolution_notes = f"Auto-resolved upon confirmed e-POD handover to {recipient_name}."
                exc.resolved_at = now_utc
                logger.info("Auto-resolved exception %s on confirmed delivery", exc.id)

            if open_exceptions:
                await self.session.flush()
        except Exception as err:
            logger.warning("Failed to auto-resolve shipment exceptions: %s", err)

    async def record_failed_attempt(
        self,
        shipment_id: uuid.UUID,
        request: FailedDeliveryAttemptRequest,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
    ) -> DeliveryAttemptResponse:
        """Log an unsuccessful delivery attempt and trigger automated exception escalation if repeated."""
        shipment = await self.repository.get_shipment_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        if shipment.status == "DELIVERED":
            raise ValidationException("Cannot log failed attempt for an already delivered shipment.")

        prior_count = await self.repository.count_attempts(shipment_id)
        attempt_num = prior_count + 1
        now_utc = datetime.now(timezone.utc)

        attempt = DeliveryAttempt(
            id=uuid.uuid4(),
            shipment_id=shipment.id,
            attempt_number=attempt_num,
            reason_code=request.reason_code.upper(),
            notes=request.notes,
            driver_name=request.driver_name,
            latitude=request.latitude,
            longitude=request.longitude,
            attempted_at=now_utc,
            recorded_by_user_id=actor_id,
            created_at=now_utc,
            updated_at=now_utc,
        )
        saved_attempt = await self.repository.create_delivery_attempt(attempt)

        # Transition shipment to DELAYED if currently in transit
        if shipment.status != "DELAYED":
            shipment.status = "DELAYED"
            await self.session.flush()

        # If 2 or more attempts failed, trigger automated Exception in Exception Management
        if attempt_num >= 2:
            await self._trigger_failed_delivery_exception(shipment, attempt_num, request)

        # Record system audit log (Phase 15)
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="DELIVERY_ATTEMPT_FAILED",
                resource_type="SHIPMENT",
                resource_id=str(shipment.id),
                actor_id=actor_id,
                diff_summary={
                    "attempt_number": attempt_num,
                    "reason_code": request.reason_code,
                    "driver_name": request.driver_name,
                },
            )
        except Exception as audit_err:
            logger.debug("Audit record skipped for failed attempt: %s", audit_err)

        # Broadcast live alert (Phase 16)
        try:
            from app.modules.realtime.broadcaster import broadcaster
            from app.modules.realtime.schemas import CHANNEL_ALERTS_ALL, EVENT_EXCEPTION_TRIGGERED
            broadcaster.publish_nowait(
                channel=CHANNEL_ALERTS_ALL,
                event_type="DELIVERY_ATTEMPT_FAILED",
                payload={
                    "shipment_id": str(shipment.id),
                    "tracking_number": shipment.tracking_number,
                    "attempt_number": attempt_num,
                    "reason_code": request.reason_code,
                    "driver_name": request.driver_name,
                },
            )
        except Exception as ws_err:
            logger.debug("Real-time broadcast skipped: %s", ws_err)

        return DeliveryAttemptResponse.model_validate(saved_attempt)

    async def _trigger_failed_delivery_exception(
        self,
        shipment,
        attempt_number: int,
        request: FailedDeliveryAttemptRequest,
    ) -> None:
        """Trigger an automated operational exception when multiple delivery attempts fail."""
        try:
            from app.modules.exceptions.models import ShipmentException

            exc = ShipmentException(
                shipment_id=shipment.id,
                exception_type="DELIVERY_FAILURE",
                severity="HIGH",
                status="OPEN",
                title=f"Repeated Delivery Failure ({attempt_number} Attempts) - {request.reason_code}",
                description=f"Delivery attempted {attempt_number} times without successful recipient handover. Latest failure reason: {request.reason_code}. Driver notes: {request.notes or 'None'}.",
                sla_breach_at=datetime.now(timezone.utc) + timedelta(hours=4),
                metadata_payload={
                    "failed_attempts": attempt_number,
                    "reason_code": request.reason_code,
                    "driver_name": request.driver_name,
                },
            )
            self.session.add(exc)
            await self.session.flush()
            logger.info("Automatically escalated delivery failure exception %s for shipment %s", exc.id, shipment.id)
        except Exception as err:
            logger.warning("Failed to auto-escalate delivery failure exception: %s", err)

    async def get_pod(self, shipment_id: uuid.UUID) -> ProofOfDeliveryResponse:
        """Retrieve existing Proof of Delivery certificate."""
        pod = await self.repository.get_pod_by_shipment_id(shipment_id)
        if not pod:
            raise EntityNotFoundException("ProofOfDelivery", str(shipment_id))
        return ProofOfDeliveryResponse.model_validate(pod)

    async def get_delivery_history(self, shipment_id: uuid.UUID) -> DeliveryHistoryResponse:
        """Retrieve full delivery lifecycle audit history, attempts, and certificate."""
        shipment = await self.repository.get_shipment_by_id(shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(shipment_id))

        attempts = await self.repository.get_delivery_attempts(shipment_id)
        pod = await self.repository.get_pod_by_shipment_id(shipment_id)

        return DeliveryHistoryResponse(
            shipment_id=shipment.id,
            tracking_number=shipment.tracking_number,
            shipment_status=shipment.status,
            actual_delivery_date=shipment.actual_delivery,
            is_delivered=(shipment.status == "DELIVERED"),
            attempts=[DeliveryAttemptResponse.model_validate(a) for a in attempts],
            proof_of_delivery=ProofOfDeliveryResponse.model_validate(pod) if pod else None,
        )
