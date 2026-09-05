from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.config.settings import get_settings
from app.dependencies.auth import CurrentUser, DatabaseSession, current_access_payload, current_session_id
from app.middleware.rate_limit import rate_limiter
from app.permissions.dependencies import require_admin, require_owner, require_permission, require_roles
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutAllResponse,
    LogoutRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    SessionResponse,
    UserRead,
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService, RequestMetadata

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _metadata(request: Request) -> RequestMetadata:
    return RequestMetadata(
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent", "")[:2048] or None,
    )


@router.post(
    "/login",
    response_model=APIResponse[LoginResponse],
    summary="Sign in and create a secure session",
)
async def login(payload: LoginRequest, request: Request, session: DatabaseSession) -> APIResponse[LoginResponse]:
    await rate_limiter.enforce(request)
    tokens = await AuthService(session).authenticate(
        payload.email,
        payload.password.get_secret_value(),
        payload.remember_me,
        _metadata(request),
    )
    return APIResponse(data=tokens, message="Login successful")


@router.post(
    "/refresh",
    response_model=APIResponse[RefreshTokenResponse],
    summary="Rotate a refresh token and issue new credentials",
)
async def refresh(payload: RefreshRequest, request: Request, session: DatabaseSession) -> APIResponse[RefreshTokenResponse]:
    tokens = await AuthService(session).refresh(payload.refresh_token, _metadata(request))
    return APIResponse(data=tokens, message="Token refreshed successfully")


@router.post("/logout", response_model=APIResponse[None], summary="End the current refresh-token session")
async def logout(
    payload: LogoutRequest,
    request: Request,
    session: DatabaseSession,
    user: CurrentUser,
) -> APIResponse[None]:
    await AuthService(session).logout(user, payload.refresh_token, current_access_payload(request))
    return APIResponse(data=None, message="Logout successful")


@router.post("/logout-all", response_model=APIResponse[LogoutAllResponse], summary="End every active user session")
async def logout_all(session: DatabaseSession, user: CurrentUser) -> APIResponse[LogoutAllResponse]:
    revoked_sessions = await AuthService(session).logout_all(user)
    return APIResponse(data=LogoutAllResponse(revoked_sessions=revoked_sessions), message="Logged out from all devices successfully")


@router.post(
    "/forgot-password",
    response_model=APIResponse[ForgotPasswordResponse | None],
    summary="Request password reset instructions",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: DatabaseSession,
) -> APIResponse[ForgotPasswordResponse | None]:
    await rate_limiter.enforce(request)
    raw_token = await AuthService(session).request_password_reset(payload.email, _metadata(request))
    response_data = ForgotPasswordResponse(development_reset_token=raw_token) if raw_token else None
    return APIResponse(
        data=response_data,
        message="If an account exists for this email, password reset instructions have been sent.",
    )


@router.post("/reset-password", response_model=APIResponse[None], summary="Set a password with a one-time reset token")
async def reset_password(payload: ResetPasswordRequest, session: DatabaseSession) -> APIResponse[None]:
    await AuthService(session).reset_password(payload.token, payload.new_password.get_secret_value())
    return APIResponse(data=None, message="Password reset successfully. Please log in again.")


@router.post("/change-password", response_model=APIResponse[None], summary="Change the authenticated user's password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    session: DatabaseSession,
    user: CurrentUser,
) -> APIResponse[None]:
    await AuthService(session).change_password(
        user,
        payload.current_password.get_secret_value(),
        payload.new_password.get_secret_value(),
        payload.logout_other_sessions,
        current_session_id(request),
    )
    return APIResponse(data=None, message="Password changed successfully")


@router.get("/me", response_model=APIResponse[UserRead], summary="Get the authenticated user's profile")
async def me(user: CurrentUser, session: DatabaseSession) -> APIResponse[UserRead]:
    return APIResponse(data=AuthService(session).profile.serialize(user), message="Profile retrieved successfully")


@router.patch("/me", response_model=APIResponse[UserRead], summary="Update approved profile fields")
async def update_me(
    payload: ProfileUpdateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> APIResponse[UserRead]:
    profile = await AuthService(session).profile.update(user, payload)
    return APIResponse(data=profile, message="Profile updated successfully")


@router.get("/sessions", response_model=APIResponse[list[SessionResponse]], summary="List active sessions for the current user")
async def sessions(request: Request, session: DatabaseSession, user: CurrentUser) -> APIResponse[list[SessionResponse]]:
    data = await AuthService(session).list_sessions(user, current_session_id(request))
    return APIResponse(data=data, message="Active sessions retrieved successfully")


@router.delete("/sessions/{session_id}", response_model=APIResponse[None], summary="Revoke one of the current user's sessions")
async def revoke_session(session_id: UUID, session: DatabaseSession, user: CurrentUser) -> APIResponse[None]:
    await AuthService(session).revoke_session(user, session_id)
    return APIResponse(data=None, message="Session revoked successfully")


if get_settings().enable_auth_test_routes:
    test_router = APIRouter(prefix="/test", tags=["Authentication test routes"], include_in_schema=False)

    @test_router.get("/authenticated")
    async def authenticated(user: CurrentUser) -> dict[str, str]:
        return {"user_id": str(user.id)}

    @test_router.get("/owner", dependencies=[Depends(require_owner)])
    async def owner_only() -> dict[str, bool]:
        return {"authorized": True}

    @test_router.get("/manager", dependencies=[Depends(require_roles("MANAGER"))])
    async def manager_only() -> dict[str, bool]:
        return {"authorized": True}

    @test_router.get("/permission/users-read", dependencies=[Depends(require_permission("users.read"))])
    async def users_read() -> dict[str, bool]:
        return {"authorized": True}

    @test_router.get("/admin", dependencies=[Depends(require_admin)])
    async def admin_only() -> dict[str, bool]:
        return {"authorized": True}

    router.include_router(test_router)
