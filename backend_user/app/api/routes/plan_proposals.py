from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_current_user,
    get_plan_management_service,
    get_plan_proposal_service,
)
from app.api.errors import APIErrorEnvelope
from app.api.schemas import PlanProposalCreateRequest, PlanProposalReviseRequest
from app.auth.models import CurrentUser
from app.plans.service import PlanManagementService, PlanProposalService
from app.plans.views import PlanProposalView, PlanView, build_plan_proposal_view, build_plan_view

router = APIRouter(prefix="/plan-proposals", tags=["plan-proposals"])

CREATE_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PROFILE_NOT_FOUND`: 확정 프로필 또는 준비도 평가 없음",
    },
    409: {
        "model": APIErrorEnvelope,
        "description": (
            "- `IDEMPOTENCY_KEY_REUSED`: request_id가 다른 작업에 이미 사용됨\n"
            "- `PLAN_PROPOSAL_ALREADY_PENDING`: 다른 pending 제안이 존재\n"
            "- `ACTIVE_PLAN_EXISTS`: 진행 중인 active plan이 존재\n"
            "- `PLAN_GENERATION_IN_PROGRESS`: 같은 생성 요청을 처리 중 (retryable=true)\n"
            "- `PLAN_PROFILE_CHANGED`: 생성 중 프로필 또는 assessment가 변경됨\n"
            "- `PLAN_PROPOSAL_STALE`: 생성 중 KST 날짜가 변경됨"
        ),
    },
    422: {
        "model": APIErrorEnvelope,
        "description": (
            "- `VALIDATION_ERROR`: request_id 형식 오류\n"
            "- `PLAN_TARGET_DATE_EXPIRED`: 프로필 목표일 경과\n"
            "- `PLAN_HORIZON_TOO_LONG`: 생성 기간이 최대 365일 초과\n"
            "- `GEMINI_CONTENT_BLOCKED`: Gemini 안전 필터 차단"
        ),
    },
    429: {
        "model": APIErrorEnvelope,
        "description": "`GEMINI_RATE_LIMITED`: 호출 제한 초과 (retryable=true)",
    },
    500: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_DATA_INTEGRITY_ERROR`: 계획 데이터 무결성 검증 실패",
    },
    502: {
        "model": APIErrorEnvelope,
        "description": (
            "- `GEMINI_UNAVAILABLE`: Gemini 일시 장애 (retryable=true)\n"
            "- `GEMINI_CONFIGURATION_ERROR`: Gemini 설정 오류\n"
            "- `GEMINI_INVALID_RESPONSE`: 구조화 응답 검증 실패"
        ),
    },
    503: {
        "model": APIErrorEnvelope,
        "description": (
            "`SERVICE_UNAVAILABLE`: PostgreSQL 또는 Redis 처리 실패 "
            "(retryable=true; 복구 후 같은 request_id와 body로 재시도)"
        ),
    },
    504: {
        "model": APIErrorEnvelope,
        "description": (
            "`PLAN_GENERATION_TIMEOUT`: 생성 시간 초과 (retryable=true; 같은 request_id로 "
            "재시도하며 유효한 checkpoint가 있으면 재개)"
        ),
    },
}
READ_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_PROPOSAL_NOT_FOUND`: 소유 계획 제안을 찾을 수 없음",
    },
    422: {
        "model": APIErrorEnvelope,
        "description": (
            "- `VALIDATION_ERROR`: UUID, 날짜 또는 days 범위 오류\n"
            "- `PLAN_WINDOW_OUT_OF_RANGE`: start_on이 제안 기간 밖"
        ),
    },
    500: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_DATA_INTEGRITY_ERROR`: 저장된 제안 무결성 검증 실패",
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}
ACCEPT_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_PROPOSAL_NOT_FOUND`: 소유 계획 제안을 찾을 수 없음",
    },
    409: {
        "model": APIErrorEnvelope,
        "description": (
            "- `PLAN_PROPOSAL_NOT_PENDING`: pending/applied가 아닌 제안\n"
            "- `ACTIVE_PLAN_EXISTS`: 다른 active plan이 존재\n"
            "- `PLAN_PROFILE_CHANGED`: 제안 생성 후 프로필 또는 assessment 변경\n"
            "- `PLAN_PROPOSAL_STALE`: 제안 생성 KST 날짜가 지남"
        ),
    },
    422: {"model": APIErrorEnvelope, "description": "`VALIDATION_ERROR`: proposal_id 형식 오류"},
    500: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_DATA_INTEGRITY_ERROR`: 제안·plan 투영 무결성 검증 실패",
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}
REJECT_ERROR_RESPONSES = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_PROPOSAL_NOT_FOUND`: 소유 계획 제안을 찾을 수 없음",
    },
    409: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_PROPOSAL_NOT_PENDING`: applied 제안은 거절할 수 없음",
    },
    422: {"model": APIErrorEnvelope, "description": "`VALIDATION_ERROR`: proposal_id 형식 오류"},
    500: {
        "model": APIErrorEnvelope,
        "description": "`PLAN_DATA_INTEGRITY_ERROR`: 저장된 제안 무결성 검증 실패",
    },
    503: {
        "model": APIErrorEnvelope,
        "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
    },
}


@router.post(
    "",
    response_model=PlanProposalView,
    status_code=status.HTTP_201_CREATED,
    summary="프로필 기반 계획 제안 생성",
    description="""
확정 프로필과 추적 가능한 준비도 평가를 기준으로 계획 제안을 생성합니다.

- `request_id`는 생성 요청의 멱등성 키이며 사용자 ID는 Bearer access token에서 결정합니다.
- KST 오늘부터 프로필 목표일까지 주차별 milestone과 날짜별 task 1~3개를 생성합니다.
- 전체 기간은 시작일과 종료일을 포함해 최대 365일입니다.
- Gemini 생성은 28일 task batch, 최대 동시성 3으로 수행됩니다.
- 생성 입력, 검증된 outline·batch·완성 proposal checkpoint는 Redis에 1시간 보관됩니다.
- `retryable=true` 오류나 전송 결과 불확실성에는 같은 `request_id`와 body를 유지합니다. 유효한
  checkpoint가 있으면 이어서 처리하고, 영속 성공 상태면 동일 제안을 `201 Created`로 반환합니다.
- checkpoint가 없거나 만료된 경우에도 같은 `request_id`로 생성부터 안전하게 다시 시도할 수 있습니다.
- 성공 응답은 제안 시작일부터 기본 7일 window를 포함합니다.
""",
    response_description="생성·검증·저장된 계획 제안의 첫 7일 window",
    responses=CREATE_ERROR_RESPONSES,
)
async def create_plan_proposal(
    payload: PlanProposalCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanProposalService, Depends(get_plan_proposal_service)],
) -> PlanProposalView:
    proposal = await service.create(user_id=current_user.id, request_id=payload.request_id)
    return build_plan_proposal_view(proposal, start_on=None, days=7)


@router.get(
    "/pending",
    response_model=PlanProposalView,
    summary="대기 중인 계획 제안 조회",
    description="""
현재 사용자에게 남아 있는 `pending` 계획 제안을 날짜 window로 조회합니다.

- `start_on`을 생략하면 제안의 `starts_on`부터 조회합니다.
- `days`는 1~28, 기본값은 7이며 제안 종료일을 넘으면 마지막 날까지 잘립니다.
- milestone은 전체 제안 범위를 반환하고 `days` 배열만 요청 window로 제한됩니다.
- 다른 사용자의 제안 존재 여부는 노출하지 않고 `PLAN_PROPOSAL_NOT_FOUND`로 처리합니다.
""",
    response_description="대기 중인 계획 제안과 요청한 날짜 window",
    responses=READ_ERROR_RESPONSES,
)
async def get_pending_plan_proposal(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanProposalService, Depends(get_plan_proposal_service)],
    start_on: date | None = None,
    days: int = Query(default=7, ge=1, le=28),
) -> PlanProposalView:
    proposal = await service.get_pending(user_id=current_user.id)
    return build_plan_proposal_view(proposal, start_on=start_on, days=days)


@router.get(
    "/{proposal_id}",
    response_model=PlanProposalView,
    summary="계획 제안 상세 조회",
    description="""
현재 사용자가 소유한 계획 제안을 ID와 날짜 window로 조회합니다.

- `pending`, `applied`, `rejected` 상태의 제안을 조회할 수 있습니다.
- `start_on`을 생략하면 제안의 `starts_on`, `days`는 기본 7일입니다.
- `days`는 1~28이며 제안 종료일을 넘으면 마지막 날까지 잘립니다.
- 응답에는 proposal/profile hash, assessment result ID와 생성 engine version이 포함됩니다.
- 다른 사용자 소유 ID도 `PLAN_PROPOSAL_NOT_FOUND`로 처리합니다.
""",
    response_description="계획 제안 상세 정보와 요청한 날짜 window",
    responses=READ_ERROR_RESPONSES,
)
async def get_plan_proposal(
    proposal_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanProposalService, Depends(get_plan_proposal_service)],
    start_on: date | None = None,
    days: int = Query(default=7, ge=1, le=28),
) -> PlanProposalView:
    proposal = await service.get(user_id=current_user.id, proposal_id=proposal_id)
    return build_plan_proposal_view(proposal, start_on=start_on, days=days)


@router.post(
    "/{proposal_id}/revise",
    response_model=PlanProposalView,
    status_code=status.HTTP_201_CREATED,
    summary="계획 제안 수정",
    description="""
현재 사용자가 소유한 `pending` 계획 제안을 사용자 피드백을 반영해 수정 생성합니다.

- `request_id`는 수정 요청의 멱등성 키이며 사용자 ID는 Bearer access token에서 결정합니다.
- `feedback`은 1자 이상 4,000자 이하의 수정 요청 텍스트입니다.
- 기존 제안은 `rejected`로 전환되고 수정된 새 제안이 `pending`으로 생성됩니다.
- Gemini가 기존 계획과 피드백을 바탕으로 outline과 tasks를 재생성합니다.
- 활성 plan이 있거나 프로필이 변경된 경우 수정할 수 없습니다.
- 성공 응답은 제안 시작일부터 기본 7일 window를 포함합니다.
""",
    response_description="수정 생성된 새 계획 제안의 첫 7일 window",
    responses=CREATE_ERROR_RESPONSES,
)
async def revise_plan_proposal(
    proposal_id: UUID,
    payload: PlanProposalReviseRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanProposalService, Depends(get_plan_proposal_service)],
) -> PlanProposalView:
    proposal = await service.revise(
        user_id=current_user.id,
        proposal_id=proposal_id,
        feedback=payload.feedback,
        request_id=payload.request_id,
    )
    return build_plan_proposal_view(proposal, start_on=None, days=7)


@router.post(
    "/{proposal_id}/accept",
    response_model=PlanView,
    summary="계획 제안 수락 및 활성 계획 생성",
    description="""
`pending` 계획 제안을 수락하고 schedule을 투영해 active plan으로 전환합니다.

- 요청 body는 필요하지 않으며 사용자 ID는 Bearer access token에서만 결정합니다.
- 수락 직전 profile hash, assessment result와 KST 생성일을 다시 검증합니다.
- plan, milestone/task schedule, proposal 상태와 상호 링크를 하나의 DB 트랜잭션에서 갱신합니다.
- schedule 시각은 수락 시점 프로필의 `daily_notification_time`으로 고정됩니다.
- 이미 applied된 같은 제안을 다시 수락하면 연결된 동일 plan을 반환합니다.
- 성공 응답은 KST 오늘을 plan 기간에 맞춘 날짜부터 기본 7일 window입니다.
""",
    response_description="수락된 제안에서 생성된 active plan의 첫 조회 window",
    responses=ACCEPT_ERROR_RESPONSES,
)
async def accept_plan_proposal(
    proposal_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
) -> PlanView:
    plan = await service.accept(user_id=current_user.id, proposal_id=proposal_id)
    return build_plan_view(
        plan,
        start_on=None,
        days=7,
        today=plan.view_today or service.today(),
    )


@router.post(
    "/{proposal_id}/reject",
    response_model=PlanProposalView,
    summary="계획 제안 거절",
    description="""
현재 사용자가 소유한 `pending` 계획 제안을 `rejected`로 변경합니다.

- 요청 body는 필요하지 않으며 사용자 ID는 Bearer access token에서만 결정합니다.
- 이미 rejected된 제안은 최초 `decided_at`을 보존하고 현재 값을 멱등 반환합니다.
- 이미 applied된 제안은 거절할 수 없습니다.
- 성공 응답은 제안의 `starts_on`부터 기본 7일 window입니다.
""",
    response_description="rejected 상태로 갱신된 계획 제안",
    responses=REJECT_ERROR_RESPONSES,
)
async def reject_plan_proposal(
    proposal_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PlanManagementService, Depends(get_plan_management_service)],
) -> PlanProposalView:
    proposal = await service.reject(user_id=current_user.id, proposal_id=proposal_id)
    return build_plan_proposal_view(proposal, start_on=None, days=7)
