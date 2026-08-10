"""AI 응답 사용자 피드백의 데이터 접근 계층."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.supabase_config import get_supabase
from app.schemas.feedback_schema import FeedbackCreate


APP_SCHEMA = "app"
FEEDBACK_TABLE = "feedback"


class FeedbackRepositoryError(RuntimeError):
    """피드백 DB 작업에 실패했을 때 발생한다."""


class FeedbackRepository:
    """`app.feedback` 테이블에 접근한다."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase()
        return self._client

    def get_feedback(
        self,
        log_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any] | None:
        """사용자가 해당 로그에 남긴 피드백을 반환한다."""

        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(FEEDBACK_TABLE)
                .select("*")
                .eq("log_id", str(log_id))
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise FeedbackRepositoryError(
                "피드백 조회에 실패했습니다."
            ) from exc

        if not response.data:
            return None

        return response.data[0]

    def upsert_feedback(
        self,
        log_id: UUID,
        user_id: UUID,
        feedback: FeedbackCreate,
    ) -> dict[str, Any]:
        """피드백을 생성하거나 기존 사용자의 평가를 갱신한다."""

        payload = {
            "log_id": str(log_id),
            "user_id": str(user_id),
            **feedback.model_dump(mode="json"),
        }

        try:
            response = (
                self.client.schema(APP_SCHEMA)
                .table(FEEDBACK_TABLE)
                .upsert(
                    payload,
                    on_conflict="log_id,user_id",
                )
                .execute()
            )
        except (APIError, httpx.HTTPError) as exc:
            raise FeedbackRepositoryError(
                "피드백 저장에 실패했습니다."
            ) from exc

        if not response.data:
            raise FeedbackRepositoryError(
                "피드백 저장 결과가 반환되지 않았습니다."
            )

        return response.data[0]
