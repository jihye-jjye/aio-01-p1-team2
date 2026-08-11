"""관리자 로그인 및 현재 관리자 조회 API."""

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentAdmin, get_current_admin
from app.schemas.admin_auth_schema import (
    AdminIdentity,
    AdminLoginRequest,
    AdminLoginResponse,
)
from app.services.admin_auth_service import AdminAuthService
from app.services.exceptions import (
    AdminAccountDisabledError,
    AdminAuthenticationError,
    AdminAuthStorageError,
)


admin_auth_router = APIRouter(
    prefix="/api/v1/admin/auth",
    tags=["Admin Auth"],
)
admin_auth_service = AdminAuthService()


def _raise_admin_auth_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, AdminAuthenticationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if isinstance(exc, AdminAccountDisabledError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@admin_auth_router.post(
    "/login",
    response_model=AdminLoginResponse,
    summary="관리자 로그인",
    description=(
        "user_accounts에서 login_id와 비밀번호를 확인하고 role이 admin인 "
        "활성 계정에만 관리자 Access Token을 발급합니다."
    ),
)
def login(payload: AdminLoginRequest) -> AdminLoginResponse:
    try:
        return admin_auth_service.login(payload)
    except (
        AdminAuthenticationError,
        AdminAccountDisabledError,
        AdminAuthStorageError,
    ) as exc:
        _raise_admin_auth_http_error(exc)


@admin_auth_router.get(
    "/me",
    response_model=AdminIdentity,
    summary="현재 관리자 확인",
)
def get_me(
    admin: Annotated[CurrentAdmin, Depends(get_current_admin)],
) -> AdminIdentity:
    return AdminIdentity(id=admin.id, login_id=admin.login_id, role="admin")
