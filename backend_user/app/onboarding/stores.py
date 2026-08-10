from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import LockError

from app.onboarding.models import OnboardingResponse, OnboardingState


class OnboardingSessionBusyError(RuntimeError):
    pass


class RedisOnboardingSessionStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, *, user_id: UUID, session_id: UUID) -> OnboardingState | None:
        raw_state = await self._redis.get(self._key(user_id, session_id))
        if raw_state is None:
            return None
        return OnboardingState.model_validate_json(raw_state)

    async def save(self, state: OnboardingState, *, ttl_seconds: int) -> None:
        await self._redis.set(
            self._key(state.user_id, state.session_id),
            state.model_dump_json(),
            ex=ttl_seconds,
        )

    async def get_start(self, *, user_id: UUID, request_id: UUID) -> OnboardingResponse | None:
        raw_response = await self._redis.get(self._start_key(user_id, request_id))
        if raw_response is None:
            return None
        return OnboardingResponse.model_validate_json(raw_response)

    async def save_start(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        response: OnboardingResponse,
        ttl_seconds: int,
    ) -> None:
        await self._redis.set(
            self._start_key(user_id, request_id),
            response.model_dump_json(),
            ex=ttl_seconds,
        )

    async def save_started(
        self,
        *,
        state: OnboardingState,
        request_id: UUID,
        response: OnboardingResponse,
        ttl_seconds: int,
    ) -> None:
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.set(
                self._key(state.user_id, state.session_id),
                state.model_dump_json(),
                ex=ttl_seconds,
            )
            pipeline.set(
                self._start_key(state.user_id, request_id),
                response.model_dump_json(),
                ex=ttl_seconds,
            )
            await pipeline.execute()

    @staticmethod
    def _key(user_id: UUID, session_id: UUID) -> str:
        return f"onboarding:v2:{user_id}:{session_id}"

    @staticmethod
    def _start_key(user_id: UUID, request_id: UUID) -> str:
        return f"onboarding:v2:start:{user_id}:{request_id}"


class RedisOnboardingSessionLock:
    def __init__(self, redis: Redis, *, timeout_seconds: float = 90) -> None:
        self._redis = redis
        self._timeout_seconds = max(timeout_seconds, 1)

    @asynccontextmanager
    async def hold(self, *, user_id: UUID, session_id: UUID) -> AsyncIterator[None]:
        lock = self._redis.lock(
            f"onboarding:v2:lock:{user_id}:{session_id}",
            timeout=self._timeout_seconds,
            blocking_timeout=2,
            raise_on_release_error=False,
        )
        try:
            async with lock:
                yield
        except LockError as exc:
            raise OnboardingSessionBusyError("온보딩 요청을 처리 중입니다.") from exc
