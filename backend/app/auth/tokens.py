from datetime import datetime
from uuid import UUID, uuid4

import jwt

from app.config.settings import get_settings
from app.exceptions.domain import AuthenticationError
from app.models.auth import RoleName, User
from app.utils.time import after_days, after_minutes, utc_now


def user_role_names(user: User) -> list[str]:
    return sorted({role.code or str(role.name) for role in user.roles})


def user_permission_codes(user: User) -> list[str]:
    permissions = {permission.code for role in user.roles for permission in role.permissions}
    if any((role.code or str(role.name)) == RoleName.OWNER.value for role in user.roles):
        permissions.add("*")
    return sorted(permissions)


class TokenService:
    """Creates and validates signed, audience-bound authentication tokens."""

    @staticmethod
    def _encode(payload: dict[str, object]) -> str:
        settings = get_settings()
        return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    @classmethod
    def create_access_token(cls, user: User, session_family_id: UUID | None = None) -> tuple[str, datetime]:
        settings = get_settings()
        issued_at = utc_now()
        expires_at = after_minutes(settings.access_token_expire_minutes)
        payload: dict[str, object] = {
            "sub": str(user.id),
            "email": user.email,
            "roles": user_role_names(user),
            "permissions": user_permission_codes(user),
            "token_type": "access",
            "jti": str(uuid4()),
            "ver": user.token_version,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": issued_at,
            "exp": expires_at,
        }
        if session_family_id is not None:
            payload["sid"] = str(session_family_id)
        return cls._encode(payload), expires_at

    @classmethod
    def create_refresh_token(
        cls,
        user: User,
        *,
        session_family_id: UUID | None = None,
        expires_days: int | None = None,
    ) -> tuple[str, str, datetime]:
        settings = get_settings()
        issued_at = utc_now()
        expires_at = after_days(expires_days or settings.refresh_token_expire_days)
        jti = str(uuid4())
        payload: dict[str, object] = {
            "sub": str(user.id),
            "token_type": "refresh",
            "jti": jti,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": issued_at,
            "exp": expires_at,
        }
        if session_family_id is not None:
            payload["sid"] = str(session_family_id)
        return cls._encode(payload), jti, expires_at

    @staticmethod
    def decode_token(token: str, token_type: str) -> dict[str, object]:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "jti", "token_type"]},
            )
        except jwt.ExpiredSignatureError as error:
            raise AuthenticationError("Authentication token has expired", "AUTH_TOKEN_EXPIRED") from error
        except jwt.PyJWTError as error:
            raise AuthenticationError("Authentication token is invalid", "AUTH_TOKEN_INVALID") from error

        if payload.get("token_type") != token_type:
            raise AuthenticationError("Token type is not valid for this operation", "AUTH_TOKEN_INVALID")
        try:
            UUID(str(payload["sub"]))
            UUID(str(payload["jti"]))
            if payload.get("sid") is not None:
                UUID(str(payload["sid"]))
        except (KeyError, TypeError, ValueError) as error:
            raise AuthenticationError("Authentication token is invalid", "AUTH_TOKEN_INVALID") from error
        return payload


def create_access_token(user: User, session_family_id: UUID | None = None) -> tuple[str, datetime]:
    return TokenService.create_access_token(user, session_family_id)


def create_refresh_token(
    user: User, *, session_family_id: UUID | None = None, expires_days: int | None = None
) -> tuple[str, str, datetime]:
    return TokenService.create_refresh_token(user, session_family_id=session_family_id, expires_days=expires_days)


def decode_token(token: str, token_type: str) -> dict[str, object]:
    return TokenService.decode_token(token, token_type)
