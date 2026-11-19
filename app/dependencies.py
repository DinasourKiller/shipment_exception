"""Global FastAPI dependencies for injection."""

import uuid
from typing import Optional
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import CORRELATION_ID_HEADER
from app.config import Settings, get_settings
from app.core.exceptions import UnauthorizedException
from app.core.jwt import decode_access_token
from app.core.logging import get_correlation_id
from app.database.connection import get_db_session
from app.modules.authentication.models import User
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.authentication.service import AuthenticationService

security_scheme = HTTPBearer(auto_error=False)


def get_app_settings() -> Settings:
    """Dependency that returns validated application settings."""
    return get_settings()


def get_correlation_id_dep(
    x_correlation_id: Optional[str] = Header(default=None, alias=CORRELATION_ID_HEADER)
) -> Optional[str]:
    """Dependency that extracts correlation ID from header or context."""
    return x_correlation_id or get_correlation_id()


def get_auth_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AuthenticationRepository:
    """Dependency that instantiates AuthenticationRepository."""
    return AuthenticationRepository(session=session)


def get_auth_service(
    repo: AuthenticationRepository = Depends(get_auth_repository),
) -> AuthenticationService:
    """Dependency that instantiates AuthenticationService."""
    return AuthenticationService(repository=repo)


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    repo: AuthenticationRepository = Depends(get_auth_repository),
) -> User:
    """Extract and validate JWT Bearer token, then load current User."""
    if not auth_header or not auth_header.credentials:
        raise UnauthorizedException("Authentication token is required.")

    payload = decode_access_token(auth_header.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Malformed token: subject claim missing.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException("Invalid user ID in token.")

    user = await repo.get_user_by_id(user_uuid)
    if not user:
        raise UnauthorizedException("User associated with token no longer exists.")

    if not user.is_active:
        raise UnauthorizedException("User account is inactive.")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure current user is active."""
    if not current_user.is_active:
        raise UnauthorizedException("User account is disabled.")
    return current_user
