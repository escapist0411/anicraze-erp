from uuid import UUID

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.get_with_roles_and_permissions_by_email(email)

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.get_with_roles_and_permissions(user_id)

    @staticmethod
    def _security_options() -> tuple[object, ...]:
        return (selectinload(User.roles).selectinload(Role.permissions), selectinload(User.direct_permissions))

    async def get_with_roles_and_permissions_by_email(self, email: str, *, lock: bool = False) -> User | None:
        statement = (
            select(User)
            .options(*self._security_options())
            .where(User.email == email, User.deleted_at.is_(None))
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_with_roles_and_permissions(self, user_id: UUID, *, lock: bool = False) -> User | None:
        statement = (
            select(User)
            .options(*self._security_options())
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def update_login_success(self, user: User, occurred_at: datetime, ip_address: str | None) -> None:
        user.failed_login_attempts = 0
        user.last_failed_login_at = None
        user.locked_until = None
        user.last_login_at = occurred_at
        user.last_login_ip = ip_address
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["updated_at"])

    async def update_login_failure(self, user: User, occurred_at: datetime, locked_until: datetime | None) -> None:
        user.failed_login_attempts += 1
        user.last_failed_login_at = occurred_at
        user.locked_until = locked_until
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["updated_at"])

    async def reset_login_attempts(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.last_failed_login_at = None
        user.locked_until = None
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["updated_at"])

    async def update_password(self, user: User, password_hash: str, changed_at: datetime, *, invalidate_access: bool) -> None:
        user.password_hash = password_hash
        user.password_changed_at = changed_at
        user.failed_login_attempts = 0
        user.last_failed_login_at = None
        user.locked_until = None
        if invalidate_access:
            user.token_version += 1
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["updated_at"])

    async def update_profile(self, user: User, values: dict[str, object]) -> User:
        for field, value in values.items():
            setattr(user, field, value)
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["updated_at"])
        return user

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
