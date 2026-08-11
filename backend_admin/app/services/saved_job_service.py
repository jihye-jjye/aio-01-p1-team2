"""관리자용 취업 공고 목록 Service."""

from math import ceil

from app.repositories.saved_job_repository import (
    SavedJobRepository,
    SavedJobRepositoryError,
)
from app.schemas.saved_job_schema import (
    SavedJobListResponse,
    SavedJobQueryParams,
    SavedJobResponse,
)
from app.services.exceptions import SavedJobStorageError


class SavedJobService:
    def __init__(
        self,
        repository: SavedJobRepository | None = None,
    ) -> None:
        self.repository = repository or SavedJobRepository()

    def get_saved_jobs(
        self,
        params: SavedJobQueryParams,
    ) -> SavedJobListResponse:
        try:
            rows, total = self.repository.get_saved_jobs(params)
            items = [SavedJobResponse.model_validate(row) for row in rows]
        except (SavedJobRepositoryError, ValueError) as exc:
            raise SavedJobStorageError(
                "취업 공고 목록을 조회할 수 없습니다."
            ) from exc

        return SavedJobListResponse(
            items=items,
            page=params.page,
            size=params.size,
            total=total,
            total_pages=ceil(total / params.size) if total else 0,
        )
