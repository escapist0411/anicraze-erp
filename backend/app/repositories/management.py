from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog, Permission, RefreshToken, Role, User, UserStatus, user_permissions, user_roles


class ManagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def user_options():
        return (selectinload(User.roles).selectinload(Role.permissions), selectinload(User.direct_permissions))

    async def user(self, user_id: UUID, *, lock: bool = False) -> User | None:
        stmt = select(User).options(*self.user_options()).where(User.id == user_id, User.deleted_at.is_(None))
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(func.lower(User.email) == email.lower()))

    async def user_by_employee_code(self, code: str) -> User | None:
        return await self.session.scalar(select(User).where(func.lower(User.employee_code) == code.lower(), User.deleted_at.is_(None)))

    async def list_users(self, *, page: int, page_size: int, search: str | None, role: str | None, status: UserStatus | None, store_id: UUID | None, department: str | None, designation: str | None, sort_by: str, sort_order: str) -> tuple[list[User], int]:
        stmt = select(User).options(*self.user_options()).where(User.deleted_at.is_(None))
        count_stmt = select(func.count(func.distinct(User.id))).where(User.deleted_at.is_(None))
        filters = []
        if search:
            term = f"%{search.strip()}%"
            filters.append(or_(User.full_name.ilike(term), User.email.ilike(term), User.phone.ilike(term), User.employee_code.ilike(term)))
        if status: filters.append(User.status == status)
        if store_id: filters.append(User.assigned_store_id == store_id)
        if department: filters.append(User.department == department)
        if designation: filters.append(User.designation == designation)
        if role:
            stmt = stmt.join(User.roles).where(Role.code == role.upper())
            count_stmt = count_stmt.join(user_roles, user_roles.c.user_id == User.id).join(Role, Role.id == user_roles.c.role_id).where(Role.code == role.upper())
        stmt = stmt.where(*filters); count_stmt = count_stmt.where(*filters)
        columns = {"name": User.full_name, "created_at": User.created_at, "last_login_at": User.last_login_at, "status": User.status}
        column = columns.get(sort_by, User.created_at)
        stmt = stmt.order_by(column.desc().nullslast() if sort_order == "desc" else column.asc().nullslast()).offset((page - 1) * page_size).limit(page_size)
        return list((await self.session.scalars(stmt)).unique().all()), int(await self.session.scalar(count_stmt) or 0)

    async def role(self, role_id: UUID) -> Role | None:
        return await self.session.scalar(select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id))

    async def roles_by_ids(self, ids: list[UUID]) -> list[Role]:
        return list((await self.session.scalars(select(Role).options(selectinload(Role.permissions)).where(Role.id.in_(set(ids)), Role.is_active.is_(True)))).all()) if ids else []

    async def role_by_code(self, code: str) -> Role | None:
        return await self.session.scalar(select(Role).options(selectinload(Role.permissions)).where(Role.code == code.upper()))

    async def list_roles(self) -> list[Role]:
        return list((await self.session.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.code))).all())

    async def permission(self, permission_id: UUID) -> Permission | None:
        return await self.session.get(Permission, permission_id)

    async def permissions_by_ids(self, ids: list[UUID]) -> list[Permission]:
        return list((await self.session.scalars(select(Permission).where(Permission.id.in_(set(ids))))).all()) if ids else []

    async def permission_by_code(self, code: str) -> Permission | None:
        return await self.session.scalar(select(Permission).where(Permission.code == code.lower()))

    async def list_permissions(self) -> list[Permission]:
        return list((await self.session.scalars(select(Permission).order_by(Permission.module, Permission.code))).all())

    async def active_owner_count(self) -> int:
        return int(await self.session.scalar(select(func.count(func.distinct(User.id))).join(user_roles).join(Role).where(Role.code == "OWNER", User.status == UserStatus.ACTIVE, User.is_active.is_(True), User.deleted_at.is_(None))) or 0)

    async def role_user_count(self, role_id: UUID) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role_id)) or 0)

    async def active_session_count(self, user_id: UUID, now: datetime) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)) or 0)

    async def audit(self, log: AuditLog) -> None:
        self.session.add(log); await self.session.flush()

    async def audit_logs(self, user_id: UUID) -> list[AuditLog]:
        return list((await self.session.scalars(select(AuditLog).where(AuditLog.target_user_id == user_id).order_by(AuditLog.created_at.desc()).limit(200))).all())
