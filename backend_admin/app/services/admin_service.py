"""관리자 로그 목록, 상세 및 KPI 조회 Service."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from app.repositories.log_repository import (
    LogRepository,
    LogRepositoryError,
)
from app.schemas.log_schema import (
    LogListResponse,
    LogQueryParams,
    LogResponse,
    LogSummaryResponse,
)
from app.services.exceptions import LogNotFoundError, LogStorageError


class AdminService:
    """관리자 화면에 필요한 AI 로그 데이터를 구성한다."""

    def __init__(
        self,
        repository: LogRepository | None = None,
    ) -> None:
        self.repository = repository or LogRepository()

    def get_logs(self, params: LogQueryParams) -> LogListResponse:
        """필터 및 pagination이 적용된 로그 목록을 반환한다."""

        try:
            rows, total = self.repository.get_logs(params)
        except LogRepositoryError as exc:
            raise LogStorageError(
                "AI 로그 목록을 조회할 수 없습니다."
            ) from exc

        items = [LogResponse.model_validate(row) for row in rows]
        total_pages = ceil(total / params.size) if total > 0 else 0

        return LogListResponse(
            items=items,
            page=params.page,
            size=params.size,
            total=total,
            total_pages=total_pages,
        )

    def get_log_detail(self, log_id: UUID) -> LogResponse:
        """로그 한 건을 반환하고, 존재하지 않으면 도메인 예외를 낸다."""

        try:
            row = self.repository.get_log_by_id(log_id)
        except LogRepositoryError as exc:
            raise LogStorageError(
                "AI 로그를 조회할 수 없습니다."
            ) from exc

        if row is None:
            raise LogNotFoundError("로그를 찾을 수 없습니다.")

        return LogResponse.model_validate(row)

    def get_log_summary(self) -> LogSummaryResponse:
        """관리자 대시보드 KPI를 API 응답 타입으로 변환한다."""

        try:
            row = self.repository.get_log_summary()
        except LogRepositoryError as exc:
            raise LogStorageError(
                "로그 KPI를 조회할 수 없습니다."
            ) from exc

        return LogSummaryResponse(
            total_requests=int(row.get("total_requests") or 0),
            error_count=int(row.get("error_count") or 0),
            error_rate=float(row.get("error_rate") or 0),
            average_latency_ms=float(
                row.get("average_latency_ms") or 0
            ),
        )
