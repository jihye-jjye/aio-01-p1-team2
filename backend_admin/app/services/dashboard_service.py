"""관리자 대시보드 응답 구성 Service."""

from app.repositories.dashboard_repository import (
    DashboardRepository,
    DashboardRepositoryError,
)
from pydantic import ValidationError

from app.schemas.dashboard_schema import AdminDashboardResponse
from app.services.exceptions import DashboardStorageError


class DashboardService:
    def __init__(
        self,
        repository: DashboardRepository | None = None,
    ) -> None:
        self.repository = repository or DashboardRepository()

    def get_dashboard(self, days: int) -> AdminDashboardResponse:
        try:
            row = self.repository.get_dashboard(days)
        except DashboardRepositoryError as exc:
            raise DashboardStorageError(
                "관리자 대시보드를 조회할 수 없습니다."
            ) from exc

        try:
            return AdminDashboardResponse.model_validate(row)
        except ValidationError as exc:
            raise DashboardStorageError(
                "대시보드 집계 결과 형식이 올바르지 않습니다."
            ) from exc
