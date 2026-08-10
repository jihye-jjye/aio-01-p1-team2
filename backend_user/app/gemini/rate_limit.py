from uuid import UUID

from redis.asyncio import Redis

from app.gemini.errors import GeminiRateLimitedError

RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RedisGeminiRateLimiter:
    def __init__(self, redis: Redis, *, limit: int = 30, window_seconds: int = 600) -> None:
        self._redis = redis
        self._limit = limit
        self._window_seconds = window_seconds

    async def acquire(self, user_id: UUID) -> None:
        count = await self._redis.eval(
            RATE_LIMIT_SCRIPT,
            1,
            f"gemini:rate:v1:{user_id}",
            self._window_seconds,
        )
        if int(count) > self._limit:
            raise GeminiRateLimitedError("Gemini 사용자별 호출 한도를 초과했습니다.")
