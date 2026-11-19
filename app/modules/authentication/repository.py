"""Authentication Data Access Repository.

Encapsulates all SQLAlchemy 2.x queries for User, RefreshToken, and LoginAttempt.
Never allows external modules to access internal database implementation directly.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.authentication.models import LoginAttempt, RefreshToken, User


class AuthenticationRepository:
    """Repository handling database operations for authentication entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ================= User Operations =================

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Retrieve user by unique UUID with roles preloaded."""
        stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieve user by unique lowercase email with roles preloaded."""
        stmt = select(User).options(selectinload(User.roles)).where(User.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        """Persist a new user entity."""
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        await self.session.flush()
        return user

    # ================= Refresh Token Operations =================

    async def create_refresh_token(self, token: RefreshToken) -> RefreshToken:
        """Store a new hashed refresh token."""
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_refresh_token_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """Lookup a refresh token record by its SHA-256 hash."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self,
        token: RefreshToken,
        replaced_by_token_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Mark a refresh token as revoked."""
        token.is_revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        if replaced_by_token_id:
            token.replaced_by_token_id = replaced_by_token_id
        await self.session.flush()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """Revoke all active tokens for a user (triggered on logout or reuse detection)."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True, revoked_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    # ================= Audit / Login Attempt Operations =================

    async def record_login_attempt(
        self,
        email: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> LoginAttempt:
        """Log authentication attempt for security monitoring."""
        attempt = LoginAttempt(
            email=email.lower().strip(),
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt
