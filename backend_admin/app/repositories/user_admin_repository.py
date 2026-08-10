"""관리자 사용자 목록·상세·수정·삭제 데이터 접근 계층."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase
from app.schemas.user_admin_schema import AdminUserQueryParams


APP_SCHEMA = "app"
USER_TABLE = "user_accounts"
PROFILE_TABLE = "profiles"
USER_ACCOUNT_COLUMNS = (
    "id,login_id,role,user_exp,last_login_at,is_active,"
    "failed_login_count,locked_until,created_at,updated_at"
)
PROFILE_COLUMNS = (
    "user_id,target_role,skills,experience_summary,target_date,target_company,"
    "preferred_environment,assistant_style,daily_notification_time,"
    "assessment_score,assessment_level,assessment_summary,assessed_at,"
    "assessment_version,assessment_result_id,onboarding_completed_at,"
    "created_at,updated_at"
)
USER_LIST_COLUMNS = USER_ACCOUNT_COLUMNS + ",profiles(" + PROFILE_COLUMNS + ")"


class UserAdminRepositoryError(RuntimeError):
    """사용자 관리 DB 작업 실패."""


class UserAdminRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def get_users(
        self,
        params: AdminUserQueryParams,
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (params.page - 1) * params.size
        range_end = offset + params.size - 1

        try:
            query = (
                self.client.schema(APP_SCHEMA)
                .table(USER_TABLE)
                .select(USER_LIST_COLUMNS, count="exact")
            )

            if params.search is not None:
                try:
                    search_id = UUID(params.search)
                except ValueError:
                    query = query.ilike("login_id", f"%{params.search}%")
                else:
                    query = query.eq("id", str(search_id))

            if params.role is not None:
                query = query.eq("role", params.role.value)
            if params.is_active is not None:
                query = query.eq("is_active", params.is_active)

            response = (
                query.order("created_at", desc=True)
                .range(offset, range_end)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise UserAdminRepositoryError(
                "사용자 목록을 조회할 수 없습니다."
            ) from exc

        rows = [self._normalize_profile(row) for row in (response.data or [])]
        return rows, int(response.count or 0)

    @staticmethod
    def _normalize_profile(row: dict[str, Any]) -> dict[str, Any]:
        """PostgREST의 관계 이름 `profiles`를 API 응답 이름 `profile`로 바꾼다."""

        normalized = dict(row)
        profile = normalized.pop("profiles", None)
        if isinstance(profile, list):
            profile = profile[0] if profile else None
        normalized["profile"] = profile
        return normalized

    def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        try:
            account_response = (
                self.client.schema(APP_SCHEMA)
                .table(USER_TABLE)
                .select(USER_ACCOUNT_COLUMNS)
                .eq("id", str(user_id))
                .limit(1)
                .execute()
            )
            if not account_response.data:
                return None

            profile_response = (
                self.client.schema(APP_SCHEMA)
                .table(PROFILE_TABLE)
                .select(PROFILE_COLUMNS)
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise UserAdminRepositoryError(
                "사용자 상세 정보를 조회할 수 없습니다."
            ) from exc

        account = dict(account_response.data[0])
        account["profile"] = (
            profile_response.data[0]
            if profile_response.data
            else None
        )
        return account

    def update_user_active(
        self,
        user_id: UUID,
        *,
        is_active: bool,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(USER_TABLE)
                .update({"is_active": is_active})
                .eq("id", str(user_id))
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise UserAdminRepositoryError(
                "사용자 상태를 수정할 수 없습니다."
            ) from exc

        if not response.data:
            return None
        return response.data[0]

    def delete_user(self, user_id: UUID) -> dict[str, Any] | None:
        """사용자 계정 행을 실제로 삭제하고 삭제된 row를 반환한다."""

        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(USER_TABLE)
                .delete()
                .eq("id", str(user_id))
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise UserAdminRepositoryError(
                "사용자를 삭제할 수 없습니다."
            ) from exc

        if not response.data:
            return None
        return response.data[0]
