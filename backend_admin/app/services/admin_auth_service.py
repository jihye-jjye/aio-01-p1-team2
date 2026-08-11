"""관리자 자격 검증과 Access Token 발급 Service."""

from datetime import datetime, timezone

from pydantic import ValidationError

from app.core.jwt import create_admin_access_token
from app.core.password import verify_password
from app.repositories.admin_auth_repository import (
    AdminAuthRepository,
    AdminAuthRepositoryError,
)
from app.schemas.admin_auth_schema import (
    AdminIdentity,
    AdminLoginRequest,
    AdminLoginResponse,
)
from app.services.exceptions import (
    AdminAccountDisabledError,
    AdminAuthenticationError,
    AdminAuthStorageError,
)


class AdminAuthService:
    def __init__(
        self,
        repository: AdminAuthRepository | None = None,
    ) -> None:
        self.repository = repository or AdminAuthRepository()

    def login(self, payload: AdminLoginRequest) -> AdminLoginResponse:
        login_id = payload.login_id.strip().lower()
        try:
            account = self.repository.get_account_by_login_id(login_id)
        except AdminAuthRepositoryError as exc:
            raise AdminAuthStorageError(
                "관리자 인증 저장소를 사용할 수 없습니다."
            ) from exc

        if (
            account is None
            or account.get("role") != "admin"
            or not verify_password(
                payload.password,
                str(account.get("password_hash", "")),
            )
        ):
            raise AdminAuthenticationError(
                "아이디 또는 비밀번호가 올바르지 않습니다."
            )

        if not account.get("is_active", False):
            raise AdminAccountDisabledError("비활성화된 관리자 계정입니다.")

        locked_until = account.get("locked_until")
        if locked_until is not None:
            if isinstance(locked_until, str):
                locked_until = datetime.fromisoformat(
                    locked_until.replace("Z", "+00:00")
                )
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > datetime.now(timezone.utc):
                raise AdminAccountDisabledError("잠긴 관리자 계정입니다.")

        try:
            admin = AdminIdentity.model_validate(account)
            token, expires_in = create_admin_access_token(admin.id)
            self.repository.record_login_success(admin.id)
        except AdminAuthRepositoryError as exc:
            raise AdminAuthStorageError(
                "관리자 로그인 정보를 갱신할 수 없습니다."
            ) from exc
        except (ValidationError, RuntimeError, ValueError) as exc:
            raise AdminAuthStorageError(
                "관리자 로그인을 처리할 수 없습니다."
            ) from exc

        return AdminLoginResponse(
            access_token=token,
            expires_in=expires_in,
            admin=admin,
        )
