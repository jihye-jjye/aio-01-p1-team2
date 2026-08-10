"""사용자 화면용 공지사항 조회 API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.notice_schema import (
    NoticeListResponse,
    NoticeQueryParams,
    NoticeResponse,
)
from app.services.exceptions import NoticeNotFoundError, NoticeStorageError
from app.services.notice_service import NoticeService


notice_router = APIRouter(
    prefix="/api/v1/notices",
    tags=["Notice"],
)
notice_service = NoticeService()


@notice_router.get("", response_model=NoticeListResponse)
def get_notices(
    params: Annotated[NoticeQueryParams, Query()],
) -> NoticeListResponse:
    try:
        return notice_service.get_notices(params)
    except NoticeStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@notice_router.get("/{notice_id}", response_model=NoticeResponse)
def get_notice(notice_id: UUID) -> NoticeResponse:
    try:
        return notice_service.get_notice(notice_id)
    except NoticeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NoticeStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
