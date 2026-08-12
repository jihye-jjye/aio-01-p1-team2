from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_notification_service
from app.api.errors import APIErrorEnvelope
from app.auth.models import CurrentUser
from app.notifications.models import NotificationFeed, NotificationView
from app.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

COMMON_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    500: {
        "model": APIErrorEnvelope,
        "description": "`NOTIFICATION_DATA_INTEGRITY_ERROR`: 저장된 알림 payload 검증 실패",
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}


@router.post(
    "/login-feed",
    response_model=NotificationFeed,
    summary="로그인 로드맵 알림 동기화 및 조회",
    description=(
        "KST 오늘부터 7일 동안의 활성 로드맵 일정을 날짜별 알림으로 동기화한 뒤 "
        "현재 사용자의 미확인·유효·도래 알림을 반환합니다. 조회만으로 확인 처리하지 않습니다."
    ),
    responses=COMMON_RESPONSES,
)
async def login_notification_feed(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationFeed:
    return await service.login_feed(user_id=current_user.id)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationView,
    summary="알림 확인 처리",
    description=(
        "현재 사용자가 소유한 알림 하나를 확인 처리합니다. 재호출 시 최초 read_at을 보존하며 "
        "없거나 다른 사용자 소유인 ID는 같은 404로 응답합니다."
    ),
    responses={
        **COMMON_RESPONSES,
        404: {
            "model": APIErrorEnvelope,
            "description": "`NOTIFICATION_NOT_FOUND`: 소유 알림을 찾을 수 없음",
        },
        422: {
            "model": APIErrorEnvelope,
            "description": "`VALIDATION_ERROR`: notification_id UUID 형식 오류",
        },
    },
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationView:
    return await service.mark_read(
        user_id=current_user.id,
        notification_id=notification_id,
    )
