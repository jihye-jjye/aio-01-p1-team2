"""공지사항 CRUD 및 목록 구성 Service."""

from math import ceil
from uuid import UUID

from app.repositories.notice_repository import (
    NoticeRepository,
    NoticeRepositoryError,
)
from app.schemas.notice_schema import (
    NoticeCreate,
    NoticeListResponse,
    NoticeQueryParams,
    NoticeResponse,
    NoticeUpdate,
)
from app.services.exceptions import (
    NoticeNotFoundError,
    NoticeStorageError,
)


class NoticeService:
    def __init__(
        self,
        repository: NoticeRepository | None = None,
    ) -> None:
        self.repository = repository or NoticeRepository()

    def create_notice(self, payload: NoticeCreate) -> NoticeResponse:
        try:
            row = self.repository.create_notice(payload)
        except NoticeRepositoryError as exc:
            raise NoticeStorageError(
                "공지사항을 등록할 수 없습니다."
            ) from exc
        return NoticeResponse.model_validate(row)

    def get_notices(
        self,
        params: NoticeQueryParams,
    ) -> NoticeListResponse:
        try:
            rows, total = self.repository.get_notices(params)
        except NoticeRepositoryError as exc:
            raise NoticeStorageError(
                "공지사항 목록을 조회할 수 없습니다."
            ) from exc

        return NoticeListResponse(
            items=[NoticeResponse.model_validate(row) for row in rows],
            page=params.page,
            size=params.size,
            total=total,
            total_pages=ceil(total / params.size) if total else 0,
        )

    def get_notice(self, notice_id: UUID) -> NoticeResponse:
        try:
            row = self.repository.get_notice_by_id(notice_id)
        except NoticeRepositoryError as exc:
            raise NoticeStorageError(
                "공지사항을 조회할 수 없습니다."
            ) from exc

        if row is None:
            raise NoticeNotFoundError("공지사항을 찾을 수 없습니다.")
        return NoticeResponse.model_validate(row)

    def update_notice(
        self,
        notice_id: UUID,
        payload: NoticeUpdate,
    ) -> NoticeResponse:
        try:
            row = self.repository.update_notice(notice_id, payload)
        except NoticeRepositoryError as exc:
            raise NoticeStorageError(
                "공지사항을 수정할 수 없습니다."
            ) from exc

        if row is None:
            raise NoticeNotFoundError("공지사항을 찾을 수 없습니다.")
        return NoticeResponse.model_validate(row)

    def delete_notice(self, notice_id: UUID) -> NoticeResponse:
        try:
            row = self.repository.delete_notice(notice_id)
        except NoticeRepositoryError as exc:
            raise NoticeStorageError(
                "공지사항을 삭제할 수 없습니다."
            ) from exc

        if row is None:
            raise NoticeNotFoundError("공지사항을 찾을 수 없습니다.")
        return NoticeResponse.model_validate(row)
