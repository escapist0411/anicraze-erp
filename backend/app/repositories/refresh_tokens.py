from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import RefreshToken, RevocationReason


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, record: RefreshToken) -> RefreshToken:
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_jti(self, jti: str, *, lock: bool = False) -> RefreshToken | None:
        statement = select(RefreshToken).where(RefreshToken.jti == jti)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def rotate_token(self, record: RefreshToken, replacement: RefreshToken, occurred_at: datetime) -> RefreshToken:
        record.revoked_at = occurred_at
        record.revoked_reason = RevocationReason.TOKEN_ROTATED
        record.last_used_at = occurred_at
        self.session.add(replacement)
        await self.session.flush()
        record.replaced_by_token_id = replacement.id
        await self.session.flush()
        return replacement

    async def revoke_token(self, record: RefreshToken, reason: RevocationReason, occurred_at: datetime) -> bool:
        if record.revoked_at is not None:
            return False
        record.revoked_at = occurred_at
        record.revoked_reason = reason
        await self.session.flush()
        return True

    async def revoke_family(self, family_id: UUID, reason: RevocationReason, occurred_at: datetime) -> int:
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=occurred_at, revoked_reason=reason)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def revoke_all_for_user(self, user_id: UUID, reason: RevocationReason, occurred_at: datetime) -> int:
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=occurred_at, revoked_reason=reason)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def revoke_all_except_family(self, user_id: UUID, family_id: UUID, reason: RevocationReason, occurred_at: datetime) -> int:
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_family_id != family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=occurred_at, revoked_reason=reason)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def list_active_sessions(self, user_id: UUID, occurred_at: datetime) -> list[RefreshToken]:
        statement = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > occurred_at,
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get_active_session(self, user_id: UUID, family_id: UUID, occurred_at: datetime) -> RefreshToken | None:
        return await self.session.scalar(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_family_id == family_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > occurred_at,
            )
        )

    async def delete_expired_tokens(self, occurred_at: datetime) -> int:
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.expires_at <= occurred_at, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=occurred_at, revoked_reason=RevocationReason.ADMIN_REVOKED)
        )
        await self.session.flush()
        return int(result.rowcount or 0)
