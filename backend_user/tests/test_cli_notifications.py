from collections import deque
from copy import deepcopy
from io import StringIO
from typing import Any

import pytest
from rich.console import Console

from app.cli.api import ApiError
from app.cli.app import CliApp
from app.cli.renderer import RichRenderer

PLAN_ID = "60000000-0000-0000-0000-000000000001"
SCHEDULE_ID = "70000000-0000-0000-0000-000000000001"
DAILY_ID = "92000000-0000-0000-0000-000000000001"
CHANGE_ID = "92000000-0000-0000-0000-000000000002"

PROFILE = {
    "target_role": "백엔드 개발자",
    "skills": ["Python"],
    "experience_summary": "API 프로젝트",
    "target_date": "2026-11-08",
    "target_company": None,
    "preferred_environment": "원격 근무",
    "daily_notification_time": "09:30:00",
    "assistant_style": "friendly",
}


def notification_feed() -> dict[str, Any]:
    return {
        "window_start": "2026-08-11",
        "window_end": "2026-08-17",
        "upcoming": [
            {
                "id": DAILY_ID,
                "type": "daily_tasks",
                "title": "[bold]오늘의 일정[/bold]",
                "message": "API 테스트 1건",
                "plan_id": PLAN_ID,
                "schedule_item_id": None,
                "available_at": "2026-08-11T00:00:00+00:00",
                "is_read": False,
                "read_at": None,
                "payload": {
                    "version": "daily_tasks.v1",
                    "date": "2026-08-11",
                    "plan_title": "백엔드 로드맵",
                    "count": 1,
                    "schedules": [
                        {
                            "id": SCHEDULE_ID,
                            "kind": "task",
                            "title": "API 테스트 작성",
                            "scheduled_at": "2026-08-11T01:00:00+00:00",
                            "status": "pending",
                        }
                    ],
                },
            }
        ],
        "changes": [
            {
                "id": CHANGE_ID,
                "type": "roadmap_changed",
                "title": "로드맵 일정 변경",
                "message": "일정 1건 수정",
                "plan_id": PLAN_ID,
                "schedule_item_id": SCHEDULE_ID,
                "available_at": "2026-08-11T00:30:00+00:00",
                "is_read": False,
                "read_at": None,
                "payload": {
                    "version": "roadmap_change.v1",
                    "target": "schedule",
                    "change_kind": "update",
                    "affected_count": 1,
                    "plan_id": PLAN_ID,
                    "schedule_ids": [SCHEDULE_ID],
                    "before": None,
                    "after": None,
                },
            }
        ],
        "unread_count": 2,
    }


class ScriptedInput:
    def __init__(self, values: list[str]) -> None:
        self.values = deque(values)

    async def read(self, prompt: str) -> str:
        if not self.values:
            raise EOFError
        return self.values.popleft()

    async def read_secret(self, prompt: str) -> str:
        return await self.read(prompt)


class NotificationApi:
    def __init__(
        self,
        *,
        feed: dict[str, Any] | ApiError | None = None,
        signup: bool = False,
        read_results: dict[str, dict[str, Any] | ApiError] | None = None,
    ) -> None:
        self.feed = deepcopy(notification_feed()) if feed is None else feed
        self.use_signup = signup
        self.read_results = read_results or {}
        self.calls: list[tuple[Any, ...]] = []
        self.closed = False

    async def login(self, login_id: str, login_pw: str) -> None:
        self.calls.append(("login", login_id, login_pw))

    async def signup(self, login_id: str, login_pw: str, user_name: str) -> str:
        self.calls.append(("signup", login_id, login_pw, user_name))
        return "new.user"

    async def login_feed(self) -> dict[str, Any]:
        self.calls.append(("login_feed",))
        if isinstance(self.feed, ApiError):
            raise self.feed
        return deepcopy(self.feed)

    async def mark_notification_read(self, notification_id: str) -> dict[str, Any]:
        self.calls.append(("mark_notification_read", notification_id))
        result = self.read_results.get(notification_id)
        if isinstance(result, ApiError):
            raise result
        if result is None:
            assert not isinstance(self.feed, ApiError)
            notifications = self.feed["upcoming"] + self.feed["changes"]
            result = next(item for item in notifications if item["id"] == notification_id)
            result = {**result, "is_read": True, "read_at": "2026-08-11T02:00:00+00:00"}
        return deepcopy(result)

    async def profile(self) -> dict[str, Any]:
        self.calls.append(("profile",))
        return deepcopy(PROFILE)

    def clear_access_token(self) -> None:
        self.calls.append(("clear_access_token",))

    async def aclose(self) -> None:
        self.closed = True


async def run_app(
    api: NotificationApi,
    values: list[str],
) -> tuple[int, str]:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=220, color_system=None)
    app = CliApp(
        api=api,
        input_port=ScriptedInput(values),
        renderer=RichRenderer(console=console),
    )
    return await app.run(), stream.getvalue()


@pytest.mark.asyncio
async def test_login_fetches_feed_before_profile_and_reads_only_explicit_selection() -> None:
    api = NotificationApi()

    code, output = await run_app(api, ["demo.user", "password", "2", "0"])

    assert code == 0
    assert [call[0] for call in api.calls] == [
        "login",
        "login_feed",
        "mark_notification_read",
        "profile",
    ]
    assert api.calls[2] == ("mark_notification_read", CHANGE_ID)
    assert "[bold]오늘의 일정[/bold]" in output
    assert "로드맵 일정 변경" in output


@pytest.mark.asyncio
async def test_blank_selection_never_marks_notifications_read() -> None:
    api = NotificationApi()

    code, _ = await run_app(api, ["demo.user", "password", "", "0"])

    assert code == 0
    assert [call[0] for call in api.calls] == ["login", "login_feed", "profile"]


@pytest.mark.asyncio
async def test_invalid_selection_warns_and_reprompts_without_crashing() -> None:
    api = NotificationApi()

    code, output = await run_app(api, ["demo.user", "password", "3", "1", "0"])

    assert code == 0
    assert ("mark_notification_read", DAILY_ID) in api.calls
    assert "표시된 알림 번호" in output


@pytest.mark.asyncio
async def test_feed_unauthorized_warns_but_keeps_token_and_continues_to_profile() -> None:
    api = NotificationApi(feed=ApiError(401, "UNAUTHORIZED", "raw secret"))

    code, output = await run_app(api, ["demo.user", "password", "0"])

    assert code == 0
    assert [call[0] for call in api.calls] == ["login", "login_feed", "profile"]
    assert "clear_access_token" not in [call[0] for call in api.calls]
    assert "로그인 알림을 불러오지 못했습니다" in output
    assert "raw secret" not in output


@pytest.mark.asyncio
async def test_read_unauthorized_warns_keeps_token_and_continues_other_reads_and_profile() -> None:
    api = NotificationApi(
        read_results={
            DAILY_ID: ApiError(401, "UNAUTHORIZED", "raw authentication detail"),
        }
    )

    code, output = await run_app(api, ["demo.user", "password", "1,2", "0"])

    assert code == 0
    assert [call[0] for call in api.calls] == [
        "login",
        "login_feed",
        "mark_notification_read",
        "mark_notification_read",
        "profile",
    ]
    assert "clear_access_token" not in [call[0] for call in api.calls]
    assert "알림 확인 상태를 저장하지 못했습니다" in output
    assert "raw authentication detail" not in output


@pytest.mark.asyncio
async def test_signup_fetches_feed_after_token_and_before_profile() -> None:
    api = NotificationApi(
        feed={
            **notification_feed(),
            "upcoming": [],
            "changes": [],
            "unread_count": 0,
        }
    )

    code, _ = await run_app(
        api,
        ["/signup", "new.user", "홍길동", "password", "password", "0"],
    )

    assert code == 0
    assert [call[0] for call in api.calls] == ["signup", "login_feed", "profile"]
