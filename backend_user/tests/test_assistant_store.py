import json
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, time, timedelta
from types import TracebackType
from uuid import UUID

import pytest
from pydantic import ValidationError
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
    AssistantConversationTurn,
    AssistantMessageResponse,
    AssistantProfileSnapshot,
    AssistantSessionCreateResponse,
    AssistantSessionState,
    AssistantSessionTombstone,
    CareerCoachAssessmentSnapshot,
    CareerCoachReportEngine,
    CareerCoachReportV1,
    CoachingResult,
    ProcessedAssistantRequest,
)
from app.coach.stores import RedisAssistantSessionLocks, RedisAssistantSessionStore
from app.profiles.models import ProfileOnboardingData

USER_ID = UUID("00000000-0000-0000-0000-000000000201")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000202")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000203")
REPORT_ID = UUID("00000000-0000-0000-0000-000000000204")
TURN_REQUEST_ID = UUID(int=295)
FINALIZE_REQUEST_ID = UUID(int=291)
CREATED_AT = datetime(2026, 8, 11, 1, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(hours=24)


def profile_snapshot() -> AssistantProfileSnapshot:
    return AssistantProfileSnapshot(
        profile=ProfileOnboardingData(
            target_role="백엔드 개발자",
            skills=["Python", "FastAPI"],
            experience_summary="API 운영 경험",
            target_date=date(2026, 12, 31),
            target_company=None,
            preferred_environment="원격과 코드 리뷰",
            daily_notification_time=time(9),
            assistant_style="friendly",
        ),
        assessment_score=61,
        assessment_level="intermediate",
        assessment_summary={"reason": "기초는 있으나 실행 보강 필요"},
        assessment_version="v1",
        assessment_result_id=UUID(int=205),
        snapshot_hash="a" * 64,
    )


def create_response(
    session_id: UUID = SESSION_ID,
    *,
    expires_at: datetime = EXPIRES_AT,
) -> AssistantSessionCreateResponse:
    return AssistantSessionCreateResponse(
        session_id=session_id,
        revision=0,
        assistant_style="friendly",
        assistant_message="어떤 취업 고민부터 이야기해볼까요?",
        expires_at=expires_at,
    )


def request_record(
    *,
    request_id: UUID = REQUEST_ID,
    fingerprint: str = "b" * 64,
    operation: str = "create",
    session_id: UUID = SESSION_ID,
    response: dict[str, object] | None = None,
    expires_at: datetime = EXPIRES_AT,
) -> ProcessedAssistantRequest:
    return ProcessedAssistantRequest(
        request_id=request_id,
        fingerprint=fingerprint,
        operation=operation,  # type: ignore[arg-type]
        session_id=session_id,
        response=response or create_response(session_id).model_dump(mode="json"),
        expires_at=expires_at,
    )


def session_state(
    session_id: UUID = SESSION_ID,
    *,
    created_at: datetime = CREATED_AT,
    expires_at: datetime | None = None,
) -> AssistantSessionState:
    resolved_expires_at = expires_at or created_at + timedelta(hours=24)
    return AssistantSessionState(
        user_id=USER_ID,
        session_id=session_id,
        created_at=created_at,
        expires_at=resolved_expires_at,
        profile_snapshot=profile_snapshot(),
    )


def message_response(
    *,
    session_id: UUID = SESSION_ID,
    revision: int = 1,
    expires_at: datetime = EXPIRES_AT,
) -> AssistantMessageResponse:
    return AssistantMessageResponse(
        session_id=session_id,
        revision=revision,
        intent="general",
        assistant_message="경험을 성과 중심으로 정리해보세요.",
        tool_results=[],
        coaching=CoachingResult(
            style="friendly",
            message="작은 성과부터 수치로 바꿔보면 좋아요.",
            source="llm",
        ),
        expires_at=expires_at,
    )


def conversation_turn(
    *,
    request_id: UUID = TURN_REQUEST_ID,
    assistant_message: str = "경험을 성과 중심으로 정리해보세요.",
) -> AssistantConversationTurn:
    return AssistantConversationTurn(
        turn_id=UUID(int=294),
        request_id=request_id,
        user_text="경험을 어떻게 쓰죠?",
        assistant_message=assistant_message,
        intent="general",
        tool_results=[],
        coaching=CoachingResult(
            style="friendly",
            message="작은 성과부터 수치로 바꿔보면 좋아요.",
            source="llm",
        ),
        created_at=CREATED_AT + timedelta(minutes=1),
    )


def report() -> CareerCoachReportV1:
    return CareerCoachReportV1(
        session_id=SESSION_ID,
        session_revision=1,
        started_at_kst=datetime.fromisoformat("2026-08-11T10:00:00+09:00"),
        finalized_at_kst=datetime.fromisoformat("2026-08-11T10:05:00+09:00"),
        user_turn_count=1,
        profile_snapshot=profile_snapshot().profile,
        assessment_snapshot=CareerCoachAssessmentSnapshot(
            score=61,
            level="intermediate",
            summary={"reason": "기초는 있으나 실행 보강 필요"},
            version="v1",
        ),
        profile_hash="a" * 64,
        assessment_result_id=UUID(int=205),
        assistant_style="friendly",
        summary="사용자는 백엔드 취업 준비의 실행 우선순위를 점검했습니다.",
        strengths=["Python API 경험"],
        improvements=["성과 수치화"],
        priority_actions=["오늘 이력서 성과 한 줄을 수치로 수정합니다."],
        evidence=[],
        tool_snapshots=[],
        excluded_tool_call_count=0,
        engine=CareerCoachReportEngine(),
        source_session_hash="b" * 64,
        report_hash="c" * 64,
    )


def finalize_response() -> dict[str, object]:
    return {
        "ai_result_id": str(REPORT_ID),
        "session_id": str(SESSION_ID),
        "session_revision": 1,
        "report": report().model_dump(mode="json"),
        "created_at": (CREATED_AT + timedelta(minutes=5)).isoformat(),
    }


def finalize_request(
    *,
    request_id: UUID = FINALIZE_REQUEST_ID,
    fingerprint: str = "f" * 64,
) -> ProcessedAssistantRequest:
    return request_record(
        request_id=request_id,
        fingerprint=fingerprint,
        operation="finalize",
        response=finalize_response(),
    )


def test_session_state_requires_exact_24_hour_lifetime_and_exact_transcript_size() -> None:
    with pytest.raises(ValidationError):
        session_state(expires_at=CREATED_AT + timedelta(hours=23, minutes=59))

    turn = conversation_turn()
    with pytest.raises(ValidationError):
        AssistantSessionState(
            user_id=USER_ID,
            session_id=SESSION_ID,
            created_at=CREATED_AT,
            expires_at=EXPIRES_AT,
            profile_snapshot=profile_snapshot(),
            revision=1,
            turns=[turn],
            transcript_chars=29,
        )

    other_session_id = UUID(int=999)
    other_request = request_record(
        session_id=other_session_id,
        response=create_response(other_session_id).model_dump(mode="json"),
    )
    with pytest.raises(ValidationError):
        AssistantSessionState(
            user_id=USER_ID,
            session_id=SESSION_ID,
            created_at=CREATED_AT,
            expires_at=EXPIRES_AT,
            profile_snapshot=profile_snapshot(),
            processed_requests={str(REQUEST_ID): other_request},
        )


def test_processed_request_validates_operation_response_session_and_expiry() -> None:
    with pytest.raises(ValidationError):
        request_record(
            operation="message",
            response=create_response().model_dump(mode="json"),
        )

    with pytest.raises(ValidationError):
        request_record(
            operation="message",
            session_id=UUID(int=999),
            response=message_response().model_dump(mode="json"),
        )

    with pytest.raises(ValidationError):
        request_record(
            operation="message",
            response=message_response().model_dump(mode="json"),
            expires_at=EXPIRES_AT + timedelta(seconds=1),
        )

    with pytest.raises(ValidationError):
        request_record(operation="finalize", response={"report_id": str(REPORT_ID)})


class FakeLock(AbstractAsyncContextManager[None]):
    def __init__(self, *, busy: bool) -> None:
        self.busy = busy

    async def __aenter__(self) -> None:
        if self.busy:
            raise LockError("busy")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expire_at: dict[str, int] = {}
        self.active: dict[str, dict[str, int]] = {}
        self.active_expire_at: dict[str, int] = {}
        self.lock_calls: list[tuple[str, dict[str, object]]] = []
        self.busy = False
        self.now = CREATED_AT

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.expire_at.pop(key, None)
        return int(existed)

    async def zrem(self, key: str, member: str) -> int:
        active = self.active.setdefault(key, {})
        existed = member in active
        active.pop(member, None)
        return int(existed)

    async def eval(self, script: str, key_count: int, *values: object) -> object:
        keys = [str(value) for value in values[:key_count]]
        args = [str(value) for value in values[key_count:]]
        if "assistant-load-session" in script:
            session_key, active_key = keys
            (session_id,) = args
            raw = self.values.get(session_key)
            if raw is None:
                return None
            current = json.loads(raw)
            if current.get("status") == "active":
                now_epoch_ms = int(self.now.timestamp() * 1000)
                expires_epoch_ms = current.get("expires_at_epoch_ms")
                idle_expires_epoch_ms = self.active.setdefault(active_key, {}).get(session_id)
                if (
                    not isinstance(expires_epoch_ms, int)
                    or expires_epoch_ms <= now_epoch_ms
                    or idle_expires_epoch_ms is None
                    or idle_expires_epoch_ms <= now_epoch_ms
                ):
                    await self.delete(session_key)
                    self.active[active_key].pop(session_id, None)
                    return None
            return raw
        if "assistant-create-session" in script:
            session_key, request_key, active_key = keys
            (
                state_json,
                request_json,
                session_id,
                expires_epoch_ms,
                idle_timeout_ms,
                limit,
            ) = args
            now_epoch_ms = int(self.now.timestamp() * 1000)
            if int(expires_epoch_ms) <= now_epoch_ms:
                return -2
            idle_expires_epoch_ms = min(
                int(expires_epoch_ms),
                now_epoch_ms + int(idle_timeout_ms),
            )
            if request_key in self.values:
                return 2
            active = self.active.setdefault(active_key, {})
            for member, expiry in list(active.items()):
                if expiry <= now_epoch_ms:
                    del active[member]
            if len(active) >= int(limit):
                return -1
            if session_key in self.values:
                return -3
            self.values[session_key] = state_json
            self.values[request_key] = request_json
            self.expire_at[session_key] = int(expires_epoch_ms)
            self.expire_at[request_key] = int(expires_epoch_ms)
            active[session_id] = int(idle_expires_epoch_ms)
            self.active_expire_at[active_key] = max(active.values())
            return 1
        if "assistant-admit-turn" in script:
            session_key, active_key = keys
            session_id, expected_revision, idle_timeout_ms = args
            raw = self.values.get(session_key)
            if raw is None:
                return -1
            current = json.loads(raw)
            if current.get("status") != "active":
                return -3
            if current.get("revision") != int(expected_revision):
                return -4
            now_epoch_ms = int(self.now.timestamp() * 1000)
            expires_epoch_ms = current.get("expires_at_epoch_ms")
            active = self.active.setdefault(active_key, {})
            idle_expires_epoch_ms = active.get(session_id)
            if (
                not isinstance(expires_epoch_ms, int)
                or expires_epoch_ms <= now_epoch_ms
                or idle_expires_epoch_ms is None
                or idle_expires_epoch_ms <= now_epoch_ms
            ):
                await self.delete(session_key)
                active.pop(session_id, None)
                return -1
            next_idle_expires_epoch_ms = min(
                expires_epoch_ms,
                now_epoch_ms + int(idle_timeout_ms),
            )
            active[session_id] = next_idle_expires_epoch_ms
            self.active_expire_at[active_key] = max(active.values())
            return raw
        if "assistant-commit-turn" in script:
            session_key, request_key = keys
            expected_revision, state_json, request_json = args[:3]
            if request_key in self.values:
                return 2
            raw = self.values.get(session_key)
            if raw is None:
                return -1
            current = json.loads(raw)
            if current.get("status") != "active":
                return -3
            if current.get("revision") != int(expected_revision):
                return -4
            expires_epoch_ms = current.get("expires_at_epoch_ms")
            if not isinstance(expires_epoch_ms, int) or expires_epoch_ms <= int(
                self.now.timestamp() * 1000
            ):
                await self.delete(session_key)
                return -1
            self.values[session_key] = state_json
            self.values[request_key] = request_json
            self.expire_at[request_key] = self.expire_at[session_key]
            return 1
        if "assistant-finalize-tombstone" in script:
            session_key, request_key, active_key = keys
            expected_revision, tombstone_json, request_json, session_id = args
            if request_key in self.values:
                return 2
            raw = self.values.get(session_key)
            if raw is None:
                return -1
            current = json.loads(raw)
            if current.get("status") != "active":
                return -3
            if current.get("revision") != int(expected_revision):
                return -4
            expires_epoch_ms = current.get("expires_at_epoch_ms")
            now_epoch_ms = int(self.now.timestamp() * 1000)
            idle_expires_epoch_ms = self.active.setdefault(active_key, {}).get(session_id)
            if (
                not isinstance(expires_epoch_ms, int)
                or expires_epoch_ms <= now_epoch_ms
                or idle_expires_epoch_ms is None
                or idle_expires_epoch_ms <= now_epoch_ms
            ):
                await self.delete(session_key)
                self.active.setdefault(active_key, {}).pop(session_id, None)
                return -1
            self.values[session_key] = tombstone_json
            self.values[request_key] = request_json
            self.expire_at[request_key] = self.expire_at[session_key]
            self.active.setdefault(active_key, {}).pop(session_id, None)
            return 1
        raise AssertionError("unknown script")

    def lock(self, key: str, **kwargs: object) -> FakeLock:
        self.lock_calls.append((key, kwargs))
        return FakeLock(busy=self.busy)


@pytest.mark.asyncio
async def test_create_allows_six_active_sessions_and_replays_at_limit() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    state = session_state()
    request = request_record()

    created = await store.create_session(state=state, request=request, max_active_sessions=6)

    session_key = f"assistant:v1:{USER_ID}:{SESSION_ID}"
    assert created.created is True
    assert created.replay is None
    assert redis.expire_at[session_key] == int(EXPIRES_AT.timestamp() * 1000)
    loaded = await store.load(user_id=USER_ID, session_id=SESSION_ID)
    assert isinstance(loaded, AssistantSessionState)
    assert loaded.user_id == state.user_id
    assert loaded.session_id == state.session_id
    assert loaded.expires_at == state.expires_at
    assert loaded.processed_requests == {str(REQUEST_ID): request}

    for suffix in (298, 297, 296, 295, 294):
        await store.create_session(
            state=session_state(UUID(int=suffix)),
            request=request_record(
                request_id=UUID(int=suffix - 10),
                session_id=UUID(int=suffix),
                response=create_response(UUID(int=suffix)).model_dump(mode="json"),
            ),
            max_active_sessions=6,
        )

    replayed = await store.create_session(
        state=session_state(),
        request=request,
        max_active_sessions=6,
    )
    assert replayed.created is False
    assert replayed.replay == request

    with pytest.raises(AssistantSessionLimitReachedError):
        await store.create_session(
            state=session_state(UUID(int=293)),
            request=request_record(
                request_id=UUID(int=283),
                session_id=UUID(int=293),
                response=create_response(UUID(int=293)).model_dump(mode="json"),
            ),
            max_active_sessions=6,
        )


@pytest.mark.asyncio
async def test_create_rejects_non_product_session_limit_override() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]

    with pytest.raises(AssistantDataIntegrityError):
        await store.create_session(
            state=session_state(),
            request=request_record(),
            max_active_sessions=1,
        )


@pytest.mark.asyncio
async def test_create_releases_idle_slots_at_120_second_boundary() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]

    for value in range(310, 316):
        session_id = UUID(int=value)
        await store.create_session(
            state=session_state(session_id),
            request=request_record(
                request_id=UUID(int=value + 100),
                session_id=session_id,
                response=create_response(session_id).model_dump(mode="json"),
            ),
            max_active_sessions=6,
        )

    redis.now = CREATED_AT + timedelta(seconds=120)
    replacement_session_id = UUID(int=316)
    replacement_expires_at = redis.now + timedelta(hours=24)
    result = await store.create_session(
        state=session_state(replacement_session_id, created_at=redis.now),
        request=request_record(
            request_id=UUID(int=416),
            session_id=replacement_session_id,
            expires_at=replacement_expires_at,
            response=create_response(
                replacement_session_id,
                expires_at=replacement_expires_at,
            ).model_dump(mode="json"),
        ),
        max_active_sessions=6,
    )

    assert result.created is True
    active = redis.active[f"assistant:v2:{USER_ID}:active"]
    assert active == {str(replacement_session_id): 1_786_410_240_000}


@pytest.mark.asyncio
async def test_create_uses_versioned_idle_index_and_ignores_legacy_absolute_scores() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    legacy_active_key = f"assistant:v1:{USER_ID}:active"
    redis.active[legacy_active_key] = {
        str(SESSION_ID): int(EXPIRES_AT.timestamp() * 1000),
    }

    replacement_session_id = UUID(int=317)
    await store.create_session(
        state=session_state(replacement_session_id),
        request=request_record(
            request_id=UUID(int=417),
            session_id=replacement_session_id,
            response=create_response(replacement_session_id).model_dump(mode="json"),
        ),
        max_active_sessions=6,
    )

    active_key = f"assistant:v2:{USER_ID}:active"
    assert redis.active[active_key] == {
        str(replacement_session_id): 1_786_410_120_000,
    }
    assert redis.active[legacy_active_key] == {
        str(SESSION_ID): int(EXPIRES_AT.timestamp() * 1000),
    }


@pytest.mark.asyncio
async def test_create_keeps_absolute_data_expiry_and_uses_idle_index_ttl() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    later_created_at = CREATED_AT + timedelta(hours=2, microseconds=123_000)
    later_expires_at = later_created_at + timedelta(hours=24)
    later_session_id = UUID(int=283)
    redis.now = later_created_at
    await store.create_session(
        state=session_state(later_session_id, created_at=later_created_at),
        request=request_record(
            request_id=UUID(int=282),
            session_id=later_session_id,
            expires_at=later_expires_at,
            response=create_response(
                later_session_id,
                expires_at=later_expires_at,
            ).model_dump(mode="json"),
        ),
        max_active_sessions=6,
    )

    active_key = f"assistant:v2:{USER_ID}:active"
    later_session_key = f"assistant:v1:{USER_ID}:{later_session_id}"
    assert redis.expire_at[later_session_key] == int(later_expires_at.timestamp() * 1000)
    assert redis.active_expire_at[active_key] == 1_786_417_320_123


@pytest.mark.asyncio
async def test_load_enforces_logical_expiry_for_state_and_global_request() -> None:
    redis = FakeRedis()
    writer = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    await writer.create_session(
        state=session_state(),
        request=request_record(),
        max_active_sessions=6,
    )
    expired_reader = RedisAssistantSessionStore(
        redis,  # type: ignore[arg-type]
        now_provider=lambda: EXPIRES_AT + timedelta(microseconds=1),
    )

    assert (
        await expired_reader.load_request(
            user_id=USER_ID,
            request_id=REQUEST_ID,
        )
        is None
    )
    redis.now = EXPIRES_AT + timedelta(microseconds=1)
    assert await expired_reader.load(user_id=USER_ID, session_id=SESSION_ID) is None
    assert f"assistant:v1:{USER_ID}:request:{REQUEST_ID}" not in redis.values
    assert f"assistant:v1:{USER_ID}:{SESSION_ID}" not in redis.values


@pytest.mark.asyncio
async def test_load_expires_active_session_at_exact_idle_deadline() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(
        redis,  # type: ignore[arg-type]
        now_provider=lambda: redis.now,
    )
    await store.create_session(
        state=session_state(),
        request=request_record(),
        max_active_sessions=6,
    )

    redis.now = CREATED_AT + timedelta(seconds=119, milliseconds=999)
    assert isinstance(
        await store.load(user_id=USER_ID, session_id=SESSION_ID),
        AssistantSessionState,
    )

    redis.now = CREATED_AT + timedelta(seconds=120)
    assert await store.load(user_id=USER_ID, session_id=SESSION_ID) is None
    assert f"assistant:v1:{USER_ID}:{SESSION_ID}" not in redis.values
    assert str(SESSION_ID) not in redis.active[f"assistant:v2:{USER_ID}:active"]


@pytest.mark.asyncio
async def test_load_expires_state_indexed_only_by_legacy_active_key() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    await store.create_session(
        state=session_state(),
        request=request_record(),
        max_active_sessions=6,
    )
    active_key = f"assistant:v2:{USER_ID}:active"
    legacy_active_key = f"assistant:v1:{USER_ID}:active"
    redis.active[active_key].pop(str(SESSION_ID))
    redis.active[legacy_active_key] = {
        str(SESSION_ID): int(EXPIRES_AT.timestamp() * 1000),
    }

    assert await store.load(user_id=USER_ID, session_id=SESSION_ID) is None
    assert f"assistant:v1:{USER_ID}:{SESSION_ID}" not in redis.values
    assert str(SESSION_ID) not in redis.active[active_key]
    assert str(SESSION_ID) in redis.active[legacy_active_key]


@pytest.mark.asyncio
async def test_create_rejects_same_request_id_with_different_fingerprint() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    await store.create_session(
        state=session_state(),
        request=request_record(),
        max_active_sessions=6,
    )

    with pytest.raises(IdempotencyKeyReusedError):
        await store.create_session(
            state=session_state(UUID(int=296)),
            request=request_record(fingerprint="c" * 64, session_id=UUID(int=296)),
            max_active_sessions=6,
        )


@pytest.mark.asyncio
async def test_turn_admission_refreshes_idle_deadline_before_processing() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    await store.create_session(
        state=session_state(),
        request=request_record(),
        max_active_sessions=6,
    )

    redis.now = CREATED_AT + timedelta(seconds=30)
    admitted = await store.admit_turn(
        user_id=USER_ID,
        session_id=SESSION_ID,
        expected_revision=0,
    )

    active_key = f"assistant:v2:{USER_ID}:active"
    session_key = f"assistant:v1:{USER_ID}:{SESSION_ID}"
    assert admitted.session_id == SESSION_ID
    assert redis.active[active_key][str(SESSION_ID)] == 1_786_410_150_000
    assert redis.active_expire_at[active_key] == 1_786_410_150_000
    assert redis.expire_at[session_key] == int(EXPIRES_AT.timestamp() * 1000)

    redis.now = CREATED_AT + timedelta(seconds=150)
    with pytest.raises(AssistantSessionExpiredError):
        await store.admit_turn(
            user_id=USER_ID,
            session_id=SESSION_ID,
            expected_revision=0,
        )

    assert session_key not in redis.values
    assert str(SESSION_ID) not in redis.active[active_key]


@pytest.mark.asyncio
async def test_turn_cas_preserves_absolute_expiry_and_replays_identical_request() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    response = message_response()
    message_request = request_record(
        request_id=UUID(int=295),
        operation="message",
        response=response.model_dump(mode="json"),
    )
    turn = conversation_turn()
    next_state = initial.model_copy(update={"revision": 1, "turns": [turn], "transcript_chars": 30})

    committed = await store.commit_turn(
        state=next_state,
        expected_revision=0,
        request=message_request,
    )
    replayed = await store.commit_turn(
        state=next_state,
        expected_revision=0,
        request=message_request,
    )

    session_key = f"assistant:v1:{USER_ID}:{SESSION_ID}"
    assert committed == message_request
    assert replayed == message_request
    assert redis.expire_at[session_key] == int(EXPIRES_AT.timestamp() * 1000)
    assert (await store.load(user_id=USER_ID, session_id=SESSION_ID)).revision == 1  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_admitted_turn_can_commit_after_idle_deadline_without_reviving_session() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    redis.now = CREATED_AT + timedelta(seconds=30)
    await store.admit_turn(
        user_id=USER_ID,
        session_id=SESSION_ID,
        expected_revision=0,
    )
    turn = conversation_turn()
    next_state = initial.model_copy(update={"revision": 1, "turns": [turn], "transcript_chars": 30})
    message_request = request_record(
        request_id=UUID(int=295),
        operation="message",
        response=message_response().model_dump(mode="json"),
    )

    redis.now = CREATED_AT + timedelta(seconds=150)
    committed = await store.commit_turn(
        state=next_state,
        expected_revision=0,
        request=message_request,
    )

    active_key = f"assistant:v2:{USER_ID}:active"
    assert committed == message_request
    assert redis.active[active_key][str(SESSION_ID)] == 1_786_410_150_000
    assert await store.load(user_id=USER_ID, session_id=SESSION_ID) is None
    assert str(SESSION_ID) not in redis.active[active_key]


@pytest.mark.asyncio
async def test_turn_revalidates_model_copy_and_rejects_inexact_transcript() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    invalid_copy = initial.model_copy(
        update={
            "revision": 1,
            "turns": [conversation_turn()],
            "transcript_chars": 29,
        }
    )
    message_request = request_record(
        request_id=UUID(int=295),
        operation="message",
        response=message_response().model_dump(mode="json"),
    )

    with pytest.raises(AssistantDataIntegrityError):
        await store.commit_turn(
            state=invalid_copy,
            expected_revision=0,
            request=message_request,
        )

    loaded = await store.load(user_id=USER_ID, session_id=SESSION_ID)
    assert isinstance(loaded, AssistantSessionState)
    assert loaded.revision == 0


@pytest.mark.asyncio
async def test_turn_cas_rejects_stale_revision_and_never_resurrects_missing_session() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    first_turn = conversation_turn(request_id=UUID(int=293))
    second_turn = conversation_turn(request_id=UUID(int=292)).model_copy(
        update={
            "turn_id": UUID(int=290),
            "user_text": "두 번째 질문",
            "assistant_message": "두 번째 답변",
        }
    )
    stale_state = initial.model_copy(
        update={
            "revision": 2,
            "turns": [first_turn, second_turn],
            "transcript_chars": 44,
        }
    )

    with pytest.raises(AssistantRevisionConflictError):
        await store.commit_turn(
            state=stale_state,
            expected_revision=1,
            request=request_record(
                request_id=UUID(int=292),
                fingerprint="d" * 64,
                operation="message",
                response=message_response(revision=2).model_dump(mode="json"),
            ),
        )

    redis.values.pop(f"assistant:v1:{USER_ID}:{SESSION_ID}")
    with pytest.raises(AssistantSessionExpiredError):
        await store.commit_turn(
            state=initial.model_copy(
                update={
                    "revision": 1,
                    "turns": [conversation_turn(request_id=UUID(int=289))],
                    "transcript_chars": 30,
                }
            ),
            expected_revision=0,
            request=request_record(
                request_id=UUID(int=289),
                fingerprint="e" * 64,
                operation="message",
                response=message_response().model_dump(mode="json"),
            ),
        )
    assert f"assistant:v1:{USER_ID}:{SESSION_ID}" not in redis.values


@pytest.mark.asyncio
async def test_finalize_replaces_transcript_with_small_tombstone_and_removes_active_member() -> (
    None
):
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    turn = conversation_turn()
    active = initial.model_copy(update={"revision": 1, "turns": [turn], "transcript_chars": 30})
    await store.commit_turn(
        state=active,
        expected_revision=0,
        request=request_record(
            request_id=turn.request_id,
            operation="message",
            response=message_response().model_dump(mode="json"),
        ),
    )
    tombstone = AssistantSessionTombstone(
        user_id=USER_ID,
        session_id=SESSION_ID,
        session_revision=1,
        report_id=REPORT_ID,
        created_at=CREATED_AT,
        finalized_at=CREATED_AT + timedelta(minutes=5),
        expires_at=EXPIRES_AT,
    )

    request = finalize_request()
    replaced = await store.replace_with_tombstone(
        tombstone,
        expected_revision=1,
        request=request,
    )

    assert replaced == request
    raw = redis.values[f"assistant:v1:{USER_ID}:{SESSION_ID}"]
    assert "profile_snapshot" not in raw
    assert "turns" not in raw
    assert await store.load(user_id=USER_ID, session_id=SESSION_ID) == tombstone
    active_key = f"assistant:v2:{USER_ID}:active"
    assert str(SESSION_ID) not in redis.active[active_key]
    assert redis.expire_at[f"assistant:v1:{USER_ID}:{SESSION_ID}"] == int(
        EXPIRES_AT.timestamp() * 1000
    )


@pytest.mark.asyncio
async def test_finalize_replays_globally_and_rejects_request_id_reuse() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    turn = conversation_turn()
    active = initial.model_copy(update={"revision": 1, "turns": [turn], "transcript_chars": 30})
    await store.commit_turn(
        state=active,
        expected_revision=0,
        request=request_record(
            request_id=turn.request_id,
            operation="message",
            response=message_response().model_dump(mode="json"),
        ),
    )
    tombstone = AssistantSessionTombstone(
        user_id=USER_ID,
        session_id=SESSION_ID,
        session_revision=1,
        report_id=REPORT_ID,
        created_at=CREATED_AT,
        finalized_at=CREATED_AT + timedelta(minutes=5),
        expires_at=EXPIRES_AT,
    )
    request = finalize_request()

    assert (
        await store.replace_with_tombstone(
            tombstone,
            expected_revision=1,
            request=request,
        )
        == request
    )
    assert (
        await store.replace_with_tombstone(
            tombstone,
            expected_revision=1,
            request=request,
        )
        == request
    )

    with pytest.raises(IdempotencyKeyReusedError):
        await store.replace_with_tombstone(
            tombstone,
            expected_revision=1,
            request=finalize_request(fingerprint="0" * 64),
        )


@pytest.mark.asyncio
async def test_expired_finalize_writes_neither_tombstone_nor_request_record() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    turn = conversation_turn()
    active = initial.model_copy(update={"revision": 1, "turns": [turn], "transcript_chars": 30})
    await store.commit_turn(
        state=active,
        expected_revision=0,
        request=request_record(
            request_id=turn.request_id,
            operation="message",
            response=message_response().model_dump(mode="json"),
        ),
    )
    tombstone = AssistantSessionTombstone(
        user_id=USER_ID,
        session_id=SESSION_ID,
        session_revision=1,
        report_id=REPORT_ID,
        created_at=CREATED_AT,
        finalized_at=CREATED_AT + timedelta(minutes=5),
        expires_at=EXPIRES_AT,
    )
    request = finalize_request()
    redis.now = EXPIRES_AT + timedelta(microseconds=1)

    with pytest.raises(AssistantSessionExpiredError):
        await store.replace_with_tombstone(
            tombstone,
            expected_revision=1,
            request=request,
        )

    session_key = f"assistant:v1:{USER_ID}:{SESSION_ID}"
    request_key = f"assistant:v1:{USER_ID}:request:{request.request_id}"
    assert session_key not in redis.values
    assert request_key not in redis.values
    assert str(SESSION_ID) not in redis.active[f"assistant:v2:{USER_ID}:active"]


@pytest.mark.asyncio
async def test_idle_finalize_writes_neither_tombstone_nor_request_record() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    turn = conversation_turn()
    active = initial.model_copy(update={"revision": 1, "turns": [turn], "transcript_chars": 30})
    await store.commit_turn(
        state=active,
        expected_revision=0,
        request=request_record(
            request_id=turn.request_id,
            operation="message",
            response=message_response().model_dump(mode="json"),
        ),
    )
    tombstone = AssistantSessionTombstone(
        user_id=USER_ID,
        session_id=SESSION_ID,
        session_revision=1,
        report_id=REPORT_ID,
        created_at=CREATED_AT,
        finalized_at=CREATED_AT + timedelta(seconds=119),
        expires_at=EXPIRES_AT,
    )
    request = finalize_request()
    redis.now = CREATED_AT + timedelta(seconds=120)

    with pytest.raises(AssistantSessionExpiredError):
        await store.replace_with_tombstone(
            tombstone,
            expected_revision=1,
            request=request,
        )

    session_key = f"assistant:v1:{USER_ID}:{SESSION_ID}"
    request_key = f"assistant:v1:{USER_ID}:request:{request.request_id}"
    assert session_key not in redis.values
    assert request_key not in redis.values
    assert str(SESSION_ID) not in redis.active[f"assistant:v2:{USER_ID}:active"]


@pytest.mark.asyncio
async def test_stale_finalize_cannot_overwrite_newer_turn_or_tombstone() -> None:
    redis = FakeRedis()
    store = RedisAssistantSessionStore(redis)  # type: ignore[arg-type]
    initial = session_state()
    await store.create_session(
        state=initial,
        request=request_record(),
        max_active_sessions=6,
    )
    first_turn = conversation_turn()
    revision_one = initial.model_copy(
        update={"revision": 1, "turns": [first_turn], "transcript_chars": 30}
    )
    await store.commit_turn(
        state=revision_one,
        expected_revision=0,
        request=request_record(
            request_id=first_turn.request_id,
            operation="message",
            response=message_response().model_dump(mode="json"),
        ),
    )
    second_turn = conversation_turn(request_id=UUID(int=288)).model_copy(
        update={
            "turn_id": UUID(int=287),
            "user_text": "두 번째 질문",
            "assistant_message": "두 번째 답변",
        }
    )
    revision_two = revision_one.model_copy(
        update={
            "revision": 2,
            "turns": [first_turn, second_turn],
            "transcript_chars": 44,
        }
    )
    await store.commit_turn(
        state=revision_two,
        expected_revision=1,
        request=request_record(
            request_id=second_turn.request_id,
            fingerprint="1" * 64,
            operation="message",
            response=message_response(revision=2).model_dump(mode="json"),
        ),
    )
    stale_tombstone = AssistantSessionTombstone(
        user_id=USER_ID,
        session_id=SESSION_ID,
        session_revision=1,
        report_id=REPORT_ID,
        created_at=CREATED_AT,
        finalized_at=CREATED_AT + timedelta(minutes=5),
        expires_at=EXPIRES_AT,
    )

    with pytest.raises(AssistantRevisionConflictError):
        await store.replace_with_tombstone(
            stale_tombstone,
            expected_revision=1,
            request=finalize_request(),
        )
    loaded = await store.load(user_id=USER_ID, session_id=SESSION_ID)
    assert isinstance(loaded, AssistantSessionState)
    assert loaded.revision == 2

    winning_tombstone = stale_tombstone.model_copy(
        update={"session_revision": 2, "report_id": UUID(int=286)}
    )
    winning_request = finalize_request(
        request_id=UUID(int=285),
        fingerprint="2" * 64,
    ).model_copy(
        update={
            "response": {
                **finalize_response(),
                "ai_result_id": str(UUID(int=286)),
                "session_revision": 2,
                "report": report()
                .model_copy(update={"session_revision": 2, "user_turn_count": 2})
                .model_dump(mode="json"),
            }
        }
    )
    await store.replace_with_tombstone(
        winning_tombstone,
        expected_revision=2,
        request=winning_request,
    )

    with pytest.raises(AssistantAlreadyFinalizedError):
        await store.replace_with_tombstone(
            stale_tombstone,
            expected_revision=1,
            request=finalize_request(request_id=UUID(int=284)),
        )
    assert await store.load(user_id=USER_ID, session_id=SESSION_ID) == winning_tombstone


@pytest.mark.asyncio
async def test_tenant_and_session_locks_map_busy_without_exposing_redis_error() -> None:
    redis = FakeRedis()
    locks = RedisAssistantSessionLocks(redis, timeout_seconds=90)  # type: ignore[arg-type]

    async with locks.hold_tenant(user_id=USER_ID):
        pass
    async with locks.hold_session(user_id=USER_ID, session_id=SESSION_ID):
        pass

    assert redis.lock_calls == [
        (
            f"assistant:v1:lock:{USER_ID}:tenant",
            {
                "timeout": 90,
                "blocking_timeout": 2,
                "raise_on_release_error": False,
                "thread_local": False,
            },
        ),
        (
            f"assistant:v1:lock:{USER_ID}:{SESSION_ID}",
            {
                "timeout": 90,
                "blocking_timeout": 2,
                "raise_on_release_error": False,
                "thread_local": False,
            },
        ),
    ]

    redis.busy = True
    with pytest.raises(AssistantSessionBusyError):
        async with locks.hold_session(user_id=USER_ID, session_id=SESSION_ID):
            pass
