from typing import Protocol

from app.saved_jobs.models import SavedJobView


class SavedJobRepositoryPort(Protocol):
    async def list_all(self) -> list[SavedJobView]: ...


class SavedJobService:
    def __init__(self, repository: SavedJobRepositoryPort) -> None:
        self._repository = repository

    async def list_saved_jobs(self) -> list[SavedJobView]:
        return await self._repository.list_all()
