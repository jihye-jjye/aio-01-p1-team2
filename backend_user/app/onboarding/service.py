from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.gemini.errors import GeminiInvalidResponseError
from app.onboarding.flow import OnboardingValidationError
from app.onboarding.models import (
    PROFILE_FIELDS,
    ConversationMessage,
    GeminiConversationDecision,
    OnboardingPayload,
    OnboardingResponse,
    OnboardingState,
    ProcessedOnboardingRequest,
    ProfileField,
)
from app.profiles.models import ProfileAssessment, ProfileOnboardingData, ProfileRecord


class OnboardingSessionNotFoundError(LookupError):
    pass


class OnboardingResultNotReadyError(RuntimeError):
    pass


class OnboardingAlreadyCompletedError(RuntimeError):
    pass


class IdempotencyKeyReusedError(RuntimeError):
    pass


class OnboardingRevisionConflictError(RuntimeError):
    pass


class OnboardingSessionStore(Protocol):
    async def get(self, *, user_id: UUID, session_id: UUID) -> OnboardingState | None: ...

    async def save(self, state: OnboardingState, *, ttl_seconds: int) -> None: ...

    async def get_start(self, *, user_id: UUID, request_id: UUID) -> OnboardingResponse | None: ...

    async def save_start(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        response: OnboardingResponse,
        ttl_seconds: int,
    ) -> None: ...

    async def save_started(
        self,
        *,
        state: OnboardingState,
        request_id: UUID,
        response: OnboardingResponse,
        ttl_seconds: int,
    ) -> None: ...


class OnboardingSessionLock(Protocol):
    def hold(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> AbstractAsyncContextManager[None]: ...


class NoopOnboardingSessionLock:
    @asynccontextmanager
    async def hold(self, *, user_id: UUID, session_id: UUID) -> AsyncIterator[None]:
        yield


class ProfileReadPort(Protocol):
    async def get_by_user_id(self, user_id: UUID) -> ProfileRecord | None: ...


class ProfileRepository(Protocol):
    async def save_onboarding(
        self,
        *,
        user_id: UUID,
        profile: ProfileOnboardingData,
        assessment: ProfileAssessment,
        request_id: UUID,
        draft_revision: int,
    ) -> ProfileRecord: ...


class ConversationPort(Protocol):
    async def converse(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        messages: Sequence[ConversationMessage],
        draft_profile: dict[str, Any],
        answered_fields: Sequence[ProfileField],
        missing_fields: Sequence[ProfileField],
        today: date,
        existing_profile: dict[str, Any] | None = None,
    ) -> GeminiConversationDecision: ...


class AssessmentPort(Protocol):
    async def assess(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        profile: ProfileOnboardingData,
    ) -> ProfileAssessment: ...


def request_fingerprint(
    *, text: str | None, action: str | None, expected_revision: int | None
) -> str:
    canonical = json.dumps(
        {
            "action": action,
            "expected_revision": expected_revision,
            "text": text,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def kst_date(value: datetime | None = None) -> date:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(ZoneInfo("Asia/Seoul")).date()


def _profile_record_to_draft(record: ProfileRecord) -> dict[str, Any]:
    return record.model_dump(mode="json", include=set(PROFILE_FIELDS))


class OnboardingService:
    def __init__(
        self,
        *,
        sessions: OnboardingSessionStore,
        profiles: ProfileRepository,
        conversation: ConversationPort,
        assessor: AssessmentPort,
        session_lock: OnboardingSessionLock | None = None,
        profile_reader: ProfileReadPort | None = None,
        session_id_provider: Callable[[], UUID] = uuid4,
        turn_id_provider: Callable[[], UUID] = uuid4,
        today_provider: Callable[[], date] = kst_date,
        session_ttl_seconds: int = 1800,
    ) -> None:
        self._sessions = sessions
        self._profiles = profiles
        self._conversation = conversation
        self._assessor = assessor
        self._session_lock = session_lock or NoopOnboardingSessionLock()
        self._profile_reader = profile_reader
        self._session_id_provider = session_id_provider
        self._turn_id_provider = turn_id_provider
        self._today_provider = today_provider
        self._session_ttl_seconds = session_ttl_seconds

    async def start(self, *, user_id: UUID, request_id: UUID) -> OnboardingResponse:
        async with self._session_lock.hold(user_id=user_id, session_id=request_id):
            return await self._start_locked(user_id=user_id, request_id=request_id)

    async def get_result(self, *, user_id: UUID, session_id: UUID) -> OnboardingResponse:
        async with self._session_lock.hold(user_id=user_id, session_id=session_id):
            state = await self._sessions.get(user_id=user_id, session_id=session_id)
            if state is None or state.user_id != user_id:
                raise OnboardingSessionNotFoundError("온보딩 세션을 찾을 수 없습니다.")
            if state.phase == "collecting":
                raise OnboardingResultNotReadyError("온보딩 결과가 아직 준비되지 않았습니다.")
            if state.phase == "completed":
                raise OnboardingAlreadyCompletedError("이미 완료된 온보딩 세션입니다.")
            assistant_message = next(
                (
                    message.text
                    for message in reversed(state.messages)
                    if message.role == "assistant"
                ),
                "온보딩 결과를 확인해주세요.",
            )
            return self._response(state, assistant_message)

    async def _start_locked(self, *, user_id: UUID, request_id: UUID) -> OnboardingResponse:
        cached = await self._sessions.get_start(user_id=user_id, request_id=request_id)
        if cached is not None:
            return cached

        session_id = self._session_id_provider()
        state = OnboardingState(user_id=user_id, session_id=session_id)

        existing_profile_record = None
        if self._profile_reader is not None:
            existing_profile_record = await self._profile_reader.get_by_user_id(user_id)

        if existing_profile_record is not None:
            profile_data = _profile_record_to_draft(existing_profile_record)
            state.draft_profile = profile_data
            state.answered_fields = list(PROFILE_FIELDS)
            state.missing_fields = []
            state.existing_profile = profile_data
            state.draft_revision = 1

        decision = await self._conversation.converse(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            messages=[],
            draft_profile=state.draft_profile,
            answered_fields=state.answered_fields,
            missing_fields=state.missing_fields,
            today=self._today_provider(),
            existing_profile=state.existing_profile,
        )
        if decision.field_updates:
            raise GeminiInvalidResponseError(
                "사용자 근거가 없는 시작 응답에 필드 값이 포함됐습니다."
            )
        state.messages.append(
            ConversationMessage(
                turn_id=self._turn_id_provider(),
                role="assistant",
                text=decision.assistant_message,
            )
        )
        response = self._response(state, decision.assistant_message)
        state.processed_requests[str(request_id)] = ProcessedOnboardingRequest(
            fingerprint=request_fingerprint(
                text=None, action="onboarding.start", expected_revision=None
            ),
            response=response,
        )
        await self._sessions.save_started(
            state=state,
            request_id=request_id,
            response=response,
            ttl_seconds=self._session_ttl_seconds,
        )
        return response

    async def handle(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        text: str | None = None,
        action: str | None = None,
        expected_revision: int | None = None,
    ) -> OnboardingResponse:
        if (text is None) == (action is None):
            raise OnboardingValidationError("text와 action 중 정확히 하나만 필요합니다.")
        if text is not None and (not text.strip() or len(text) > 4000):
            raise OnboardingValidationError("답변은 1자 이상 4,000자 이하여야 합니다.")
        fingerprint = request_fingerprint(
            text=text, action=action, expected_revision=expected_revision
        )
        async with self._session_lock.hold(user_id=user_id, session_id=session_id):
            state = await self._sessions.get(user_id=user_id, session_id=session_id)
            if state is None or state.user_id != user_id:
                raise OnboardingSessionNotFoundError("온보딩 세션을 찾을 수 없습니다.")
            cached = state.processed_requests.get(str(request_id))
            if cached is not None:
                if cached.fingerprint != fingerprint:
                    raise IdempotencyKeyReusedError("request_id가 다른 payload에 재사용됐습니다.")
                return cached.response
            if state.phase == "completed":
                raise OnboardingValidationError("이미 완료된 온보딩 세션입니다.")

            if text is not None:
                response, next_state = await self._handle_text(
                    state=state,
                    request_id=request_id,
                    text=text.strip(),
                )
            elif action == "onboarding.confirm":
                response, next_state = await self._confirm(
                    state=state,
                    request_id=request_id,
                    expected_revision=expected_revision,
                )
            elif action == "onboarding.restart":
                response, next_state = await self._restart(state=state, request_id=request_id)
            else:
                raise OnboardingValidationError("현재 단계에서 실행할 수 없는 action입니다.")

            next_state.processed_requests[str(request_id)] = ProcessedOnboardingRequest(
                fingerprint=fingerprint,
                response=response,
            )
            while len(next_state.processed_requests) > 64:
                next_state.processed_requests.pop(next(iter(next_state.processed_requests)))
            await self._sessions.save(next_state, ttl_seconds=self._session_ttl_seconds)
            return response

    async def confirm(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        expected_revision: int,
    ) -> OnboardingResponse:
        return await self.handle(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            action="onboarding.confirm",
            expected_revision=expected_revision,
        )

    async def _handle_text(
        self,
        *,
        state: OnboardingState,
        request_id: UUID,
        text: str,
    ) -> tuple[OnboardingResponse, OnboardingState]:
        if sum(message.role == "user" for message in state.messages) >= 12:
            raise OnboardingValidationError("온보딩 사용자 발화는 최대 12개까지 가능합니다.")
        next_state = state.model_copy(deep=True)
        user_message = ConversationMessage(
            turn_id=self._turn_id_provider(),
            role="user",
            text=text,
        )
        candidate_messages = [*next_state.messages, user_message]
        decision = await self._conversation.converse(
            user_id=state.user_id,
            session_id=state.session_id,
            request_id=request_id,
            messages=candidate_messages,
            draft_profile=next_state.draft_profile,
            answered_fields=next_state.answered_fields,
            missing_fields=next_state.missing_fields,
            today=self._today_provider(),
            existing_profile=next_state.existing_profile,
        )
        changed = self._apply_updates(
            state=next_state,
            decision=decision,
            messages=candidate_messages,
            latest_user_turn_id=user_message.turn_id,
        )
        next_state.messages = candidate_messages
        next_state.messages.append(
            ConversationMessage(
                turn_id=self._turn_id_provider(),
                role="assistant",
                text=decision.assistant_message,
            )
        )
        if changed:
            next_state.draft_revision += 1
        next_state.missing_fields = [
            field for field in PROFILE_FIELDS if field not in next_state.answered_fields
        ]

        if not next_state.missing_fields:
            next_state.phase = "review"
            if changed or next_state.assessment is None:
                profile = ProfileOnboardingData.model_validate(next_state.draft_profile)
                next_state.assessment = await self._assessor.assess(
                    user_id=state.user_id,
                    session_id=state.session_id,
                    request_id=request_id,
                    profile=profile,
                )
        else:
            next_state.phase = "collecting"
            next_state.assessment = None
        return self._response(next_state, decision.assistant_message), next_state

    def _apply_updates(
        self,
        *,
        state: OnboardingState,
        decision: GeminiConversationDecision,
        messages: Sequence[ConversationMessage],
        latest_user_turn_id: UUID,
    ) -> bool:
        message_by_id = {message.turn_id: message for message in messages}
        seen_fields: set[ProfileField] = set()
        changed = False
        for update in decision.field_updates:
            field = update.field
            if field in seen_fields:
                raise GeminiInvalidResponseError("동일 필드가 한 응답에서 중복 업데이트됐습니다.")
            seen_fields.add(field)
            for evidence in update.evidence:
                source = message_by_id.get(evidence.turn_id)
                if source is None or source.role != "user" or evidence.quote not in source.text:
                    raise GeminiInvalidResponseError(
                        "필드 업데이트의 사용자 인용 근거가 유효하지 않습니다."
                    )

            value = self._normalized_value(field, update.value)
            already_answered = field in state.answered_fields
            old_value = state.draft_profile.get(field)
            if (
                already_answered
                and old_value != value
                and not any(evidence.turn_id == latest_user_turn_id for evidence in update.evidence)
            ):
                raise GeminiInvalidResponseError(
                    "확정된 필드는 최신 사용자 수정 근거 없이 변경할 수 없습니다."
                )
            if not already_answered or old_value != value:
                state.draft_profile[field] = value
                if not already_answered:
                    state.answered_fields.append(field)
                changed = True
        return changed

    def _normalized_value(self, field: ProfileField, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise GeminiInvalidResponseError(f"{field} 값이 비어 있습니다.")
        if field == "skills":
            normalized: list[str] = []
            for item in value:
                clean = item.strip()
                if clean and clean not in normalized:
                    normalized.append(clean)
            if not normalized or len(normalized) > 20:
                raise GeminiInvalidResponseError(
                    "skills는 1~20개의 비어 있지 않은 값이어야 합니다."
                )
            return normalized
        if field == "target_date" and value <= self._today_provider():
            raise GeminiInvalidResponseError("target_date는 KST 기준 오늘 이후여야 합니다.")
        return value

    async def _confirm(
        self,
        *,
        state: OnboardingState,
        request_id: UUID,
        expected_revision: int | None,
    ) -> tuple[OnboardingResponse, OnboardingState]:
        if state.phase != "review" or state.assessment is None:
            raise OnboardingValidationError("현재 단계에서는 프로필을 확인할 수 없습니다.")
        if expected_revision is None or expected_revision != state.draft_revision:
            raise OnboardingRevisionConflictError(
                "표시된 프로필 revision과 현재 revision이 다릅니다."
            )
        profile = ProfileOnboardingData.model_validate(state.draft_profile)
        assessment = ProfileAssessment.model_validate(state.assessment)
        stored = await self._profiles.save_onboarding(
            user_id=state.user_id,
            profile=profile,
            assessment=assessment,
            request_id=request_id,
            draft_revision=state.draft_revision,
        )
        next_state = state.model_copy(deep=True)
        next_state.phase = "completed"
        return (
            self._response(
                next_state,
                "확인한 프로필과 준비도 평가를 저장했습니다.",
                stored_profile=stored.model_dump(mode="json"),
            ),
            next_state,
        )

    async def _restart(
        self, *, state: OnboardingState, request_id: UUID
    ) -> tuple[OnboardingResponse, OnboardingState]:
        decision = await self._conversation.converse(
            user_id=state.user_id,
            session_id=state.session_id,
            request_id=request_id,
            messages=[],
            draft_profile={},
            answered_fields=[],
            missing_fields=list(PROFILE_FIELDS),
            today=self._today_provider(),
            existing_profile=None,
        )
        if decision.field_updates:
            raise GeminiInvalidResponseError(
                "사용자 근거가 없는 재시작 응답에 필드 값이 포함됐습니다."
            )
        next_state = OnboardingState(user_id=state.user_id, session_id=state.session_id)
        next_state.processed_requests = dict(state.processed_requests)
        next_state.messages.append(
            ConversationMessage(
                turn_id=self._turn_id_provider(),
                role="assistant",
                text=decision.assistant_message,
            )
        )
        return self._response(next_state, decision.assistant_message), next_state

    @staticmethod
    def _response(
        state: OnboardingState,
        assistant_message: str,
        *,
        stored_profile: dict[str, Any] | None = None,
    ) -> OnboardingResponse:
        step = (
            "completed"
            if state.phase == "completed"
            else "review"
            if state.phase == "review"
            else "conversation"
        )
        assessment = (
            ProfileAssessment.model_validate(state.assessment) if state.assessment else None
        )
        return OnboardingResponse(
            session_id=state.session_id,
            step=step,
            assistant_message=assistant_message,
            choices=(["onboarding.confirm", "onboarding.restart"] if step == "review" else []),
            payload=OnboardingPayload(
                draft_revision=state.draft_revision,
                draft_profile=ProfileOnboardingData.model_validate(state.draft_profile).model_dump(
                    mode="json"
                )
                if not state.missing_fields
                else state.draft_profile,
                answered_fields=state.answered_fields,
                missing_fields=state.missing_fields,
                assessment=assessment,
                stored_profile=stored_profile,
                existing_profile=state.existing_profile,
            ),
            completed=step == "completed",
        )
