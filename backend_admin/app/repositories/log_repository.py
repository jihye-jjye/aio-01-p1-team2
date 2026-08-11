"""AI 로그 테이블과 관리자 KPI View의 데이터 접근 계층."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase
from app.schemas.log_schema import LogCreate, LogQueryParams


APP_SCHEMA = "app"
LOG_TABLE = "ai_logs"
LOG_SUMMARY_VIEW = "admin_log_summary"


class LogRepositoryError(RuntimeError):
    """AI 로그 DB 작업에 실패했을 때 발생한다."""


class LogRepository:
    """`app.ai_logs`와 `app.admin_log_summary`에 접근한다.

    Client를 전달하지 않으면 실제 Supabase Client를 지연 생성한다. 테스트에서는
    가짜 Client를 주입할 수 있어 환경 변수나 네트워크가 필요하지 않다.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def create_log(self, log: LogCreate) -> dict[str, Any]:
        """AI 로그 한 건을 저장하고 생성된 row를 반환한다."""

        payload = log.model_dump(mode="json", exclude_none=True)

        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(LOG_TABLE)
                .insert(payload)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise LogRepositoryError("AI 로그 저장에 실패했습니다.") from exc

        if not response.data:
            raise LogRepositoryError(
                "AI 로그 저장 결과가 반환되지 않았습니다."
            )

        return response.data[0]

    def get_logs(
        self,
        params: LogQueryParams,
    ) -> tuple[list[dict[str, Any]], int]:
        """필터와 페이지 조건에 맞는 로그 목록 및 전체 개수를 반환한다."""

        offset = (params.page - 1) * params.size
        range_end = offset + params.size - 1

        try:
            query = (
                self.client.schema(APP_SCHEMA)
                .table(LOG_TABLE)
                .select("*", count="exact")
            )

            if params.level is not None:
                query = query.eq("level", params.level.value)

            if params.endpoint is not None:
                query = query.eq("endpoint", params.endpoint)

            if params.start_at is not None:
                query = query.gte(
                    "created_at",
                    params.start_at.isoformat(),
                )

            if params.end_at is not None:
                query = query.lte(
                    "created_at",
                    params.end_at.isoformat(),
                )

            response = (
                query.order("created_at", desc=True)
                .range(offset, range_end)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise LogRepositoryError("AI 로그 조회에 실패했습니다.") from exc

        return list(response.data or []), int(response.count or 0)

    def get_log_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        """ID에 해당하는 로그를 반환하며, 없으면 None을 반환한다."""

        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(LOG_TABLE)
                .select("*")
                .eq("id", str(log_id))
                .limit(1)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise LogRepositoryError(
                "AI 로그 상세 조회에 실패했습니다."
            ) from exc

        if not response.data:
            return None

        return response.data[0]

    def get_log_summary(self) -> dict[str, Any]:
        """관리자 대시보드의 전체 기간 KPI를 반환한다."""

        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(LOG_SUMMARY_VIEW)
                .select("*")
                .limit(1)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise LogRepositoryError("로그 KPI 조회에 실패했습니다.") from exc

        if not response.data:
            return {
                "total_requests": 0,
                "error_count": 0,
                "error_rate": 0.0,
                "average_latency_ms": 0.0,
            }

        return response.data[0]
