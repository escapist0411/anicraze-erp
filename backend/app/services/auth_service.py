import logging
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token, create_refresh_token
from app.config.settings import get_settings
from app.database.redis import redis_manager
from app.exceptions.domain import AuthenticationError, PasswordValidationError
from app.models.auth import PasswordResetToken, RefreshToken, RevocationReason, User, UserStatus
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import LoginResponse, RefreshTokenResponse, SessionResponse
from app.services.email_service import EmailService
from app.services.password_service import PasswordService
from app.services.profile_service import ProfileService
from app.services.token_service import SecurityTokenService
from app.utils.time import after_minutes, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestMetadata:
    ip_address: str | None
    user_agent: str | None

    @property
    def device_name(self) -> str | None:
        if not self.user_agent:
            return None
        return self.user_agent.split("(", maxsplit=1)[0].strip()[:255] or "Unknown device"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = RefreshTokenRepository(session)
        self.password_resets = PasswordResetTokenRepository(session)
        self.passwords = PasswordService()
        self.profile = ProfileService(self.users)
        self.email = EmailService()

    async def authenticate(
        self,
        email: str,
        password: str,
        remember_me: bool,
        metadata: RequestMetadata,
    ) -> LoginResponse:
        occurred_at = utc_now()
        user = await self.users.get_with_roles_and_permissions_by_email(email.lower(), lock=True)
        if user is None:
            raise AuthenticationError("Invalid email or password.", "AUTH_INVALID_CREDENTIALS")
        if not self._can_authenticate(user, occurred_at):
            raise AuthenticationError("Invalid email or password.", "AUTH_INVALID_CREDENTIALS")
        if not self.passwords.verify(password, user.password_hash):
            await self._record_login_failure(user, occurred_at)
            raise AuthenticationError("Invalid email or password.", "AUTH_INVALID_CREDENTIALS")

        await self.users.update_login_success(user, occurred_at, metadata.ip_address)
        expiry_days = (
            get_settings().remember_me_refresh_token_expire_days
            if remember_me
            else get_settings().refresh_token_expire_days
        )
        family_id = uuid4()
        return await self._issue_login_tokens(user, family_id, expiry_days, metadata, occurred_at)

    async def refresh(self, encoded_refresh_token: str, metadata: RequestMetadata) -> RefreshTokenResponse:
        payload = SecurityTokenService.decode_refresh_token(encoded_refresh_token)
        occurred_at = utc_now()
        jti = str(payload["jti"])
        record = await self.sessions.get_by_jti(jti, lock=True)
        if record is None:
            raise AuthenticationError("Refresh token is invalid", "AUTH_TOKEN_INVALID")

        if (
            record.revoked_at is not None
            or record.expires_at <= occurred_at
            or record.token_hash != SecurityTokenService.hash_token(encoded_refresh_token)
        ):
            await self.sessions.revoke_family(
                record.token_family_id,
                RevocationReason.SECURITY_REUSE_DETECTED,
                occurred_at,
            )
            await self.session.commit()
            logger.warning("Refresh token reuse detected for user_id=%s family_id=%s", record.user_id, record.token_family_id)
            raise AuthenticationError("Refresh token is invalid", "AUTH_REFRESH_TOKEN_REUSED")

        try:
            subject = UUID(str(payload["sub"]))
            family_id = UUID(str(payload["sid"]))
        except (KeyError, TypeError, ValueError) as error:
            raise AuthenticationError("Refresh token is invalid", "AUTH_TOKEN_INVALID") from error
        if subject != record.user_id or family_id != record.token_family_id:
            await self.sessions.revoke_family(record.token_family_id, RevocationReason.SECURITY_REUSE_DETECTED, occurred_at)
            await self.session.commit()
            logger.warning("Refresh token session claim mismatch for user_id=%s", record.user_id)
            raise AuthenticationError("Refresh token is invalid", "AUTH_TOKEN_INVALID")

        user = await self.users.get_with_roles_and_permissions(record.user_id, lock=True)
        if user is None or not self._can_authenticate(user, occurred_at):
            raise AuthenticationError("User account is unavailable", "AUTH_ACCOUNT_INACTIVE")

        original_lifetime_days = max(1, ceil((record.expires_at - record.created_at).total_seconds() / 86_400))
        refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
            user,
            session_family_id=record.token_family_id,
            expires_days=original_lifetime_days,
        )
        replacement = RefreshToken(
            user_id=user.id,
            jti=refresh_jti,
            token_hash=SecurityTokenService.hash_token(refresh_token),
            token_family_id=record.token_family_id,
            user_agent=metadata.user_agent or record.user_agent,
            ip_address=metadata.ip_address or record.ip_address,
            device_name=metadata.device_name or record.device_name,
            last_used_at=occurred_at,
            expires_at=refresh_expires_at,
        )
        await self.sessions.rotate_token(record, replacement, occurred_at)
        access_token, access_expires_at = create_access_token(user, record.token_family_id)
        return RefreshTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_in=self._seconds_until(access_expires_at),
            refresh_token_expires_in=self._seconds_until(refresh_expires_at),
        )

    async def logout(self, user: User, encoded_refresh_token: str, access_payload: dict[str, object] | None) -> None:
        occurred_at = utc_now()
        try:
            payload = SecurityTokenService.decode_refresh_token(encoded_refresh_token)
            record = await self.sessions.get_by_jti(str(payload["jti"]), lock=True)
        except AuthenticationError:
            record = None
        if record is not None and record.user_id == user.id:
            await self.sessions.revoke_token(record, RevocationReason.LOGOUT, occurred_at)
        await self._blacklist_access_token(access_payload, occurred_at)

    async def logout_all(self, user: User) -> int:
        occurred_at = utc_now()
        count = await self.sessions.revoke_all_for_user(user.id, RevocationReason.LOGOUT_ALL, occurred_at)
        user.token_version += 1
        await self.session.flush()
        return count

    async def list_sessions(self, user: User, current_session_id: UUID | None) -> list[SessionResponse]:
        sessions = await self.sessions.list_active_sessions(user.id, utc_now())
        return [
            SessionResponse(
                session_id=record.token_family_id,
                device_name=record.device_name,
                user_agent=record.user_agent,
                ip_address=record.ip_address,
                created_at=record.created_at,
                last_used_at=record.last_used_at,
                expires_at=record.expires_at,
                is_current_session=record.token_family_id == current_session_id,
            )
            for record in sessions
        ]

    async def revoke_session(self, user: User, session_id: UUID) -> bool:
        record = await self.sessions.get_active_session(user.id, session_id, utc_now())
        if record is None:
            return False
        await self.sessions.revoke_family(session_id, RevocationReason.LOGOUT, utc_now())
        return True

    async def request_password_reset(self, email: str, metadata: RequestMetadata) -> str | None:
        user = await self.users.get_with_roles_and_permissions_by_email(email.lower())
        if user is None or not user.account_is_active:
            return None
        occurred_at = utc_now()
        raw_token = SecurityTokenService.generate_password_reset_token()
        await self.password_resets.invalidate_existing_tokens(user.id, occurred_at)
        await self.password_resets.create(
            PasswordResetToken(
                user_id=user.id,
                token_hash=SecurityTokenService.hash_token(raw_token),
                expires_at=after_minutes(get_settings().password_reset_expire_minutes),
                requested_ip=metadata.ip_address,
                user_agent=metadata.user_agent,
            )
        )
        await self.email.send_password_reset(user, raw_token)
        if get_settings().environment == "development" and get_settings().expose_dev_reset_token:
            return raw_token
        return None

    async def reset_password(self, token: str, new_password: str) -> None:
        occurred_at = utc_now()
        reset_record = await self.password_resets.get_valid_token_by_hash(
            SecurityTokenService.hash_token(token), occurred_at, lock=True
        )
        if reset_record is None:
            raise AuthenticationError("Password reset token is invalid or expired", "AUTH_TOKEN_INVALID")
        user = await self.users.get_with_roles_and_permissions(reset_record.user_id, lock=True)
        if user is None:
            raise AuthenticationError("Password reset token is invalid or expired", "AUTH_TOKEN_INVALID")
        self.passwords.validate_new_password(new_password, user)
        if self.passwords.verify(new_password, user.password_hash):
            raise PasswordValidationError("New password cannot match the current password", "AUTH_PASSWORD_REUSE_NOT_ALLOWED")
        await self.users.update_password(user, self.passwords.hash(new_password), occurred_at, invalidate_access=True)
        await self.password_resets.mark_as_used(reset_record, occurred_at)
        await self.sessions.revoke_all_for_user(user.id, RevocationReason.PASSWORD_RESET, occurred_at)

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        logout_other_sessions: bool,
        current_session_id: UUID | None,
    ) -> None:
        locked_user = await self.users.get_with_roles_and_permissions(user.id, lock=True)
        if locked_user is None or not self.passwords.verify(current_password, locked_user.password_hash):
            raise AuthenticationError("Current password is invalid", "AUTH_CURRENT_PASSWORD_INVALID")
        self.passwords.validate_new_password(new_password, locked_user)
        if self.passwords.verify(new_password, locked_user.password_hash):
            raise PasswordValidationError("New password cannot match the current password", "AUTH_PASSWORD_REUSE_NOT_ALLOWED")
        occurred_at = utc_now()
        await self.users.update_password(locked_user, self.passwords.hash(new_password), occurred_at, invalidate_access=False)
        if logout_other_sessions:
            if current_session_id is None:
                await self.sessions.revoke_all_for_user(locked_user.id, RevocationReason.PASSWORD_CHANGED, occurred_at)
            else:
                await self.sessions.revoke_all_except_family(
                    locked_user.id,
                    current_session_id,
                    RevocationReason.PASSWORD_CHANGED,
                    occurred_at,
                )

    async def _record_login_failure(self, user: User, occurred_at: datetime) -> None:
        settings = get_settings()
        next_attempt = user.failed_login_attempts + 1
        locked_until = after_minutes(settings.auth_lock_minutes) if next_attempt >= settings.auth_max_login_attempts else None
        await self.users.update_login_failure(user, occurred_at, locked_until)
        await self.session.commit()

    @staticmethod
    def _can_authenticate(user: User, occurred_at: datetime) -> bool:
        return (
            user.account_is_active
            and user.status != UserStatus.LOCKED
            and (user.locked_until is None or user.locked_until <= occurred_at)
        )

    async def _issue_login_tokens(
        self,
        user: User,
        family_id: UUID,
        refresh_expiry_days: int,
        metadata: RequestMetadata,
        occurred_at: datetime,
    ) -> LoginResponse:
        access_token, access_expires_at = create_access_token(user, family_id)
        refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
            user,
            session_family_id=family_id,
            expires_days=refresh_expiry_days,
        )
        await self.sessions.create_session(
            RefreshToken(
                user_id=user.id,
                jti=refresh_jti,
                token_hash=SecurityTokenService.hash_token(refresh_token),
                token_family_id=family_id,
                user_agent=metadata.user_agent,
                ip_address=metadata.ip_address,
                device_name=metadata.device_name,
                last_used_at=occurred_at,
                expires_at=refresh_expires_at,
            )
        )
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_in=self._seconds_until(access_expires_at),
            refresh_token_expires_in=self._seconds_until(refresh_expires_at),
            user=self.profile.serialize(user),
        )

    @staticmethod
    def _seconds_until(expires_at: datetime) -> int:
        return max(0, int((expires_at - utc_now()).total_seconds()))

    async def _blacklist_access_token(self, access_payload: dict[str, object] | None, occurred_at: datetime) -> None:
        if access_payload is None or redis_manager.client is None or not redis_manager.available:
            return
        expires_at = access_payload.get("exp")
        jti = access_payload.get("jti")
        if not isinstance(expires_at, (int, float)) or not isinstance(jti, str):
            return
        remaining = max(1, int(expires_at - utc_now().timestamp()))
        try:
            await redis_manager.client.set(f"auth:access-revoked:{jti}", "1", ex=remaining)
        except Exception:
            logger.warning("Unable to add access token revocation entry")
