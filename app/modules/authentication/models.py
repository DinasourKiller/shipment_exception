"""SQLAlchemy Models for Authentication & Session Tracking.

Follows SQLAlchemy 2.x standard with UUID primary keys and UTC audit timestamps.
Enforces security: Refresh tokens are stored ONLY as SHA-256 hashes.
Tracks token replacement to detect token reuse attacks.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Opaque Refresh Token session entity.

    Stores SHA-256 hash of token to protect against database exfiltration.
    Tracks replacement chain for automatic reuse detection.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_token_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class LoginAttempt(Base, UUIDPrimaryKeyMixin):
    """Audit log of authentication attempts."""

    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
