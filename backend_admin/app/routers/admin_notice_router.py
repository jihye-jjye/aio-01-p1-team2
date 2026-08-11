"""관리자 공지사항 CRUD API."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_admin
from app.schemas.notice_schema import (
    NoticeCreate,
    NoticeListResponse,
    NoticeQueryParams,
    NoticeResponse,
    NoticeUpdate,
)
from app.services.exceptions import NoticeNotFoundError, NoticeStorageError
from app.services.notice_service import NoticeService


admin_notice_router = APIRouter(
    prefix="/api/v1/admin/notices",
    tags=["Notice Admin"],
    dependencies=[Depends(get_current_admin)],
)
notice_service = NoticeService()


def _raise_notice_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, NoticeNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@admin_notice_router.post(
    "",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notice(payload: NoticeCreate) -> NoticeResponse:
    try:
        return notice_service.create_notice(payload)
    except NoticeStorageError as exc:
        _raise_notice_http_error(exc)


@admin_notice_router.get("", response_model=NoticeListResponse)
def get_notices(
    params: Annotated[NoticeQueryParams, Query()],
) -> NoticeListResponse:
    try:
        return notice_service.get_notices(params)
    except NoticeStorageError as exc:
        _raise_notice_http_error(exc)


@admin_notice_router.get(
    "/{notice_id}",
    response_model=NoticeResponse,
)
def get_notice(notice_id: UUID) -> NoticeResponse:
    try:
        return notice_service.get_notice(notice_id)
    except (NoticeNotFoundError, NoticeStorageError) as exc:
        _raise_notice_http_error(exc)


@admin_notice_router.patch(
    "/{notice_id}",
    response_model=NoticeResponse,
)
def update_notice(
    notice_id: UUID,
    payload: NoticeUpdate,
) -> NoticeResponse:
    try:
        return notice_service.update_notice(notice_id, payload)
    except (NoticeNotFoundError, NoticeStorageError) as exc:
        _raise_notice_http_error(exc)


@admin_notice_router.delete(
    "/{notice_id}",
    response_model=NoticeResponse,
)
def delete_notice(notice_id: UUID) -> NoticeResponse:
    try:
        return notice_service.delete_notice(notice_id)
    except (NoticeNotFoundError, NoticeStorageError) as exc:
        _raise_notice_http_error(exc)
