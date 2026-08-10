from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.dependencies import build_token_service
from app.api.errors import ProfileNotFoundError, UnauthorizedError
from app.api.router import api_router
from app.auth.errors import LoginIdAlreadyExistsError
from app.auth.passwords import PasswordService
from app.auth.service import InvalidCredentialsError
from app.core.config import Settings
from app.db.pool import create_pool
from app.db.repositories import OnboardingSnapshotConflictError
from app.gemini.client import create_genai_client
from app.gemini.errors import GeminiError
from app.onboarding.flow import OnboardingValidationError
from app.onboarding.service import (
    IdempotencyKeyReusedError,
    OnboardingAlreadyCompletedError,
    OnboardingResultNotReadyError,
    OnboardingRevisionConflictError,
    OnboardingSessionNotFoundError,
)
from app.onboarding.stores import OnboardingSessionBusyError
from app.plans.errors import PlanDomainError

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "자체 계정 가입·로그인, JWT access token과 현재 인증 사용자 조회",
    },
    {
        "name": "onboarding",
        "description": ("Gemini 자유대화, review snapshot 조회·수정, confirm과 프로필 확정 저장"),
    },
    {
        "name": "profile",
        "description": "온보딩으로 확정 저장된 프로필과 추적 가능한 준비도 평가 조회",
    },
    {
        "name": "plan-proposals",
        "description": "프로필 기반 계획 제안 생성·window 조회와 수락·거절 lifecycle",
    },
    {
        "name": "plans",
        "description": "활성·완료 plan window 조회, task 진행 상태 변경과 plan 완료",
    },
    {
        "name": "notices",
        "description": "현재 게시 중인 고정·일반 공지 조회",
    },
    {
        "name": "quests",
        "description": "KST 오늘 퀘스트 조회와 완료 상태 변경",
    },
    {
        "name": "saved-jobs",
        "description": "모든 인증 사용자가 공유하는 저장 공고 조회",
    },
]


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details or {},
            }
        },
    )


def build_lifespan(
    settings_override: Settings | None,
) -> Callable[[FastAPI], AsyncIterator[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = settings_override or Settings()  # type: ignore[call-arg]
        pool = create_pool(settings)
        redis = Redis.from_url(settings.upstash_redis_url, decode_responses=True)
        gemini_client = create_genai_client(settings)
        pool_opened = False
        try:
            await pool.open(wait=True)
            pool_opened = True
            await redis.ping()
            app.state.settings = settings
            app.state.db_pool = pool
            app.state.redis = redis
            app.state.password_service = PasswordService()
            app.state.token_service = build_token_service(settings)
            app.state.gemini_client = gemini_client
            yield
        finally:
            await gemini_client.aio.aclose()
            await redis.aclose()
            if pool_opened:
                await pool.close()

    return lifespan


def create_app(
    *,
    settings: Settings | None = None,
    lifespan_enabled: bool = True,
) -> FastAPI:
    lifespan = build_lifespan(settings) if lifespan_enabled else None
    app = FastAPI(
        title="AI Job Coach API",
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.include_router(api_router)

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request,
        exc: InvalidCredentialsError,
    ) -> JSONResponse:
        return error_response(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message=str(exc),
        )

    @app.exception_handler(LoginIdAlreadyExistsError)
    async def login_id_already_exists_handler(
        request: Request,
        exc: LoginIdAlreadyExistsError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="LOGIN_ID_ALREADY_EXISTS",
            message=str(exc),
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return error_response(
            status_code=401,
            code="UNAUTHORIZED",
            message="인증이 필요합니다.",
        )

    @app.exception_handler(OnboardingValidationError)
    async def onboarding_validation_handler(
        request: Request,
        exc: OnboardingValidationError,
    ) -> JSONResponse:
        return error_response(
            status_code=422,
            code="ONBOARDING_VALIDATION_ERROR",
            message=str(exc),
        )

    @app.exception_handler(OnboardingSessionNotFoundError)
    async def onboarding_session_handler(
        request: Request,
        exc: OnboardingSessionNotFoundError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="ONBOARDING_SESSION_EXPIRED",
            message="온보딩 세션이 만료되었습니다. 다시 시작해주세요.",
        )

    @app.exception_handler(OnboardingSessionBusyError)
    async def onboarding_busy_handler(
        request: Request,
        exc: OnboardingSessionBusyError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="ONBOARDING_REQUEST_IN_PROGRESS",
            message="이전 온보딩 요청을 처리 중입니다. 잠시 후 다시 시도해주세요.",
            retryable=True,
        )

    @app.exception_handler(OnboardingResultNotReadyError)
    async def onboarding_result_not_ready_handler(
        request: Request,
        exc: OnboardingResultNotReadyError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="ONBOARDING_RESULT_NOT_READY",
            message="온보딩 결과가 아직 준비되지 않았습니다.",
        )

    @app.exception_handler(OnboardingAlreadyCompletedError)
    async def onboarding_already_completed_handler(
        request: Request,
        exc: OnboardingAlreadyCompletedError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="ONBOARDING_ALREADY_COMPLETED",
            message="이미 완료된 온보딩 세션입니다. 저장된 프로필을 조회해주세요.",
        )

    @app.exception_handler(IdempotencyKeyReusedError)
    async def idempotency_reused_handler(
        request: Request,
        exc: IdempotencyKeyReusedError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message="request_id가 다른 요청 payload에 이미 사용되었습니다.",
        )

    @app.exception_handler(OnboardingRevisionConflictError)
    async def onboarding_revision_handler(
        request: Request,
        exc: OnboardingRevisionConflictError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="ONBOARDING_REVISION_CONFLICT",
            message="화면의 프로필 revision이 최신 상태와 다릅니다.",
        )

    @app.exception_handler(OnboardingSnapshotConflictError)
    async def onboarding_snapshot_handler(
        request: Request,
        exc: OnboardingSnapshotConflictError,
    ) -> JSONResponse:
        return error_response(
            status_code=409,
            code="ONBOARDING_SNAPSHOT_CONFLICT",
            message="같은 request_id에 다른 프로필 snapshot이 저장되어 있습니다.",
        )

    @app.exception_handler(GeminiError)
    async def gemini_error_handler(request: Request, exc: GeminiError) -> JSONResponse:
        return error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=str(exc),
            retryable=exc.retryable,
        )

    @app.exception_handler(ProfileNotFoundError)
    async def profile_not_found_handler(
        request: Request,
        exc: ProfileNotFoundError,
    ) -> JSONResponse:
        return error_response(
            status_code=404,
            code="PROFILE_NOT_FOUND",
            message="저장된 프로필이 없습니다.",
        )

    @app.exception_handler(PlanDomainError)
    async def plan_domain_error_handler(
        request: Request,
        exc: PlanDomainError,
    ) -> JSONResponse:
        return error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.default_message,
            retryable=exc.retryable,
            details=exc.safe_details,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        safe_errors = [
            {
                "location": list(error.get("loc", ())),
                "message": error.get("msg", "입력값이 올바르지 않습니다."),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        return error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="요청 입력값을 확인해주세요.",
            details={"errors": safe_errors},
        )

    async def infrastructure_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return error_response(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="일시적으로 서비스를 사용할 수 없습니다.",
            retryable=True,
        )

    app.add_exception_handler(psycopg.Error, infrastructure_error_handler)
    app.add_exception_handler(RedisError, infrastructure_error_handler)
    return app


app = create_app()
