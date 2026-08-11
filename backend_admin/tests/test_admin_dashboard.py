from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.dashboard_repository import (
    DashboardRepository,
    DashboardRepositoryError,
)
from app.routers import dashboard_router
from app.services.dashboard_service import DashboardService
from app.services.exceptions import DashboardStorageError


NOW = datetime(2026, 8, 11, 3, 0, tzinfo=UTC)


def make_dashboard_data(days: int = 7) -> dict[str, Any]:
    return {
        "generated_at": NOW.isoformat(),
        "period": {
            "days": days,
            "start_at": "2026-08-04T15:00:00+00:00",
            "end_at": NOW.isoformat(),
        },
        "users": {
            "total_users": 10,
            "active_accounts": 8,
            "inactive_accounts": 2,
            "new_users": 3,
        },
        "onboarding": {
            "profile_count": 9,
            "completed_count": 7,
            "incomplete_count": 3,
            "completion_rate": 70.0,
        },
        "assessment": {
            "assessed_users": 6,
            "average_score": 72.5,
            "level_distribution": {
                "beginner": 2,
                "intermediate": 3,
                "advanced": 1,
            },
        },
        "roadmaps": {
            "users_with_plans": 8,
            "active_plans": 6,
            "completed_plans": 2,
            "expired_plans": 1,
            "status_distribution": {
                "draft": 1,
                "active": 6,
                "completed": 2,
                "expired": 1,
                "superseded": 1,
                "rejected": 0,
            },
        },
        "quests": {
            "total": 20,
            "completed": 10,
            "in_progress": 4,
            "pending": 6,
            "completion_rate": 50.0,
            "scheduled_today": 5,
            "completed_today": 2,
            "overdue": 3,
            "interviews_today": 1,
        },
        "daily_signups": [
            {"date": "2026-08-10", "count": 1},
            {"date": "2026-08-11", "count": 2},
        ],
        "recent_users": [
            {
                "id": str(uuid4()),
                "login_id": "recent-user",
                "is_active": True,
                "user_exp": 40,
                "target_role": "backend",
                "onboarding_completed": True,
                "created_at": NOW.isoformat(),
            }
        ],
    }


class FakeDashboardRepository:
    def __init__(
        self,
        data: dict[str, Any] | None = None,
        error: bool = False,
    ) -> None:
        self.data = data or make_dashboard_data()
        self.error = error
        self.received_days: int | None = None

    def get_dashboard(self, days: int) -> dict[str, Any]:
        self.received_days = days
        if self.error:
            raise DashboardRepositoryError("DB failure")
        return self.data


def test_dashboard_service_validates_response() -> None:
    repository = FakeDashboardRepository()
    service = DashboardService(repository=repository)  # type: ignore[arg-type]

    result = service.get_dashboard(7)

    assert repository.received_days == 7
    assert result.users.total_users == 10
    assert result.quests.completion_rate == 50.0
    assert result.recent_users[0].login_id == "recent-user"


def test_dashboard_service_converts_repository_error() -> None:
    repository = FakeDashboardRepository(error=True)
    service = DashboardService(repository=repository)  # type: ignore[arg-type]

    with pytest.raises(DashboardStorageError):
        service.get_dashboard(7)


def test_dashboard_service_rejects_invalid_aggregate() -> None:
    data = make_dashboard_data()
    data["users"]["total_users"] = -1
    repository = FakeDashboardRepository(data=data)
    service = DashboardService(repository=repository)  # type: ignore[arg-type]

    with pytest.raises(DashboardStorageError):
        service.get_dashboard(7)


def test_dashboard_repository_calls_rpc() -> None:
    data = make_dashboard_data()

    class FakeRpcClient:
        def __init__(self) -> None:
            self.function_name: str | None = None
            self.parameters: dict[str, int] | None = None

        def schema(self, schema_name: str) -> "FakeRpcClient":
            assert schema_name == "app"
            return self

        def rpc(
            self,
            function_name: str,
            parameters: dict[str, int],
        ) -> "FakeRpcClient":
            self.function_name = function_name
            self.parameters = parameters
            return self

        def execute(self) -> object:
            return type("Response", (), {"data": data})()

    client = FakeRpcClient()
    repository = DashboardRepository(client=client)  # type: ignore[arg-type]

    result = repository.get_dashboard(30)

    assert result == data
    assert client.function_name == "get_admin_dashboard"
    assert client.parameters == {"period_days": 30}


def test_dashboard_endpoint_returns_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDashboardService:
        def get_dashboard(self, days: int) -> dict[str, Any]:
            return make_dashboard_data(days)

    monkeypatch.setattr(
        dashboard_router,
        "dashboard_service",
        FakeDashboardService(),
    )

    response = TestClient(app).get("/api/v1/admin/dashboard?days=30")

    assert response.status_code == 200
    assert response.json()["period"]["days"] == 30
    assert response.json()["users"]["total_users"] == 10


@pytest.mark.parametrize("days", [0, 91])
def test_dashboard_endpoint_rejects_invalid_days(days: int) -> None:
    response = TestClient(app).get(
        "/api/v1/admin/dashboard",
        params={"days": days},
    )

    assert response.status_code == 422


def test_dashboard_endpoint_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingDashboardService:
        def get_dashboard(self, days: int) -> None:
            raise DashboardStorageError("관리자 대시보드를 조회할 수 없습니다.")

    monkeypatch.setattr(
        dashboard_router,
        "dashboard_service",
        FailingDashboardService(),
    )

    response = TestClient(app).get("/api/v1/admin/dashboard")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "관리자 대시보드를 조회할 수 없습니다."
    }
