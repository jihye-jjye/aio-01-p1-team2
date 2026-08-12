import logging
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from app.api.dependencies import get_assistant_service, get_current_user
from app.auth.models import CurrentUser
from app.coach.errors import AssistantRevisionConflictError
from app.coach.models import (
    AssistantFinalizeResponse,
    AssistantMessageResponse,
    AssistantSessionCreateResponse,
    CareerCoachAssessmentSnapshot,
    CareerCoachReportEngine,
    CareerCoachReportV1,
    CoachingResult,
)
from app.main import create_app
from app.profiles.models import ProfileOnboardingData

USER_ID = UUID("00000000-0000-0000-0000-000000000701")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000702")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000703")
REPORT_ID = UUID("00000000-0000-0000-0000-000000000704")
ASSESSMENT_ID = UUID("00000000-0000-0000-0000-000000000705")
NOW = datetime(2026, 8, 11, 1, tzinfo=UTC)


def _report() -> CareerCoachReportV1:
    profile = ProfileOnboardingData(
        target_role="백엔드 개발자",
        skills=["Python"],
        experience_summary="API 개발 경험",
        target_date=date(2026, 12, 31),
        target_company=None,
        preferred_environment="원격 근무",
        daily_notification_time=time(9),
        assistant_style="friendly",
    )
    return CareerCoachReportV1(
        session_id=SESSION_ID,
        session_revision=1,
        started_at_kst=datetime.fromisoformat("2026-08-11T10:00:00+09:00"),
        finalized_at_kst=datetime.fromisoformat("2026-08-11T10:05:00+09:00"),
        user_turn_count=1,
        profile_snapshot=profile,
        assessment_snapshot=CareerCoachAssessmentSnapshot(
            score=60,
            level="intermediate",
            summary={"reason": "실행 보강 필요"},
            version="v1",
        ),
        profile_hash="a" * 64,
        assessment_result_id=ASSESSMENT_ID,
        assistant_style="friendly",
        summary="상담 요약",
        strengths=["API 경험"],
        improvements=["지원 실행"],
        priority_actions=["오늘 지원합니다."],
        evidence=[],
        tool_snapshots=[],
        excluded_tool_call_count=0,
        excluded_tool_calls_hash=None,
        engine=CareerCoachReportEngine(),
        source_session_hash="b" * 64,
        report_hash="c" * 64,
    )


class StubAssistantService:
    def __init__(self, *, finalize_created: bool = True) -> None:
        self.finalize_created = finalize_created
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def create_session(self, **kwargs: object) -> AssistantSessionCreateResponse:
        self.calls.append(("create", kwargs))
        return AssistantSessionCreateResponse(
            session_id=SESSION_ID,
            assistant_style="friendly",
            assistant_message="상담을 시작할게요.",
            expires_at=NOW + timedelta(hours=24),
        )

    async def send_message(self, **kwargs: object) -> AssistantMessageResponse:
        self.calls.append(("message", kwargs))
        return AssistantMessageResponse(
            session_id=SESSION_ID,
            revision=1,
            intent="general",
            assistant_message="바로 한 가지를 실행해보세요.",
            coaching=CoachingResult(
                style="friendly",
                message="바로 한 가지를 실행해보세요.",
                source="llm",
            ),
            expires_at=NOW + timedelta(hours=24),
        )

    async def finalize_session(self, **kwargs: object) -> object:
        self.calls.append(("finalize", kwargs))
        return SimpleNamespace(
            created=self.finalize_created,
            response=AssistantFinalizeResponse(
                ai_result_id=REPORT_ID,
                session_id=SESSION_ID,
                session_revision=1,
                report=_report(),
                created_at=NOW + timedelta(minutes=5),
            ),
        )


def _client(service: StubAssistantService) -> TestClient:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID,
        role="user",
        session_id=UUID(int=999),
    )
    app.dependency_overrides[get_assistant_service] = lambda: service
    return TestClient(app)


def test_assistant_routes_take_user_only_from_jwt_and_return_contract_statuses() -> None:
    service = StubAssistantService()
    client = _client(service)

    created = client.post("/api/v1/assistant/sessions", json={"request_id": str(REQUEST_ID)})
    message = client.post(
        f"/api/v1/assistant/sessions/{SESSION_ID}/messages",
        json={"request_id": str(REQUEST_ID), "expected_revision": 0, "text": "도와주세요"},
    )
    finalized = client.post(
        f"/api/v1/assistant/sessions/{SESSION_ID}/finalize",
        json={"request_id": str(REQUEST_ID), "expected_revision": 1},
    )

    assert created.status_code == 201
    assert created.json()["revision"] == 0
    assert message.status_code == 200
    assert message.json()["revision"] == 1
    assert finalized.status_code == 201
    assert finalized.json()["ai_result_id"] == str(REPORT_ID)
    assert all(call[1]["user_id"] == USER_ID for call in service.calls)


def test_finalize_durable_replay_returns_200() -> None:
    client = _client(StubAssistantService(finalize_created=False))

    response = client.post(
        f"/api/v1/assistant/sessions/{SESSION_ID}/finalize",
        json={"request_id": str(REQUEST_ID), "expected_revision": 1},
    )

    assert response.status_code == 200


def test_assistant_request_models_forbid_user_id_and_extra_fields() -> None:
    client = _client(StubAssistantService())

    response = client.post(
        "/api/v1/assistant/sessions",
        json={"request_id": str(REQUEST_ID), "user_id": str(UUID(int=123))},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_assistant_domain_error_uses_stable_error_envelope() -> None:
    class ConflictService(StubAssistantService):
        async def send_message(self, **kwargs: object) -> AssistantMessageResponse:
            raise AssistantRevisionConflictError()

    client = _client(ConflictService())

    response = client.post(
        f"/api/v1/assistant/sessions/{SESSION_ID}/messages",
        json={"request_id": str(REQUEST_ID), "expected_revision": 0, "text": "도와주세요"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "ASSISTANT_REVISION_CONFLICT",
            "message": "상담 revision이 최신 상태와 다릅니다.",
            "retryable": False,
            "details": {},
        }
    }


def test_openapi_exposes_non_streaming_assistant_contract() -> None:
    schema = create_app(lifespan_enabled=False).openapi()

    create_operation = schema["paths"]["/api/v1/assistant/sessions"]["post"]
    finalize_operation = schema["paths"]["/api/v1/assistant/sessions/{session_id}/finalize"]["post"]
    assert create_operation["tags"] == ["assistant"]
    assert {"200", "201"}.issubset(finalize_operation["responses"])
    assert "text/event-stream" not in str(schema["paths"]["/api/v1/assistant/sessions"])


def test_infrastructure_error_logs_safe_database_metadata_without_raw_message(
    caplog,
) -> None:
    class FailingFinalizeService(StubAssistantService):
        async def finalize_session(self, **kwargs: object) -> object:
            raise psycopg.errors.CheckViolation("raw-sensitive-database-message")

    client = _client(FailingFinalizeService())
    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client.post(
            f"/api/v1/assistant/sessions/{SESSION_ID}/finalize",
            json={"request_id": str(REQUEST_ID), "expected_revision": 1},
        )

    assert response.status_code == 503
    records = [
        record
        for record in caplog.records
        if record.getMessage().startswith("Infrastructure failure")
    ]
    assert len(records) == 1
    record = records[0]
    assert record.error_type == "CheckViolation"
    assert record.sqlstate == "23514"
    assert record.constraint_name is None
    assert record.request_method == "POST"
    assert record.request_path == f"/api/v1/assistant/sessions/{SESSION_ID}/finalize"
    assert record.getMessage() == (
        "Infrastructure failure "
        "error_type=CheckViolation "
        "sqlstate=23514 "
        "constraint_name=None "
        "request_method=POST "
        f"request_path=/api/v1/assistant/sessions/{SESSION_ID}/finalize"
    )
    assert "raw-sensitive-database-message" not in caplog.text
