from collections.abc import Iterable

from sqlalchemy import Select, asc, desc
from sqlalchemy.orm import InstrumentedAttribute

from app.schemas.common import PaginationParams


def apply_pagination(statement: Select, params: PaginationParams) -> Select:
    return statement.offset(params.offset).limit(params.page_size)


def apply_sort(statement: Select, sort_by: str | None, sort_order: str, allowed_columns: dict[str, InstrumentedAttribute]) -> Select:
    if sort_by is None or sort_by not in allowed_columns:
        return statement
    column = allowed_columns[sort_by]
    return statement.order_by(desc(column) if sort_order == "desc" else asc(column))


def clean_filters(filters: dict[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in filters.items() if value is not None and value != ""}
