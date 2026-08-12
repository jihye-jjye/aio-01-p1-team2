from uuid import UUID

from redis.asyncio import Redis


class RedisRefreshTokenStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def save(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        token_hash: str,
        ttl_seconds: int,
    ) -> None:
        key = f"auth:refresh:{session_id}"
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.hset(
                key,
                mapping={"user_id": str(user_id), "token_hash": token_hash},
            )
            pipeline.expire(key, ttl_seconds)
            await pipeline.execute()

    async def revoke(self, *, session_id: UUID) -> None:
        await self._redis.delete(f"auth:refresh:{session_id}")
