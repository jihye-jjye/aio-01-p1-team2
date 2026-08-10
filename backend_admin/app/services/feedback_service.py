"""AI 응답 피드백의 소유권 확인 및 저장 Service."""

from __future__ import annotations

from uuid import UUID

from app.repositories.feedback_repository import (
    FeedbackRepository,
    FeedbackRepositoryError,
)
from app.repositories.log_repository import (
    LogRepository,
    LogRepositoryError,
)
from app.schemas.feedback_schema import FeedbackCreate, FeedbackResponse
from app.services.exceptions import (
    FeedbackStorageError,
    LogAccessDeniedError,
    LogNotFoundError,
)


class FeedbackService:
    """사용자가 본인의 AI 로그에만 피드백을 남기도록 보장한다."""

    def __init__(
        self,
        feedback_repository: FeedbackRepository | None = None,
        log_repository: LogRepository | None = None,
    ) -> None:
        self.feedback_repository = (
            feedback_repository or FeedbackRepository()
        )
        self.log_repository = log_repository or LogRepository()

    def _ensure_log_owner(self, log_id: UUID, user_id: UUID) -> None:
        try:
            log = self.log_repository.get_log_by_id(log_id)
        except LogRepositoryError as exc:
            raise FeedbackStorageError(
                "AI 로그를 확인할 수 없습니다."
            ) from exc

        if log is None:
            raise LogNotFoundError("로그를 찾을 수 없습니다.")

        log_user_id = log.get("user_id")
        if log_user_id is None or str(log_user_id) != str(user_id):
            raise LogAccessDeniedError(
                "다른 사용자의 로그에는 접근할 수 없습니다."
            )

    def get_feedback(
        self,
        *,
        log_id: UUID,
        user_id: UUID,
    ) -> FeedbackResponse | None:
        """소유권을 확인한 뒤 현재 사용자의 피드백을 반환한다."""

        self._ensure_log_owner(log_id, user_id)

        try:
            row = self.feedback_repository.get_feedback(log_id, user_id)
        except FeedbackRepositoryError as exc:
            raise FeedbackStorageError(
                "피드백을 조회할 수 없습니다."
            ) from exc

        if row is None:
            return None

        return FeedbackResponse.model_validate(row)

    def submit_feedback(
        self,
        *,
        log_id: UUID,
        user_id: UUID,
        feedback: FeedbackCreate,
    ) -> FeedbackResponse:
        """소유권을 확인한 뒤 피드백을 생성하거나 갱신한다."""

        self._ensure_log_owner(log_id, user_id)

        try:
            row = self.feedback_repository.upsert_feedback(
                log_id=log_id,
                user_id=user_id,
                feedback=feedback,
            )
        except FeedbackRepositoryError as exc:
            raise FeedbackStorageError(
                "피드백을 저장할 수 없습니다."
            ) from exc

        return FeedbackResponse.model_validate(row)
