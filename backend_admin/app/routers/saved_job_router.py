"""관리자용 저장된 취업 공고 조회 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_admin
from app.schemas.saved_job_schema import (
    SavedJobListResponse,
    SavedJobQueryParams,
)
from app.services.exceptions import SavedJobStorageError
from app.services.saved_job_service import SavedJobService


saved_job_router = APIRouter(
    prefix="/api/v1/admin/saved-jobs",
    tags=["Saved Job Admin"],
    dependencies=[Depends(get_current_admin)],
)
saved_job_service = SavedJobService()


@saved_job_router.get(
    "",
    response_model=SavedJobListResponse,
    summary="저장된 취업 공고 목록 조회",
    response_description=(
        "saved_jobs의 공고 정보와 page, size, total, total_pages를 반환합니다."
    ),
)
def get_saved_jobs(
    params: Annotated[SavedJobQueryParams, Query()],
) -> SavedJobListResponse:
    """최신 등록순으로 saved_jobs 테이블의 내용만 조회한다."""

    try:
        return saved_job_service.get_saved_jobs(params)
    except SavedJobStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
