"""관리자 대시보드 집계 함수 데이터 접근 계층."""

from __future__ import annotations

from typing import Any

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase


APP_SCHEMA = "app"
DASHBOARD_FUNCTION = "get_admin_dashboard"


class DashboardRepositoryError(RuntimeError):
    """대시보드 DB 집계 작업 실패."""


class DashboardRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def get_dashboard(self, days: int) -> dict[str, Any]:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .rpc(
                    DASHBOARD_FUNCTION,
                    {"period_days": days},
                )
                .execute()
            )
        except (APIError, httpx.HTTPError, RuntimeError) as exc:
            raise DashboardRepositoryError(
                "대시보드 데이터를 조회할 수 없습니다."
            ) from exc

        data = response.data
        if data is None:
            raise DashboardRepositoryError(
                "대시보드 집계 결과가 반환되지 않았습니다."
            )

        if isinstance(data, list):
            if not data:
                raise DashboardRepositoryError(
                    "대시보드 집계 결과가 반환되지 않았습니다."
                )
            data = data[0]

        if not isinstance(data, dict):
            raise DashboardRepositoryError(
                "대시보드 집계 결과 형식이 올바르지 않습니다."
            )

        return dict(data)
