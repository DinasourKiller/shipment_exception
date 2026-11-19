"""Impact Assessment Database Models.

Defines PostgreSQL entities for exception financial, customer, and composite impact scoring.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.authentication.models import User
from app.modules.exceptions.models import ShipmentException


class CustomerImpactLevel(str, enum.Enum):
    """Categorization of severity on customer experience / contractual satisfaction."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SupplyChainImpactLevel(str, enum.Enum):
    """Network-level cascade disruption assessment."""

    MINIMAL = "MINIMAL"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class ImpactAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Quantitative impact assessment evaluated for an operational shipment exception."""

    __tablename__ = "impact_assessments"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipment_exceptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Associated shipment exception",
    )

    # Financial Exposure Metrics (in USD)
    financial_impact: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Total calculated financial exposure in USD",
    )
    delay_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Direct cost of delivery delay",
    )
    cargo_damage_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Estimated loss or spoilage risk on cargo value",
    )
    contractual_penalty_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Carrier SLA penalties or demurrage charges",
    )

    # Qualitative & Network Categorizations
    customer_impact: Mapped[str] = mapped_column(
        String(20),
        default=CustomerImpactLevel.MEDIUM.value,
        nullable=False,
        comment="Customer satisfaction/relationship impact level",
    )
    supply_chain_impact: Mapped[str] = mapped_column(
        String(20),
        default=SupplyChainImpactLevel.MINIMAL.value,
        nullable=False,
        comment="Supply chain ripple effect or multimodal delay risk",
    )

    # Composite Priority Metric (0.0 - 100.0)
    composite_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        index=True,
        nullable=False,
        comment="Normalized priority index (0-100)",
    )

    # Automated Escalation State
    is_auto_escalated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        nullable=False,
        comment="True if auto-escalated to supervisor/manager due to high impact",
    )
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Reason recorded if automatic escalation triggered",
    )

    # Granular calculation variables & audit factors
    calculation_factors: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Granular formula inputs and factor breakdowns",
    )

    assessed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who triggered or confirmed assessment (null if system)",
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    exception: Mapped["ShipmentException"] = relationship(
        "ShipmentException",
        foreign_keys=[exception_id],
        lazy="selectin",
    )
    assessed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assessed_by_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_impact_exception_created", "exception_id", "created_at"),
        Index("ix_impact_score_escalated", "composite_score", "is_auto_escalated"),
    )
