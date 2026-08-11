from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_assistant_service, get_current_user
from app.api.errors import APIErrorEnvelope
from app.auth.models import CurrentUser
from app.coach.models import (
    AssistantFinalizeRequest,
    AssistantFinalizeResponse,
    AssistantMessageRequest,
    AssistantMessageResponse,
    AssistantSessionCreateRequest,
    AssistantSessionCreateResponse,
)
from app.coach.service import CareerCoachService

router = APIRouter(prefix="/assistant", tags=["assistant"])

_COMMON_ERRORS = {
    401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
    404: {"model": APIErrorEnvelope, "description": "`PROFILE_NOT_FOUND`: 완료 프로필 없음"},
    409: {
        "model": APIErrorEnvelope,
        "description": ("상담 세션 만료·처리 중·revision 충돌·멱등성 키 재사용·세션 수 제한"),
    },
    422: {"model": APIErrorEnvelope, "description": "요청 형식 또는 상담 한도 오류"},
    429: {"model": APIErrorEnvelope, "description": "Gemini 사용자별 호출 제한"},
    502: {"model": APIErrorEnvelope, "description": "Gemini 호출·응답 검증 실패"},
    503: {"model": APIErrorEnvelope, "description": "DB 또는 Redis 장애"},
}


@router.post(
    "/sessions",
    response_model=AssistantSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI 취업 코치 상담 시작",
    description=(
        "완료 프로필과 코치 스타일을 최대 24시간 snapshot으로 고정하며, "
        "마지막 입력 후 45초가 지나면 활성 세션을 종료합니다."
    ),
    responses=_COMMON_ERRORS,
)
async def create_assistant_session(
    payload: AssistantSessionCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[CareerCoachService, Depends(get_assistant_service)],
) -> AssistantSessionCreateResponse:
    return await service.create_session(
        user_id=current_user.id,
        request_id=payload.request_id,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=AssistantMessageResponse,
    summary="AI 취업 코치 메시지 처리",
    description="최신 revision을 CAS로 검증하고 DB 사실과 코칭을 분리한 JSON을 반환합니다.",
    responses=_COMMON_ERRORS,
)
async def send_assistant_message(
    session_id: UUID,
    payload: AssistantMessageRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[CareerCoachService, Depends(get_assistant_service)],
) -> AssistantMessageResponse:
    return await service.send_message(
        user_id=current_user.id,
        session_id=session_id,
        request_id=payload.request_id,
        expected_revision=payload.expected_revision,
        text=payload.text,
    )


@router.post(
    "/sessions/{session_id}/finalize",
    response_model=AssistantFinalizeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI 취업 코치 상담 종료 및 보고서 저장",
    description="구조화 보고서를 저장하고 Redis 대화 원문을 tombstone으로 교체합니다.",
    responses={
        200: {
            "model": AssistantFinalizeResponse,
            "description": "이미 저장된 동일 세션 보고서의 durable replay",
        },
        **_COMMON_ERRORS,
    },
)
async def finalize_assistant_session(
    session_id: UUID,
    payload: AssistantFinalizeRequest,
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[CareerCoachService, Depends(get_assistant_service)],
) -> AssistantFinalizeResponse:
    result = await service.finalize_session(
        user_id=current_user.id,
        session_id=session_id,
        request_id=payload.request_id,
        expected_revision=payload.expected_revision,
    )
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return result.response
