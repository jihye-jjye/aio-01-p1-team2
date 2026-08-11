from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import user_admin_router
from app.repositories.user_admin_repository import UserAdminRepository
from app.services.exceptions import (
    UserDeleteForbiddenError,
    UserNotFoundError,
)
from app.services.user_admin_service import UserAdminService


NOW = datetime(2026, 8, 11, tzinfo=UTC)


class FakeUserAdminRepository:
    def __init__(
        self,
        *,
        user: dict[str, Any] | None,
        plans: list[dict[str, Any]] | None = None,
        quests: list[dict[str, Any]] | None = None,
    ) -> None:
        self.user = user
        self.plans = plans or []
        self.quests = quests or []

    def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        return self.user

    def get_user_by_login_id(
        self,
        login_id: str,
    ) -> dict[str, Any] | None:
        if self.user is None:
            return None
        if self.user["login_id"] != login_id.strip().lower():
            return None
        return self.user

    def get_user_plans(self, user_id: UUID) -> list[dict[str, Any]]:
        return self.plans

    def get_user_quests(self, user_id: UUID) -> list[dict[str, Any]]:
        return self.quests

    def delete_user(self, user_id: UUID) -> dict[str, Any] | None:
        deleted = self.user
        self.user = None
        return deleted


def make_user(user_id: UUID) -> dict[str, Any]:
    return {
        "id": user_id,
        "login_id": "roadmap-user",
        "role": "user",
        "user_exp": 50,
        "is_active": True,
        "last_login_at": NOW,
        "failed_login_count": 0,
        "locked_until": None,
        "created_at": NOW,
        "updated_at": NOW,
        "profile": None,
    }


def make_plan(
    plan_id: UUID,
    *,
    status: str,
    final_progress: int | None = None,
) -> dict[str, Any]:
    terminal = status in {"completed", "expired", "superseded"}
    return {
        "id": plan_id,
        "source_saved_job_id": None,
        "proposal_result_id": None,
        "previous_plan_id": None,
        "title": f"{status} roadmap",
        "summary": None,
        "goal_snapshot": {"target_role": "backend"},
        "starts_on": date(2026, 8, 1),
        "ends_on": date(2026, 8, 31),
        "total_task_count": 2,
        "final_progress": final_progress,
        "status": status,
        "activated_at": NOW if status not in {"draft", "rejected"} else None,
        "ended_at": NOW if terminal else None,
        "archived_at": NOW if terminal else None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def make_quest(
    plan_id: UUID | None,
    *,
    status: str,
    kind: str = "task",
    counts_toward_progress: bool = True,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "plan_id": plan_id,
        "saved_job_id": None,
        "kind": kind,
        "title": f"{status} quest",
        "description": None,
        "scheduled_at": NOW,
        "remind_at": None,
        "status": status,
        "plan_day": 1 if plan_id is not None else None,
        "slot": 1 if plan_id is not None else None,
        "detail_status": "ready",
        "counts_toward_progress": counts_toward_progress,
        "metadata": {},
        "completed_at": NOW if status == "completed" else None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def make_service(
    user_id: UUID,
    *,
    plans: list[dict[str, Any]] | None = None,
    quests: list[dict[str, Any]] | None = None,
) -> UserAdminService:
    repository = FakeUserAdminRepository(
        user=make_user(user_id),
        plans=plans,
        quests=quests,
    )
    return UserAdminService(repository=repository)  # type: ignore[arg-type]


def test_overview_returns_empty_history_without_plans() -> None:
    user_id = uuid4()

    overview = make_service(user_id).get_user_overview(user_id)

    assert overview.roadmap_history == []
    assert overview.quest_progress.total == 0
    assert overview.quest_progress.progress_percent == 0


def test_overview_groups_quests_and_calculates_each_plan_separately() -> None:
    user_id = uuid4()
    old_plan_id = uuid4()
    active_plan_id = uuid4()
    standalone_quest = make_quest(
        None,
        status="pending",
        counts_toward_progress=False,
    )
    cancelled_quest = make_quest(active_plan_id, status="cancelled")

    service = make_service(
        user_id,
        plans=[
            make_plan(active_plan_id, status="active"),
            make_plan(old_plan_id, status="superseded", final_progress=75),
        ],
        quests=[
            make_quest(active_plan_id, status="completed"),
            make_quest(active_plan_id, status="pending"),
            cancelled_quest,
            make_quest(old_plan_id, status="completed"),
            standalone_quest,
        ],
    )

    overview = service.get_user_overview(user_id)

    active_history, old_history = overview.roadmap_history
    assert len(active_history.quests) == 3
    assert active_history.progress.total == 2
    assert active_history.progress.completed == 1
    assert active_history.progress.pending == 1
    assert active_history.progress.progress_percent == 50
    assert active_history.progress.is_final is False

    assert len(old_history.quests) == 1
    assert old_history.progress.progress_percent == 75
    assert old_history.progress.is_final is True

    assert standalone_quest["id"] not in {
        quest.id
        for history in overview.roadmap_history
        for quest in history.quests
    }
    assert len(overview.quests) == 5
    assert overview.quest_progress == active_history.progress

    by_login_id = service.get_user_overview_by_login_id("ROADMAP-USER")
    assert by_login_id.account.id == user_id

    roadmaps = service.get_user_roadmaps_by_login_id("roadmap-user")
    assert len(roadmaps.items) == 2

    quest_overview = service.get_user_quests_by_login_id("roadmap-user")
    assert len(quest_overview.quests) == 5
    assert quest_overview.active_plan_progress.progress_percent == 50


def test_non_progress_items_do_not_affect_progress() -> None:
    user_id = uuid4()
    plan_id = uuid4()
    service = make_service(
        user_id,
        plans=[make_plan(plan_id, status="active")],
        quests=[
            make_quest(
                plan_id,
                status="completed",
                kind="milestone",
                counts_toward_progress=False,
            ),
            make_quest(
                plan_id,
                status="pending",
                counts_toward_progress=False,
            ),
        ],
    )

    progress = service.get_user_overview(user_id).quest_progress

    assert progress.total == 0
    assert progress.progress_percent == 0


def test_overview_raises_not_found_for_missing_user() -> None:
    user_id = uuid4()
    repository = FakeUserAdminRepository(user=None)
    service = UserAdminService(repository=repository)  # type: ignore[arg-type]

    with pytest.raises(UserNotFoundError):
        service.get_user_overview(user_id)


def test_overview_endpoint_returns_404_for_missing_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    repository = FakeUserAdminRepository(user=None)
    service = UserAdminService(repository=repository)  # type: ignore[arg-type]
    monkeypatch.setattr(user_admin_router, "user_admin_service", service)

    response = TestClient(app).get(
        "/api/v1/admin/users/by-login-id/roadmap-user/overview"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "사용자를 찾을 수 없습니다."}


def test_user_routes_document_response_contents() -> None:
    paths = app.openapi()["paths"]

    base_path = "/api/v1/admin/users/by-login-id/{login_id}"
    overview = paths[f"{base_path}/overview"]["get"]
    roadmaps = paths[f"{base_path}/roadmaps"]["get"]
    quests = paths[f"{base_path}/quests"]["get"]
    detail = paths[base_path]["get"]

    assert "roadmap_history" in overview["responses"]["200"]["description"]
    assert "plan·quests·progress" in roadmaps["responses"]["200"]["description"]
    assert "active_plan_progress" in quests["responses"]["200"]["description"]
    assert "profile" in detail["responses"]["200"]["description"]


def test_delete_user_returns_deleted_account() -> None:
    user_id = uuid4()
    repository = FakeUserAdminRepository(user=make_user(user_id))
    service = UserAdminService(repository=repository)  # type: ignore[arg-type]

    deleted = service.delete_user(user_id)

    assert deleted.id == user_id
    assert deleted.profile is None
    assert repository.user is None


def test_delete_user_rejects_admin_account() -> None:
    user_id = uuid4()
    admin = make_user(user_id)
    admin["role"] = "admin"
    admin["user_exp"] = 0
    repository = FakeUserAdminRepository(user=admin)
    service = UserAdminService(repository=repository)  # type: ignore[arg-type]

    with pytest.raises(UserDeleteForbiddenError):
        service.delete_user(user_id)

    assert repository.user is admin


def test_delete_user_repository_calls_atomic_rpc() -> None:
    user_id = uuid4()
    deleted_row = make_user(user_id)

    class FakeRpcClient:
        def __init__(self) -> None:
            self.function_name: str | None = None
            self.parameters: dict[str, str] | None = None

        def schema(self, schema_name: str) -> "FakeRpcClient":
            assert schema_name == "app"
            return self

        def rpc(
            self,
            function_name: str,
            parameters: dict[str, str],
        ) -> "FakeRpcClient":
            self.function_name = function_name
            self.parameters = parameters
            return self

        def execute(self) -> object:
            return type("Response", (), {"data": deleted_row})()

    client = FakeRpcClient()
    repository = UserAdminRepository(client=client)  # type: ignore[arg-type]

    result = repository.delete_user(user_id)

    assert result == deleted_row
    assert client.function_name == "delete_user_completely"
    assert client.parameters == {"target_user_id": str(user_id)}
