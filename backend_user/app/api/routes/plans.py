from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_plan_management_service
from app.api.errors import APIErrorEnvelope
from app.api.schemas import PlanTaskStatusRequest
from app.auth.models import CurrentUser
from app.plans.service import PlanManagementService
from app.plans.views import PlanView, TaskUpdateView, build_plan_view, build_task_update_view

router = APIRouter(prefix="/plans", tags=["plans"])

PLAN_READ_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_NOT_FOUND`: 소유 계획을 찾을 수 없음",
    },
    422: {
        "model": APIErrorEnvelope,
        "description": (
            "- `VALIDATION_ERROR`: UUID, 날짜 또는 days 범위 오류\n"
            "- `PLAN_WINDOW_OUT_OF_RANGE`: start_on이 계획 기간 밖"
        ),
    },
    500: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_DATA_INTEGRITY_ERROR`: 저장된 plan·schedule 무결성 검증 실패",
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}
TASK_UPDATE_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_TASK_NOT_FOUND`: 소유 plan의 task를 찾을 수 없음",
    },
    409: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_NOT_ACTIVE`: active plan의 task만 다른 상태로 변경 가능",
    },
    422: {
        "model": APIErrorEnvelope,
        "description": "`VALIDATION_ERROR`: UUID, status 또는 추가 body 필드 오류",
    },
    500: {
        "model": APIErrorEnvelope,
        "description": (
            "`PLAN_DATA_INTEGRITY_ERROR`: task, 일별 달성 기록 또는 account/EXP 무결성 검증 실패"
        ),
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}
COMPLETE_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_NOT_FOUND`: 소유 계획을 찾을 수 없음",
    },
    409: {
        "model": APIErrorEnvelope,
        "description": (
            "- `PLAN_NOT_ACTIVE`: active 상태가 아닌 plan\n"
            "- `PLAN_NOT_COMPLETE`: 완료되지 않은 progress task가 존재"
        ),
    },
    422: {"model": APIErrorEnvelope, "description": "`VALIDATION_ERROR`: plan_id 형식 오류"},
    500: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_DATA_INTEGRITY_ERROR`: plan·schedule 무결성 검증 실패",
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}


@router.get(
    "/active",
    response_model=PlanView,
    summary="현재 활성 계획 조회",
    description="""
현재 사용자에게 하나만 허용되는 active plan을 날짜 window로 조회합니다.

- `start_on`을 생략하면 KST 오늘을 plan 기간에 맞춰 보정한 날짜부터 조회합니다.
- plan 시작 전이면 `starts_on`, 종료 후이면 `ends_on`을 기본 시작일로 사용합니다.
- `days`는 1~28, 기본값은 7이며 plan 종료일을 넘으면 마지막 날까지 잘립니다.
- milestone은 전체 plan 범위를, `days` 배열은 요청 window의 task만 반환합니다.
- 응답의 progress는 완료 task 수를 전체 task 수로 나눈 정수 백분율입니다.
""",
    response_description="현재 active plan과 요청한 날짜 window 및 progress",
    responses=PLAN_READ_ERROR_RESPONSES,
)
async def get_active_plan(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
    start_on: date | None = None,
    days: int = Query(default=7, ge=1, le=28),
) -> PlanView:
    plan = await service.get_active(user_id=current_user.id)
    return build_plan_view(plan, start_on=start_on, days=days, today=service.today())


@router.get(
    "/{plan_id}",
    response_model=PlanView,
    summary="계획 상세 조회",
    description="""
현재 사용자가 소유한 active 또는 completed plan을 ID와 날짜 window로 조회합니다.

- `start_on`을 생략하면 KST 오늘을 plan 기간에 맞춰 보정한 날짜부터 조회합니다.
- `days`는 1~28, 기본값은 7이며 plan 종료일을 넘으면 마지막 날까지 잘립니다.
- 응답에는 출처 proposal/profile hash, assessment result ID와 생성 engine version이 포함됩니다.
- 다른 사용자 소유 ID도 `PLAN_NOT_FOUND`로 처리해 존재 여부를 노출하지 않습니다.
""",
    response_description="소유 계획 상세 정보와 요청한 날짜 window 및 progress",
    responses=PLAN_READ_ERROR_RESPONSES,
)
async def get_plan(
    plan_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
    start_on: date | None = None,
    days: int = Query(default=7, ge=1, le=28),
) -> PlanView:
    plan = await service.get(user_id=current_user.id, plan_id=plan_id)
    return build_plan_view(plan, start_on=start_on, days=days, today=service.today())


@router.patch(
    "/{plan_id}/tasks/{task_id}",
    response_model=TaskUpdateView,
    summary="계획 task 상태 변경",
    description="""
active plan에 속한 progress task 상태를 `pending` 또는 `completed`로 변경합니다.

- 요청 body는 `status` 필드 하나만 허용하며 추가 필드는 거부합니다.
- `completed` task를 다시 `pending`으로 되돌릴 수 있습니다.
- 같은 목표 상태를 재요청하면 기존 `completed_at`을 보존해 멱등 반환합니다.
- 다른 상태로 변경하는 요청은 active plan에서만 허용됩니다.
- 해당 날짜의 모든 task가 완료되는 전이에만 `+10 EXP`, 달성이 취소되는 전이에만
  `-10 EXP`를 반영하며 과거·오늘·미래 날짜를 동일하게 처리합니다.
- 성공 응답에는 변경된 task, plan/day progress, 일별 달성 상태, 이번 `exp_delta`와
  최신 누적 `user_exp`가 포함됩니다.
- 모든 task가 완료되어도 plan은 자동 종료되지 않으며 별도 complete 요청이 필요합니다.
""",
    response_description="변경된 task, plan/day 진행률, 일별 달성 상태와 누적 EXP",
    responses=TASK_UPDATE_ERROR_RESPONSES,
)
async def update_plan_task(
    plan_id: UUID,
    task_id: UUID,
    payload: PlanTaskStatusRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
) -> TaskUpdateView:
    update = await service.set_task_status(
        user_id=current_user.id,
        plan_id=plan_id,
        task_id=task_id,
        status=payload.status,
    )
    return build_task_update_view(update)


@router.post(
    "/{plan_id}/complete",
    response_model=PlanView,
    summary="활성 계획 완료",
    description="""
모든 progress task가 완료된 active plan을 completed 상태로 종료합니다.

- 요청 body는 필요하지 않으며 사용자 ID는 Bearer access token에서 결정합니다.
- 미완료 task가 있으면 `PLAN_NOT_COMPLETE`와 안전한 완료/전체 task 수만 반환합니다.
- 성공 시 `ended_at`을 기록하고 `restart_offer_status`를 `pending`으로 엽니다.
- 이미 completed된 같은 plan의 재요청은 저장된 완료 결과를 반환합니다.
- 성공 응답은 KST 오늘을 plan 기간에 맞춘 날짜부터 기본 7일 window입니다.
""",
    response_description="completed 상태와 pending restart offer를 포함한 plan",
    responses=COMPLETE_ERROR_RESPONSES,
)
async def complete_plan(
    plan_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
) -> PlanView:
    plan = await service.complete(user_id=current_user.id, plan_id=plan_id)
    return build_plan_view(plan, start_on=None, days=7, today=service.today())
