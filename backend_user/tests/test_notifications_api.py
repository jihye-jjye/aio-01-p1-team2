from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_notification_service
from app.auth.models import CurrentUser
from app.auth.tokens import TokenService
from app.main import OPENAPI_TAGS, create_app
from app.notifications.errors import NotificationDataIntegrityError, NotificationNotFoundError
from app.notifications.models import (
    LegacyNotificationPayloadV1,
    NotificationFeed,
    NotificationFeedSnapshot,
    NotificationView,
    StoredNotification,
)
from app.notifications.service import NotificationService

USER_ID = UUID(int=921)
OTHER_USER_ID = UUID(int=922)
NOTIFICATION_ID = UUID(int=923)
NOW = datetime(2026, 8, 11, 1, tzinfo=UTC)


def stored(*, notification_id: UUID = NOTIFICATION_ID) -> StoredNotification:
    return StoredNotification(
        id=notification_id,
        type="check_in",
        plan_id=None,
        schedule_item_id=None,
        available_at=NOW,
        is_read=False,
        read_at=None,
        payload={"prompt": "확인"},
        created_at=NOW,
    )


def view(*, notification_id: UUID = NOTIFICATION_ID) -> NotificationView:
    return NotificationView(
        id=notification_id,
        type="check_in",
        title="로드맵 체크인",
        message="로드맵 진행 상황을 확인해보세요.",
        plan_id=None,
        schedule_item_id=None,
        available_at=NOW,
        is_read=False,
        read_at=None,
        payload=LegacyNotificationPayloadV1(data={"prompt": "확인"}),
    )


class RecordingRepository:
    def __init__(self, *, mark_result: StoredNotification | None = None) -> None:
        self.mark_result = mark_result
        self.feed_user_ids: list[UUID] = []
        self.mark_calls: list[tuple[UUID, UUID]] = []

    async def sync_login_feed(self, *, user_id: UUID) -> NotificationFeedSnapshot:
        self.feed_user_ids.append(user_id)
        return NotificationFeedSnapshot(
            window_start=date(2026, 8, 11),
            window_end=date(2026, 8, 17),
            upcoming=[],
            changes=[stored()],
            unread_count=58,
        )

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> StoredNotification | None:
        self.mark_calls.append((user_id, notification_id))
        return self.mark_result


@pytest.mark.asyncio
async def test_service_builds_views_and_maps_missing_or_foreign_id_to_not_found() -> None:
    repository = RecordingRepository()
    service = NotificationService(repository)

    feed = await service.login_feed(user_id=USER_ID)

    assert feed.unread_count == 58
    assert [item.id for item in feed.changes] == [NOTIFICATION_ID]
    assert repository.feed_user_ids == [USER_ID]

    with pytest.raises(NotificationNotFoundError):
        await service.mark_read(user_id=OTHER_USER_ID, notification_id=NOTIFICATION_ID)
    assert repository.mark_calls == [(OTHER_USER_ID, NOTIFICATION_ID)]


class StubNotificationService:
    def __init__(self) -> None:
        self.feed_user_ids: list[UUID] = []
        self.mark_calls: list[tuple[UUID, UUID]] = []
        self.mark_error: Exception | None = None

    async def login_feed(self, *, user_id: UUID) -> NotificationFeed:
        self.feed_user_ids.append(user_id)
        return NotificationFeed(
            window_start=date(2026, 8, 11),
            window_end=date(2026, 8, 17),
            upcoming=[],
            changes=[view()],
            unread_count=1,
        )

    async def mark_read(self, *, user_id: UUID, notification_id: UUID) -> NotificationView:
        self.mark_calls.append((user_id, notification_id))
        if self.mark_error is not None:
            raise self.mark_error
        return view(notification_id=notification_id).model_copy(
            update={"is_read": True, "read_at": NOW}
        )


def client_with_service() -> tuple[TestClient, StubNotificationService]:
    app = create_app(lifespan_enabled=False)
    service = StubNotificationService()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID,
        role="user",
        session_id=UUID(int=924),
    )
    app.dependency_overrides[get_notification_service] = lambda: service
    return TestClient(app), service


def test_login_feed_is_post_bodyless_and_uses_only_authenticated_user() -> None:
    client, service = client_with_service()

    response = client.post(
        "/api/v1/notifications/login-feed",
        json={"user_id": str(OTHER_USER_ID)},
    )

    assert response.status_code == 200
    assert response.json()["unread_count"] == 1
    assert response.json()["changes"][0]["payload"]["version"] == "legacy.v1"
    assert service.feed_user_ids == [USER_ID]

    operation = client.get("/openapi.json").json()["paths"]["/api/v1/notifications/login-feed"][
        "post"
    ]
    assert "requestBody" not in operation
    assert operation["security"] == [{"HTTPBearer": []}]
    assert "notifications" in {tag["name"] for tag in OPENAPI_TAGS}


def test_notification_feed_requires_bearer_authentication() -> None:
    app = create_app(lifespan_enabled=False)
    app.state.token_service = TokenService(
        secret_key="test-secret-that-is-longer-than-thirty-two-bytes",
        access_ttl=timedelta(minutes=30),
        refresh_ttl=timedelta(days=7),
    )
    app.state.db_pool = object()
    app.dependency_overrides[get_notification_service] = StubNotificationService

    response = TestClient(app).post("/api/v1/notifications/login-feed")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_mark_read_uses_jwt_owner_and_not_found_error_is_anti_enumerating() -> None:
    client, service = client_with_service()

    read = client.patch(f"/api/v1/notifications/{NOTIFICATION_ID}/read")
    assert read.status_code == 200
    assert read.json()["is_read"] is True
    assert service.mark_calls == [(USER_ID, NOTIFICATION_ID)]

    service.mark_error = NotificationNotFoundError()
    missing = client.patch(f"/api/v1/notifications/{UUID(int=999)}/read")
    assert missing.status_code == 404
    assert missing.json()["error"] == {
        "code": "NOTIFICATION_NOT_FOUND",
        "message": "알림을 찾을 수 없습니다.",
        "retryable": False,
        "details": {},
    }

    service.mark_error = NotificationDataIntegrityError()
    malformed = client.patch(f"/api/v1/notifications/{NOTIFICATION_ID}/read")
    assert malformed.status_code == 500
    assert malformed.json()["error"] == {
        "code": "NOTIFICATION_DATA_INTEGRITY_ERROR",
        "message": "알림 데이터를 안전하게 처리할 수 없습니다.",
        "retryable": False,
        "details": {},
    }


def test_notification_openapi_documents_exact_methods_models_and_errors() -> None:
    schema = create_app(lifespan_enabled=False).openapi()
    feed = schema["paths"]["/api/v1/notifications/login-feed"]["post"]
    mark = schema["paths"]["/api/v1/notifications/{notification_id}/read"]["patch"]

    assert feed["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/NotificationFeed"
    )
    assert mark["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/NotificationView"
    )
    assert "NOTIFICATION_NOT_FOUND" in mark["responses"]["404"]["description"]
