from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import EntityBase
from app.schemas.common import Page, PaginationParams
from app.utils.query import apply_pagination

ModelT = TypeVar("ModelT", bound=EntityBase)


class Repository(Generic[ModelT]):
    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, entity_id: UUID) -> ModelT | None:
        return await self.session.scalar(select(self.model).where(self.model.id == entity_id, self.model.deleted_at.is_(None)))

    async def list(self, params: PaginationParams, statement: Select | None = None) -> Page[ModelT]:
        query = statement or select(self.model).where(self.model.deleted_at.is_(None))
        total = await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = list((await self.session.scalars(apply_pagination(query, params))).all())
        pages = max(1, (total + params.page_size - 1) // params.page_size)
        return Page(items=items, page=params.page, page_size=params.page_size, total=total, pages=pages)

    async def soft_delete(self, entity: ModelT) -> None:
        from app.utils.time import utc_now
        entity.deleted_at = utc_now()
