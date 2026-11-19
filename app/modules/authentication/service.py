"""Authentication Business Logic Service.

Implements enterprise authentication workflows:
- Argon2id password verification and automatic rehashing.
- Account lockout policy on repeated authentication failures.
- Access token generation (RS256 JWT).
- Opaque Refresh Token issuance and single-use rotation.
- Automatic Token Reuse Detection (revokes entire user session family if reused).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.core.jwt import create_access_token
from app.core.logging import get_logger
from app.core.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.modules.authentication.models import RefreshToken, User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.authentication.schemas import TokenResponse

logger = get_logger("control_tower.auth_service")
settings = get_settings()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthenticationService:
    """Service handling authentication business operations."""

    def __init__(self, repository: AuthenticationRepository) -> None:
        self.repo = repository

    async def authenticate(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[TokenResponse, str]:
        """Authenticate user credentials, enforce lockout, and issue token pair."""
        now = datetime.now(timezone.utc)
        user = await self.repo.get_user_by_email(email)

        if not user:
            await self.repo.record_login_attempt(
                email=email,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="User not found",
            )
            raise UnauthorizedException("Invalid email or password.")

        # Check account lockout
        if user.locked_until and user.locked_until > now:
            remaining_mins = int((user.locked_until - now).total_seconds() / 60) + 1
            await self.repo.record_login_attempt(
                email=email,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="Account temporarily locked",
            )
            raise UnauthorizedException(
                f"Account is temporarily locked due to failed attempts. Try again in {remaining_mins} minutes."
            )

        # Check active status
        if not user.is_active:
            await self.repo.record_login_attempt(
                email=email,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="Account inactive",
            )
            raise UnauthorizedException("User account is inactive. Please contact your administrator.")

        # Verify password with Argon2id
        if not verify_password(password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                logger.warning(f"User account locked for {email} after {MAX_FAILED_ATTEMPTS} failed attempts.")

            await self.repo.update_user(user)
            await self.repo.record_login_attempt(
                email=email,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="Invalid password",
            )
            raise UnauthorizedException("Invalid email or password.")

        # Password is valid - reset lock counters
        user.failed_login_attempts = 0
        user.locked_until = None

        # Check if hash needs upgrading
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        await self.repo.update_user(user)
        await self.repo.record_login_attempt(
            email=email,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return await self._create_tokens_for_user(user)

    async def rotate_refresh_token(self, raw_refresh_token: str) -> Tuple[TokenResponse, str]:
        """Validate and rotate an opaque refresh token with reuse detection."""
        now = datetime.now(timezone.utc)
        token_hash = hash_token(raw_refresh_token)

        token_record = await self.repo.get_refresh_token_by_hash(token_hash)
        if not token_record:
            raise UnauthorizedException("Invalid or unrecognized refresh token.")

        # Token Reuse Detection: If token is already revoked, an attack may be occurring
        if token_record.is_revoked:
            logger.critical(
                f"SECURITY ALERT: Refresh token reuse detected for user {token_record.user_id}! "
                f"Revoking all active sessions for this user."
            )
            await self.repo.revoke_all_user_tokens(token_record.user_id)
            raise UnauthorizedException(
                "Security alert: Token reuse detected. All active sessions have been terminated."
            )

        # Check token expiration
        if token_record.expires_at < now:
            await self.repo.revoke_refresh_token(token_record)
            raise UnauthorizedException("Refresh token has expired. Please log in again.")

        # Check user status
        user = await self.repo.get_user_by_id(token_record.user_id)
        if not user or not user.is_active:
            await self.repo.revoke_refresh_token(token_record)
            raise UnauthorizedException("User account is inactive or not found.")

        # Generate new replacement token
        new_raw_token = generate_opaque_token()
        new_token_hash = hash_token(new_raw_token)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_token_record = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=expires_at,
        )
        new_token_record = await self.repo.create_refresh_token(new_token_record)

        # Revoke the old token and link to replacement
        await self.repo.revoke_refresh_token(
            token=token_record,
            replaced_by_token_id=new_token_record.id,
        )

        # Issue new short-lived access token
        access_token = create_access_token(user_id=user.id, email=user.email)
        token_response = TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return token_response, new_raw_token

    async def logout(self, raw_refresh_token: Optional[str]) -> None:
        """Revoke refresh token session on user logout."""
        if not raw_refresh_token:
            return

        token_hash = hash_token(raw_refresh_token)
        token_record = await self.repo.get_refresh_token_by_hash(token_hash)
        if token_record and not token_record.is_revoked:
            await self.repo.revoke_refresh_token(token_record)

    async def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change user password, rehash with Argon2id, and revoke existing sessions."""
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise UnauthorizedException("User not found.")

        if not verify_password(current_password, user.hashed_password):
            raise UnauthorizedException("Current password is incorrect.")

        user.hashed_password = hash_password(new_password)
        await self.repo.update_user(user)

        # Invalidate all current active refresh tokens after password change
        await self.repo.revoke_all_user_tokens(user.id)

    async def _create_tokens_for_user(self, user: User) -> Tuple[TokenResponse, str]:
        """Internal helper to create a fresh JWT access token and opaque refresh token."""
        now = datetime.now(timezone.utc)

        # Generate opaque refresh token
        raw_refresh_token = generate_opaque_token()
        token_hash = hash_token(raw_refresh_token)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        await self.repo.create_refresh_token(refresh_record)

        # Generate JWT access token
        access_token = create_access_token(user_id=user.id, email=user.email)

        token_response = TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return token_response, raw_refresh_token
