"""관리자 사용자 목록·상세·상태 변경 API."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.user_admin_schema import (
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserQueryParams,
    AdminUserUpdate,
)
from app.services.exceptions import (
    UserAdminStorageError,
    UserNotFoundError,
)
from app.services.user_admin_service import UserAdminService


user_admin_router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["User Admin"],
)
user_admin_service = UserAdminService()


def _raise_user_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, UserNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@user_admin_router.get("", response_model=AdminUserListResponse)
def get_users(
    params: Annotated[AdminUserQueryParams, Query()],
) -> AdminUserListResponse:
    try:
        return user_admin_service.get_users(params)
    except UserAdminStorageError as exc:
        _raise_user_http_error(exc)


@user_admin_router.get(
    "/{user_id}",
    response_model=AdminUserDetail,
)
def get_user_detail(user_id: UUID) -> AdminUserDetail:
    try:
        return user_admin_service.get_user_detail(user_id)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


@user_admin_router.patch(
    "/{user_id}",
    response_model=AdminUserDetail,
)
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
) -> AdminUserDetail:
    try:
        return user_admin_service.update_user(user_id, payload)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


@user_admin_router.delete(
    "/{user_id}",
    response_model=AdminUserDetail,
    summary="사용자 영구 삭제",
)
def delete_user(user_id: UUID) -> AdminUserDetail:
    try:
        return user_admin_service.delete_user(user_id)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)
