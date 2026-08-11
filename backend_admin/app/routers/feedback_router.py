"""사용자 AI 응답 피드백 API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, get_current_user
from app.schemas.feedback_schema import FeedbackCreate, FeedbackResponse
from app.services.exceptions import (
    FeedbackStorageError,
    LogAccessDeniedError,
    LogNotFoundError,
)
from app.services.feedback_service import FeedbackService


feedback_router = APIRouter(
    prefix="/api/v1/logs",
    tags=["Feedback"],
)
feedback_service = FeedbackService()


def _raise_feedback_http_error(exc: Exception) -> None:
    if isinstance(exc, (LogNotFoundError, LogAccessDeniedError)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="로그를 찾을 수 없습니다.",
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@feedback_router.get(
    "/{log_id}/feedback",
    response_model=FeedbackResponse | None,
    summary="내 AI 응답 피드백 조회",
)
def get_feedback(
    log_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> FeedbackResponse | None:
    try:
        return feedback_service.get_feedback(
            log_id=log_id,
            user_id=current_user.id,
        )
    except (
        LogNotFoundError,
        LogAccessDeniedError,
        FeedbackStorageError,
    ) as exc:
        _raise_feedback_http_error(exc)


@feedback_router.post(
    "/{log_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="AI 응답 피드백 생성 또는 수정",
)
def submit_feedback(
    log_id: UUID,
    payload: FeedbackCreate,
    current_user: CurrentUser = Depends(get_current_user),
) -> FeedbackResponse:
    try:
        return feedback_service.submit_feedback(
            log_id=log_id,
            user_id=current_user.id,
            feedback=payload,
        )
    except (
        LogNotFoundError,
        LogAccessDeniedError,
        FeedbackStorageError,
    ) as exc:
        _raise_feedback_http_error(exc)
