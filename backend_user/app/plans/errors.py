from __future__ import annotations

from typing import Any


class PlanDomainError(RuntimeError):
    status_code = 500
    code = "PLAN_DATA_INTEGRITY_ERROR"
    retryable = False
    default_message = "계획 데이터를 안전하게 처리할 수 없습니다."

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message or self.default_message)
        self.details = details or {}

    @property
    def safe_details(self) -> dict[str, Any]:
        return {}


class PlanTargetDateExpiredError(PlanDomainError):
    status_code = 422
    code = "PLAN_TARGET_DATE_EXPIRED"
    default_message = "프로필 목표일이 이미 지났습니다."


class PlanHorizonTooLongError(PlanDomainError):
    status_code = 422
    code = "PLAN_HORIZON_TOO_LONG"
    default_message = "프로필 계획 기간은 최대 365일입니다."


class PlanProposalAlreadyPendingError(PlanDomainError):
    status_code = 409
    code = "PLAN_PROPOSAL_ALREADY_PENDING"
    default_message = "검토 중인 프로필 계획 제안이 이미 있습니다."


class ActivePlanExistsError(PlanDomainError):
    status_code = 409
    code = "ACTIVE_PLAN_EXISTS"
    default_message = "진행 중인 계획이 이미 있습니다."


class PlanProfileChangedError(PlanDomainError):
    status_code = 409
    code = "PLAN_PROFILE_CHANGED"
    default_message = "계획 생성 후 프로필이 변경되었습니다. 새 요청으로 다시 시도해주세요."


class PlanProposalStaleError(PlanDomainError):
    status_code = 409
    code = "PLAN_PROPOSAL_STALE"
    default_message = "계획 생성 날짜가 지나 새 요청이 필요합니다."


class PlanGenerationInProgressError(PlanDomainError):
    status_code = 409
    code = "PLAN_GENERATION_IN_PROGRESS"
    retryable = True
    default_message = "같은 계획 요청을 처리 중입니다. 잠시 후 다시 시도해주세요."


class PlanGenerationTimeoutError(PlanDomainError):
    status_code = 504
    code = "PLAN_GENERATION_TIMEOUT"
    retryable = True
    default_message = "계획 생성 시간이 초과되었습니다. 같은 요청으로 다시 시도해주세요."


class PlanCheckpointExpiredError(PlanGenerationTimeoutError):
    """Private typed signal using the fixed public generation-timeout contract."""


class IdempotencyKeyReusedError(PlanDomainError):
    status_code = 409
    code = "IDEMPOTENCY_KEY_REUSED"
    default_message = "request_id가 다른 작업에 이미 사용되었습니다."


class PlanProposalNotFoundError(PlanDomainError):
    status_code = 404
    code = "PLAN_PROPOSAL_NOT_FOUND"
    default_message = "계획 제안을 찾을 수 없습니다."


class PlanSavedJobNotFoundError(PlanDomainError):
    status_code = 404
    code = "SAVED_JOB_NOT_FOUND"
    default_message = "선택한 채용 공고를 찾을 수 없습니다."


class PlanSavedJobExpiredError(PlanDomainError):
    status_code = 422
    code = "SAVED_JOB_EXPIRED"
    default_message = "선택한 채용 공고의 마감일이 지났습니다."


class PlanProposalNotPendingError(PlanDomainError):
    status_code = 409
    code = "PLAN_PROPOSAL_NOT_PENDING"
    default_message = "계획 제안이 대기 상태가 아닙니다."


class PlanNotFoundError(PlanDomainError):
    status_code = 404
    code = "PLAN_NOT_FOUND"
    default_message = "계획을 찾을 수 없습니다."


class PlanTaskNotFoundError(PlanDomainError):
    status_code = 404
    code = "PLAN_TASK_NOT_FOUND"
    default_message = "계획 과제를 찾을 수 없습니다."


class TodayQuestNotFoundError(PlanDomainError):
    status_code = 404
    code = "TODAY_QUEST_NOT_FOUND"
    default_message = "오늘 퀘스트를 찾을 수 없습니다."


class PlanNotActiveError(PlanDomainError):
    status_code = 409
    code = "PLAN_NOT_ACTIVE"
    default_message = "진행 중인 계획만 변경할 수 있습니다."


class PlanNotCompleteError(PlanDomainError):
    status_code = 409
    code = "PLAN_NOT_COMPLETE"
    default_message = "모든 계획 과제를 완료해야 계획을 종료할 수 있습니다."

    @property
    def safe_details(self) -> dict[str, Any]:
        completed = self.details.get("completed_task_count")
        total = self.details.get("total_task_count")
        if (
            isinstance(completed, int)
            and not isinstance(completed, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and 0 <= completed <= total
        ):
            return {
                "completed_task_count": completed,
                "total_task_count": total,
            }
        return {}


class PlanWindowOutOfRangeError(PlanDomainError):
    status_code = 422
    code = "PLAN_WINDOW_OUT_OF_RANGE"
    default_message = "조회 시작일이 계획 기간을 벗어났습니다."


class PlanDataIntegrityError(PlanDomainError):
    pass
