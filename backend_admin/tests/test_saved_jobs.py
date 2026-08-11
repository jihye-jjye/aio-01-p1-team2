from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.saved_job_repository import SavedJobRepositoryError
from app.routers import saved_job_router
from app.schemas.saved_job_schema import SavedJobQueryParams
from app.services.exceptions import SavedJobStorageError
from app.services.saved_job_service import SavedJobService


NOW = datetime(2026, 8, 11, 3, 0, tzinfo=UTC)
JOB_ID = uuid4()


def make_saved_job() -> dict[str, Any]:
    return {
        "id": str(JOB_ID),
        "source_type": "url",
        "source_url": "https://example.com/jobs/1",
        "source_key": "example-job-1",
        "company_name": "테스트 회사",
        "job_title": "백엔드 개발자",
        "deadline": date(2026, 8, 31).isoformat(),
        "posting_text": "백엔드 개발자를 채용합니다.",
        "extracted_data": {"skills": ["Python", "FastAPI"]},
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }


class FakeSavedJobRepository:
    def __init__(self, error: bool = False) -> None:
        self.error = error
        self.params: SavedJobQueryParams | None = None

    def get_saved_jobs(
        self,
        params: SavedJobQueryParams,
    ) -> tuple[list[dict[str, Any]], int]:
        self.params = params
        if self.error:
            raise SavedJobRepositoryError("DB failure")
        return [make_saved_job()], 1


def test_saved_job_service_builds_paginated_response() -> None:
    repository = FakeSavedJobRepository()
    service = SavedJobService(repository=repository)  # type: ignore[arg-type]
    params = SavedJobQueryParams(page=1, size=20)

    result = service.get_saved_jobs(params)

    assert result.total == 1
    assert result.total_pages == 1
    assert result.items[0].id == JOB_ID
    assert result.items[0].company_name == "테스트 회사"
    assert repository.params == params


def test_saved_job_service_converts_repository_error() -> None:
    service = SavedJobService(  # type: ignore[arg-type]
        repository=FakeSavedJobRepository(error=True)
    )

    with pytest.raises(SavedJobStorageError):
        service.get_saved_jobs(SavedJobQueryParams())


def test_saved_jobs_endpoint_returns_saved_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSavedJobService:
        def get_saved_jobs(self, params: SavedJobQueryParams) -> dict[str, Any]:
            assert params.source_type == "url"
            return {
                "items": [make_saved_job()],
                "page": params.page,
                "size": params.size,
                "total": 1,
                "total_pages": 1,
            }

    monkeypatch.setattr(
        saved_job_router,
        "saved_job_service",
        FakeSavedJobService(),
    )

    response = TestClient(app).get(
        "/api/v1/admin/saved-jobs",
        params={"source_type": "url"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["job_title"] == "백엔드 개발자"


def test_saved_jobs_endpoint_rejects_invalid_page() -> None:
    response = TestClient(app).get(
        "/api/v1/admin/saved-jobs",
        params={"page": 0},
    )

    assert response.status_code == 422


def test_saved_jobs_endpoint_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSavedJobService:
        def get_saved_jobs(self, params: SavedJobQueryParams) -> None:
            raise SavedJobStorageError("취업 공고 목록을 조회할 수 없습니다.")

    monkeypatch.setattr(
        saved_job_router,
        "saved_job_service",
        FailingSavedJobService(),
    )

    response = TestClient(app).get("/api/v1/admin/saved-jobs")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "취업 공고 목록을 조회할 수 없습니다."
    }
