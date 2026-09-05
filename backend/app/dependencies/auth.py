from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import decode_token
from app.database.redis import redis_manager
from app.database.session import get_db_session
from app.exceptions.domain import AuthenticationError
from app.models.auth import User, UserStatus
from app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    request: Request,
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise AuthenticationError("Authentication credentials are required", "AUTH_TOKEN_INVALID")
    payload = decode_token(credentials.credentials, "access")
    try:
        user_id = UUID(str(payload["sub"]))
        token_version = int(payload["ver"])
    except (KeyError, TypeError, ValueError) as error:
        raise AuthenticationError("Authentication token is invalid", "AUTH_TOKEN_INVALID") from error
    if await _is_access_token_revoked(str(payload["jti"])):
        raise AuthenticationError("Authentication token has been revoked", "AUTH_TOKEN_REVOKED")
    user = await UserRepository(session).get_with_roles_and_permissions(user_id)
    if user is None:
        raise AuthenticationError("User account is unavailable", "AUTH_ACCOUNT_INACTIVE")
    if user.token_version != token_version:
        raise AuthenticationError("Authentication token has been revoked", "AUTH_TOKEN_REVOKED")
    if not _is_currently_active(user):
        raise _account_unavailable_error(user)
    request.state.access_token_payload = payload
    return user


async def get_optional_current_user(
    request: Request,
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    if credentials is None:
        return None
    return await get_current_user(request, session, credentials)


async def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


async def get_current_verified_user(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    return user


def current_access_payload(request: Request) -> dict[str, object] | None:
    payload = getattr(request.state, "access_token_payload", None)
    return payload if isinstance(payload, dict) else None


def current_session_id(request: Request) -> UUID | None:
    payload = current_access_payload(request)
    if payload is None or payload.get("sid") is None:
        return None
    try:
        return UUID(str(payload["sid"]))
    except (TypeError, ValueError):
        return None


def _is_currently_active(user: User) -> bool:
    from app.utils.time import utc_now

    return (
        user.account_is_active
        and user.status != UserStatus.LOCKED
        and (user.locked_until is None or user.locked_until <= utc_now())
    )


def _account_unavailable_error(user: User) -> AuthenticationError:
    from app.utils.time import utc_now

    if (user.locked_until is not None and user.locked_until > utc_now()) or user.status == UserStatus.LOCKED:
        return AuthenticationError("User account is locked", "AUTH_ACCOUNT_LOCKED")
    if user.status == UserStatus.SUSPENDED:
        return AuthenticationError("User account is suspended", "AUTH_ACCOUNT_SUSPENDED")
    return AuthenticationError("User account is inactive", "AUTH_ACCOUNT_INACTIVE")


async def _is_access_token_revoked(jti: str) -> bool:
    if not redis_manager.available or redis_manager.client is None:
        return False
    try:
        return bool(await redis_manager.client.exists(f"auth:access-revoked:{jti}"))
    except Exception:
        return False


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
