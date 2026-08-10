from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_saved_job_service
from app.api.errors import APIErrorEnvelope
from app.auth.models import CurrentUser
from app.saved_jobs.models import SavedJobRecommendationView, SavedJobView
from app.saved_jobs.service import SavedJobService

router = APIRouter(prefix="/saved-jobs", tags=["saved-jobs"])


@router.get(
    "/recommendation",
    response_model=SavedJobRecommendationView | None,
    summary="희망 환경 기반 공고 추천",
    description="현재 사용자의 온보딩 희망 환경과 가장 많은 단서가 일치하는 공고를 반환합니다.",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        404: {"model": APIErrorEnvelope, "description": "`PROFILE_NOT_FOUND`: 온보딩 프로필 없음"},
        503: {"model": APIErrorEnvelope, "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애"},
    },
)
async def recommend_saved_job(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[SavedJobService, Depends(get_saved_job_service)],
) -> SavedJobRecommendationView | None:
    return await service.recommend_saved_job(user_id=current_user.id)


@router.get(
    "",
    response_model=list[SavedJobView],
    summary="저장 공고 목록 조회",
    description="모든 사용자가 접근할 수 있는 공고를 최신 저장 순으로 반환합니다.",
    response_description="전체 저장 공고 목록",
    responses={
        401: {"model": APIErrorEnvelope, "description": "`UNAUTHORIZED`: 인증 실패"},
        503: {"model": APIErrorEnvelope, "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애"},
    },
)
async def list_saved_jobs(
    _current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[SavedJobService, Depends(get_saved_job_service)],
) -> list[SavedJobView]:
    return await service.list_saved_jobs()
