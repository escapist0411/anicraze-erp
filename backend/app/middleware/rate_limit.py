import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config.settings import get_settings
from app.database.redis import redis_manager


class RateLimiter:
    def __init__(self) -> None:
        self._memory_hits: dict[str, deque[float]] = defaultdict(deque)

    async def enforce(self, request: Request) -> None:
        identity = request.client.host if request.client else "unknown"
        now = time.time()
        settings = get_settings()
        key = f"rate-limit:{identity}:{int(now // 60)}"
        if redis_manager.available and redis_manager.client is not None:
            count = await redis_manager.client.incr(key)
            if count == 1:
                await redis_manager.client.expire(key, 60)
            if count <= settings.rate_limit_per_minute:
                return
        else:
            bucket = self._memory_hits[identity]
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            bucket.append(now)
            if len(bucket) <= settings.rate_limit_per_minute:
                return
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


rate_limiter = RateLimiter()
