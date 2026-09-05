import logging

from redis.asyncio import Redis

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self) -> None:
        self.client: Redis | None = None
        self.available = False

    async def connect(self) -> None:
        if not get_settings().redis_enabled:
            self.client = None
            self.available = False
            logger.info("Redis is disabled; in-memory rate limiting will be used")
            return
        self.client = Redis.from_url(get_settings().redis_url, encoding="utf-8", decode_responses=True)
        try:
            await self.client.ping()
            self.available = True
        except Exception as error:
            self.available = False
            logger.warning("Redis is unavailable; in-memory rate limiting will be used: %s", error)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.available = False


redis_manager = RedisManager()
