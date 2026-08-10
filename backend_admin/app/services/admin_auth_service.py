"""고정 관리자 자격 확인 및 JWT 발급 Service."""

from __future__ import annotations

import hmac
import os

from dotenv import load_dotenv

from app.core.jwt import create_admin_access_token
from app.core.password import verify_password
from app.core.supabase_config import ENV_PATH
from app.schemas.admin_auth_schema import (
    AdminLoginRequest,
    AdminTokenResponse,
)
from app.services.exceptions import (
    AdminAuthenticationError,
    AdminAuthStorageError,
)


class AdminAuthService:
    def login(self, request: AdminLoginRequest) -> AdminTokenResponse:
        try:
            login_id, password_hash = self._get_fixed_admin_settings()
        except RuntimeError as exc:
            raise AdminAuthStorageError(
                "고정 관리자 인증 설정을 사용할 수 없습니다."
            ) from exc

        id_matches = hmac.compare_digest(request.login_id, login_id)
        password_matches = verify_password(
            request.password,
            password_hash,
        )
        if not id_matches or not password_matches:
            raise AdminAuthenticationError(
                "아이디 또는 비밀번호가 올바르지 않습니다."
            )

        try:
            token, expires_in = create_admin_access_token()
        except RuntimeError as exc:
            raise AdminAuthStorageError(
                "관리자 로그인을 완료할 수 없습니다."
            ) from exc

        return AdminTokenResponse(
            access_token=token,
            expires_in=expires_in,
        )

    @staticmethod
    def _get_fixed_admin_settings() -> tuple[str, str]:
        load_dotenv(ENV_PATH)
        login_id = os.getenv("ADMIN_LOGIN_ID", "").strip()
        password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()

        if not login_id or login_id.startswith("your-"):
            raise RuntimeError("ADMIN_LOGIN_ID를 설정해 주세요.")
        if not password_hash or password_hash.startswith("your-"):
            raise RuntimeError("ADMIN_PASSWORD_HASH를 설정해 주세요.")
        return login_id, password_hash
