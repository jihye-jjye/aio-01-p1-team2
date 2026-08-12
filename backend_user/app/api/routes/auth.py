from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_auth_service, get_current_user
from app.api.errors import APIErrorEnvelope, UnauthorizedError
from app.api.schemas import AccountUpdateRequest, LoginRequest, SignupRequest
from app.auth.errors import AccountNotFoundError
from app.auth.models import (
    AccountSummary,
    CurrentAccount,
    CurrentUser,
    LoginResult,
    SignupResult,
)
from app.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=SignupResult,
    status_code=201,
    summary="계정 생성 및 토큰 발급",
    description="""
`login_id`, `login_pw`, `user_name`으로 자체 계정을 생성하고 access/refresh token을 즉시 발급합니다.

- `login_id`는 앞뒤 공백 제거와 대소문자 정규화 후 저장되며 4~50자입니다.
- `login_pw`는 공백을 보존하고 Argon2id hash만 PostgreSQL에 저장합니다.
- `user_name`은 앞뒤 공백 제거 후 저장되며 1~50자입니다.
- 사용자 ID와 role은 서버와 DB에서 결정하며 클라이언트 입력으로 받지 않습니다.
- 계정 생성 후 Redis refresh token 저장만 실패하면 계정은 유지될 수 있으므로,
  `SERVICE_UNAVAILABLE` 응답 뒤 가입을 자동 반복하지 말고 같은 자격 증명으로 로그인합니다.
- refresh token 원문은 응답에만 포함되고 서버에는 SHA-256 hash만 저장됩니다.
""",
    response_description="생성된 사용자 정보와 access/refresh token",
    responses={
        409: {
            "model": APIErrorEnvelope,
            "description": "`LOGIN_ID_ALREADY_EXISTS`: 정규화된 로그인 ID 중복",
        },
        422: {
            "model": APIErrorEnvelope,
            "description": "`VALIDATION_ERROR`: 로그인 ID 문자·길이 또는 비밀번호 길이 위반",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 또는 Redis 장애",
        },
    },
)
async def signup(
    payload: SignupRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> SignupResult:
    return await service.signup(
        login_id=payload.login_id,
        login_pw=payload.login_pw,
        user_name=payload.user_name,
    )


@router.post(
    "/login",
    response_model=LoginResult,
    summary="로그인 및 토큰 발급",
    description="""
로그인 ID와 비밀번호를 검증하고 access/refresh token을 발급합니다.

- 로그인 ID는 앞뒤 공백 제거와 대소문자 정규화 후 조회합니다.
- 존재하지 않는 ID에도 dummy hash 검증을 수행해 계정 존재 여부 노출을 줄입니다.
- 비밀번호 5회 연속 실패 시 15분 동안 잠기며, 성공하면 실패 횟수와 잠금이 초기화됩니다.
- ID 불일치, 비밀번호 불일치, 잠금, 비활성 상태는 모두 같은 오류로 응답합니다.
- 응답에는 사용자 ID가 없으므로 필요하면 Bearer token으로 `GET /api/v1/auth/me`를 호출합니다.
""",
    response_description="access/refresh token과 access token 만료 시간",
    responses={
        401: {
            "model": APIErrorEnvelope,
            "description": "`INVALID_CREDENTIALS`: 자격 증명이 올바르지 않거나 계정 사용 불가",
        },
        422: {
            "model": APIErrorEnvelope,
            "description": "`VALIDATION_ERROR`: 로그인 ID 또는 비밀번호 길이 위반",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 또는 Redis 장애",
        },
    },
)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResult:
    return await service.login(login_id=payload.login_id, login_pw=payload.login_pw)


@router.get(
    "/me",
    response_model=CurrentAccount,
    summary="현재 인증 사용자 조회",
    description="""
Bearer access token과 계정 활성 상태를 검증하고 현재 계정 정보를 반환합니다.

- PostgreSQL에서 `sub` 계정의 `login_id`, `user_name`과 활성 상태를 조회합니다.
- `role`, `session_id`는 검증된 JWT claim을 사용합니다.
- `id`는 사용자 UUID, `session_id`는 refresh token과 연결된 인증 세션 UUID입니다.
- access token이 없거나 만료·위조됐거나 계정이 삭제·비활성 상태이면 인증 상태를 폐기해야 합니다.
""",
    response_description="현재 계정 정보와 인증 세션 정보",
    responses={
        401: {
            "model": APIErrorEnvelope,
            "description": "`UNAUTHORIZED`: Bearer token 없음·만료·위조 또는 비활성 계정",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: 계정 조회 중 PostgreSQL 장애",
        },
    },
)
async def me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> CurrentAccount:
    try:
        account = await service.get_account(user_id=current_user.id)
    except AccountNotFoundError as exc:
        raise UnauthorizedError from exc
    return CurrentAccount(
        id=account.user_id,
        role=current_user.role,
        session_id=current_user.session_id,
        login_id=account.login_id,
        user_name=account.user_name,
    )


@router.patch(
    "/me",
    response_model=AccountSummary,
    summary="현재 계정 로그인 ID·이름 수정",
    description="""
Bearer access token의 `sub`로 식별한 현재 계정의 `login_id` 또는 `user_name`을 수정합니다.

- 요청 body에 사용자 UUID를 받지 않으며 다른 사용자의 계정을 수정할 수 없습니다.
- 두 필드 중 하나 이상을 보내야 하며 명시적인 `null`과 알 수 없는 필드는 허용하지 않습니다.
- `login_id`는 앞뒤 공백 제거와 대소문자 정규화 후 4~50자, `[a-z0-9._-]+` 형식입니다.
- `user_name`은 앞뒤 공백 제거 후 1~50자입니다.
- 로그인 ID 변경 뒤에도 현재 JWT의 UUID 기반 소유권과 세션은 유지됩니다.
""",
    response_description="수정된 현재 계정의 UUID, 로그인 ID와 사용자 이름",
    responses={
        401: {
            "model": APIErrorEnvelope,
            "description": "`UNAUTHORIZED`: Bearer token 없음·만료·위조 또는 비활성 계정",
        },
        404: {
            "model": APIErrorEnvelope,
            "description": "`ACCOUNT_NOT_FOUND`: 수정 직전에 계정이 삭제됨",
        },
        409: {
            "model": APIErrorEnvelope,
            "description": "`LOGIN_ID_ALREADY_EXISTS`: 정규화된 로그인 ID 중복",
        },
        422: {
            "model": APIErrorEnvelope,
            "description": "`VALIDATION_ERROR`: 필드 누락·null·형식·길이 또는 알 수 없는 필드",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
        },
    },
)
async def update_me(
    payload: AccountUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AccountSummary:
    return await service.update_account(
        user_id=current_user.id,
        login_id=payload.login_id,
        user_name=payload.user_name,
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="현재 계정 영구 삭제",
    description="""
Bearer access token의 `sub`로 식별한 현재 계정과 사용자 소유 데이터를 영구 삭제합니다.

- 요청 body나 path에 사용자 UUID를 받지 않습니다.
- 프로필, 계획, 일정, AI 결과, 알림과 목표 달성 기록을 같은 DB 트랜잭션에서 삭제합니다.
- 모든 사용자가 공유하는 저장 공고는 삭제하지 않습니다.
- 현재 refresh 세션을 먼저 폐기하며, 삭제 뒤 남아 있는 access token도 계정 활성 확인에서 거부됩니다.
- 성공 응답을 받으면 클라이언트는 보관 중인 access/refresh token과 사용자 캐시를 즉시 폐기해야 합니다.
""",
    response_description="응답 본문 없음",
    responses={
        401: {
            "model": APIErrorEnvelope,
            "description": "`UNAUTHORIZED`: Bearer token 없음·만료·위조 또는 비활성 계정",
        },
        404: {
            "model": APIErrorEnvelope,
            "description": "`ACCOUNT_NOT_FOUND`: 삭제 직전에 계정이 이미 삭제됨",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 또는 Redis 장애",
        },
    },
)
async def delete_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    await service.delete_account(
        user_id=current_user.id,
        session_id=current_user.session_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
