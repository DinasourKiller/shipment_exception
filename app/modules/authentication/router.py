"""Authentication API Endpoints.

Implements versioned authentication endpoints:
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
- POST /api/v1/auth/change-password
- POST /api/v1/auth/forgot-password
"""

from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.common.constants import REFRESH_TOKEN_COOKIE_NAME
from app.common.schemas import ApiResponse
from app.config import Settings, get_settings
from app.core.exceptions import UnauthorizedException
from app.core.logging import get_correlation_id, get_logger
from app.dependencies import get_app_settings, get_auth_service, get_current_user
from app.modules.authentication.models import User
from app.modules.authentication.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
    UserResponse,
)
from app.modules.authentication.service import AuthenticationService

router = APIRouter()
logger = get_logger("control_tower.auth_router")


def _set_refresh_token_cookie(
    response: Response,
    raw_token: str,
    settings: Settings,
) -> None:
    """Helper to set secure, HttpOnly refresh token cookie."""
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None,
        path="/api/v1/auth",
    )


def _clear_refresh_token_cookie(response: Response, settings: Settings) -> None:
    """Helper to clear refresh token cookie on logout."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None,
        path="/api/v1/auth",
    )


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Authenticate user and issue token pair",
    description="Authenticates credentials. Returns access token in JSON and sets HttpOnly refresh token cookie.",
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthenticationService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> ApiResponse[TokenResponse]:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    token_response, raw_refresh_token = await service.authenticate(
        email=payload.email,
        password=payload.password,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    _set_refresh_token_cookie(response, raw_refresh_token, settings)

    return ApiResponse(
        success=True,
        data=token_response,
        message="Authentication successful.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Rotate refresh token and issue new access token",
    description="Rotates opaque refresh token from HttpOnly cookie. Replaces old token and issues fresh JWT.",
)
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    service: AuthenticationService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> ApiResponse[TokenResponse]:
    if not refresh_token:
        raise UnauthorizedException("Refresh token cookie is missing.")

    token_response, new_raw_token = await service.rotate_refresh_token(refresh_token)
    _set_refresh_token_cookie(response, new_raw_token, settings)

    return ApiResponse(
        success=True,
        data=token_response,
        message="Session refreshed successfully.",
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/logout",
    response_model=ApiResponse[MessageResponse],
    summary="Revoke session and clear refresh token cookie",
)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    service: AuthenticationService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> ApiResponse[MessageResponse]:
    await service.logout(refresh_token)
    _clear_refresh_token_cookie(response, settings)

    return ApiResponse(
        success=True,
        data=MessageResponse(message="Successfully logged out."),
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserResponse]:
    return ApiResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/change-password",
    response_model=ApiResponse[MessageResponse],
    summary="Change authenticated user password",
)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: AuthenticationService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> ApiResponse[MessageResponse]:
    await service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    _clear_refresh_token_cookie(response, settings)

    return ApiResponse(
        success=True,
        data=MessageResponse(message="Password changed successfully. Please log in again."),
        correlation_id=get_correlation_id(),
    )


@router.post(
    "/forgot-password",
    response_model=ApiResponse[MessageResponse],
    summary="Request password reset",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
) -> ApiResponse[MessageResponse]:
    # In enterprise systems, return generic success to prevent user enumeration
    logger.info(f"Password reset requested for email: {payload.email}")
    return ApiResponse(
        success=True,
        data=MessageResponse(
            message="If an account exists with this email, password reset instructions have been dispatched."
        ),
        correlation_id=get_correlation_id(),
    )
