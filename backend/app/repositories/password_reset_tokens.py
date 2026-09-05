from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: PasswordResetToken) -> PasswordResetToken:
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_valid_token_by_hash(self, token_hash: str, occurred_at: datetime, *, lock: bool = False) -> PasswordResetToken | None:
        statement = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > occurred_at,
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def invalidate_existing_tokens(self, user_id: UUID, occurred_at: datetime) -> int:
        result = await self.session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=occurred_at)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def mark_as_used(self, record: PasswordResetToken, occurred_at: datetime) -> None:
        record.used_at = occurred_at
        await self.session.flush()

    async def delete_expired_tokens(self, occurred_at: datetime) -> int:
        result = await self.session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.expires_at <= occurred_at, PasswordResetToken.used_at.is_(None))
            .values(used_at=occurred_at)
        )
        await self.session.flush()
        return int(result.rowcount or 0)
