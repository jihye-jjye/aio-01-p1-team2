import json
from datetime import UTC, date, datetime, time
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.coach.errors import IdempotencyKeyReusedError
from app.coach.models import (
    CareerCoachAssessmentSnapshot,
    CareerCoachReportEngine,
    CareerCoachReportV1,
)
from app.coach.repository import PsycopgCoachReportRepository, PsycopgCoachRepository
from app.profiles.models import ProfileOnboardingData
from app.saved_jobs.models import SavedJobRecommendationDecision, SavedJobView
from app.saved_jobs.service import SavedJobService
from tests.test_plan_management_repository import FakePool

USER_ID = UUID("00000000-0000-0000-0000-000000000301")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000302")
PLAN_ID = UUID("00000000-0000-0000-0000-000000000303")
ITEM_ID = UUID("00000000-0000-0000-0000-000000000304")
JOB_ID = UUID("00000000-0000-0000-0000-000000000305")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000306")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000307")
REPORT_ID = UUID("00000000-0000-0000-0000-000000000308")
OBSERVED_AT = datetime(2026, 8, 11, 3, tzinfo=UTC)


def profile() -> ProfileOnboardingData:
    return ProfileOnboardingData(
        target_role="백엔드 개발자",
        skills=["Python", "FastAPI"],
        experience_summary="API 운영 경험",
        target_date=date(2026, 12, 31),
        target_company=None,
        preferred_environment="원격과 코드 리뷰",
        daily_notification_time=time(9),
        assistant_style="direct",
    )


def job(*, deadline: date | None = date(2026, 8, 31)) -> SavedJobView:
    return SavedJobView(
        id=JOB_ID,
        source_type="url",
        source_url="https://example.com/job",
        source_key="example-job",
        company_name="예시회사",
        job_title="백엔드 개발자",
        deadline=deadline,
        posting_text="Python API 개발자를 찾습니다.",
        extracted_data={"skills": ["Python"]},
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 10, tzinfo=UTC),
    )


class SnapshotRepository:
    def __init__(self, jobs: list[SavedJobView]) -> None:
        self.jobs = jobs
        self.profile_reads = 0

    async def get_recommendation_profile(self, *, user_id: UUID) -> ProfileOnboardingData:
        self.profile_reads += 1
        raise AssertionError(
            "고정 profile snapshot 경로에서는 최신 프로필을 다시 읽으면 안 됩니다."
        )

    async def list_all(self) -> list[SavedJobView]:
        return self.jobs


class SnapshotRecommender:
    def __init__(self) -> None:
        self.candidates: list[SavedJobView] = []

    async def choose(
        self,
        *,
        user_id: UUID,
        profile: ProfileOnboardingData,
        candidates: list[SavedJobView],
    ) -> SavedJobRecommendationDecision:
        assert user_id == USER_ID
        assert profile == globals()["profile"]()
        self.candidates = candidates
        return SavedJobRecommendationDecision(
            selected_job_id=candidates[0].id,
            match_score=87,
            matched_terms=["Python"],
            reason="프로필의 기술과 공고가 일치합니다.",
        )


@pytest.mark.asyncio
async def test_saved_job_service_reuses_frozen_profile_and_queries_only_latest_candidates() -> None:
    expired = job(deadline=date(2026, 8, 10))
    eligible = job(deadline=date(2026, 8, 11))
    repository = SnapshotRepository([expired, eligible])
    recommender = SnapshotRecommender()
    service = SavedJobService(
        repository,
        recommender=recommender,
        today_provider=lambda: date(2026, 8, 11),
    )

    result = await service.recommend_from_snapshot(user_id=USER_ID, profile=profile())

    assert result is not None
    assert result.job.deadline == date(2026, 8, 11)
    assert repository.profile_reads == 0
    assert recommender.candidates == [eligible]


@pytest.mark.asyncio
async def test_schedule_repository_scopes_active_plan_and_items_to_owner_and_utc_window() -> None:
    row = {
        "plan_id": PLAN_ID,
        "plan_title": "백엔드 준비 계획",
        "item_id": ITEM_ID,
        "kind": "task",
        "item_title": "이력서 수정",
        "description": "성과를 수치로 보강",
        "item_status": "pending",
        "scheduled_at": datetime(2026, 8, 11, 0, tzinfo=UTC),
        "plan_day": 2,
        "slot": 1,
    }
    pool = FakePool([[row]])
    repository = PsycopgCoachRepository(pool)  # type: ignore[arg-type]

    result = await repository.lookup_schedule(
        user_id=USER_ID,
        range_start=date(2026, 8, 11),
        range_end=date(2026, 8, 12),
        observed_at=OBSERVED_AT,
    )

    assert result.status == "found"
    assert result.plan_id == PLAN_ID
    assert [item.id for item in result.items] == [ITEM_ID]
    sql, parameters = pool.value.statements[0]
    assert "p.user_id = %(user_id)s" in sql
    assert "si.user_id = %(user_id)s" in sql
    assert "p.status = 'active'" in sql
    assert "si.kind in ('milestone', 'task')" in sql
    assert "si.status <> 'cancelled'" in sql
    assert "si.scheduled_at >= %(starts_at)s" in sql
    assert "si.scheduled_at < %(ends_before)s" in sql
    assert parameters == {
        "user_id": USER_ID,
        "starts_at": datetime(2026, 8, 10, 15, tzinfo=UTC),
        "ends_before": datetime(2026, 8, 12, 15, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_schedule_repository_distinguishes_no_active_plan_from_empty_range() -> None:
    no_plan_repository = PsycopgCoachRepository(FakePool([[]]))  # type: ignore[arg-type]
    empty_plan_repository = PsycopgCoachRepository(
        FakePool([[{"plan_id": PLAN_ID, "plan_title": "계획", "item_id": None}]])  # type: ignore[arg-type]
    )

    no_plan = await no_plan_repository.lookup_schedule(
        user_id=USER_ID,
        range_start=date(2026, 8, 11),
        range_end=date(2026, 8, 11),
        observed_at=OBSERVED_AT,
    )
    empty = await empty_plan_repository.lookup_schedule(
        user_id=USER_ID,
        range_start=date(2026, 8, 11),
        range_end=date(2026, 8, 11),
        observed_at=OBSERVED_AT,
    )

    assert no_plan.status == "no_active_plan"
    assert empty.status == "empty"
    assert empty.plan_id == PLAN_ID
    assert empty.items == []


def report() -> CareerCoachReportV1:
    return CareerCoachReportV1(
        status="completed",
        session_id=SESSION_ID,
        session_revision=1,
        started_at_kst=datetime.fromisoformat("2026-08-11T10:00:00+09:00"),
        finalized_at_kst=datetime.fromisoformat("2026-08-11T10:05:00+09:00"),
        user_turn_count=1,
        profile_snapshot=profile(),
        assessment_snapshot=CareerCoachAssessmentSnapshot(
            score=61,
            level="intermediate",
            summary={"reason": "실행 보강 필요"},
            version="v1",
        ),
        profile_hash="a" * 64,
        assessment_result_id=UUID(int=309),
        assistant_style="direct",
        summary="사용자는 백엔드 취업 준비의 실행 우선순위를 점검했습니다.",
        strengths=["Python API 경험"],
        improvements=["성과 수치화"],
        priority_actions=["오늘 이력서 성과 한 줄을 수치로 수정합니다."],
        evidence=[],
        tool_snapshots=[],
        excluded_tool_call_count=0,
        excluded_tool_calls_hash=None,
        engine=CareerCoachReportEngine(
            provider="google",
            model="gemini-3.6-flash",
            prompt_version="career-coach-report-v1",
            schema_version="career-coach-report-draft-v1",
        ),
        redaction_version="career-coach-redaction-v1",
        source_session_hash="b" * 64,
        report_hash="c" * 64,
    )


def report_row(*, request_id: UUID = REQUEST_ID) -> dict[str, object]:
    value = report()
    return {
        "id": REPORT_ID,
        "user_id": USER_ID,
        "request_id": str(request_id),
        "kind": "career_coach_report",
        "decision_status": "not_applicable",
        "saved_job_id": None,
        "applied_plan_id": None,
        "decided_at": None,
        "content": value.model_dump(mode="json"),
        "model_name": value.engine.model,
        "prompt_version": value.engine.prompt_version,
        "created_at": datetime(2026, 8, 11, 1, 5, tzinfo=UTC),
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "assessment_snapshot",
            {
                "score": 61,
                "level": "intermediate",
                "summary": {"transcript": "raw"},
                "version": "v1",
            },
        ),
        (
            "tool_snapshots",
            [
                {
                    "tool_call_id": str(UUID(int=310)),
                    "type": "job_recommendation",
                    "observed_at": OBSERVED_AT,
                    "status": "found",
                    "facts": {"posting_text": "raw posting"},
                    "snapshot_hash": "d" * 64,
                }
            ],
        ),
    ],
)
def test_report_model_rejects_forbidden_raw_keys_recursively(
    field: str,
    value: object,
) -> None:
    payload = report().model_dump(mode="json")
    payload[field] = value

    with pytest.raises(ValidationError):
        CareerCoachReportV1.model_validate(payload)


def test_report_profile_snapshot_forbids_unknown_fields() -> None:
    payload = report().model_dump(mode="json")
    payload["profile_snapshot"]["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        CareerCoachReportV1.model_validate(payload)


@pytest.mark.parametrize("value", [0.00001, "nul\x00value"])
def test_report_model_rejects_values_with_non_identical_jsonb_text(value: object) -> None:
    payload = report().model_dump(mode="json")
    payload["assessment_snapshot"]["summary"] = {"value": value}

    with pytest.raises(ValidationError):
        CareerCoachReportV1.model_validate(payload)


def test_report_model_uses_the_same_128_kib_text_bound_as_jsonb() -> None:
    payload = report().model_dump(mode="json")
    payload["profile_snapshot"]["experience_summary"] = ""
    current_size = len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    payload["profile_snapshot"]["experience_summary"] = "x" * (128 * 1024 - current_size)

    accepted = CareerCoachReportV1.model_validate(payload)
    assert (
        len(
            json.dumps(
                accepted.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        )
        == 128 * 1024
    )

    payload["profile_snapshot"]["experience_summary"] += "x"
    with pytest.raises(ValidationError):
        CareerCoachReportV1.model_validate(payload)


@pytest.mark.asyncio
async def test_report_repository_persists_fixed_kind_status_and_null_links() -> None:
    pool = FakePool([[report_row()]])
    repository = PsycopgCoachReportRepository(pool)  # type: ignore[arg-type]

    stored = await repository.persist(
        user_id=USER_ID,
        request_id=REQUEST_ID,
        report=report(),
    )

    assert stored.created is True
    assert stored.result.report == report()
    sql, parameters = pool.value.statements[0]
    assert "'career_coach_report'" in sql
    assert "'not_applicable'" in sql
    assert "null, null" in sql
    assert "on conflict (user_id, request_id) do nothing" in sql
    assert parameters["user_id"] == USER_ID
    assert parameters["request_id"] == str(REQUEST_ID)


@pytest.mark.asyncio
async def test_report_repository_rejects_same_request_for_changed_session_snapshot() -> None:
    pool = FakePool([None, report_row()])
    repository = PsycopgCoachReportRepository(pool)  # type: ignore[arg-type]
    changed = report().model_copy(update={"source_session_hash": "d" * 64})

    with pytest.raises(IdempotencyKeyReusedError):
        await repository.persist(
            user_id=USER_ID,
            request_id=REQUEST_ID,
            report=changed,
        )


@pytest.mark.asyncio
async def test_report_repository_reads_request_without_kind_filter_before_classifying() -> None:
    pool = FakePool([[{"kind": "profile_assessment"}]])
    repository = PsycopgCoachReportRepository(pool)  # type: ignore[arg-type]

    collision = await repository.find_by_request(user_id=USER_ID, request_id=REQUEST_ID)

    assert collision == "profile_assessment"
    sql, parameters = pool.value.statements[0]
    assert "user_id = %(user_id)s" in sql
    assert "request_id = %(request_id)s" in sql
    assert "kind = 'career_coach_report'" not in sql
    assert parameters == {"user_id": USER_ID, "request_id": str(REQUEST_ID)}


@pytest.mark.asyncio
async def test_report_repository_session_replay_is_always_owner_scoped() -> None:
    pool = FakePool([[report_row()]])
    repository = PsycopgCoachReportRepository(pool)  # type: ignore[arg-type]

    stored = await repository.find_by_session(user_id=USER_ID, session_id=SESSION_ID)

    assert stored is not None
    assert stored.report.session_id == SESSION_ID
    sql, parameters = pool.value.statements[0]
    assert "user_id = %(user_id)s" in sql
    assert "kind = 'career_coach_report'" in sql
    assert "content ->> 'session_id' = %(session_id)s" in sql
    assert parameters == {"user_id": USER_ID, "session_id": str(SESSION_ID)}
