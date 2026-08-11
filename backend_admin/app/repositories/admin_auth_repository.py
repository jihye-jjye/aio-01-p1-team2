"""관리자 인증용 user_accounts 데이터 접근 계층."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase


APP_SCHEMA = "app"
USER_TABLE = "user_accounts"
ADMIN_AUTH_COLUMNS = (
    "id,login_id,password_hash,role,is_active,failed_login_count,locked_until"
)


class AdminAuthRepositoryError(RuntimeError):
    """관리자 인증 DB 작업 실패."""


class AdminAuthRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def get_account_by_login_id(
        self,
        login_id: str,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(USER_TABLE)
                .select(ADMIN_AUTH_COLUMNS)
                .ilike("login_id", login_id)
                .limit(1)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise AdminAuthRepositoryError(
                "관리자 계정을 조회할 수 없습니다."
            ) from exc

        if not response.data:
            return None
        return dict(response.data[0])

    def record_login_success(self, admin_id: UUID) -> None:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(USER_TABLE)
                .update(
                    {
                        "last_login_at": datetime.now(timezone.utc).isoformat(),
                        "failed_login_count": 0,
                        "locked_until": None,
                    }
                )
                .eq("id", str(admin_id))
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise AdminAuthRepositoryError(
                "관리자 로그인 정보를 갱신할 수 없습니다."
            ) from exc

        if not response.data:
            raise AdminAuthRepositoryError(
                "관리자 로그인 정보가 갱신되지 않았습니다."
            )
