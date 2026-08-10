from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.errors import UnauthorizedError
from app.auth.models import CurrentUser
from app.auth.passwords import PasswordService
from app.auth.service import AuthService
from app.auth.stores import RedisRefreshTokenStore
from app.auth.tokens import InvalidAccessTokenError, TokenService
from app.core.config import Settings
from app.db.plan_repository import PsycopgPlanProposalRepository
from app.db.repositories import PsycopgAccountRepository, PsycopgProfileRepository
from app.gemini.adapter import GeminiOnboardingAdapter
from app.gemini.errors import GeminiError
from app.gemini.job_recommendation_adapter import GeminiSavedJobRecommendationAdapter
from app.gemini.plan_adapter import (
    GeminiProfilePlanAdapter,
)
from app.gemini.plan_adapter import (
    normalize_plan_generation_error as normalize_gemini_plan_generation_error,
)
from app.gemini.rate_limit import RedisGeminiRateLimiter
from app.gemini.structured import GeminiStructuredClient
from app.notices.repository import PsycopgNoticeRepository
from app.notices.service import NoticeService
from app.onboarding.service import OnboardingService
from app.onboarding.stores import RedisOnboardingSessionLock, RedisOnboardingSessionStore
from app.plans.errors import PlanDomainError
from app.plans.generation import ProfilePlanGenerator
from app.plans.service import PlanManagementService, PlanProposalService
from app.plans.stores import RedisPlanGenerationLock, RedisPlanGenerationStore
from app.profiles.models import ProfileRecord
from app.saved_jobs.repository import PsycopgSavedJobRepository
from app.saved_jobs.service import SavedJobService

bearer_scheme = HTTPBearer(auto_error=False)


def normalize_plan_generation_error(group: BaseExceptionGroup) -> Exception | None:
    def leaves(value: BaseExceptionGroup) -> list[BaseException]:
        return [
            leaf
            for error in value.exceptions
            for leaf in (leaves(error) if isinstance(error, BaseExceptionGroup) else [error])
        ]

    errors = leaves(group)
    if any(not isinstance(error, (GeminiError, RedisError, PlanDomainError)) for error in errors):
        return None
    if any(isinstance(error, RedisError) for error in errors):
        return RedisError("Redis checkpoint operation failed.")
    domain_errors = [error for error in errors if isinstance(error, PlanDomainError)]
    if domain_errors:
        return type(domain_errors[0])()
    return normalize_gemini_plan_generation_error(group)


class ProfileReader(Protocol):
    async def get_by_user_id(self, user_id: UUID) -> ProfileRecord | None: ...


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.db_pool


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_password_service(request: Request) -> PasswordService:
    return request.app.state.password_service


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


def get_gemini_async_client(request: Request) -> Any:
    return request.app.state.gemini_client.aio


def get_auth_service(
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    redis: Annotated[Redis, Depends(get_redis)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    return AuthService(
        accounts=PsycopgAccountRepository(pool),
        passwords=passwords,
        tokens=tokens,
        refresh_tokens=RedisRefreshTokenStore(redis),
    )


def get_onboarding_service(
    settings: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    redis: Annotated[Redis, Depends(get_redis)],
    gemini_client: Annotated[Any, Depends(get_gemini_async_client)],
) -> OnboardingService:
    adapter = GeminiOnboardingAdapter(
        client=gemini_client,
        limiter=RedisGeminiRateLimiter(redis),
        model=settings.gemini_model,
        api_version=settings.gemini_api_version,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_attempts=settings.gemini_max_attempts,
    )
    return OnboardingService(
        sessions=RedisOnboardingSessionStore(redis),
        profiles=PsycopgProfileRepository(pool),
        conversation=adapter,
        assessor=adapter,
        session_lock=RedisOnboardingSessionLock(
            redis,
            timeout_seconds=(
                settings.gemini_timeout_seconds * settings.gemini_max_attempts * 2 + 30
            ),
        ),
        profile_reader=PsycopgProfileRepository(pool),
        today_provider=lambda: datetime.now(ZoneInfo("Asia/Seoul")).date(),
        session_ttl_seconds=settings.onboarding_session_ttl_seconds,
    )


def get_profile_reader(
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> ProfileReader:
    return PsycopgProfileRepository(pool)


def get_plan_proposal_service(
    settings: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    redis: Annotated[Redis, Depends(get_redis)],
    gemini_client: Annotated[Any, Depends(get_gemini_async_client)],
) -> PlanProposalService:
    limiter = RedisGeminiRateLimiter(redis)
    structured = GeminiStructuredClient(
        client=gemini_client,
        limiter=limiter,
        model=settings.gemini_model,
        api_version=settings.gemini_api_version,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_attempts=settings.gemini_max_attempts,
    )
    adapter = GeminiProfilePlanAdapter(structured)
    today_provider = lambda: datetime.now(ZoneInfo("Asia/Seoul")).date()
    return PlanProposalService(
        repository=PsycopgPlanProposalRepository(pool, today_provider=today_provider),
        checkpoints=RedisPlanGenerationStore(redis),
        request_lock=RedisPlanGenerationLock(redis),
        generator=ProfilePlanGenerator(
            outline_port=adapter,
            task_port=adapter,
            revision_port=adapter,
        ),
        today_provider=today_provider,
        generation_error_normalizer=normalize_plan_generation_error,
    )


def get_plan_management_service(
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> PlanManagementService:
    today_provider = lambda: datetime.now(ZoneInfo("Asia/Seoul")).date()
    return PlanManagementService(
        repository=PsycopgPlanProposalRepository(pool, today_provider=today_provider),
        today_provider=today_provider,
    )


def get_notice_service(
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> NoticeService:
    return NoticeService(PsycopgNoticeRepository(pool))


def get_saved_job_service(
    settings: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    redis: Annotated[Redis, Depends(get_redis)],
    gemini_client: Annotated[Any, Depends(get_gemini_async_client)],
) -> SavedJobService:
    structured = GeminiStructuredClient(
        client=gemini_client,
        limiter=RedisGeminiRateLimiter(redis),
        model=settings.gemini_model,
        api_version=settings.gemini_api_version,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_attempts=settings.gemini_max_attempts,
    )
    return SavedJobService(
        PsycopgSavedJobRepository(pool),
        recommender=GeminiSavedJobRecommendationAdapter(structured),
        today_provider=lambda: datetime.now(ZoneInfo("Asia/Seoul")).date(),
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise UnauthorizedError
    try:
        return tokens.decode_access(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise UnauthorizedError from exc


def build_token_service(settings: Settings) -> TokenService:
    return TokenService(
        secret_key=settings.jwt_secret_key,
        access_ttl=timedelta(minutes=settings.access_token_expire_minutes),
        refresh_ttl=timedelta(days=settings.refresh_token_expire_days),
        algorithm=settings.jwt_algorithm,
    )
