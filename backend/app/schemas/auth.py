from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator

from app.models.auth import RoleName, UserStatus
from app.schemas.common import ORMModel


class LoginRequest(ORMModel):
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)
    remember_me: bool = False

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()


class RefreshRequest(ORMModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(ORMModel):
    refresh_token: str = Field(min_length=20)


class ForgotPasswordRequest(ORMModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()


class ResetPasswordRequest(ORMModel):
    token: str = Field(min_length=32, max_length=1024)
    new_password: SecretStr = Field(min_length=8, max_length=128)
    confirm_password: SecretStr = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password.get_secret_value() != self.confirm_password.get_secret_value():
            raise ValueError("New password and confirmation do not match")
        return self


class ChangePasswordRequest(ORMModel):
    current_password: SecretStr = Field(min_length=8, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=128)
    confirm_password: SecretStr = Field(min_length=8, max_length=128)
    logout_other_sessions: bool = True

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password.get_secret_value() != self.confirm_password.get_secret_value():
            raise ValueError("New password and confirmation do not match")
        return self


class RoleRead(ORMModel):
    id: UUID
    name: RoleName
    description: str


class UserRead(ORMModel):
    id: UUID
    email: EmailStr
    name: str
    phone: str | None = None
    avatar_url: str | None = None
    status: UserStatus
    roles: list[str]
    permissions: list[str]
    assigned_store_id: UUID | None = None
    assigned_store_name: str | None = None
    assigned_store: None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    preferred_language: str
    timezone: str


class LoginResponse(ORMModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    access_token_expires_in: int
    refresh_token_expires_in: int
    user: UserRead


class RefreshTokenResponse(ORMModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    access_token_expires_in: int
    refresh_token_expires_in: int


class ProfileUpdateRequest(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    phone: str | None = Field(default=None, max_length=32)
    avatar_url: str | None = Field(default=None, max_length=2048)
    preferred_language: str | None = Field(default=None, pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        digits = normalized.removeprefix("+")
        if not digits.isdigit() or not 7 <= len(digits) <= 15:
            raise ValueError("Phone must be a valid international phone number")
        return normalized

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("Avatar URL must use HTTP or HTTPS")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Timezone must be a valid IANA timezone") from error
        return value


class SessionResponse(ORMModel):
    session_id: UUID
    device_name: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    is_current_session: bool


class LogoutAllResponse(ORMModel):
    revoked_sessions: int


class ForgotPasswordResponse(ORMModel):
    development_reset_token: str | None = None


TokenPair = LoginResponse
