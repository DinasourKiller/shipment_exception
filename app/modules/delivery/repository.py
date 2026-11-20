"""Delivery Management Database Repository."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.models import DeliveryAttempt, DeliveryOtp, ProofOfDelivery
from app.modules.shipments.models import Shipment


class DeliveryRepository:
    """Async repository for e-POD, delivery attempts, and delivery verification OTPs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_shipment_by_id(self, shipment_id: uuid.UUID) -> Optional[Shipment]:
        """Fetch shipment by primary ID."""
        stmt = select(Shipment).where(Shipment.id == shipment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pod_by_shipment_id(self, shipment_id: uuid.UUID) -> Optional[ProofOfDelivery]:
        """Fetch e-POD record for a given shipment."""
        stmt = select(ProofOfDelivery).where(ProofOfDelivery.shipment_id == shipment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_pod(self, pod: ProofOfDelivery) -> ProofOfDelivery:
        """Persist a new Proof of Delivery record."""
        self.session.add(pod)
        await self.session.flush()
        return pod

    async def count_attempts(self, shipment_id: uuid.UUID) -> int:
        """Count total prior delivery attempts for a shipment."""
        stmt = select(func.count(DeliveryAttempt.id)).where(DeliveryAttempt.shipment_id == shipment_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def create_delivery_attempt(self, attempt: DeliveryAttempt) -> DeliveryAttempt:
        """Persist a delivery attempt record."""
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def get_delivery_attempts(self, shipment_id: uuid.UUID) -> List[DeliveryAttempt]:
        """Retrieve all delivery attempts for a shipment ordered chronologically."""
        stmt = (
            select(DeliveryAttempt)
            .where(DeliveryAttempt.shipment_id == shipment_id)
            .order_by(DeliveryAttempt.attempt_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_otp(self, otp: DeliveryOtp) -> DeliveryOtp:
        """Persist a new delivery release OTP."""
        self.session.add(otp)
        await self.session.flush()
        return otp

    async def get_latest_valid_otp(self, shipment_id: uuid.UUID) -> Optional[DeliveryOtp]:
        """Retrieve unexpired, unused OTP for a shipment."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(DeliveryOtp)
            .where(
                DeliveryOtp.shipment_id == shipment_id,
                DeliveryOtp.is_used.is_(False),
                DeliveryOtp.expires_at > now,
            )
            .order_by(DeliveryOtp.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def mark_otp_used(self, otp: DeliveryOtp) -> None:
        """Mark OTP as redeemed."""
        otp.is_used = True
        otp.used_at = datetime.now(timezone.utc)
        await self.session.flush()
