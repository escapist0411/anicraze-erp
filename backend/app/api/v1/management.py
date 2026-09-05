from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.dependencies.auth import DatabaseSession
from app.models.auth import RevocationReason, User, UserStatus, user_permissions
from app.permissions.dependencies import require_permission
from app.repositories.management import ManagementRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.schemas.auth import SessionResponse
from app.schemas.common import APIResponse
from app.schemas.management import *
from app.services.management import ManagementService
from app.utils.time import utc_now

router = APIRouter(tags=["Access management"])


def service(session: DatabaseSession, actor: User, request: Request) -> ManagementService:
    return ManagementService(session, actor, request.client.host if request.client else None, request.headers.get("user-agent"))


@router.get("/users", response_model=APIResponse[UserListResponse])
async def list_users(request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.read")), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = None, role: str | None = None, status_filter: UserStatus | None = Query(None, alias="status"), store_id: UUID | None = None, department: str | None = None, designation: str | None = None, sort_by: str = Query("created_at", pattern="^(name|created_at|last_login_at|status)$"), sort_order: str = Query("desc", pattern="^(asc|desc)$")):
    svc = service(session, actor, request); users, total = await svc.repo.list_users(page=page, page_size=page_size, search=search, role=role, status=status_filter, store_id=store_id, department=department, designation=designation, sort_by=sort_by, sort_order=sort_order)
    return APIResponse(data=UserListResponse(items=[await svc.serialize_user(u) for u in users], page=page, page_size=page_size, total=total, pages=ceil(total / page_size) if total else 0))


@router.post("/users", response_model=APIResponse[UserResponse], status_code=201)
async def create_user(data: UserCreateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.create"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.create_user(data)), message="User created")


@router.get("/users/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(user_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.read"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.get_user(user_id)))


@router.patch("/users/{user_id}", response_model=APIResponse[UserResponse])
async def update_user(user_id: UUID, data: UserUpdateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.update"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.update_user(user_id, data)))


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.delete"))):
    await service(session, actor, request).soft_delete(user_id); return Response(status_code=204)


@router.patch("/users/{user_id}/status", response_model=APIResponse[UserResponse])
async def change_status(user_id: UUID, data: UserStatusUpdateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.manage_status"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.status(user_id, data.status, data.reason)))


@router.post("/users/{user_id}/roles", response_model=APIResponse[UserResponse])
async def assign_roles(user_id: UUID, data: IdAssignmentRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.assign_roles"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.assign_roles(user_id, data.role_ids)))


@router.delete("/users/{user_id}/roles/{role_id}", response_model=APIResponse[UserResponse])
async def remove_role(user_id: UUID, role_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.assign_roles"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.remove_role(user_id, role_id)))


@router.post("/users/{user_id}/permissions", response_model=APIResponse[UserResponse])
async def assign_permissions(user_id: UUID, data: UserPermissionAssignmentRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.assign_permissions"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.assign_permissions(user_id, data.permission_ids)))


@router.delete("/users/{user_id}/permissions/{permission_id}", response_model=APIResponse[UserResponse])
async def remove_permission(user_id: UUID, permission_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.assign_permissions"))):
    svc = service(session, actor, request); user = await svc.get_user(user_id); await session.execute(user_permissions.delete().where(user_permissions.c.user_id == user_id, user_permissions.c.permission_id == permission_id)); session.expire(user, ["direct_permissions"]); await svc._audit("USER_PERMISSION_REMOVED", "user", user.id, user.id, {"permission_id": str(permission_id)}); return APIResponse(data=await svc.serialize_user(await svc.get_user(user.id)))


@router.post("/users/{user_id}/reset-password", response_model=APIResponse[dict])
async def reset_password(user_id: UUID, data: AdminPasswordResetRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.reset_password"))):
    await service(session, actor, request).reset_password(user_id, data.new_password, data.force_change_on_next_login, data.revoke_all_sessions); return APIResponse(data={}, message="Password reset")


@router.post("/users/{user_id}/unlock", response_model=APIResponse[UserResponse])
async def unlock(user_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.manage_status"))):
    svc = service(session, actor, request); return APIResponse(data=await svc.serialize_user(await svc.unlock(user_id)))


@router.get("/users/{user_id}/sessions", response_model=APIResponse[list[SessionResponse]])
async def sessions(user_id: UUID, session: DatabaseSession, actor: User = Depends(require_permission("users.manage_sessions"))):
    records = await RefreshTokenRepository(session).list_active_sessions(user_id, utc_now()); return APIResponse(data=[SessionResponse(session_id=r.token_family_id, device_name=r.device_name, user_agent=r.user_agent, ip_address=r.ip_address, created_at=r.created_at, last_used_at=r.last_used_at, expires_at=r.expires_at, is_current_session=False) for r in records])


@router.post("/users/{user_id}/revoke-sessions", response_model=APIResponse[dict])
async def revoke_sessions(user_id: UUID, data: SessionRevocationRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("users.manage_sessions"))):
    svc = service(session, actor, request); await svc.get_user(user_id); count = await svc.sessions.revoke_all_for_user(user_id, RevocationReason.ADMIN_REVOKED, utc_now()); await svc._audit("USER_SESSIONS_REVOKED", "user", user_id, user_id, {"reason": data.reason, "count": count}); return APIResponse(data={"revoked_sessions": count})


@router.get("/users/{user_id}/audit-logs", response_model=APIResponse[list[AuditLogResponse]])
async def audit_logs(user_id: UUID, session: DatabaseSession, actor: User = Depends(require_permission("users.read"))): return APIResponse(data=await ManagementRepository(session).audit_logs(user_id))


@router.get("/roles", response_model=APIResponse[list[RoleDetailResponse]])
async def roles(session: DatabaseSession, actor: User = Depends(require_permission("roles.read"))): return APIResponse(data=await ManagementRepository(session).list_roles())
@router.post("/roles", response_model=APIResponse[RoleDetailResponse], status_code=201)
async def create_role(data: RoleCreateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("roles.create"))): return APIResponse(data=await service(session, actor, request).create_role(data))
@router.get("/roles/{role_id}", response_model=APIResponse[RoleDetailResponse])
async def get_role(role_id: UUID, session: DatabaseSession, actor: User = Depends(require_permission("roles.read"))):
    role = await ManagementRepository(session).role(role_id)
    if not role: from app.exceptions.domain import NotFoundError; raise NotFoundError("Role not found")
    return APIResponse(data=role)
@router.patch("/roles/{role_id}", response_model=APIResponse[RoleDetailResponse])
async def update_role(role_id: UUID, data: RoleUpdateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("roles.update"))): return APIResponse(data=await service(session, actor, request).update_role(role_id, data))
@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(role_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("roles.delete"))): await service(session, actor, request).delete_role(role_id); return Response(status_code=204)
@router.post("/roles/{role_id}/permissions", response_model=APIResponse[RoleDetailResponse])
async def role_permissions_set(role_id: UUID, data: RolePermissionAssignmentRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("roles.assign_permissions"))): return APIResponse(data=await service(session, actor, request).set_role_permissions(role_id, data))
@router.delete("/roles/{role_id}/permissions/{permission_id}", response_model=APIResponse[RoleDetailResponse])
async def role_permission_remove(role_id: UUID, permission_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("roles.assign_permissions"))): return APIResponse(data=await service(session, actor, request).remove_role_permission(role_id, permission_id))
@router.get("/roles/{role_id}/users", response_model=APIResponse[list[UserResponse]])
async def role_users(role_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("roles.read"))):
    svc = service(session, actor, request); users, _ = await svc.repo.list_users(page=1, page_size=100, search=None, role=(await svc.repo.role(role_id)).code, status=None, store_id=None, department=None, designation=None, sort_by="name", sort_order="asc"); return APIResponse(data=[await svc.serialize_user(u) for u in users])


@router.get("/permissions/grouped", response_model=APIResponse[dict[str, list[PermissionResponse]]])
async def grouped_permissions(session: DatabaseSession, actor: User = Depends(require_permission("permissions.read"))):
    grouped = {}; [grouped.setdefault(p.module, []).append(p) for p in await ManagementRepository(session).list_permissions()]; return APIResponse(data=grouped)
@router.get("/permissions", response_model=APIResponse[list[PermissionResponse]])
async def permissions(session: DatabaseSession, actor: User = Depends(require_permission("permissions.read"))): return APIResponse(data=await ManagementRepository(session).list_permissions())
@router.post("/permissions", response_model=APIResponse[PermissionResponse], status_code=201)
async def create_permission(data: PermissionCreateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("permissions.create"))): return APIResponse(data=await service(session, actor, request).create_permission(data))
@router.get("/permissions/{permission_id}", response_model=APIResponse[PermissionResponse])
async def get_permission(permission_id: UUID, session: DatabaseSession, actor: User = Depends(require_permission("permissions.read"))): return APIResponse(data=await ManagementRepository(session).permission(permission_id))
@router.patch("/permissions/{permission_id}", response_model=APIResponse[PermissionResponse])
async def update_permission(permission_id: UUID, data: PermissionUpdateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("permissions.update"))): return APIResponse(data=await service(session, actor, request).update_permission(permission_id, data))
@router.delete("/permissions/{permission_id}", status_code=204)
async def delete_permission(permission_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("permissions.delete"))): await service(session, actor, request).delete_permission(permission_id); return Response(status_code=204)
