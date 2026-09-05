from fastapi import APIRouter
from sqlalchemy import text

from app.database.redis import redis_manager
from app.database.session import AsyncSessionFactory
from app.schemas.common import APIResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=APIResponse[dict[str, str]])
async def health() -> APIResponse[dict[str, str]]:
    database_status = "unavailable"
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "unavailable"
    redis_status = "ok" if redis_manager.available else "unavailable"
    overall = "ok" if database_status == "ok" else "degraded"
    return APIResponse(data={"status": overall, "database": database_status, "redis": redis_status})
