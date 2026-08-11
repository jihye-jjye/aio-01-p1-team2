from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.profiles.models import ProfileOnboardingData

KST = ZoneInfo("Asia/Seoul")
SESSION_TTL_SECONDS = 86_400
REPORT_FORBIDDEN_KEYS = frozenset(
    {
        "transcript",
        "messages",
        "assistant_message",
        "raw_provider_response",
        "raw_response",
        "raw_prompt",
        "prompt",
        "posting_text",
        "extracted_data",
        "tool_results",
    }
)

type AssistantStyle = Literal["friendly", "direct"]
type AssistantIntent = Literal[
    "general",
    "job_recommendation",
    "schedule_lookup",
    "mixed",
    "clarification",
    "out_of_scope",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CareerCoachProfileSnapshot(ProfileOnboardingData):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def accept_profile_model(cls, value: object) -> object:
        if isinstance(value, ProfileOnboardingData):
            return value.model_dump(mode="python")
        return value


class AssistantSessionCreateRequest(StrictModel):
    request_id: UUID


class AssistantMessageRequest(StrictModel):
    request_id: UUID
    expected_revision: int = Field(strict=True, ge=0)
    text: str = Field(min_length=1, max_length=4000)


class AssistantFinalizeRequest(StrictModel):
    request_id: UUID
    expected_revision: int = Field(strict=True, ge=0)


class ScheduleLookupArguments(StrictModel):
    period: Literal["today", "tomorrow", "this_week", "next_week", "explicit"]
    start_on: date | None = None
    end_on: date | None = None

    @model_validator(mode="after")
    def validate_explicit_range_shape(self) -> ScheduleLookupArguments:
        if self.period == "explicit":
            if self.start_on is None or self.end_on is None:
                raise ValueError("explicit 기간에는 start_on과 end_on이 모두 필요합니다.")
            day_count = (self.end_on - self.start_on).days + 1
            if day_count < 1:
                raise ValueError("조회 종료일은 시작일보다 빠를 수 없습니다.")
            if day_count > 28:
                raise ValueError("일정 조회 기간은 양 끝을 포함해 최대 28일입니다.")
        elif self.start_on is not None or self.end_on is not None:
            raise ValueError("상대 기간에는 명시 날짜를 함께 보낼 수 없습니다.")
        return self


class JobFact(StrictModel):
    id: UUID
    company_name: str = Field(min_length=1, max_length=300)
    job_title: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=4000)
    deadline: date | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class JobRecommendationToolResult(StrictModel):
    type: Literal["job_recommendation"] = "job_recommendation"
    status: Literal["found", "no_eligible_jobs"]
    observed_at: AwareDatetime
    job: JobFact | None = None
    match_score: int | None = Field(default=None, ge=0, le=100)
    matched_terms: list[str] = Field(default_factory=list, max_length=50)
    reason: str | None = Field(default=None, max_length=500)
    recommendation_source: Literal["llm", "keyword_fallback"] | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> JobRecommendationToolResult:
        if self.status == "found":
            if (
                self.job is None
                or self.match_score is None
                or self.reason is None
                or self.recommendation_source is None
            ):
                raise ValueError("found 공고 추천에는 사실과 판단이 모두 필요합니다.")
        elif (
            any(
                value is not None
                for value in (
                    self.job,
                    self.match_score,
                    self.reason,
                    self.recommendation_source,
                )
            )
            or self.matched_terms
        ):
            raise ValueError("공고가 없으면 추천 판단을 포함할 수 없습니다.")
        return self


class ScheduleItemFact(StrictModel):
    id: UUID
    kind: Literal["milestone", "task"]
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    status: Literal["pending", "in_progress", "completed"]
    scheduled_at: AwareDatetime
    plan_day: int | None = Field(default=None, ge=1)
    slot: int | None = Field(default=None, ge=1)


class ScheduleLookupToolResult(StrictModel):
    type: Literal["schedule_lookup"] = "schedule_lookup"
    status: Literal["found", "empty", "no_active_plan"]
    observed_at: AwareDatetime
    range_start: date
    range_end: date
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    plan_id: UUID | None = None
    plan_title: str | None = Field(default=None, max_length=500)
    items: list[ScheduleItemFact] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_status_shape(self) -> ScheduleLookupToolResult:
        if self.range_end < self.range_start:
            raise ValueError("일정 조회 종료일은 시작일보다 빠를 수 없습니다.")
        if self.status == "no_active_plan":
            if self.plan_id is not None or self.plan_title is not None or self.items:
                raise ValueError("활성 계획이 없으면 계획 사실을 포함할 수 없습니다.")
        else:
            if self.plan_id is None or not self.plan_title:
                raise ValueError("일정 결과에는 활성 계획 정보가 필요합니다.")
            if (self.status == "found") != bool(self.items):
                raise ValueError("found 상태와 일정 항목 유무가 일치해야 합니다.")
            if any(
                not self.range_start <= item.scheduled_at.astimezone(KST).date() <= self.range_end
                for item in self.items
            ):
                raise ValueError("일정 항목은 조회 기간의 KST 날짜 범위 안에 있어야 합니다.")
        return self


type ToolResult = Annotated[
    JobRecommendationToolResult | ScheduleLookupToolResult,
    Field(discriminator="type"),
]


class AssistantProfileSnapshot(StrictModel):
    profile: CareerCoachProfileSnapshot
    assessment_score: int = Field(ge=0, le=100)
    assessment_level: Literal["beginner", "intermediate", "advanced"]
    assessment_summary: dict[str, Any]
    assessment_version: str = Field(min_length=1, max_length=200)
    assessment_result_id: UUID
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CoachingResult(StrictModel):
    style: AssistantStyle
    message: str = Field(min_length=1, max_length=12000)
    source: Literal["llm", "deterministic_fallback"]


class AssistantSessionCreateResponse(StrictModel):
    session_id: UUID
    revision: Literal[0] = 0
    assistant_style: AssistantStyle
    assistant_message: str = Field(min_length=1, max_length=12000)
    expires_at: AwareDatetime


class AssistantMessageResponse(StrictModel):
    session_id: UUID
    revision: int = Field(strict=True, ge=1)
    intent: AssistantIntent
    assistant_message: str = Field(min_length=1, max_length=12000)
    tool_results: list[ToolResult] = Field(default_factory=list, max_length=2)
    coaching: CoachingResult
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def validate_tool_counts(self) -> AssistantMessageResponse:
        _validate_tool_result_counts(self.tool_results)
        return self


class ProcessedAssistantRequest(StrictModel):
    request_id: UUID
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation: Literal["create", "message", "finalize"]
    session_id: UUID
    response: dict[str, Any]
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def validate_response_shape(self) -> ProcessedAssistantRequest:
        response_model: (
            AssistantSessionCreateResponse | AssistantMessageResponse | AssistantFinalizeResponse
        )
        if self.operation == "create":
            response_model = AssistantSessionCreateResponse.model_validate(self.response)
        elif self.operation == "message":
            response_model = AssistantMessageResponse.model_validate(self.response)
        else:
            response_model = AssistantFinalizeResponse.model_validate(self.response)
        if response_model.session_id != self.session_id:
            raise ValueError("처리 요청의 session_id가 응답과 일치하지 않습니다.")
        response_expires_at = getattr(response_model, "expires_at", None)
        if response_expires_at is not None and response_expires_at != self.expires_at:
            raise ValueError("처리 요청의 만료 시각이 응답과 일치하지 않습니다.")
        self.response = response_model.model_dump(mode="json")
        return self


class AssistantConversationTurn(StrictModel):
    turn_id: UUID
    request_id: UUID
    user_text: str = Field(min_length=1, max_length=4000)
    assistant_message: str = Field(min_length=1, max_length=12000)
    intent: AssistantIntent
    tool_results: list[ToolResult] = Field(default_factory=list, max_length=2)
    coaching: CoachingResult
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_tool_counts(self) -> AssistantConversationTurn:
        _validate_tool_result_counts(self.tool_results)
        return self


class AssistantSessionState(StrictModel):
    status: Literal["active"] = "active"
    user_id: UUID
    session_id: UUID
    created_at: AwareDatetime
    expires_at: AwareDatetime
    expires_at_epoch: int | None = Field(default=None, ge=1)
    expires_at_epoch_ms: int | None = Field(default=None, ge=1)
    profile_snapshot: AssistantProfileSnapshot
    revision: int = Field(default=0, strict=True, ge=0, le=20)
    turns: list[AssistantConversationTurn] = Field(default_factory=list, max_length=20)
    transcript_chars: int = Field(default=0, strict=True, ge=0, le=40000)
    processed_requests: dict[str, ProcessedAssistantRequest] = Field(default_factory=dict)
    tool_snapshots: list[CareerCoachReportToolSnapshot] = Field(
        default_factory=list,
        max_length=40,
    )

    @model_validator(mode="after")
    def validate_session_state(self) -> AssistantSessionState:
        if self.expires_at - self.created_at != timedelta(seconds=SESSION_TTL_SECONDS):
            raise ValueError("상담 세션 수명은 정확히 24시간이어야 합니다.")
        expected_epoch = int(self.expires_at.timestamp())
        expected_epoch_ms = int(self.expires_at.timestamp() * 1000)
        if self.expires_at_epoch is None:
            self.expires_at_epoch = expected_epoch
        elif self.expires_at_epoch != expected_epoch:
            raise ValueError("상담 절대 만료 시각이 일치하지 않습니다.")
        if self.expires_at_epoch_ms is None:
            self.expires_at_epoch_ms = expected_epoch_ms
        elif self.expires_at_epoch_ms != expected_epoch_ms:
            raise ValueError("상담 밀리초 절대 만료 시각이 일치하지 않습니다.")
        if self.revision != len(self.turns):
            raise ValueError("상담 revision과 성공한 사용자 턴 수가 일치해야 합니다.")
        expected_transcript_chars = sum(
            len(turn.user_text) + len(turn.assistant_message) for turn in self.turns
        )
        if self.transcript_chars != expected_transcript_chars:
            raise ValueError("상담 transcript_chars가 실제 대화 길이와 일치하지 않습니다.")
        if any(key != str(value.request_id) for key, value in self.processed_requests.items()):
            raise ValueError("처리 요청 인덱스가 request_id와 일치하지 않습니다.")
        if any(
            request.session_id != self.session_id or request.expires_at != self.expires_at
            for request in self.processed_requests.values()
        ):
            raise ValueError("처리 요청이 상담 세션 또는 만료 시각과 일치하지 않습니다.")
        return self


class AssistantSessionTombstone(StrictModel):
    status: Literal["finalized"] = "finalized"
    user_id: UUID
    session_id: UUID
    session_revision: int = Field(strict=True, ge=1, le=20)
    report_id: UUID
    created_at: AwareDatetime
    finalized_at: AwareDatetime
    expires_at: AwareDatetime
    expires_at_epoch: int | None = Field(default=None, ge=1)
    expires_at_epoch_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_tombstone(self) -> AssistantSessionTombstone:
        if not self.created_at <= self.finalized_at < self.expires_at:
            raise ValueError("상담 종료 시각이 세션 수명 안에 있어야 합니다.")
        if self.expires_at - self.created_at != timedelta(seconds=SESSION_TTL_SECONDS):
            raise ValueError("상담 세션 수명은 정확히 24시간이어야 합니다.")
        expected_epoch = int(self.expires_at.timestamp())
        expected_epoch_ms = int(self.expires_at.timestamp() * 1000)
        if self.expires_at_epoch is None:
            self.expires_at_epoch = expected_epoch
        elif self.expires_at_epoch != expected_epoch:
            raise ValueError("상담 절대 만료 시각이 일치하지 않습니다.")
        if self.expires_at_epoch_ms is None:
            self.expires_at_epoch_ms = expected_epoch_ms
        elif self.expires_at_epoch_ms != expected_epoch_ms:
            raise ValueError("상담 밀리초 절대 만료 시각이 일치하지 않습니다.")
        return self


class CareerCoachAssessmentSnapshot(StrictModel):
    score: int = Field(ge=0, le=100)
    level: Literal["beginner", "intermediate", "advanced"]
    summary: dict[str, Any]
    version: str = Field(min_length=1, max_length=200)


class CareerCoachReportEvidence(StrictModel):
    turn_id: UUID
    quote: str = Field(min_length=1, max_length=200)
    category: Literal["strength", "improvement", "goal", "action", "context"]
    redacted: bool


class CareerCoachReportToolSnapshot(StrictModel):
    tool_call_id: UUID
    type: Literal["job_recommendation", "schedule_lookup"]
    observed_at: AwareDatetime
    status: str = Field(min_length=1, max_length=100)
    facts: dict[str, Any]
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CareerCoachReportEngine(StrictModel):
    provider: Literal["google"] = "google"
    model: Literal["gemini-3.6-flash"] = "gemini-3.6-flash"
    prompt_version: Literal["career-coach-report-v1"] = "career-coach-report-v1"
    schema_version: Literal["career-coach-report-draft-v1"] = "career-coach-report-draft-v1"


class CareerCoachReportV1(StrictModel):
    schema_version: Literal["career-coach-report-v1"] = "career-coach-report-v1"
    status: Literal["completed"] = "completed"
    session_id: UUID
    session_revision: int = Field(strict=True, ge=1, le=20)
    started_at_kst: AwareDatetime
    finalized_at_kst: AwareDatetime
    user_turn_count: int = Field(strict=True, ge=1, le=20)
    profile_snapshot: CareerCoachProfileSnapshot
    assessment_snapshot: CareerCoachAssessmentSnapshot
    profile_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    assessment_result_id: UUID
    assistant_style: AssistantStyle
    summary: str = Field(min_length=1, max_length=4000)
    strengths: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(max_length=5)
    improvements: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(max_length=5)
    priority_actions: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(
        min_length=1,
        max_length=7,
    )
    evidence: list[CareerCoachReportEvidence] = Field(max_length=8)
    tool_snapshots: list[CareerCoachReportToolSnapshot] = Field(max_length=5)
    excluded_tool_call_count: int = Field(strict=True, ge=0)
    excluded_tool_calls_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    engine: CareerCoachReportEngine
    redaction_version: Literal["career-coach-redaction-v1"] = "career-coach-redaction-v1"
    source_session_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> CareerCoachReportV1:
        if self.session_revision != self.user_turn_count:
            raise ValueError("보고서 revision과 사용자 턴 수가 일치해야 합니다.")
        if self.finalized_at_kst < self.started_at_kst:
            raise ValueError("보고서 종료 시각은 시작 시각보다 빠를 수 없습니다.")
        kst_offset_seconds = 9 * 60 * 60
        if any(
            value.utcoffset() is None
            or int(value.utcoffset().total_seconds()) != kst_offset_seconds
            for value in (self.started_at_kst, self.finalized_at_kst)
        ):
            raise ValueError("보고서 시작·종료 시각은 KST(+09:00)여야 합니다.")
        if (self.excluded_tool_call_count == 0) != (self.excluded_tool_calls_hash is None):
            raise ValueError("제외된 tool call 수와 hash가 일치해야 합니다.")
        payload = self.model_dump(mode="json")
        if _contains_forbidden_report_key(payload):
            raise ValueError("보고서에 원문 또는 provider 내부 필드를 저장할 수 없습니다.")
        if _contains_noncanonical_report_value(payload):
            raise ValueError("보고서 임의 JSON 값은 JSONB와 동일하게 표현 가능한 값이어야 합니다.")
        canonical_jsonb_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if len(canonical_jsonb_text.encode("utf-8")) > 128 * 1024:
            raise ValueError("보고서 JSON은 128KiB 이하여야 합니다.")
        return self


class AssistantFinalizeResponse(StrictModel):
    ai_result_id: UUID
    session_id: UUID
    session_revision: int = Field(strict=True, ge=1, le=20)
    report: CareerCoachReportV1
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_report_identity(self) -> AssistantFinalizeResponse:
        if (
            self.report.session_id != self.session_id
            or self.report.session_revision != self.session_revision
        ):
            raise ValueError("종료 응답과 보고서의 상담 식별자가 일치하지 않습니다.")
        return self


class StoredCareerCoachReport(StrictModel):
    id: UUID
    user_id: UUID
    request_id: UUID
    report: CareerCoachReportV1
    created_at: AwareDatetime


class CareerCoachReportPersistenceResult(StrictModel):
    result: StoredCareerCoachReport
    created: bool


class CoachRouteDecision(StrictModel):
    intent: AssistantIntent
    response: str | None = Field(default=None, min_length=1, max_length=12000)
    schedule: ScheduleLookupArguments | None = None

    @model_validator(mode="after")
    def validate_route_shape(self) -> CoachRouteDecision:
        if self.intent in {"general", "clarification", "out_of_scope"}:
            if self.response is None or self.schedule is not None:
                raise ValueError("비도구 응답에는 답변만 필요합니다.")
        elif self.intent in {"schedule_lookup", "mixed"}:
            if self.response is not None or self.schedule is None:
                raise ValueError("일정 의도에는 허용된 일정 인자만 필요합니다.")
        elif self.response is not None or self.schedule is not None:
            raise ValueError("공고 추천 의도에는 추가 인자가 필요하지 않습니다.")
        return self


class CoachNarrativeDecision(StrictModel):
    coaching: str = Field(min_length=1, max_length=4000)


class CareerCoachEvidenceReference(StrictModel):
    turn_id: UUID
    category: Literal["strength", "improvement", "goal", "action", "context"]


class CareerCoachReportDraft(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    strengths: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(max_length=5)
    improvements: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(max_length=5)
    priority_actions: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(
        min_length=1,
        max_length=7,
    )
    evidence_refs: list[CareerCoachEvidenceReference] = Field(max_length=8)
    tool_call_ids: list[UUID] = Field(max_length=5)


def _validate_tool_result_counts(tool_results: list[ToolResult]) -> None:
    types = [result.type for result in tool_results]
    if len(types) != len(set(types)):
        raise ValueError("한 요청에서 같은 도구를 두 번 실행할 수 없습니다.")


def _contains_forbidden_report_key(value: object) -> bool:
    if isinstance(value, dict):
        return bool(REPORT_FORBIDDEN_KEYS.intersection(value)) or any(
            _contains_forbidden_report_key(child) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_report_key(child) for child in value)
    return False


def _contains_noncanonical_report_value(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_noncanonical_report_value(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_noncanonical_report_value(child) for child in value)
    if isinstance(value, float):
        return True
    return isinstance(value, str) and "\x00" in value
