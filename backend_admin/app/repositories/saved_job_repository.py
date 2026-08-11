"""saved_jobs 읽기 전용 데이터 접근 계층."""

from __future__ import annotations

from typing import Any

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase
from app.schemas.saved_job_schema import SavedJobQueryParams


APP_SCHEMA = "app"
SAVED_JOB_TABLE = "saved_jobs"
SAVED_JOB_COLUMNS = (
    "id,source_type,source_url,source_key,company_name,job_title,"
    "deadline,posting_text,extracted_data,created_at,updated_at"
)


class SavedJobRepositoryError(RuntimeError):
    """취업 공고 DB 조회 실패."""


class SavedJobRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def get_saved_jobs(
        self,
        params: SavedJobQueryParams,
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (params.page - 1) * params.size
        range_end = offset + params.size - 1

        try:
            query = (
                self.client.schema(APP_SCHEMA)
                .table(SAVED_JOB_TABLE)
                .select(SAVED_JOB_COLUMNS, count="exact")
            )
            if params.source_type is not None:
                query = query.eq("source_type", params.source_type)

            response = (
                query.order("created_at", desc=True)
                .range(offset, range_end)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise SavedJobRepositoryError(
                "취업 공고 목록을 조회할 수 없습니다."
            ) from exc

        return list(response.data or []), int(response.count or 0)
