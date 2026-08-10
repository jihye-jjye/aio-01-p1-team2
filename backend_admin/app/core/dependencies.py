"""JWT 인증과 관리자 권한을 확인하는 FastAPI 의존성."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.core.jwt import TokenValidationError, decode_access_token
from app.core.supabase_config import get_supabase


APP_SCHEMA = "app"
USER_TABLE = "user_accounts"
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """인증과 권한 검사에 필요한 최소 사용자 정보."""

    id: UUID
    login_id: str
    role: Literal["user", "admin"]
    is_active: bool
    locked_until: datetime | None = None


def _authentication_error(message: str = "인증이 필요합니다.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_access_token(token: str) -> UUID:
    try:
        return decode_access_token(token)
    except RuntimeError:
        raise
    except TokenValidationError as exc:
        raise _authentication_error("유효하지 않거나 만료된 토큰입니다.") from exc


def _get_user(user_id: UUID) -> CurrentUser | None:
    try:
        response = (
            get_supabase()
            .schema(APP_SCHEMA)
            .table(USER_TABLE)
            .select("id,login_id,role,is_active,locked_until")
            .eq("id", str(user_id))
            .limit(1)
            .execute()
        )
    except (APIError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="인증 저장소를 사용할 수 없습니다.",
        ) from exc

    if not response.data:
        return None

    return CurrentUser.model_validate(response.data[0])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> CurrentUser:
    """Bearer JWT를 검증하고 활성 사용자 정보를 반환한다."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()

    user_id = _decode_access_token(credentials.credentials)
    user = _get_user(user_id)

    if user is None:
        raise _authentication_error("사용자를 찾을 수 없습니다.")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    if user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="잠긴 계정입니다.",
            )

    return user
