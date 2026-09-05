from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.auth import UserStatus


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    phone: str | None = Field(None, max_length=32)
    password: str
    confirm_password: str
    role_ids: list[UUID] = Field(default_factory=list)
    assigned_store_id: UUID | None = None
    employee_code: str | None = Field(None, max_length=64)
    designation: str | None = Field(None, max_length=120)
    department: str | None = Field(None, max_length=120)
    status: UserStatus = UserStatus.ACTIVE

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserUpdateRequest(StrictModel):
    name: str | None = Field(None, min_length=2, max_length=180)
    phone: str | None = Field(None, max_length=32)
    avatar_url: str | None = Field(None, max_length=2048)
    assigned_store_id: UUID | None = None
    employee_code: str | None = Field(None, max_length=64)
    designation: str | None = Field(None, max_length=120)
    department: str | None = Field(None, max_length=120)
    status: UserStatus | None = None
    timezone: str | None = Field(None, max_length=64)
    preferred_language: str | None = Field(None, max_length=10)


class UserStatusUpdateRequest(StrictModel):
    status: UserStatus
    reason: str | None = Field(None, max_length=500)


class IdAssignmentRequest(StrictModel):
    role_ids: list[UUID] = Field(default_factory=list)


class UserPermissionAssignmentRequest(StrictModel):
    permission_ids: list[UUID] = Field(default_factory=list)


class AdminPasswordResetRequest(StrictModel):
    new_password: str
    confirm_password: str
    force_change_on_next_login: bool = True
    revoke_all_sessions: bool = True

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class SessionRevocationRequest(StrictModel):
    reason: str | None = Field(None, max_length=500)


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    description: str
    module: str
    action: str
    is_system: bool


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str
    description: str
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RoleDetailResponse(RoleResponse):
    permissions: list[PermissionResponse] = Field(default_factory=list)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    phone: str | None
    avatar_url: str | None
    status: UserStatus
    assigned_store_id: UUID | None
    employee_code: str | None
    designation: str | None
    department: str | None
    timezone: str
    preferred_language: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by_id: UUID | None
    roles: list[RoleResponse]
    direct_permissions: list[PermissionResponse]
    effective_permissions: list[str]
    active_session_count: int = 0


class UserListResponse(BaseModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int
    pages: int


class RoleCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=255)
    permission_ids: list[UUID] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper().replace(" ", "_")


class RoleUpdateRequest(StrictModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    code: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class RolePermissionAssignmentRequest(StrictModel):
    mode: Literal["replace", "add"] = "replace"
    permission_ids: list[UUID] = Field(default_factory=list)


class PermissionCreateRequest(StrictModel):
    code: str = Field(pattern=r"^(\*|[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=255)
    module: str | None = None
    action: str | None = None


class PermissionUpdateRequest(StrictModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=255)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_user_id: UUID | None
    target_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    metadata_json: dict[str, object] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
