"""공지사항 CRUD 데이터 접근 계층."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase
from app.schemas.notice_schema import (
    NoticeCreate,
    NoticeQueryParams,
    NoticeUpdate,
)


APP_SCHEMA = "app"
NOTICE_TABLE = "notices"
NOTICE_COLUMNS = "id,title,content,created_at,updated_at"


class NoticeRepositoryError(RuntimeError):
    """공지사항 DB 작업 실패."""


class NoticeRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def create_notice(self, notice: NoticeCreate) -> dict[str, Any]:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(NOTICE_TABLE)
                .insert(notice.model_dump(mode="json"))
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise NoticeRepositoryError(
                "공지사항을 등록할 수 없습니다."
            ) from exc

        if not response.data:
            raise NoticeRepositoryError(
                "공지사항 등록 결과가 반환되지 않았습니다."
            )
        return response.data[0]

    def get_notices(
        self,
        params: NoticeQueryParams,
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (params.page - 1) * params.size
        range_end = offset + params.size - 1

        try:
            query = (
                self.client.schema(APP_SCHEMA)
                .table(NOTICE_TABLE)
                .select(NOTICE_COLUMNS, count="exact")
            )
            if params.search is not None:
                query = query.ilike("title", f"%{params.search}%")
            response = (
                query.order("created_at", desc=True)
                .range(offset, range_end)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise NoticeRepositoryError(
                "공지사항 목록을 조회할 수 없습니다."
            ) from exc

        return list(response.data or []), int(response.count or 0)

    def get_notice_by_id(self, notice_id: UUID) -> dict[str, Any] | None:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(NOTICE_TABLE)
                .select(NOTICE_COLUMNS)
                .eq("id", str(notice_id))
                .limit(1)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise NoticeRepositoryError(
                "공지사항을 조회할 수 없습니다."
            ) from exc

        if not response.data:
            return None
        return response.data[0]

    def update_notice(
        self,
        notice_id: UUID,
        notice: NoticeUpdate,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(NOTICE_TABLE)
                .update(notice.model_dump(exclude_none=True, mode="json"))
                .eq("id", str(notice_id))
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise NoticeRepositoryError(
                "공지사항을 수정할 수 없습니다."
            ) from exc

        if not response.data:
            return None
        return response.data[0]

    def delete_notice(self, notice_id: UUID) -> dict[str, Any] | None:
        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(NOTICE_TABLE)
                .delete()
                .eq("id", str(notice_id))
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise NoticeRepositoryError(
                "공지사항을 삭제할 수 없습니다."
            ) from exc

        if not response.data:
            return None
        return response.data[0]
