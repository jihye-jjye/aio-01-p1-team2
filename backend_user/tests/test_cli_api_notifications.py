from copy import deepcopy
from datetime import date, timedelta
from uuid import UUID

import httpx
import pytest

from app.cli.api import ApiError, CoachApiClient

PLAN_ID = "60000000-0000-0000-0000-000000000001"
SCHEDULE_ID = "70000000-0000-0000-0000-000000000001"
DAILY_ID = "92000000-0000-0000-0000-000000000001"
CHANGE_ID = "92000000-0000-0000-0000-000000000002"
CASE_ID = "aaaaaaaa-0000-0000-0000-000000000001"


def notification_feed() -> dict:
    return {
        "window_start": "2026-08-11",
        "window_end": "2026-08-17",
        "upcoming": [
            {
                "id": DAILY_ID,
                "type": "daily_tasks",
                "title": "오늘의 로드맵",
                "message": "과제 1건이 예정되어 있습니다.",
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
                "message": "일정 1건이 수정되었습니다.",
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
                    "before": {
                        "id": SCHEDULE_ID,
                        "title": "이전 제목",
                        "status": "pending",
                        "scheduled_at": "2026-08-11T01:00:00+00:00",
                        "starts_on": None,
                        "ends_on": None,
                        "total_task_count": None,
                    },
                    "after": {
                        "id": SCHEDULE_ID,
                        "title": "새 제목",
                        "status": "pending",
                        "scheduled_at": "2026-08-11T02:00:00+00:00",
                        "starts_on": None,
                        "ends_on": None,
                        "total_task_count": None,
                    },
                },
            }
        ],
        "unread_count": 2,
    }


@pytest.mark.asyncio
async def test_login_feed_posts_without_body_and_validates_authenticated_response() -> None:
    feed = notification_feed()
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=feed)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.login_feed()

    assert response == feed
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v1/notifications/login-feed"
    assert requests[0].content == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_mark_notification_read_patches_only_path_id_and_validates_view() -> None:
    notification = deepcopy(notification_feed()["upcoming"][0])
    notification.update(
        id=CASE_ID,
        is_read=True,
        read_at="2026-08-11T02:00:00+00:00",
    )
    requested_id = CASE_ID.upper()
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=notification)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.mark_notification_read(requested_id)

    assert response == notification
    assert len(requests) == 1
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == f"/api/v1/notifications/{requested_id}/read"
    assert requests[0].content == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda feed: feed.update(unread_count=True),
            id="boolean-unread-count",
        ),
        pytest.param(
            lambda feed: feed.update(upcoming="not-a-list"),
            id="upcoming-not-list",
        ),
        pytest.param(
            lambda feed: feed["upcoming"][0].update(id="not-a-uuid"),
            id="invalid-notification-id",
        ),
        pytest.param(
            lambda feed: feed["upcoming"][0]["payload"].update(version="roadmap_change.v1"),
            id="payload-version-mismatch",
        ),
        pytest.param(
            lambda feed: feed.update(upcoming=feed["upcoming"] * 8),
            id="upcoming-over-limit",
        ),
        pytest.param(
            lambda feed: feed["changes"][0]["payload"].pop("plan_id"),
            id="roadmap-plan-id-missing",
        ),
        pytest.param(
            lambda feed: feed["upcoming"][0].update(unexpected="must-not-pass"),
            id="notification-extra-field",
        ),
        pytest.param(
            lambda feed: feed.update(upcoming=[], changes=[], unread_count=1),
            id="unread-count-exceeds-uncapped-sections",
        ),
    ],
)
@pytest.mark.asyncio
async def test_login_feed_rejects_malformed_success_payload(mutate) -> None:
    feed = notification_feed()
    mutate(feed)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=feed)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.login_feed()

    assert raised.value.status_code == 502
    assert raised.value.code == "INVALID_RESPONSE"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_login_feed_accepts_interview_schedule_kind_from_public_model() -> None:
    feed = notification_feed()
    feed["upcoming"][0]["payload"]["schedules"][0]["kind"] = "interview"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=feed)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    assert await client.login_feed() == feed
    await http_client.aclose()


@pytest.mark.asyncio
async def test_login_feed_accepts_larger_unread_count_when_upcoming_is_capped() -> None:
    feed = notification_feed()
    template = feed["upcoming"][0]
    upcoming = []
    for offset in range(7):
        item = deepcopy(template)
        item_date = date(2026, 8, 11) + timedelta(days=offset)
        item["id"] = str(UUID(int=100 + offset))
        item["available_at"] = f"{item_date.isoformat()}T00:00:00+00:00"
        item["payload"]["date"] = item_date.isoformat()
        item["payload"]["schedules"][0]["id"] = str(UUID(int=200 + offset))
        item["payload"]["schedules"][0]["scheduled_at"] = f"{item_date.isoformat()}T01:00:00+00:00"
        upcoming.append(item)
    feed.update(upcoming=upcoming, changes=[], unread_count=8)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=feed)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    assert await client.login_feed() == feed
    await http_client.aclose()


@pytest.mark.asyncio
async def test_mark_notification_read_rejects_different_response_id() -> None:
    notification = deepcopy(notification_feed()["upcoming"][0])
    notification.update(
        id=CHANGE_ID,
        is_read=True,
        read_at="2026-08-11T02:00:00+00:00",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=notification)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.mark_notification_read(DAILY_ID)

    assert raised.value.status_code == 502
    assert raised.value.code == "INVALID_RESPONSE"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_mark_notification_read_rejects_malformed_success_payload() -> None:
    notification = deepcopy(notification_feed()["upcoming"][0])
    notification["is_read"] = True
    notification["read_at"] = None

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=notification)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.mark_notification_read(str(UUID(DAILY_ID)))

    assert raised.value.status_code == 502
    assert raised.value.code == "INVALID_RESPONSE"
    await http_client.aclose()
