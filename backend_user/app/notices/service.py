from typing import Protocol
from uuid import UUID

from app.notices.models import NoticeView


class NoticeRepositoryPort(Protocol):
    async def list_published(self, *, user_id: UUID) -> list[NoticeView]: ...


class NoticeService:
    def __init__(self, repository: NoticeRepositoryPort) -> None:
        self._repository = repository

    async def list_published(self, *, user_id: UUID) -> list[NoticeView]:
        return await self._repository.list_published(user_id=user_id)
