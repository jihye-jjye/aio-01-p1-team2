import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from app.coach.errors import (
    AssistantAlreadyFinalizedError,
    AssistantReportEmptyError,
    AssistantRevisionConflictError,
    AssistantSessionExpiredError,
    AssistantTranscriptLimitReachedError,
    AssistantTurnLimitReachedError,
    IdempotencyKeyReusedError,
)
from app.coach.models import (
    AssistantFinalizeResponse,
    AssistantSessionState,
    CareerCoachEvidenceReference,
    CareerCoachReportDraft,
    CareerCoachReportPersistenceResult,
    CoachNarrativeDecision,
    CoachRouteDecision,
    ProcessedAssistantRequest,
    ScheduleLookupArguments,
    StoredCareerCoachReport,
)
from app.coach.service import CareerCoachService, _redact
from app.gemini.errors import GeminiInvalidResponseError, GeminiUnavailableError
from app.profiles.models import ProfileRecord
from app.saved_jobs.models import SavedJobRecommendationView, SavedJobView

USER_ID = UUID("00000000-0000-0000-0000-000000000501")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000502")
TURN_ID = UUID("00000000-0000-0000-0000-000000000503")
TOOL_ID = UUID("00000000-0000-0000-0000-000000000504")
CREATE_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000505")
MESSAGE_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000506")
FINALIZE_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000507")
REPORT_ID = UUID("00000000-0000-0000-0000-000000000508")
JOB_ID = UUID("00000000-0000-0000-0000-000000000509")
NOW = datetime(2026, 8, 11, 1, tzinfo=UTC)


def profile(*, style: str = "friendly") -> ProfileRecord:
    return ProfileRecord(
        user_id=USER_ID,
        target_role="백엔드 개발자",
        skills=["Python", "FastAPI"],
        experience_summary="API 운영 경험",
        target_date=date(2026, 12, 31),
        target_company=None,
        preferred_environment="원격과 코드 리뷰",
        daily_notification_time=time(9),
        assistant_style=style,  # type: ignore[arg-type]
        assessment_score=61,
        assessment_level="intermediate",
        assessment_summary={"reason": "실행 보강 필요"},
        assessment_version="v1",
        assessed_at=NOW,
        onboarding_completed_at=NOW,
        assessment_result_id=UUID(int=510),
        draft_revision=3,
        snapshot_hash="a" * 64,
    )


class ProfileReader:
    def __init__(self, value: ProfileRecord) -> None:
        self.value = value
        self.calls: list[UUID] = []

    async def get_by_user_id(self, user_id: UUID) -> ProfileRecord | None:
        self.calls.append(user_id)
        return self.value


class MemoryStore:
    def __init__(self) -> None:
        self.sessions: dict[tuple[UUID, UUID], object] = {}
        self.requests: dict[tuple[UUID, UUID], ProcessedAssistantRequest] = {}
        self.tombstones: list[object] = []
        self.admissions: list[tuple[UUID, UUID, int]] = []
        self.admission_error: Exception | None = None
        self.create_limits: list[int] = []

    async def load_request(
        self, *, user_id: UUID, request_id: UUID
    ) -> ProcessedAssistantRequest | None:
        return self.requests.get((user_id, request_id))

    async def create_session(
        self,
        *,
        state: AssistantSessionState,
        request: ProcessedAssistantRequest,
        max_active_sessions: int,
    ) -> object:
        self.create_limits.append(max_active_sessions)
        self.sessions[(state.user_id, state.session_id)] = state
        self.requests[(state.user_id, request.request_id)] = request
        return SimpleNamespace(created=True, replay=None)

    async def load(self, *, user_id: UUID, session_id: UUID) -> object | None:
        return self.sessions.get((user_id, session_id))

    async def admit_turn(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        expected_revision: int,
    ) -> AssistantSessionState:
        self.admissions.append((user_id, session_id, expected_revision))
        if self.admission_error is not None:
            raise self.admission_error
        current = self.sessions[(user_id, session_id)]
        assert isinstance(current, AssistantSessionState)
        if current.revision != expected_revision:
            raise AssistantRevisionConflictError()
        return current

    async def commit_turn(
        self,
        *,
        state: AssistantSessionState,
        expected_revision: int,
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest:
        existing = self.requests.get((state.user_id, request.request_id))
        if existing is not None:
            if existing.fingerprint != request.fingerprint:
                raise IdempotencyKeyReusedError()
            return existing
        current = self.sessions[(state.user_id, state.session_id)]
        assert isinstance(current, AssistantSessionState)
        if current.revision != expected_revision:
            raise AssistantRevisionConflictError()
        self.sessions[(state.user_id, state.session_id)] = state
        self.requests[(state.user_id, request.request_id)] = request
        return request

    async def replace_with_tombstone(
        self,
        tombstone: object,
        *,
        expected_revision: int,
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest:
        self.tombstones.append(tombstone)
        self.sessions[(USER_ID, SESSION_ID)] = tombstone
        self.requests[(USER_ID, request.request_id)] = request
        return request


class NoopLocks:
    @asynccontextmanager
    async def hold_tenant(self, *, user_id: UUID) -> Any:
        yield

    @asynccontextmanager
    async def hold_session(self, *, user_id: UUID, session_id: UUID) -> Any:
        yield


class CoachAdapter:
    def __init__(self) -> None:
        self.routes: list[CoachRouteDecision] = []
        self.coaching: CoachNarrativeDecision | Exception = CoachNarrativeDecision(
            coaching="지금 바로 한 가지를 실행하세요."
        )
        self.report_draft = CareerCoachReportDraft(
            summary="준비 현황과 실행 우선순위를 점검했습니다.",
            strengths=["Python API 경험"],
            improvements=["지원 실행"],
            priority_actions=["오늘 이력서 성과 한 줄을 수치로 수정합니다."],
            evidence_refs=[],
            tool_call_ids=[],
        )
        self.route_calls = 0
        self.coach_calls = 0
        self.report_inputs: list[dict[str, object]] = []

    async def route(self, **_kwargs: object) -> CoachRouteDecision:
        self.route_calls += 1
        return self.routes.pop(0)

    async def coach(self, **_kwargs: object) -> CoachNarrativeDecision:
        self.coach_calls += 1
        if isinstance(self.coaching, Exception):
            raise self.coaching
        return self.coaching

    async def generate_report(self, **kwargs: object) -> CareerCoachReportDraft:
        self.report_inputs.append(kwargs)
        return self.report_draft


class SavedJobs:
    def __init__(self, result: SavedJobRecommendationView | None = None) -> None:
        self.result = result
        self.calls = 0
        self.use_llm_values: list[bool] = []
        self.today_values: list[date | None] = []

    async def recommend_from_snapshot(
        self,
        *,
        use_llm: bool = True,
        today: date | None = None,
        **_kwargs: object,
    ) -> SavedJobRecommendationView | None:
        self.calls += 1
        self.use_llm_values.append(use_llm)
        self.today_values.append(today)
        return self.result


class ScheduleRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def lookup_schedule(self, **kwargs: object) -> object:
        from app.coach.models import ScheduleLookupToolResult

        self.calls.append(kwargs)
        return ScheduleLookupToolResult(
            status="no_active_plan",
            observed_at=kwargs["observed_at"],
            range_start=kwargs["range_start"],
            range_end=kwargs["range_end"],
        )


class ReportRepository:
    def __init__(self) -> None:
        self.by_request: dict[UUID, StoredCareerCoachReport | str] = {}
        self.by_session: dict[UUID, StoredCareerCoachReport] = {}
        self.persisted: list[object] = []

    async def find_by_request(self, *, user_id: UUID, request_id: UUID) -> object | None:
        return self.by_request.get(request_id)

    async def find_by_session(self, *, user_id: UUID, session_id: UUID) -> object | None:
        return self.by_session.get(session_id)

    async def persist(self, *, user_id: UUID, request_id: UUID, report: object) -> object:
        from app.coach.models import CareerCoachReportV1

        assert isinstance(report, CareerCoachReportV1)
        self.persisted.append(report)
        stored = StoredCareerCoachReport(
            id=REPORT_ID,
            user_id=user_id,
            request_id=request_id,
            report=report,
            created_at=NOW + timedelta(minutes=5),
        )
        self.by_request[request_id] = stored
        self.by_session[report.session_id] = stored
        return CareerCoachReportPersistenceResult(result=stored, created=True)


def saved_job_result() -> SavedJobRecommendationView:
    job = SavedJobView(
        id=JOB_ID,
        source_type="url",
        source_url="https://example.com/job",
        source_key="example-job",
        company_name="예시회사",
        job_title="백엔드 개발자",
        deadline=date(2026, 8, 31),
        posting_text="Python API 개발자를 찾습니다.",
        extracted_data={"skills": ["Python"]},
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 10, tzinfo=UTC),
    )
    return SavedJobRecommendationView(
        preferred_environment="원격과 코드 리뷰",
        match_score=91,
        matched_terms=["Python"],
        recommendation_source="llm",
        reason="프로필 기술과 공고가 일치합니다.",
        job=job,
    )


@pytest.mark.parametrize(
    "secret",
    [
        "AIzaSyDUMMY012345678901234567890123456",
        "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        "AKIAABCDEFGHIJKLMNOP",
        "refresh_token=very-sensitive-token-value",
        "postgresql://app_api:password@db.example/postgres",
    ],
)
def test_report_evidence_redaction_masks_common_credential_shapes(secret: str) -> None:
    redacted, changed = _redact(f"credential: {secret}")

    assert changed is True
    assert secret not in redacted
    assert "[REDACTED]" in redacted


def service(
    *,
    adapter: CoachAdapter | None = None,
    store: MemoryStore | None = None,
    reports: ReportRepository | None = None,
    saved_jobs: SavedJobs | None = None,
    profile_value: ProfileRecord | None = None,
) -> tuple[CareerCoachService, MemoryStore, CoachAdapter, ReportRepository]:
    values = iter([SESSION_ID, TURN_ID, TOOL_ID, UUID(int=511), UUID(int=512)])
    memory = store or MemoryStore()
    coach = adapter or CoachAdapter()
    report_repository = reports or ReportRepository()
    return (
        CareerCoachService(
            sessions=memory,
            locks=NoopLocks(),
            profiles=ProfileReader(profile_value or profile()),
            coach=coach,
            saved_jobs=saved_jobs or SavedJobs(),
            schedules=ScheduleRepository(),
            reports=report_repository,
            now_provider=lambda: NOW,
            uuid_provider=lambda: next(values),
        ),
        memory,
        coach,
        report_repository,
    )


@pytest.mark.asyncio
async def test_create_freezes_completed_profile_and_uses_absolute_24_hour_expiry() -> None:
    target, store, _adapter, _reports = service(profile_value=profile(style="direct"))

    response = await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    assert response.session_id == SESSION_ID
    assert response.revision == 0
    assert response.assistant_style == "direct"
    assert response.expires_at == NOW + timedelta(hours=24)
    state = store.sessions[(USER_ID, SESSION_ID)]
    assert isinstance(state, AssistantSessionState)
    assert state.profile_snapshot.snapshot_hash == "a" * 64
    assert state.profile_snapshot.assessment_result_id == UUID(int=510)
    assert store.create_limits == [6]


@pytest.mark.asyncio
async def test_general_message_uses_first_call_answer_and_commits_only_complete_turn() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="성과를 수치로 적어보세요.")]
    target, store, _adapter, _reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    response = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="이력서 경험을 어떻게 쓰죠?",
    )

    assert response.revision == 1
    assert response.intent == "general"
    assert response.assistant_message == "성과를 수치로 적어보세요."
    assert response.tool_results == []
    assert adapter.route_calls == 1
    assert adapter.coach_calls == 0
    state = store.sessions[(USER_ID, SESSION_ID)]
    assert isinstance(state, AssistantSessionState)
    assert len(state.turns) == 1


@pytest.mark.asyncio
async def test_idle_session_is_rejected_before_coach_routing() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="실행해보세요.")]
    target, store, _adapter, _reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    store.admission_error = AssistantSessionExpiredError()

    with pytest.raises(AssistantSessionExpiredError):
        await target.send_message(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=MESSAGE_REQUEST_ID,
            expected_revision=0,
            text="도와주세요.",
        )

    assert store.admissions == [(USER_ID, SESSION_ID, 0)]
    assert adapter.route_calls == 0


@pytest.mark.asyncio
async def test_turn_limit_rejection_does_not_refresh_idle_admission() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="실행해보세요.")]
    target, store, _adapter, _reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="첫 질문",
    )
    current = store.sessions[(USER_ID, SESSION_ID)]
    assert isinstance(current, AssistantSessionState)
    base_turn = current.turns[0]
    turns = [
        base_turn.model_copy(
            update={
                "turn_id": UUID(int=600 + index),
                "request_id": UUID(int=700 + index),
            }
        )
        for index in range(20)
    ]
    store.sessions[(USER_ID, SESSION_ID)] = AssistantSessionState.model_validate(
        {
            **current.model_dump(mode="python"),
            "revision": 20,
            "turns": turns,
            "transcript_chars": sum(
                len(turn.user_text) + len(turn.assistant_message) for turn in turns
            ),
        }
    )
    store.admissions.clear()

    with pytest.raises(AssistantTurnLimitReachedError):
        await target.send_message(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=UUID(int=800),
            expected_revision=20,
            text="한도를 넘긴 질문",
        )

    assert store.admissions == []
    assert adapter.route_calls == 1


@pytest.mark.asyncio
async def test_transcript_limit_rejection_does_not_refresh_idle_admission() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="실행해보세요.")]
    target, store, _adapter, _reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="첫 질문",
    )
    current = store.sessions[(USER_ID, SESSION_ID)]
    assert isinstance(current, AssistantSessionState)
    base_turn = current.turns[0]
    turns = [
        base_turn.model_copy(
            update={
                "turn_id": UUID(int=810),
                "request_id": UUID(int=820),
                "user_text": "u" * 4_000,
                "assistant_message": "a" * 12_000,
            }
        ),
        base_turn.model_copy(
            update={
                "turn_id": UUID(int=811),
                "request_id": UUID(int=821),
                "user_text": "u" * 4_000,
                "assistant_message": "a" * 12_000,
            }
        ),
        base_turn.model_copy(
            update={
                "turn_id": UUID(int=812),
                "request_id": UUID(int=822),
                "user_text": "u" * 4_000,
                "assistant_message": "a" * 4_000,
            }
        ),
    ]
    store.sessions[(USER_ID, SESSION_ID)] = AssistantSessionState.model_validate(
        {
            **current.model_dump(mode="python"),
            "revision": 3,
            "turns": turns,
            "transcript_chars": 40_000,
        }
    )
    store.admissions.clear()

    with pytest.raises(AssistantTranscriptLimitReachedError):
        await target.send_message(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=UUID(int=823),
            expected_revision=3,
            text="x",
        )

    assert store.admissions == []
    assert adapter.route_calls == 1


@pytest.mark.asyncio
async def test_job_message_keeps_canonical_fact_block_when_final_coaching_fails() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="job_recommendation")]
    adapter.coaching = GeminiUnavailableError("provider secret")
    jobs = SavedJobs(saved_job_result())
    target, _store, _adapter, _reports = service(adapter=adapter, saved_jobs=jobs)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    response = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="지원할 공고를 추천해주세요.",
    )

    assert response.tool_results[0].type == "job_recommendation"
    assert "예시회사" in response.assistant_message
    assert "백엔드 개발자" in response.assistant_message
    assert "2026-08-31" in response.assistant_message
    assert "provider secret" not in response.assistant_message
    assert response.coaching.source == "deterministic_fallback"
    assert jobs.calls == 1
    assert jobs.use_llm_values == [False]
    assert jobs.today_values == [date(2026, 8, 11)]
    assert adapter.coach_calls == 1


@pytest.mark.asyncio
async def test_schedule_message_resolves_relative_kst_range_without_guessing() -> None:
    adapter = CoachAdapter()
    adapter.routes = [
        CoachRouteDecision(
            intent="schedule_lookup",
            schedule=ScheduleLookupArguments(period="this_week"),
        )
    ]
    target, _store, _adapter, _reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    response = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="이번 주 일정 알려주세요.",
    )

    schedule = response.tool_results[0]
    assert schedule.type == "schedule_lookup"
    assert schedule.range_start == date(2026, 8, 10)
    assert schedule.range_end == date(2026, 8, 16)


@pytest.mark.asyncio
async def test_mixed_message_executes_each_allowed_tool_once_in_canonical_order() -> None:
    adapter = CoachAdapter()
    adapter.routes = [
        CoachRouteDecision(
            intent="mixed",
            schedule=ScheduleLookupArguments(period="tomorrow"),
        )
    ]
    jobs = SavedJobs()
    target, _store, _adapter, _reports = service(adapter=adapter, saved_jobs=jobs)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    response = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="지원할 공고와 내일 계획을 함께 알려주세요.",
    )

    assert [result.type for result in response.tool_results] == [
        "job_recommendation",
        "schedule_lookup",
    ]
    assert response.tool_results[0].status == "no_eligible_jobs"
    assert response.tool_results[1].status == "no_active_plan"
    assert jobs.calls == 1
    assert adapter.coach_calls == 1


@pytest.mark.parametrize("intent", ["clarification", "out_of_scope"])
@pytest.mark.asyncio
async def test_non_tool_routing_is_a_successful_200_style_turn(intent: str) -> None:
    adapter = CoachAdapter()
    adapter.routes = [
        CoachRouteDecision(
            intent=intent,  # type: ignore[arg-type]
            response="조회할 날짜 범위를 구체적으로 말씀해주세요.",
        )
    ]
    jobs = SavedJobs()
    target, _store, _adapter, _reports = service(adapter=adapter, saved_jobs=jobs)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    response = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="언젠가 계획을 알려주세요.",
    )

    assert response.intent == intent
    assert response.tool_results == []
    assert response.revision == 1
    assert jobs.calls == 0
    assert adapter.coach_calls == 0


@pytest.mark.asyncio
async def test_retry_replays_identical_message_without_second_model_call() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="첫 답변")]
    target, _store, _adapter, _reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    first = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="같은 질문",
    )

    replay = await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="같은 질문",
    )

    assert replay == first
    assert adapter.route_calls == 1


@pytest.mark.asyncio
async def test_finalize_rejects_empty_session_without_db_write() -> None:
    target, _store, _adapter, reports = service()
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)

    with pytest.raises(AssistantReportEmptyError):
        await target.finalize_session(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=FINALIZE_REQUEST_ID,
            expected_revision=0,
        )

    assert reports.persisted == []


@pytest.mark.asyncio
async def test_finalize_rejects_request_id_already_used_by_message_before_db_write() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="지원 계획을 정리하세요.")]
    target, _store, _adapter, reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="지원 계획이 필요해요.",
    )

    with pytest.raises(IdempotencyKeyReusedError):
        await target.finalize_session(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=MESSAGE_REQUEST_ID,
            expected_revision=1,
        )

    assert reports.persisted == []


@pytest.mark.asyncio
async def test_admitted_finalize_returns_durable_report_if_redis_expires_during_persist() -> None:
    class CleanupFailureStore(MemoryStore):
        async def replace_with_tombstone(self, *args: object, **kwargs: object) -> object:
            raise AssistantSessionExpiredError()

    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="지원 계획을 정리하세요.")]
    store = CleanupFailureStore()
    target, _store, _adapter, reports = service(adapter=adapter, store=store)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="지원 계획이 필요해요.",
    )

    result = await target.finalize_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=FINALIZE_REQUEST_ID,
        expected_revision=1,
    )

    assert result.created is True
    assert len(reports.persisted) == 1

    with pytest.raises(AssistantAlreadyFinalizedError):
        await target.send_message(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=UUID(int=520),
            expected_revision=1,
            text="종료 뒤 메시지",
        )


@pytest.mark.asyncio
async def test_finalize_detects_turn_committed_while_report_was_generating() -> None:
    store = MemoryStore()

    class RacingCoach(CoachAdapter):
        async def generate_report(self, **kwargs: object) -> CareerCoachReportDraft:
            current = store.sessions[(USER_ID, SESSION_ID)]
            assert isinstance(current, AssistantSessionState)
            first = current.turns[0]
            second = first.model_copy(
                update={
                    "turn_id": UUID(int=530),
                    "request_id": UUID(int=531),
                    "user_text": "동시에 저장된 질문",
                    "assistant_message": "동시에 저장된 답변",
                }
            )
            store.sessions[(USER_ID, SESSION_ID)] = AssistantSessionState.model_validate(
                {
                    **current.model_dump(mode="python"),
                    "revision": 2,
                    "turns": [first, second],
                    "transcript_chars": sum(
                        len(turn.user_text) + len(turn.assistant_message)
                        for turn in (first, second)
                    ),
                }
            )
            return await super().generate_report(**kwargs)

    adapter = RacingCoach()
    adapter.routes = [CoachRouteDecision(intent="general", response="지원 계획을 정리하세요.")]
    target, _store, _adapter, reports = service(adapter=adapter, store=store)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="지원 계획이 필요해요.",
    )

    with pytest.raises(AssistantRevisionConflictError):
        await target.finalize_session(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=FINALIZE_REQUEST_ID,
            expected_revision=1,
        )

    assert reports.persisted == []


@pytest.mark.asyncio
async def test_finalize_redacts_secret_and_persists_only_verified_user_evidence() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="지원 계획을 정리해볼게요.")]
    adapter.report_draft = adapter.report_draft.model_copy(
        update={
            "summary": ("노출되면 안 되는 sk-proj-abcdefghijklmnopqrstuvwxyz123456 을 제거합니다."),
            "evidence_refs": [CareerCoachEvidenceReference(turn_id=TURN_ID, category="context")],
        }
    )
    target, store, _adapter, reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="제 키는 sk-proj-abcdefghijklmnopqrstuvwxyz123456 이고 지원이 두려워요.",
    )

    finalized = await target.finalize_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=FINALIZE_REQUEST_ID,
        expected_revision=1,
    )

    assert isinstance(finalized.response, AssistantFinalizeResponse)
    assert finalized.created is True
    report = finalized.response.report
    assert report.evidence[0].turn_id == TURN_ID
    assert "sk-proj" not in report.evidence[0].quote
    assert "[REDACTED]" in report.evidence[0].quote
    assert report.evidence[0].redacted is True
    assert "sk-proj" not in report.summary
    assert report.source_session_hash != report.report_hash
    assert reports.persisted == [report]
    assert len(store.tombstones) == 1
    provider_input = adapter.report_inputs[0]["redacted_turns"]
    assert "sk-proj" not in str(provider_input)


@pytest.mark.asyncio
async def test_finalize_rejects_forged_turn_reference_without_db_write() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="general", response="지원 계획을 정리하세요.")]
    adapter.report_draft = adapter.report_draft.model_copy(
        update={
            "evidence_refs": [
                CareerCoachEvidenceReference(turn_id=UUID(int=999), category="context")
            ]
        }
    )
    target, _store, _adapter, reports = service(adapter=adapter)
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="지원 계획이 필요해요.",
    )

    with pytest.raises(GeminiInvalidResponseError):
        await target.finalize_session(
            user_id=USER_ID,
            session_id=SESSION_ID,
            request_id=FINALIZE_REQUEST_ID,
            expected_revision=1,
        )

    assert reports.persisted == []


@pytest.mark.asyncio
async def test_report_tool_snapshot_keeps_public_facts_and_posting_hash_only() -> None:
    adapter = CoachAdapter()
    adapter.routes = [CoachRouteDecision(intent="job_recommendation")]
    adapter.report_draft = adapter.report_draft.model_copy(update={"tool_call_ids": [TURN_ID]})
    target, _store, _adapter, _reports = service(
        adapter=adapter,
        saved_jobs=SavedJobs(saved_job_result()),
    )
    await target.create_session(user_id=USER_ID, request_id=CREATE_REQUEST_ID)
    await target.send_message(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=MESSAGE_REQUEST_ID,
        expected_revision=0,
        text="공고를 추천해주세요.",
    )

    finalized = await target.finalize_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
        request_id=FINALIZE_REQUEST_ID,
        expected_revision=1,
    )

    facts = finalized.response.report.tool_snapshots[0].facts
    assert (
        facts["posting_hash"]
        == hashlib.sha256("Python API 개발자를 찾습니다.".encode()).hexdigest()
    )
    assert "posting_text" not in str(facts)
    assert "extracted_data" not in str(facts)
