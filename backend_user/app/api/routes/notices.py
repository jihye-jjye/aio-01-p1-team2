from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_notice_service
from app.api.errors import APIErrorEnvelope
from app.auth.models import CurrentUser
from app.notices.models import NoticeView
from app.notices.service import NoticeService

router = APIRouter(prefix="/notices", tags=["notices"])


@router.get(
    "",
    response_model=list[NoticeView],
    summary="게시 중인 공지 조회",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        503: {"model": APIErrorEnvelope, "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애"},
    },
)
async def list_notices(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[NoticeService, Depends(get_notice_service)],
) -> list[NoticeView]:
    return await service.list_published(user_id=current_user.id)
