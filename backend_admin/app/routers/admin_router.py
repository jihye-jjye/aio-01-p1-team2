"""관리자 로그 목록, 상세 및 KPI API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.log_schema import (
    LogListResponse,
    LogQueryParams,
    LogResponse,
    LogSummaryResponse,
)
from app.services.admin_service import AdminService
from app.services.exceptions import LogNotFoundError, LogStorageError


admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
)
admin_service = AdminService()


@admin_router.get(
    "/logs/summary",
    response_model=LogSummaryResponse,
    summary="AI 로그 KPI 조회",
)
def get_log_summary() -> LogSummaryResponse:
    try:
        return admin_service.get_log_summary()
    except LogStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@admin_router.get(
    "/logs",
    response_model=LogListResponse,
    summary="AI 로그 목록 조회",
)
def get_logs(
    params: Annotated[LogQueryParams, Query()],
) -> LogListResponse:
    try:
        return admin_service.get_logs(params)
    except LogStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@admin_router.get(
    "/logs/{log_id}",
    response_model=LogResponse,
    summary="AI 로그 상세 조회",
)
def get_log_detail(log_id: UUID) -> LogResponse:
    try:
        return admin_service.get_log_detail(log_id)
    except LogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LogStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
