"""관리자 로그인 API."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.admin_auth_schema import (
    AdminLoginRequest,
    AdminTokenResponse,
)
from app.services.admin_auth_service import AdminAuthService
from app.services.exceptions import (
    AdminAuthenticationError,
    AdminAuthStorageError,
)


admin_auth_router = APIRouter(
    prefix="/api/v1/admin/auth",
    tags=["Admin Auth"],
)
admin_auth_service = AdminAuthService()


@admin_auth_router.post(
    "/login",
    response_model=AdminTokenResponse,
    summary="관리자 로그인",
)
def login(request: AdminLoginRequest) -> AdminTokenResponse:
    try:
        return admin_auth_service.login(request)
    except AdminAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AdminAuthStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="관리자 인증 서비스를 사용할 수 없습니다.",
        ) from exc
