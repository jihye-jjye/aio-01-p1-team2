from __future__ import annotations

from typing import Any


class AssistantDomainError(RuntimeError):
    status_code = 500
    code = "ASSISTANT_DATA_INTEGRITY_ERROR"
    retryable = False
    default_message = "AI 취업 코치 데이터를 안전하게 처리할 수 없습니다."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.default_message)
        self.details = details or {}

    @property
    def safe_details(self) -> dict[str, Any]:
        return {}


class AssistantSessionExpiredError(AssistantDomainError):
    status_code = 409
    code = "ASSISTANT_SESSION_EXPIRED"
    default_message = "상담 세션이 없거나 만료되었습니다. 새 대화를 시작해주세요."


class AssistantSessionBusyError(AssistantDomainError):
    status_code = 409
    code = "ASSISTANT_SESSION_BUSY"
    retryable = True
    default_message = "이전 상담 요청을 처리 중입니다. 잠시 후 다시 시도해주세요."


class AssistantRevisionConflictError(AssistantDomainError):
    status_code = 409
    code = "ASSISTANT_REVISION_CONFLICT"
    default_message = "상담 revision이 최신 상태와 다릅니다."


class AssistantSessionLimitReachedError(AssistantDomainError):
    status_code = 409
    code = "ASSISTANT_SESSION_LIMIT_REACHED"
    default_message = "동시에 유지할 수 있는 상담 세션은 최대 6개입니다."


class IdempotencyKeyReusedError(AssistantDomainError):
    status_code = 409
    code = "IDEMPOTENCY_KEY_REUSED"
    default_message = "request_id가 다른 요청 payload에 이미 사용되었습니다."


class AssistantAlreadyFinalizedError(AssistantDomainError):
    status_code = 409
    code = "ASSISTANT_ALREADY_FINALIZED"
    default_message = "이미 종료된 상담 세션입니다."


class AssistantReportEmptyError(AssistantDomainError):
    status_code = 409
    code = "ASSISTANT_REPORT_EMPTY"
    default_message = "사용자 메시지가 없는 상담은 보고서로 종료할 수 없습니다."


class AssistantTurnLimitReachedError(AssistantDomainError):
    status_code = 422
    code = "ASSISTANT_TURN_LIMIT_REACHED"
    default_message = "한 상담에서 보낼 수 있는 사용자 메시지는 최대 20개입니다."


class AssistantTranscriptLimitReachedError(AssistantDomainError):
    status_code = 422
    code = "ASSISTANT_TRANSCRIPT_LIMIT_REACHED"
    default_message = "한 상담의 대화 텍스트는 최대 40,000자입니다."


class AssistantResponseTooLongError(AssistantDomainError):
    status_code = 502
    code = "ASSISTANT_RESPONSE_TOO_LONG"
    default_message = "AI 코치 응답이 허용 길이를 초과했습니다."


class AssistantDataIntegrityError(AssistantDomainError):
    pass
