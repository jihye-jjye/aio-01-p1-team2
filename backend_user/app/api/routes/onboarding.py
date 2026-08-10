from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_onboarding_service
from app.api.errors import APIErrorEnvelope
from app.api.schemas import (
    OnboardingConfirmRequest,
    OnboardingMessageRequest,
    OnboardingStartRequest,
)
from app.auth.models import CurrentUser
from app.onboarding.models import OnboardingResponse
from app.onboarding.service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/sessions",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="온보딩 세션 시작",
    description="""
인증된 사용자의 온보딩 세션을 시작하고 Gemini가 생성한 첫 질문을 반환합니다.

- `request_id`는 클라이언트가 생성한 UUID이며 시작 요청의 멱등성 키로 사용됩니다.
- 세션의 임시 상태는 Redis에 저장되고 설정된 TTL 동안 유지됩니다.
- 사용자 ID는 요청 본문이 아니라 Bearer access token에서만 결정됩니다.
- 같은 `request_id`를 동일 사용자가 재전송하면 캐시된 첫 응답을 반환합니다.
""",
    response_description="생성된 세션 ID와 첫 conversation 응답",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        409: {
            "model": APIErrorEnvelope,
            "description": (
                "`ONBOARDING_REQUEST_IN_PROGRESS`: 동일 사용자의 같은 시작 요청을 처리 중"
            ),
        },
        422: {
            "model": APIErrorEnvelope,
            "description": (
                "- `VALIDATION_ERROR`: request_id 형식 오류\n"
                "- `GEMINI_CONTENT_BLOCKED`: Gemini 안전 필터 차단"
            ),
        },
        429: {
            "model": APIErrorEnvelope,
            "description": "`GEMINI_RATE_LIMITED`: Gemini 호출 제한 초과",
        },
        502: {
            "model": APIErrorEnvelope,
            "description": (
                "`GEMINI_UNAVAILABLE`, `GEMINI_CONFIGURATION_ERROR`, "
                "`GEMINI_INVALID_RESPONSE`: Gemini 호출·설정·응답 검증 실패"
            ),
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: Redis 장애",
        },
    },
)
async def start_session(
    payload: OnboardingStartRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingResponse:
    return await service.start(user_id=current_user.id, request_id=payload.request_id)


@router.get(
    "/sessions/{session_id}/result",
    response_model=OnboardingResponse,
    summary="온보딩 review 결과 조회",
    description="""
현재 사용자가 소유한 온보딩 세션의 **서버 review snapshot**을 조회합니다.

- 8개 프로필 필드와 준비도 평가가 모두 생성된 `review` 단계에서만 성공합니다.
- 응답의 `payload.draft_revision`을 이후 confirm 요청의 `expected_revision`으로 사용합니다.
- Redis 상태를 읽기만 하며 세션 TTL을 갱신하지 않습니다.
- 대화 transcript는 응답하지 않으며 conversation 중간 상태 복구 API가 아닙니다.
- 만료된 세션과 다른 사용자가 소유한 세션은 보안을 위해 같은 오류로 처리합니다.
""",
    response_description="확정 저장 전 검토할 OnboardingResponse review snapshot",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        409: {
            "model": APIErrorEnvelope,
            "description": (
                "- `ONBOARDING_SESSION_EXPIRED`: 세션 만료 또는 소유권 불일치\n"
                "- `ONBOARDING_RESULT_NOT_READY`: 아직 collecting 단계\n"
                "- `ONBOARDING_ALREADY_COMPLETED`: 이미 확정 저장된 세션\n"
                "- `ONBOARDING_REQUEST_IN_PROGRESS`: 같은 세션의 요청을 처리 중"
            ),
        },
        422: {
            "model": APIErrorEnvelope,
            "description": "`VALIDATION_ERROR`: session_id UUID 형식 오류",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: Redis 장애",
        },
    },
)
async def get_result(
    session_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingResponse:
    return await service.get_result(user_id=current_user.id, session_id=session_id)


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=OnboardingResponse,
    summary="온보딩 review 결과 확정 저장",
    description="""
직전에 확인한 서버 review snapshot을 PostgreSQL에 확정 저장합니다.

- `request_id`는 confirm 논리 요청의 멱등성 키입니다.
- `expected_revision`은 `GET .../result`에서 받은 `payload.draft_revision`과 같아야 합니다.
- 요청 본문에는 `request_id`, `expected_revision` 외의 필드를 허용하지 않습니다.
- 프로필 assessment 결과 INSERT와 profile UPSERT는 하나의 DB 트랜잭션에서 처리됩니다.
- 기존 messages의 `action="onboarding.confirm"`과 fingerprint 및 응답 cache를 공유하므로
  두 경로 사이에서 같은 요청을 재시도해도 중복 저장하지 않습니다.
- 성공 후에는 confirm을 반복하지 말고 `GET /api/v1/profile`로 영속 결과를 재조회합니다.
""",
    response_description="저장된 프로필 정보를 포함한 completed 응답",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        409: {
            "model": APIErrorEnvelope,
            "description": (
                "- `ONBOARDING_SESSION_EXPIRED`: 세션 만료 또는 소유권 불일치\n"
                "- `ONBOARDING_REQUEST_IN_PROGRESS`: 같은 세션의 요청을 처리 중\n"
                "- `IDEMPOTENCY_KEY_REUSED`: request_id를 다른 payload에 재사용\n"
                "- `ONBOARDING_REVISION_CONFLICT`: expected_revision 불일치\n"
                "- `ONBOARDING_SNAPSHOT_CONFLICT`: 같은 request_id의 DB snapshot 불일치"
            ),
        },
        422: {
            "model": APIErrorEnvelope,
            "description": (
                "- `VALIDATION_ERROR`: UUID, revision 또는 추가 필드 등 요청 형식 오류\n"
                "- `ONBOARDING_VALIDATION_ERROR`: review 이전 confirm 등 단계 검증 실패"
            ),
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 또는 Redis 장애",
        },
    },
)
async def confirm_result(
    session_id: UUID,
    payload: OnboardingConfirmRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingResponse:
    return await service.confirm(
        user_id=current_user.id,
        session_id=session_id,
        request_id=payload.request_id,
        expected_revision=payload.expected_revision,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=OnboardingResponse,
    summary="온보딩 답변·수정·기존 action 처리",
    description="""
온보딩 세션에서 사용자 답변, review 자연어 수정 또는 기존 action을 처리합니다.

- `text`와 `action` 중 정확히 하나만 보내야 합니다.
- `text`는 최대 4,000자이며 conversation과 review 단계에서 사용할 수 있습니다.
- 지원 action은 `onboarding.restart`와 하위 호환용 `onboarding.confirm`입니다.
- confirm action에는 화면에 표시한 `draft_revision`과 같은 `expected_revision`이 필요합니다.
- 각 논리 요청은 새 `request_id`를 사용하고, 네트워크 재시도 때만 같은 ID와 payload를 유지합니다.
- 응답 `step`은 수집 중 `conversation`, 평가 완료 `review`, 저장 완료 `completed`입니다.
""",
    response_description="처리 후 최신 온보딩 세션 상태",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        409: {
            "model": APIErrorEnvelope,
            "description": (
                "- `ONBOARDING_SESSION_EXPIRED`: 세션 만료 또는 소유권 불일치\n"
                "- `ONBOARDING_REQUEST_IN_PROGRESS`: 같은 세션의 요청을 처리 중\n"
                "- `IDEMPOTENCY_KEY_REUSED`: request_id를 다른 payload에 재사용\n"
                "- `ONBOARDING_REVISION_CONFLICT`: confirm revision 불일치\n"
                "- `ONBOARDING_SNAPSHOT_CONFLICT`: DB snapshot 충돌"
            ),
        },
        422: {
            "model": APIErrorEnvelope,
            "description": (
                "- `VALIDATION_ERROR`: text/action/revision 등 요청 스키마 위반\n"
                "- `ONBOARDING_VALIDATION_ERROR`: 단계, action 또는 사용자 발화 제한 위반\n"
                "- `GEMINI_CONTENT_BLOCKED`: Gemini 안전 필터 차단"
            ),
        },
        429: {
            "model": APIErrorEnvelope,
            "description": "`GEMINI_RATE_LIMITED`: Gemini 호출 제한 초과",
        },
        502: {
            "model": APIErrorEnvelope,
            "description": (
                "`GEMINI_UNAVAILABLE`, `GEMINI_CONFIGURATION_ERROR`, "
                "`GEMINI_INVALID_RESPONSE`: Gemini 호출·설정·응답 검증 실패"
            ),
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 또는 Redis 장애",
        },
    },
)
async def send_message(
    session_id: UUID,
    payload: OnboardingMessageRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingResponse:
    return await service.handle(
        user_id=current_user.id,
        session_id=session_id,
        request_id=payload.request_id,
        text=payload.text,
        action=payload.action,
        expected_revision=payload.expected_revision,
    )
