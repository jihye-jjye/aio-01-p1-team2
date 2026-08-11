from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from redis.exceptions import RedisError

from app.api.errors import ProfileNotFoundError
from app.coach.errors import (
    AssistantAlreadyFinalizedError,
    AssistantDataIntegrityError,
    AssistantDomainError,
    AssistantReportEmptyError,
    AssistantResponseTooLongError,
    AssistantRevisionConflictError,
    AssistantSessionExpiredError,
    AssistantTranscriptLimitReachedError,
    AssistantTurnLimitReachedError,
    IdempotencyKeyReusedError,
)
from app.coach.models import (
    AssistantConversationTurn,
    AssistantFinalizeResponse,
    AssistantMessageResponse,
    AssistantProfileSnapshot,
    AssistantSessionCreateResponse,
    AssistantSessionState,
    AssistantSessionTombstone,
    AssistantStyle,
    CareerCoachAssessmentSnapshot,
    CareerCoachProfileSnapshot,
    CareerCoachReportDraft,
    CareerCoachReportEngine,
    CareerCoachReportEvidence,
    CareerCoachReportPersistenceResult,
    CareerCoachReportToolSnapshot,
    CareerCoachReportV1,
    CoachingResult,
    CoachNarrativeDecision,
    CoachRouteDecision,
    JobFact,
    JobRecommendationToolResult,
    ProcessedAssistantRequest,
    ScheduleLookupToolResult,
    StoredCareerCoachReport,
    ToolResult,
)
from app.coach.presentation import (
    coaching_fallback,
    render_job_recommendation,
    render_schedule_lookup,
)
from app.coach.schedule_ranges import resolve_schedule_range
from app.coach.stores import CreateSessionStoreResult
from app.gemini.errors import GeminiError, GeminiInvalidResponseError
from app.profiles.models import ProfileOnboardingData, ProfileRecord
from app.saved_jobs.models import SavedJobRecommendationView

KST = ZoneInfo("Asia/Seoul")
SESSION_TTL = timedelta(hours=24)
MAX_TURNS = 20
MAX_TRANSCRIPT_CHARS = 40_000
MAX_ASSISTANT_CHARS = 12_000
_INITIAL_MESSAGES = {
    "friendly": "반가워요. 지금 가장 답답한 취업·커리어 고민부터 편하게 이야기해주세요.",
    "direct": (
        "고민만 반복하면 준비는 한 발도 나아가지 않습니다. 지금 가장 부족하다고 느끼는 "
        "취업 준비부터 솔직하게 말씀해주세요."
    ),
}
_SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
        r"password|secret)\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)\bpostgres(?:ql)?://[^:\s]+:[^@\s]+@[^\s]+"),
)


class SessionStorePort(Protocol):
    async def load_request(
        self, *, user_id: UUID, request_id: UUID
    ) -> ProcessedAssistantRequest | None: ...

    async def create_session(
        self,
        *,
        state: AssistantSessionState,
        request: ProcessedAssistantRequest,
        max_active_sessions: int = 3,
    ) -> CreateSessionStoreResult: ...

    async def load(
        self, *, user_id: UUID, session_id: UUID
    ) -> AssistantSessionState | AssistantSessionTombstone | None: ...

    async def commit_turn(
        self,
        *,
        state: AssistantSessionState,
        expected_revision: int,
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest: ...

    async def replace_with_tombstone(
        self,
        tombstone: AssistantSessionTombstone,
        *,
        expected_revision: int,
        request: ProcessedAssistantRequest,
    ) -> ProcessedAssistantRequest: ...


class SessionLocksPort(Protocol):
    def hold_tenant(self, *, user_id: UUID) -> Any: ...

    def hold_session(self, *, user_id: UUID, session_id: UUID) -> Any: ...


class ProfileReaderPort(Protocol):
    async def get_by_user_id(self, user_id: UUID) -> ProfileRecord | None: ...


class CoachPort(Protocol):
    async def route(
        self,
        *,
        user_id: UUID,
        state: AssistantSessionState,
        text: str,
        reference_at: datetime,
    ) -> CoachRouteDecision: ...

    async def coach(
        self,
        *,
        user_id: UUID,
        style: AssistantStyle,
        question: str,
        tool_results: list[ToolResult],
    ) -> CoachNarrativeDecision: ...

    async def generate_report(
        self,
        *,
        user_id: UUID,
        style: AssistantStyle,
        redacted_turns: list[dict[str, str]],
        tool_snapshots: list[dict[str, Any]],
    ) -> CareerCoachReportDraft: ...


class SavedJobsPort(Protocol):
    async def recommend_from_snapshot(
        self,
        *,
        user_id: UUID,
        profile: ProfileOnboardingData,
        use_llm: bool = True,
        today: date | None = None,
    ) -> SavedJobRecommendationView | None: ...


class SchedulePort(Protocol):
    async def lookup_schedule(
        self,
        *,
        user_id: UUID,
        range_start: Any,
        range_end: Any,
        observed_at: datetime,
    ) -> ScheduleLookupToolResult: ...


class ReportRepositoryPort(Protocol):
    async def find_by_request(
        self, *, user_id: UUID, request_id: UUID
    ) -> StoredCareerCoachReport | str | None: ...

    async def find_by_session(
        self, *, user_id: UUID, session_id: UUID
    ) -> StoredCareerCoachReport | None: ...

    async def persist(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        report: CareerCoachReportV1,
    ) -> CareerCoachReportPersistenceResult: ...


@dataclass(frozen=True, slots=True)
class FinalizeServiceResult:
    response: AssistantFinalizeResponse
    created: bool


class CareerCoachService:
    def __init__(
        self,
        *,
        sessions: SessionStorePort,
        locks: SessionLocksPort,
        profiles: ProfileReaderPort,
        coach: CoachPort,
        saved_jobs: SavedJobsPort,
        schedules: SchedulePort,
        reports: ReportRepositoryPort,
        now_provider: Callable[[], datetime] | None = None,
        uuid_provider: Callable[[], UUID] | None = None,
    ) -> None:
        self._sessions = sessions
        self._locks = locks
        self._profiles = profiles
        self._coach = coach
        self._saved_jobs = saved_jobs
        self._schedules = schedules
        self._reports = reports
        self._now = now_provider or (lambda: datetime.now(UTC))
        self._uuid = uuid_provider or uuid4

    async def create_session(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
    ) -> AssistantSessionCreateResponse:
        fingerprint = _fingerprint({"operation": "create"})
        async with self._locks.hold_tenant(user_id=user_id):
            existing = await self._sessions.load_request(
                user_id=user_id,
                request_id=request_id,
            )
            if existing is not None:
                _validate_replay(existing, fingerprint=fingerprint, operation="create")
                return AssistantSessionCreateResponse.model_validate(existing.response)

            profile = await self._profiles.get_by_user_id(user_id)
            snapshot = _profile_snapshot(profile)
            now = _aware_now(self._now()).astimezone(UTC)
            now = now.replace(microsecond=(now.microsecond // 1000) * 1000)
            expires_at = now + SESSION_TTL
            session_id = self._uuid()
            response = AssistantSessionCreateResponse(
                session_id=session_id,
                assistant_style=snapshot.profile.assistant_style,
                assistant_message=_INITIAL_MESSAGES[snapshot.profile.assistant_style],
                expires_at=expires_at,
            )
            request = ProcessedAssistantRequest(
                request_id=request_id,
                fingerprint=fingerprint,
                operation="create",
                session_id=session_id,
                response=response.model_dump(mode="json"),
                expires_at=expires_at,
            )
            state = AssistantSessionState(
                user_id=user_id,
                session_id=session_id,
                created_at=now,
                expires_at=expires_at,
                profile_snapshot=snapshot,
            )
            stored = await self._sessions.create_session(
                state=state,
                request=request,
                max_active_sessions=3,
            )
            if not stored.created:
                if stored.replay is None:
                    raise AssistantDataIntegrityError()
                _validate_replay(stored.replay, fingerprint=fingerprint, operation="create")
                return AssistantSessionCreateResponse.model_validate(stored.replay.response)
            return response

    async def send_message(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        expected_revision: int,
        text: str,
    ) -> AssistantMessageResponse:
        fingerprint = _fingerprint(
            {
                "operation": "message",
                "session_id": str(session_id),
                "expected_revision": expected_revision,
                "text": text,
            }
        )
        async with (
            self._locks.hold_tenant(user_id=user_id),
            self._locks.hold_session(user_id=user_id, session_id=session_id),
        ):
            existing = await self._sessions.load_request(
                user_id=user_id,
                request_id=request_id,
            )
            if existing is not None:
                _validate_replay(
                    existing,
                    fingerprint=fingerprint,
                    operation="message",
                    session_id=session_id,
                )
                return AssistantMessageResponse.model_validate(existing.response)

            finalized = await self._reports.find_by_session(
                user_id=user_id,
                session_id=session_id,
            )
            if finalized is not None:
                raise AssistantAlreadyFinalizedError()

            state = await self._active_state(user_id=user_id, session_id=session_id)
            if state.revision != expected_revision:
                raise AssistantRevisionConflictError()
            if len(state.turns) >= MAX_TURNS:
                raise AssistantTurnLimitReachedError()
            if state.transcript_chars + len(text) > MAX_TRANSCRIPT_CHARS:
                raise AssistantTranscriptLimitReachedError()

            route_reference_at = _aware_now(self._now())
            route = await self._coach.route(
                user_id=user_id,
                state=state,
                text=text,
                reference_at=route_reference_at,
            )
            observed_at = _aware_now(self._now())
            tool_results, new_snapshots = await self._execute_tools(
                user_id=user_id,
                state=state,
                route=route,
                observed_at=observed_at,
            )
            style = state.profile_snapshot.profile.assistant_style
            if tool_results:
                try:
                    narrative = await self._coach.coach(
                        user_id=user_id,
                        style=style,
                        question=text,
                        tool_results=tool_results,
                    )
                    coaching = CoachingResult(
                        style=style,
                        message=narrative.coaching,
                        source="llm",
                    )
                except GeminiError:
                    coaching = CoachingResult(
                        style=style,
                        message=coaching_fallback(style=style, has_tools=True),
                        source="deterministic_fallback",
                    )
                fact_blocks = [_render_tool_result(result) for result in tool_results]
                assistant_message = "\n\n".join([*fact_blocks, coaching.message])
            else:
                if route.response is None:
                    raise AssistantDataIntegrityError()
                coaching = CoachingResult(
                    style=style,
                    message=route.response,
                    source="llm",
                )
                assistant_message = route.response

            if len(assistant_message) > MAX_ASSISTANT_CHARS:
                raise AssistantResponseTooLongError()
            turn = AssistantConversationTurn(
                turn_id=self._uuid(),
                request_id=request_id,
                user_text=text,
                assistant_message=assistant_message,
                intent=route.intent,
                tool_results=tool_results,
                coaching=coaching,
                created_at=observed_at,
            )
            transcript_chars = state.transcript_chars + len(text) + len(assistant_message)
            if transcript_chars > MAX_TRANSCRIPT_CHARS:
                raise AssistantTranscriptLimitReachedError()
            response = AssistantMessageResponse(
                session_id=session_id,
                revision=expected_revision + 1,
                intent=route.intent,
                assistant_message=assistant_message,
                tool_results=tool_results,
                coaching=coaching,
                expires_at=state.expires_at,
            )
            request = ProcessedAssistantRequest(
                request_id=request_id,
                fingerprint=fingerprint,
                operation="message",
                session_id=session_id,
                response=response.model_dump(mode="json"),
                expires_at=state.expires_at,
            )
            try:
                next_state = AssistantSessionState.model_validate(
                    {
                        **state.model_dump(mode="python"),
                        "revision": expected_revision + 1,
                        "turns": [*state.turns, turn],
                        "transcript_chars": transcript_chars,
                        "tool_snapshots": [*state.tool_snapshots, *new_snapshots],
                    }
                )
            except ValidationError as exc:
                raise AssistantDataIntegrityError() from exc
            winner = await self._sessions.commit_turn(
                state=next_state,
                expected_revision=expected_revision,
                request=request,
            )
            return AssistantMessageResponse.model_validate(winner.response)

    async def finalize_session(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        expected_revision: int,
    ) -> FinalizeServiceResult:
        fingerprint = _fingerprint(
            {
                "operation": "finalize",
                "session_id": str(session_id),
                "expected_revision": expected_revision,
            }
        )
        durable = await self._durable_replay(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            expected_revision=expected_revision,
        )
        if durable is not None:
            return durable

        async with (
            self._locks.hold_tenant(user_id=user_id),
            self._locks.hold_session(user_id=user_id, session_id=session_id),
        ):
            durable = await self._durable_replay(
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                expected_revision=expected_revision,
            )
            if durable is not None:
                return durable
            existing = await self._sessions.load_request(
                user_id=user_id,
                request_id=request_id,
            )
            if existing is not None:
                _validate_replay(
                    existing,
                    fingerprint=fingerprint,
                    operation="finalize",
                    session_id=session_id,
                )
                raise AssistantDataIntegrityError()
            state = await self._active_state(user_id=user_id, session_id=session_id)
            if state.revision != expected_revision:
                raise AssistantRevisionConflictError()
            if not state.turns:
                raise AssistantReportEmptyError()

            finalized_at = _aware_now(self._now())
            redacted_turns = []
            redacted_by_id: dict[UUID, tuple[str, bool]] = {}
            for turn in state.turns:
                redacted, changed = _redact(turn.user_text)
                redacted_by_id[turn.turn_id] = (redacted, changed)
                redacted_turns.append({"turn_id": str(turn.turn_id), "text": redacted})
            tool_payload = [snapshot.model_dump(mode="json") for snapshot in state.tool_snapshots]
            draft = await self._coach.generate_report(
                user_id=user_id,
                style=state.profile_snapshot.profile.assistant_style,
                redacted_turns=redacted_turns,
                tool_snapshots=tool_payload,
            )
            try:
                report = _build_report(
                    state=state,
                    finalized_at=finalized_at,
                    draft=draft,
                    redacted_by_id=redacted_by_id,
                )
            except ValidationError as exc:
                raise AssistantDataIntegrityError() from exc
            latest_state = await self._active_state(
                user_id=user_id,
                session_id=session_id,
            )
            if _hash(latest_state.model_dump(mode="json")) != _hash(state.model_dump(mode="json")):
                raise AssistantRevisionConflictError()
            persistence = await self._reports.persist(
                user_id=user_id,
                request_id=request_id,
                report=report,
            )
            response = _finalize_response(persistence.result)
            request = ProcessedAssistantRequest(
                request_id=request_id,
                fingerprint=fingerprint,
                operation="finalize",
                session_id=session_id,
                response=response.model_dump(mode="json"),
                expires_at=state.expires_at,
            )
            tombstone = AssistantSessionTombstone(
                user_id=user_id,
                session_id=session_id,
                session_revision=persistence.result.report.session_revision,
                report_id=persistence.result.id,
                created_at=state.created_at,
                finalized_at=finalized_at,
                expires_at=state.expires_at,
            )
            try:
                await self._sessions.replace_with_tombstone(
                    tombstone,
                    expected_revision=expected_revision,
                    request=request,
                )
            except (RedisError, AssistantDomainError):
                pass
            return FinalizeServiceResult(
                response=response,
                created=persistence.created,
            )

    async def _active_state(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> AssistantSessionState:
        state = await self._sessions.load(user_id=user_id, session_id=session_id)
        if state is None:
            raise AssistantSessionExpiredError()
        if isinstance(state, AssistantSessionTombstone):
            raise AssistantAlreadyFinalizedError()
        return state

    async def _execute_tools(
        self,
        *,
        user_id: UUID,
        state: AssistantSessionState,
        route: CoachRouteDecision,
        observed_at: datetime,
    ) -> tuple[list[ToolResult], list[CareerCoachReportToolSnapshot]]:
        results: list[ToolResult] = []
        snapshots: list[CareerCoachReportToolSnapshot] = []
        if route.intent in {"job_recommendation", "mixed"}:
            recommendation = await self._saved_jobs.recommend_from_snapshot(
                user_id=user_id,
                profile=state.profile_snapshot.profile,
                use_llm=False,
                today=observed_at.astimezone(KST).date(),
            )
            try:
                result, snapshot = self._job_result(
                    recommendation,
                    observed_at=observed_at,
                )
            except ValidationError as exc:
                raise AssistantDataIntegrityError() from exc
            results.append(result)
            snapshots.append(snapshot)
        if route.intent in {"schedule_lookup", "mixed"}:
            if route.schedule is None:
                raise AssistantDataIntegrityError()
            resolved = resolve_schedule_range(route.schedule, reference_at=observed_at)
            result = await self._schedules.lookup_schedule(
                user_id=user_id,
                range_start=resolved.start_on,
                range_end=resolved.end_on,
                observed_at=observed_at,
            )
            results.append(result)
            snapshots.append(_tool_snapshot(self._uuid(), result))
        return results, snapshots

    def _job_result(
        self,
        recommendation: SavedJobRecommendationView | None,
        *,
        observed_at: datetime,
    ) -> tuple[JobRecommendationToolResult, CareerCoachReportToolSnapshot]:
        if recommendation is None:
            result = JobRecommendationToolResult(
                status="no_eligible_jobs",
                observed_at=observed_at,
            )
            return result, _tool_snapshot(self._uuid(), result)
        job = recommendation.job
        result = JobRecommendationToolResult(
            status="found",
            observed_at=observed_at,
            job=JobFact(
                id=job.id,
                company_name=job.company_name,
                job_title=job.job_title,
                source_url=job.source_url,
                deadline=job.deadline,
                created_at=job.created_at,
                updated_at=job.updated_at,
            ),
            match_score=recommendation.match_score,
            matched_terms=recommendation.matched_terms,
            reason=recommendation.reason,
            recommendation_source=recommendation.recommendation_source,
        )
        snapshot = _tool_snapshot(
            self._uuid(),
            result,
            extra_facts={
                "posting_hash": hashlib.sha256(job.posting_text.encode("utf-8")).hexdigest()
            },
        )
        return result, snapshot

    async def _durable_replay(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        expected_revision: int,
    ) -> FinalizeServiceResult | None:
        request_result = await self._reports.find_by_request(
            user_id=user_id,
            request_id=request_id,
        )
        if isinstance(request_result, str):
            raise IdempotencyKeyReusedError()
        if request_result is not None:
            if (
                request_result.report.session_id != session_id
                or request_result.report.session_revision != expected_revision
            ):
                raise IdempotencyKeyReusedError()
            return FinalizeServiceResult(
                response=_finalize_response(request_result),
                created=False,
            )
        session_result = await self._reports.find_by_session(
            user_id=user_id,
            session_id=session_id,
        )
        if session_result is None:
            return None
        return FinalizeServiceResult(
            response=_finalize_response(session_result),
            created=False,
        )


def _profile_snapshot(profile: ProfileRecord | None) -> AssistantProfileSnapshot:
    if (
        profile is None
        or profile.onboarding_completed_at is None
        or profile.assessment_result_id is None
        or profile.snapshot_hash is None
        or profile.assessment_score is None
        or profile.assessment_level is None
        or profile.assessment_summary is None
        or profile.assessment_version is None
    ):
        raise ProfileNotFoundError
    return AssistantProfileSnapshot(
        profile=CareerCoachProfileSnapshot.model_validate(
            {
                field_name: getattr(profile, field_name)
                for field_name in ProfileOnboardingData.model_fields
            }
        ),
        assessment_score=profile.assessment_score,
        assessment_level=profile.assessment_level,
        assessment_summary=profile.assessment_summary,
        assessment_version=profile.assessment_version,
        assessment_result_id=profile.assessment_result_id,
        snapshot_hash=profile.snapshot_hash,
    )


def _render_tool_result(result: ToolResult) -> str:
    if isinstance(result, JobRecommendationToolResult):
        return render_job_recommendation(result)
    return render_schedule_lookup(result)


def _tool_snapshot(
    tool_call_id: UUID,
    result: ToolResult,
    *,
    extra_facts: dict[str, Any] | None = None,
) -> CareerCoachReportToolSnapshot:
    payload = result.model_dump(mode="json")
    payload.pop("type", None)
    payload.pop("status", None)
    payload.pop("observed_at", None)
    facts = {**payload, **(extra_facts or {})}
    compact = {
        "tool_call_id": str(tool_call_id),
        "type": result.type,
        "observed_at": result.observed_at.isoformat(),
        "status": result.status,
        "facts": facts,
    }
    return CareerCoachReportToolSnapshot(
        **compact,
        snapshot_hash=_hash(compact),
    )


def _build_report(
    *,
    state: AssistantSessionState,
    finalized_at: datetime,
    draft: CareerCoachReportDraft,
    redacted_by_id: dict[UUID, tuple[str, bool]],
) -> CareerCoachReportV1:
    turn_by_id = {turn.turn_id: turn for turn in state.turns}
    evidence: list[CareerCoachReportEvidence] = []
    seen_turns: set[UUID] = set()
    for reference in draft.evidence_refs:
        turn = turn_by_id.get(reference.turn_id)
        redacted = redacted_by_id.get(reference.turn_id)
        if turn is None or redacted is None:
            raise GeminiInvalidResponseError("보고서가 허용되지 않은 사용자 turn을 참조했습니다.")
        if reference.turn_id in seen_turns:
            continue
        seen_turns.add(reference.turn_id)
        redacted_text, changed = redacted
        evidence.append(
            CareerCoachReportEvidence(
                turn_id=turn.turn_id,
                quote=redacted_text[:200],
                category=reference.category,
                redacted=changed,
            )
        )

    snapshots_by_id = {snapshot.tool_call_id: snapshot for snapshot in state.tool_snapshots}
    selected: list[CareerCoachReportToolSnapshot] = []
    seen_tools: set[UUID] = set()
    for tool_call_id in draft.tool_call_ids:
        snapshot = snapshots_by_id.get(tool_call_id)
        if snapshot is None:
            raise GeminiInvalidResponseError("보고서가 허용되지 않은 tool call을 참조했습니다.")
        if tool_call_id not in seen_tools:
            selected.append(snapshot)
            seen_tools.add(tool_call_id)
    excluded = [
        snapshot for snapshot in state.tool_snapshots if snapshot.tool_call_id not in seen_tools
    ]
    excluded_hash = (
        _hash([snapshot.model_dump(mode="json") for snapshot in excluded]) if excluded else None
    )
    base = {
        "schema_version": "career-coach-report-v1",
        "status": "completed",
        "session_id": state.session_id,
        "session_revision": state.revision,
        "started_at_kst": state.created_at.astimezone(KST),
        "finalized_at_kst": finalized_at.astimezone(KST),
        "user_turn_count": len(state.turns),
        "profile_snapshot": state.profile_snapshot.profile,
        "assessment_snapshot": CareerCoachAssessmentSnapshot(
            score=state.profile_snapshot.assessment_score,
            level=state.profile_snapshot.assessment_level,
            summary=state.profile_snapshot.assessment_summary,
            version=state.profile_snapshot.assessment_version,
        ),
        "profile_hash": state.profile_snapshot.snapshot_hash,
        "assessment_result_id": state.profile_snapshot.assessment_result_id,
        "assistant_style": state.profile_snapshot.profile.assistant_style,
        "summary": _redact(draft.summary)[0],
        "strengths": [_redact(value)[0] for value in draft.strengths],
        "improvements": [_redact(value)[0] for value in draft.improvements],
        "priority_actions": [_redact(value)[0] for value in draft.priority_actions],
        "evidence": evidence,
        "tool_snapshots": selected,
        "excluded_tool_call_count": len(excluded),
        "excluded_tool_calls_hash": excluded_hash,
        "engine": CareerCoachReportEngine(),
        "redaction_version": "career-coach-redaction-v1",
        "source_session_hash": _hash(state.model_dump(mode="json")),
    }
    report_hash = _hash(base)
    return CareerCoachReportV1.model_validate({**base, "report_hash": report_hash})


def _finalize_response(stored: StoredCareerCoachReport) -> AssistantFinalizeResponse:
    return AssistantFinalizeResponse(
        ai_result_id=stored.id,
        session_id=stored.report.session_id,
        session_revision=stored.report.session_revision,
        report=stored.report,
        created_at=stored.created_at,
    )


def _redact(value: str) -> tuple[str, bool]:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted, redacted != value


def _fingerprint(payload: object) -> str:
    return _hash(payload)


def _hash(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_replay(
    request: ProcessedAssistantRequest,
    *,
    fingerprint: str,
    operation: str,
    session_id: UUID | None = None,
) -> None:
    if request.fingerprint != fingerprint or request.operation != operation:
        raise IdempotencyKeyReusedError()
    if session_id is not None and request.session_id != session_id:
        raise IdempotencyKeyReusedError()


def _aware_now(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AssistantDataIntegrityError()
    return value
