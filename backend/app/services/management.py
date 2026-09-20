from datetime import datetime
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.exceptions.domain import AuthorizationError, ConflictError, NotFoundError
from app.models.auth import AuditLog, Permission, RevocationReason, Role, User, UserStatus, role_permissions, user_permissions, user_roles
from app.models.inventory import Store
from app.repositories.management import ManagementRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.schemas.management import PermissionCreateRequest, PermissionUpdateRequest, RoleCreateRequest, RolePermissionAssignmentRequest, RoleUpdateRequest, UserCreateRequest, UserResponse, UserUpdateRequest
from app.services.password_service import PasswordService
from app.utils.time import utc_now


class ManagementService:
    def __init__(self, session: AsyncSession, actor: User, ip: str | None = None, user_agent: str | None = None) -> None:
        self.session, self.actor = session, actor
        self.repo, self.sessions, self.passwords = ManagementRepository(session), RefreshTokenRepository(session), PasswordService()
        self.ip, self.user_agent = ip, user_agent

    def effective(self, user: User) -> list[str]:
        codes = {p.code for r in user.roles for p in r.permissions} | {p.code for p in user.direct_permissions}
        if any(r.code == "OWNER" for r in user.roles): codes.add("*")
        return sorted(codes)

    async def serialize_user(self, user: User) -> UserResponse:
        return UserResponse(id=user.id, name=user.full_name, email=user.email, phone=user.phone, avatar_url=user.avatar_url, status=user.status, assigned_store_id=user.assigned_store_id, employee_code=user.employee_code, designation=user.designation, department=user.department, timezone=user.timezone, preferred_language=user.preferred_language, last_login_at=user.last_login_at, created_at=user.created_at, updated_at=user.updated_at, created_by_id=user.created_by_id, roles=user.roles, direct_permissions=user.direct_permissions, effective_permissions=self.effective(user), active_session_count=await self.repo.active_session_count(user.id, utc_now()))

    async def get_user(self, user_id: UUID, lock: bool = False) -> User:
        user = await self.repo.user(user_id, lock=lock)
        if not user: raise NotFoundError("User not found", "USER_NOT_FOUND")
        return user

    async def create_user(self, data: UserCreateRequest) -> User:
        if await self.repo.user_by_email(data.email): raise ConflictError("Email already exists", "USER_EMAIL_EXISTS")
        if data.employee_code and await self.repo.user_by_employee_code(data.employee_code): raise ConflictError("Employee code already exists", "USER_EMPLOYEE_CODE_EXISTS")
        roles = await self.repo.roles_by_ids(data.role_ids)
        if len(roles) != len(set(data.role_ids)): raise NotFoundError("One or more roles were not found", "ROLE_NOT_FOUND")
        employee_role=bool({r.code for r in roles}&{"SALES","EMPLOYEE"})
        if employee_role and not data.assigned_store_id: raise ConflictError("Sales employees must be assigned to one selling location","EMPLOYEE_STORE_REQUIRED")
        store=await self.session.scalar(select(Store).where(Store.id==data.assigned_store_id,Store.deleted_at.is_(None))) if data.assigned_store_id else None
        if data.assigned_store_id and not store: raise NotFoundError("Assigned selling location not found","STORE_NOT_FOUND")
        employee_code=data.employee_code
        if employee_role and not employee_code:
            count=await self.session.scalar(select(func.count(User.id)).where(User.assigned_store_id==store.id)) or 0
            employee_code=f"EMP-{store.code.upper()}-{count+1:03d}"
        draft = User(email=data.email, full_name=data.name.strip(), phone=data.phone, employee_code=employee_code, designation=data.designation, department=data.department, assigned_store_id=data.assigned_store_id, status=data.status, is_active=data.status == UserStatus.ACTIVE, password_hash="", created_by_id=self.actor.id, updated_by_id=self.actor.id)
        self.passwords.validate_new_password(data.password, draft); draft.password_hash = self.passwords.hash(data.password); draft.roles = roles
        self.session.add(draft); await self.session.flush(); await self.session.refresh(draft, attribute_names=["roles", "direct_permissions"]); await self._audit("USER_CREATED", "user", draft.id, draft.id, {"roles": [r.code for r in roles]}); return draft

    async def update_user(self, user_id: UUID, data: UserUpdateRequest) -> User:
        user = await self.get_user(user_id, True); changes = data.model_dump(exclude_unset=True)
        if "assigned_store_id" in changes:
            if changes["assigned_store_id"] is None and {r.code for r in user.roles}&{"SALES","EMPLOYEE"}: raise ConflictError("Sales employees must remain assigned to one selling location","EMPLOYEE_STORE_REQUIRED")
            if changes["assigned_store_id"] and not await self.session.scalar(select(Store.id).where(Store.id==changes["assigned_store_id"],Store.deleted_at.is_(None))): raise NotFoundError("Assigned selling location not found","STORE_NOT_FOUND")
        if "employee_code" in changes and changes["employee_code"]:
            duplicate = await self.repo.user_by_employee_code(str(changes["employee_code"]))
            if duplicate and duplicate.id != user.id: raise ConflictError("Employee code already exists", "USER_EMPLOYEE_CODE_EXISTS")
        before = {k: str(getattr(user, "full_name" if k == "name" else k)) for k in changes}
        for key, value in changes.items(): setattr(user, "full_name" if key == "name" else key, value)
        if data.status is not None: user.is_active = data.status == UserStatus.ACTIVE
        user.updated_by_id = self.actor.id; await self.session.flush(); await self._audit("EMPLOYEE_SHOP_CHANGED" if "assigned_store_id" in changes else "USER_UPDATED", "user", user.id, user.id, {"before": before, "changed_fields": list(changes)}); return user

    async def ensure_owner_change_allowed(self, user: User) -> None:
        if any(r.code == "OWNER" for r in user.roles) and await self.repo.active_owner_count() <= 1:
            raise ConflictError("The final active owner is protected", "FINAL_OWNER_PROTECTED")

    async def status(self, user_id: UUID, status: UserStatus, reason: str | None) -> User:
        user = await self.get_user(user_id, True)
        if status != UserStatus.ACTIVE: await self.ensure_owner_change_allowed(user)
        user.status, user.is_active, user.updated_by_id = status, status == UserStatus.ACTIVE, self.actor.id
        if status != UserStatus.ACTIVE: user.token_version += 1; await self.sessions.revoke_all_for_user(user.id, RevocationReason.ADMIN_REVOKED, utc_now())
        await self._audit("USER_" + ("SUSPENDED" if status == UserStatus.SUSPENDED else "DEACTIVATED" if status == UserStatus.INACTIVE else "STATUS_CHANGED"), "user", user.id, user.id, {"status": status.value, "reason": reason})
        await self.session.refresh(user, attribute_names=["roles", "direct_permissions", "updated_at"])
        return user

    async def soft_delete(self, user_id: UUID) -> None:
        user = await self.get_user(user_id, True)
        if user.id == self.actor.id: raise ConflictError("Owners cannot delete their own account", "OWNER_SELF_DELETE_FORBIDDEN")
        await self.ensure_owner_change_allowed(user); user.deleted_at = utc_now(); user.status = UserStatus.INACTIVE; user.is_active = False; user.token_version += 1
        await self.sessions.revoke_all_for_user(user.id, RevocationReason.ADMIN_REVOKED, utc_now()); await self._audit("USER_DELETED", "user", user.id, user.id)

    async def assign_roles(self, user_id: UUID, ids: list[UUID]) -> User:
        user = await self.get_user(user_id, True); roles = await self.repo.roles_by_ids(ids)
        if len(roles) != len(set(ids)): raise NotFoundError("One or more roles were not found", "ROLE_NOT_FOUND")
        existing = {r.id for r in user.roles}; user.roles.extend(r for r in roles if r.id not in existing); await self.session.flush(); await self._audit("USER_ROLE_ASSIGNED", "user", user.id, user.id, {"role_ids": [str(i) for i in ids]}); return await self.get_user(user.id)

    async def remove_role(self, user_id: UUID, role_id: UUID) -> User:
        user = await self.get_user(user_id, True); role = await self.repo.role(role_id)
        if not role: raise NotFoundError("Role not found", "ROLE_NOT_FOUND")
        if role.code == "OWNER": await self.ensure_owner_change_allowed(user)
        user.roles = [r for r in user.roles if r.id != role_id]; await self.session.flush(); await self._audit("USER_ROLE_REMOVED", "user", user.id, user.id, {"role_id": str(role_id)}); return await self.get_user(user.id)

    async def assign_permissions(self, user_id: UUID, ids: list[UUID]) -> User:
        user = await self.get_user(user_id); permissions = await self.repo.permissions_by_ids(ids)
        if len(permissions) != len(set(ids)): raise NotFoundError("One or more permissions were not found", "PERMISSION_NOT_FOUND")
        for p in permissions: await self.session.execute(insert(user_permissions).values(user_id=user.id, permission_id=p.id, granted_by=self.actor.id, created_at=utc_now()).on_conflict_do_nothing())
        self.session.expire(user, ["direct_permissions"])
        await self._audit("USER_PERMISSION_ASSIGNED", "user", user.id, user.id, {"permission_ids": [str(i) for i in ids]}); return await self.get_user(user.id)

    async def reset_password(self, user_id: UUID, password: str, force: bool, revoke: bool) -> None:
        user = await self.get_user(user_id, True)
        if any(r.code == "OWNER" for r in user.roles) and not any(r.code == "OWNER" for r in self.actor.roles): raise AuthorizationError("Only an owner may reset an owner password")
        self.passwords.validate_new_password(password, user); user.password_hash = self.passwords.hash(password); user.password_changed_at = utc_now(); user.must_change_password = force; user.token_version += 1
        if revoke: await self.sessions.revoke_all_for_user(user.id, RevocationReason.PASSWORD_RESET, utc_now())
        await self._audit("USER_PASSWORD_RESET_BY_ADMIN", "user", user.id, user.id, {"sessions_revoked": revoke, "force_change": force})

    async def unlock(self, user_id: UUID) -> User:
        user = await self.get_user(user_id, True); user.failed_login_attempts = 0; user.last_failed_login_at = None; user.locked_until = None
        if user.status == UserStatus.LOCKED: user.status = UserStatus.ACTIVE; user.is_active = True
        await self._audit("USER_UNLOCKED", "user", user.id, user.id); return user

    async def create_role(self, data: RoleCreateRequest) -> Role:
        if await self.repo.role_by_code(data.code): raise ConflictError("Role code already exists", "ROLE_CODE_EXISTS")
        permissions = await self.repo.permissions_by_ids(data.permission_ids)
        if len(permissions) != len(set(data.permission_ids)): raise NotFoundError("Permission not found", "PERMISSION_NOT_FOUND")
        role = Role(name=data.name, code=data.code, description=data.description, is_system=False, is_active=True, permissions=permissions); self.session.add(role); await self.session.flush(); await self._audit("ROLE_CREATED", "role", role.id, metadata={"code": role.code}); return role

    async def create_permission(self, data: PermissionCreateRequest) -> Permission:
        if await self.repo.permission_by_code(data.code): raise ConflictError("Permission code already exists", "PERMISSION_CODE_EXISTS")
        module, action = (data.code.split(".", 1) if data.code != "*" else ("system", "*")); p = Permission(code=data.code, name=data.name, description=data.description, module=data.module or module, action=data.action or action, is_system=False); self.session.add(p); await self.session.flush(); await self._audit("PERMISSION_CREATED", "permission", p.id, metadata={"code": p.code}); return p

    async def update_role(self, role_id: UUID, data: RoleUpdateRequest) -> Role:
        role = await self.repo.role(role_id)
        if not role: raise NotFoundError("Role not found", "ROLE_NOT_FOUND")
        values = data.model_dump(exclude_unset=True)
        if role.is_system: values.pop("code", None)
        if "code" in values: values["code"] = str(values["code"]).strip().upper().replace(" ", "_")
        for key, value in values.items(): setattr(role, key, value)
        await self._audit("ROLE_UPDATED", "role", role.id, metadata={"changed_fields": list(values)}); return role

    async def delete_role(self, role_id: UUID) -> None:
        role = await self.repo.role(role_id)
        if not role: raise NotFoundError("Role not found", "ROLE_NOT_FOUND")
        if role.is_system: raise ConflictError("System roles cannot be deleted", "SYSTEM_ROLE_PROTECTED")
        if await self.repo.role_user_count(role.id): raise ConflictError("Role is assigned to users", "ROLE_IN_USE")
        role.is_active = False; await self._audit("ROLE_DELETED", "role", role.id)

    async def set_role_permissions(self, role_id: UUID, data: RolePermissionAssignmentRequest) -> Role:
        role = await self.repo.role(role_id)
        if not role: raise NotFoundError("Role not found", "ROLE_NOT_FOUND")
        permissions = await self.repo.permissions_by_ids(data.permission_ids)
        if len(permissions) != len(set(data.permission_ids)): raise NotFoundError("Permission not found", "PERMISSION_NOT_FOUND")
        if role.code == "OWNER" and data.mode == "replace" and not any(p.code == "*" for p in permissions): raise ConflictError("OWNER wildcard permission is protected", "OWNER_WILDCARD_PROTECTED")
        if data.mode == "replace": role.permissions = permissions
        else:
            current = {p.id for p in role.permissions}; role.permissions.extend(p for p in permissions if p.id not in current)
        await self.session.flush(); await self._audit("ROLE_PERMISSION_ASSIGNED", "role", role.id, metadata={"mode": data.mode}); return role

    async def remove_role_permission(self, role_id: UUID, permission_id: UUID) -> Role:
        role = await self.repo.role(role_id)
        if not role: raise NotFoundError("Role not found", "ROLE_NOT_FOUND")
        permission = await self.repo.permission(permission_id)
        if not permission: raise NotFoundError("Permission not found", "PERMISSION_NOT_FOUND")
        if role.code == "OWNER" and permission.code == "*": raise ConflictError("OWNER wildcard permission is protected", "OWNER_WILDCARD_PROTECTED")
        role.permissions = [p for p in role.permissions if p.id != permission_id]; await self._audit("ROLE_PERMISSION_REMOVED", "role", role.id, metadata={"permission_id": str(permission_id)}); return role

    async def update_permission(self, permission_id: UUID, data: PermissionUpdateRequest) -> Permission:
        permission = await self.repo.permission(permission_id)
        if not permission: raise NotFoundError("Permission not found", "PERMISSION_NOT_FOUND")
        values = data.model_dump(exclude_unset=True)
        for key, value in values.items(): setattr(permission, key, value)
        await self._audit("PERMISSION_UPDATED", "permission", permission.id, metadata={"changed_fields": list(values)}); return permission

    async def delete_permission(self, permission_id: UUID) -> None:
        permission = await self.repo.permission(permission_id)
        if not permission: raise NotFoundError("Permission not found", "PERMISSION_NOT_FOUND")
        if permission.is_system: raise ConflictError("System permissions cannot be deleted", "SYSTEM_PERMISSION_PROTECTED")
        await self.session.delete(permission); await self._audit("PERMISSION_DELETED", "permission", permission_id)

    async def _audit(self, action: str, entity_type: str, entity_id: UUID, target: UUID | None = None, metadata: dict[str, object] | None = None) -> None:
        await self.repo.audit(AuditLog(actor_user_id=self.actor.id, target_user_id=target, action=action, entity_type=entity_type, entity_id=entity_id, metadata_json=metadata, ip_address=self.ip, user_agent=self.user_agent, created_at=utc_now()))
