from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_plan_management_service
from app.api.errors import APIErrorEnvelope
from app.api.schemas import PlanTaskStatusRequest
from app.auth.models import CurrentUser
from app.plans.service import PlanManagementService
from app.plans.views import (
    TaskUpdateView,
    TodayQuestView,
    build_task_update_view,
    build_today_quest_view,
)

router = APIRouter(prefix="/quests", tags=["quests"])

QUEST_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {"model": APIErrorEnvelope, "description": "`TODAY_QUEST_NOT_FOUND`: 오늘 퀘스트 없음"},
    422: {"model": APIErrorEnvelope, "description": "`VALIDATION_ERROR`: UUID, status 또는 body 오류"},
    500: {"model": APIErrorEnvelope, "description": "`PLAN_DATA_INTEGRITY_ERROR`: 계획 데이터 무결성 오류"},
    503: {"model": APIErrorEnvelope, "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애"},
}


@router.get(
    "/today",
    response_model=TodayQuestView,
    summary="오늘 퀘스트 조회",
    responses={key: value for key, value in QUEST_ERROR_RESPONSES.items() if key != 404},
)
async def get_today_quests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
) -> TodayQuestView:
    snapshot = await service.get_today_quests(user_id=current_user.id)
    return build_today_quest_view(snapshot)


@router.patch(
    "/{task_id}",
    response_model=TaskUpdateView,
    summary="오늘 퀘스트 상태 변경",
    responses=QUEST_ERROR_RESPONSES,
)
async def update_today_quest(
    task_id: UUID,
    payload: PlanTaskStatusRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
) -> TaskUpdateView:
    update = await service.set_today_task_status(
        user_id=current_user.id,
        task_id=task_id,
        status=payload.status,
    )
    return build_task_update_view(update)
