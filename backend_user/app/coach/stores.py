from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import LockError

from app.coach.errors import (
    AssistantAlreadyFinalizedError,
    AssistantDataIntegrityError,
    AssistantRevisionConflictError,
    AssistantSessionBusyError,
    AssistantSessionExpiredError,
    AssistantSessionLimitReachedError,
    IdempotencyKeyReusedError,
)
from app.coach.models import (
    AssistantFinalizeResponse,
    AssistantSessionState,
    AssistantSessionTombstone,
    ProcessedAssistantRequest,
)

MAX_ACTIVE_SESSIONS = 3

CREATE_SESSION_SCRIPT = """
-- assistant-create-session
local redis_time = redis.call('TIME')
local now_epoch_ms = tonumber(redis_time[1]) * 1000 + math.floor(tonumber(redis_time[2]) / 1000)
local expires_epoch_ms = tonumber(ARGV[4])
if expires_epoch_ms <= now_epoch_ms then
  return -2
end
if redis.call('EXISTS', KEYS[2]) == 1 then
  return 2
end
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now_epoch_ms)
if redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[5]) then
  return -1
end
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PXAT', expires_epoch_ms) == false then
  return -3
end
redis.call('SET', KEYS[2], ARGV[2], 'PXAT', expires_epoch_ms)
redis.call('ZADD', KEYS[3], expires_epoch_ms, ARGV[3])
local last_member = redis.call('ZRANGE', KEYS[3], -1, -1, 'WITHSCORES')
if #last_member == 2 then
  redis.call('PEXPIREAT', KEYS[3], tonumber(last_member[2]))
end
return 1
"""

COMMIT_TURN_SCRIPT = """
-- assistant-commit-turn
if redis.call('EXISTS', KEYS[2]) == 1 then
  return 2
end
local current_json = redis.call('GET', KEYS[1])
if current_json == false then
  return -1
end
local ok, current = pcall(cjson.decode, current_json)
if not ok then
  return -5
end
if current['status'] ~= 'active' then
  return -3
end
if tonumber(current['revision']) ~= tonumber(ARGV[1]) then
  return -4
end
local redis_time = redis.call('TIME')
local now_epoch_ms = tonumber(redis_time[1]) * 1000 + math.floor(tonumber(redis_time[2]) / 1000)
local expires_epoch_ms = tonumber(current['expires_at_epoch_ms'])
if expires_epoch_ms == nil or expires_epoch_ms <= now_epoch_ms then
  redis.call('DEL', KEYS[1])
  return -1
end
if redis.call('SET', KEYS[1], ARGV[2], 'XX', 'KEEPTTL') == false then
  return -1
end
redis.call('SET', KEYS[2], ARGV[3], 'PXAT', expires_epoch_ms)
return 1
"""

FINALIZE_TOMBSTONE_SCRIPT = """
-- assistant-finalize-tombstone
if redis.call('EXISTS', KEYS[2]) == 1 then
  return 2
end
local current_json = redis.call('GET', KEYS[1])
if current_json == false then
  return -1
end
local ok, current = pcall(cjson.decode, current_json)
if not ok then
  return -5
end
if current['status'] ~= 'active' then
  return -3
end
if tonumber(current['revision']) ~= tonumber(ARGV[1]) then
  return -4
end
local redis_time = redis.call('TIME')
local now_epoch_ms = tonumber(redis_time[1]) * 1000 + math.floor(tonumber(redis_time[2]) / 1000)
local expires_epoch_ms = tonumber(current['expires_at_epoch_ms'])
if expires_epoch_ms == nil or expires_epoch_ms <= now_epoch_ms then
  redis.call('DEL', KEYS[1])
  redis.call('ZREM', KEYS[3], ARGV[4])
  return -1
end
if redis.call('SET', KEYS[1], ARGV[2], 'XX', 'KEEPTTL') == false then
  return -1
end
redis.call('SET', KEYS[2], ARGV[3], 'PXAT', expires_epoch_ms)
redis.call('ZREM', KEYS[3], ARGV[4])
return 1
"""


@dataclass(frozen=True, slots=True)
class CreateSessionStoreResult:
    created: bool
    replay: ProcessedAssistantRequest | None = None


class RedisAssistantSessionStore:
    def __init__(
        self,
        redis: Redis,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._redis = redis
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def load(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> AssistantSessionState | AssistantSessionTombstone | None:
        raw = await self._redis.get(self._session_key(user_id, session_id))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            model = (
                AssistantSessionTombstone
                if payload.get("status") == "finalized"
                else AssistantSessionState
            )
            state = model.model_validate(payload)
            if state.user_id != user_id or state.session_id != session_id:
                raise ValueError("assistant session identity mismatch")
            if state.expires_at <= self._now_provider():
                await self._redis.delete(self._session_key(user_id, session_id))
                return None
            return state
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc

    async def load_request(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
    ) -> ProcessedAssistantRequest | None:
        raw = await self._redis.get(self._request_key(user_id, request_id))
        if raw is None:
            return None
        try:
            request = ProcessedAssistantRequest.model_validate_json(raw)
            if request.request_id != request_id:
                raise ValueError("assistant request identity mismatch")
            if request.expires_at <= self._now_provider():
                await self._redis.delete(self._request_key(user_id, request_id))
                return None
            return request
        except (TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc

    async def create_session(
        self,
        *,
        state: AssistantSessionState,
        request: ProcessedAssistantRequest,
        max_active_sessions: int = MAX_ACTIVE_SESSIONS,
    ) -> CreateSessionStoreResult:
        if max_active_sessions != MAX_ACTIVE_SESSIONS:
            raise AssistantDataIntegrityError()
        state = self._validate_state(state)
        request = self._validate_request(request)
        if request.operation != "create" or state.revision != 0:
            raise AssistantDataIntegrityError()
        state_with_request = self._state_with_request(state, request)
        result = int(
            await self._redis.eval(
                CREATE_SESSION_SCRIPT,
                3,
                self._session_key(state.user_id, state.session_id),
                self._request_key(state.user_id, request.request_id),
                self._active_key(state.user_id),
                state_with_request.model_dump_json(),
                request.model_dump_json(),
                str(state.session_id),
                state.expires_at_epoch_ms,
                MAX_ACTIVE_SESSIONS,
            )
        )
        if result == 1:
            return CreateSessionStoreResult(created=True)
        if result == 2:
            replay = await self.load_request(user_id=state.user_id, request_id=request.request_id)
            if replay is None:
                raise AssistantDataIntegrityError()
            self._validate_replay(replay, request, require_session=False)
            return CreateSessionStoreResult(created=False, replay=replay)
        if result == -1:
            raise AssistantSessionLimitReachedError()
        if result == -2:
            raise AssistantSessionExpiredError()
        if result == -3:
            raise AssistantDataIntegrityError()
        raise AssistantDataIntegrityError()

    async def commit_turn(
        self,
        *,
        state: AssistantSessionState,
        expected_revision: int,
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest:
        state = self._validate_state(state)
        request = self._validate_request(request)
        if (
            request.operation != "message"
            or state.revision != expected_revision + 1
            or request.session_id != state.session_id
            or request.expires_at != state.expires_at
        ):
            raise AssistantDataIntegrityError()
        message_revision = request.response.get("revision")
        if message_revision != state.revision:
            raise AssistantDataIntegrityError()
        state_with_request = self._state_with_request(state, request)
        result = int(
            await self._redis.eval(
                COMMIT_TURN_SCRIPT,
                2,
                self._session_key(state.user_id, state.session_id),
                self._request_key(state.user_id, request.request_id),
                expected_revision,
                state_with_request.model_dump_json(),
                request.model_dump_json(),
            )
        )
        if result == 1:
            return request
        if result == 2:
            replay = await self.load_request(user_id=state.user_id, request_id=request.request_id)
            if replay is None:
                raise AssistantDataIntegrityError()
            self._validate_replay(replay, request, require_session=True)
            return replay
        if result == -1:
            raise AssistantSessionExpiredError()
        if result == -3:
            raise AssistantAlreadyFinalizedError()
        if result == -4:
            raise AssistantRevisionConflictError()
        raise AssistantDataIntegrityError()

    async def replace_with_tombstone(
        self,
        tombstone: AssistantSessionTombstone,
        *,
        expected_revision: int,
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest:
        tombstone = self._validate_tombstone(tombstone)
        request = self._validate_request(request)
        try:
            response = AssistantFinalizeResponse.model_validate(request.response)
        except ValidationError as exc:
            raise AssistantDataIntegrityError() from exc
        if (
            request.operation != "finalize"
            or tombstone.session_revision != expected_revision
            or request.session_id != tombstone.session_id
            or request.expires_at != tombstone.expires_at
            or response.session_id != tombstone.session_id
            or response.session_revision != tombstone.session_revision
            or response.ai_result_id != tombstone.report_id
        ):
            raise AssistantDataIntegrityError()
        result = int(
            await self._redis.eval(
                FINALIZE_TOMBSTONE_SCRIPT,
                3,
                self._session_key(tombstone.user_id, tombstone.session_id),
                self._request_key(tombstone.user_id, request.request_id),
                self._active_key(tombstone.user_id),
                expected_revision,
                tombstone.model_dump_json(),
                request.model_dump_json(),
                str(tombstone.session_id),
            )
        )
        if result == 1:
            return request
        if result == 2:
            replay = await self.load_request(
                user_id=tombstone.user_id,
                request_id=request.request_id,
            )
            if replay is None:
                raise AssistantDataIntegrityError()
            self._validate_replay(replay, request, require_session=True)
            return replay
        if result == -1:
            raise AssistantSessionExpiredError()
        if result == -3:
            raise AssistantAlreadyFinalizedError()
        if result == -4:
            raise AssistantRevisionConflictError()
        if result == -5:
            raise AssistantDataIntegrityError()
        raise AssistantDataIntegrityError()

    @staticmethod
    def _validate_state(state: AssistantSessionState) -> AssistantSessionState:
        try:
            return AssistantSessionState.model_validate(state.model_dump(mode="python"))
        except (TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc

    @staticmethod
    def _validate_tombstone(
        tombstone: AssistantSessionTombstone,
    ) -> AssistantSessionTombstone:
        try:
            return AssistantSessionTombstone.model_validate(tombstone.model_dump(mode="python"))
        except (TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc

    @staticmethod
    def _validate_request(
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest:
        try:
            return ProcessedAssistantRequest.model_validate(request.model_dump(mode="python"))
        except (TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc

    @classmethod
    def _state_with_request(
        cls,
        state: AssistantSessionState,
        request: ProcessedAssistantRequest,
    ) -> AssistantSessionState:
        try:
            return AssistantSessionState.model_validate(
                {
                    **state.model_dump(mode="python"),
                    "processed_requests": {
                        **state.processed_requests,
                        str(request.request_id): request,
                    },
                }
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc

    @staticmethod
    def _validate_replay(
        stored: ProcessedAssistantRequest,
        requested: ProcessedAssistantRequest,
        *,
        require_session: bool,
    ) -> None:
        same = (
            stored.fingerprint == requested.fingerprint and stored.operation == requested.operation
        )
        if require_session:
            same = same and stored.session_id == requested.session_id
        if not same:
            raise IdempotencyKeyReusedError()

    @staticmethod
    def _session_key(user_id: UUID, session_id: UUID) -> str:
        return f"assistant:v1:{user_id}:{session_id}"

    @staticmethod
    def _request_key(user_id: UUID, request_id: UUID) -> str:
        return f"assistant:v1:{user_id}:request:{request_id}"

    @staticmethod
    def _active_key(user_id: UUID) -> str:
        return f"assistant:v1:{user_id}:active"


class RedisAssistantSessionLocks:
    def __init__(self, redis: Redis, *, timeout_seconds: float = 90) -> None:
        self._redis = redis
        self._timeout_seconds = max(timeout_seconds, 1)

    @asynccontextmanager
    async def hold_tenant(self, *, user_id: UUID) -> AsyncIterator[None]:
        async with self._hold(f"assistant:v1:lock:{user_id}:tenant"):
            yield

    @asynccontextmanager
    async def hold_session(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> AsyncIterator[None]:
        async with self._hold(f"assistant:v1:lock:{user_id}:{session_id}"):
            yield

    @asynccontextmanager
    async def _hold(self, key: str) -> AsyncIterator[None]:
        lock = self._redis.lock(
            key,
            timeout=self._timeout_seconds,
            blocking_timeout=2,
            raise_on_release_error=False,
            thread_local=False,
        )
        renewal: asyncio.Task[None] | None = None
        try:
            async with lock:
                if callable(getattr(lock, "extend", None)):
                    renewal = asyncio.create_task(self._renew(lock))
                try:
                    yield
                finally:
                    if renewal is not None:
                        renewal.cancel()
                        with suppress(asyncio.CancelledError):
                            await renewal
        except LockError as exc:
            raise AssistantSessionBusyError() from exc

    async def _renew(self, lock: object) -> None:
        interval = max(0.25, min(self._timeout_seconds / 3, 30))
        while True:
            await asyncio.sleep(interval)
            try:
                await lock.extend(  # type: ignore[attr-defined]
                    self._timeout_seconds,
                    replace_ttl=True,
                )
            except Exception:  # noqa: BLE001 - Redis lock ownership boundary
                return
