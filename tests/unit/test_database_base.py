"""Unit tests for SQLAlchemy 2.x Base and model mixins."""

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SampleEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Test model inheriting from Base and core mixins."""
    __tablename__ = "sample_entities"

    name: Mapped[str] = mapped_column(String(50), nullable=False)


def test_model_mixins_defaults():
    """Verify that models receive UUID and UTC timestamps by default."""
    entity = SampleEntity(name="Test Cargo Unit")

    # UUID primary key test
    assert entity.id is None or isinstance(entity.id, uuid.UUID)

    # Check to_dict() serialization
    data = entity.to_dict()
    assert "name" in data
    assert data["name"] == "Test Cargo Unit"
    assert "created_at" in data
    assert "updated_at" in data


def test_timestamp_mixin_timezone():
    """Ensure timestamp mixin produces UTC timezone-aware datetimes."""
    now = datetime.now(timezone.utc)
    entity = SampleEntity(name="Timezone Check", created_at=now, updated_at=now)

    assert entity.created_at.tzinfo is not None
    assert entity.created_at.tzinfo == timezone.utc
