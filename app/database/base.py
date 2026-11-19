"""SQLAlchemy Declarative Base and Reusable Model Mixins.

Follows SQLAlchemy 2.x declarative standard.
Provides UUID primary keys and timezone-aware UTC audit timestamps.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy domain models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Default table name to lowercase entity name."""
        return cls.__name__.lower()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to a dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class UUIDPrimaryKeyMixin:
    """Mixin providing UUID v4 primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )


class TimestampMixin:
    """Mixin providing timezone-aware created_at and updated_at audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
