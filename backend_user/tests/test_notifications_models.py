from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.notifications.errors import NotificationDataIntegrityError
from app.notifications.models import (
    DailyTasksPayloadV1,
    LegacyNotificationPayloadV1,
    NotificationView,
    PlanEndedPayloadV1,
    RoadmapChangePayloadV1,
    StoredNotification,
)
from app.notifications.presentation import build_notification_view

USER_ID = UUID(int=901)
PLAN_ID = UUID(int=902)
SCHEDULE_ID = UUID(int=903)
NOTIFICATION_ID = UUID(int=904)
NOW = datetime(2026, 8, 11, 1, tzinfo=UTC)


def stored_notification(
    *,
    notification_type: str,
    payload: dict[str, object],
    plan_id: UUID | None = PLAN_ID,
    schedule_item_id: UUID | None = None,
) -> StoredNotification:
    return StoredNotification(
        id=NOTIFICATION_ID,
        type=notification_type,
        plan_id=plan_id,
        schedule_item_id=schedule_item_id,
        available_at=NOW,
        is_read=False,
        read_at=None,
        payload=payload,
        created_at=NOW,
    )


def test_daily_payload_is_typed_and_rendered_with_count_and_date() -> None:
    notification = stored_notification(
        notification_type="daily_tasks",
        payload={
            "version": "daily_tasks.v1",
            "date": "2026-08-11",
            "plan_title": "백엔드 취업 로드맵",
            "count": 1,
            "schedules": [
                {
                    "id": str(SCHEDULE_ID),
                    "kind": "task",
                    "title": "FastAPI 복습",
                    "scheduled_at": "2026-08-11T01:00:00Z",
                    "status": "pending",
                }
            ],
        },
    )

    view = build_notification_view(notification)

    assert isinstance(view.payload, DailyTasksPayloadV1)
    assert view.payload.date == date(2026, 8, 11)
    assert view.payload.count == len(view.payload.schedules) == 1
    assert view.plan_id == PLAN_ID
    assert view.schedule_item_id is None
    assert "8월 11일" in view.title
    assert "FastAPI 복습" in view.message


def test_daily_payload_preserves_plan_id_after_plan_deletion() -> None:
    notification = stored_notification(
        notification_type="daily_tasks",
        plan_id=None,
        payload={
            "version": "daily_tasks.v1",
            "date": "2026-08-11",
            "plan_title": "백엔드 취업 로드맵",
            "count": 1,
            "schedules": [
                {
                    "id": str(SCHEDULE_ID),
                    "kind": "task",
                    "title": "FastAPI 복습",
                    "scheduled_at": "2026-08-11T01:00:00Z",
                    "status": "pending",
                }
            ],
            "plan_id": str(PLAN_ID),
        },
    )

    view = build_notification_view(notification)

    assert isinstance(view.payload, DailyTasksPayloadV1)
    assert view.payload.plan_id == PLAN_ID
    assert view.plan_id == PLAN_ID


def test_single_schedule_change_exposes_payload_schedule_id_and_summary() -> None:
    notification = stored_notification(
        notification_type="roadmap_changed",
        payload={
            "version": "roadmap_change.v1",
            "target": "schedule",
            "change_kind": "update",
            "affected_count": 1,
            "plan_id": str(PLAN_ID),
            "schedule_ids": [str(SCHEDULE_ID)],
            "before": {
                "id": str(SCHEDULE_ID),
                "title": "기존 일정",
                "scheduled_at": "2026-08-11T01:00:00Z",
                "status": "pending",
            },
            "after": {
                "id": str(SCHEDULE_ID),
                "title": "변경 일정",
                "scheduled_at": "2026-08-12T01:00:00Z",
                "status": "in_progress",
            },
        },
    )

    view = build_notification_view(notification)

    assert isinstance(view.payload, RoadmapChangePayloadV1)
    assert view.schedule_item_id == SCHEDULE_ID
    assert view.payload.before is not None and view.payload.before.title == "기존 일정"
    assert view.payload.after is not None and view.payload.after.title == "변경 일정"
    assert "변경" in view.title
    assert "변경 일정" in view.message


def test_deleted_plan_uses_payload_id_when_foreign_key_was_cleared() -> None:
    notification = stored_notification(
        notification_type="plan_ended",
        plan_id=None,
        payload={
            "version": "plan_ended.v1",
            "ended_status": "deleted",
            "final_progress": 40,
            "plan_id": str(PLAN_ID),
            "plan_title": "백엔드 취업 로드맵",
        },
    )

    view = build_notification_view(notification)

    assert isinstance(view.payload, PlanEndedPayloadV1)
    assert view.plan_id == PLAN_ID
    assert "40%" in view.message


def test_legacy_notification_payload_is_wrapped_in_a_versioned_contract() -> None:
    notification = stored_notification(
        notification_type="check_in",
        payload={"prompt": "이번 주 진행 상황을 확인해보세요."},
        plan_id=None,
    )

    view = build_notification_view(notification)

    assert isinstance(view.payload, LegacyNotificationPayloadV1)
    assert view.payload.version == "legacy.v1"
    assert view.payload.data == {"prompt": "이번 주 진행 상황을 확인해보세요."}
    assert view.title == "로드맵 체크인"


@pytest.mark.parametrize(
    ("notification_type", "payload"),
    [
        ("daily_tasks", {"version": "daily_tasks.v1", "date": "not-a-date"}),
        (
            "roadmap_changed",
            {
                "version": "roadmap_change.v1",
                "target": "schedule",
                "change_kind": "update",
                "affected_count": 0,
            },
        ),
        (
            "plan_ended",
            {
                "version": "plan_ended.v1",
                "ended_status": "completed",
                "final_progress": 101,
            },
        ),
    ],
)
def test_malformed_known_payload_raises_safe_domain_integrity_error(
    notification_type: str,
    payload: dict[str, object],
) -> None:
    notification = stored_notification(
        notification_type=notification_type,
        payload=payload,
    )

    with pytest.raises(NotificationDataIntegrityError):
        build_notification_view(notification)


@pytest.mark.parametrize("field", ["available_at", "read_at", "created_at"])
def test_stored_notification_timestamps_require_timezone_information(field: str) -> None:
    naive = NOW.replace(tzinfo=None)
    values: dict[str, object] = {
        "id": NOTIFICATION_ID,
        "type": "check_in",
        "plan_id": None,
        "schedule_item_id": None,
        "available_at": NOW,
        "is_read": False,
        "read_at": None,
        "payload": {},
        "created_at": NOW,
    }
    values[field] = naive
    if field == "read_at":
        values["is_read"] = True

    with pytest.raises(ValidationError):
        StoredNotification.model_validate(values)


@pytest.mark.parametrize("field", ["available_at", "read_at"])
def test_public_notification_timestamps_require_timezone_information(field: str) -> None:
    naive = NOW.replace(tzinfo=None)
    values: dict[str, object] = {
        "id": NOTIFICATION_ID,
        "type": "check_in",
        "title": "로드맵 체크인",
        "message": "확인해보세요.",
        "plan_id": None,
        "schedule_item_id": None,
        "available_at": NOW,
        "is_read": False,
        "read_at": None,
        "payload": LegacyNotificationPayloadV1(data={}),
    }
    values[field] = naive
    if field == "read_at":
        values["is_read"] = True

    with pytest.raises(ValidationError):
        NotificationView.model_validate(values)


def test_payload_schedule_timestamps_require_timezone_information() -> None:
    with pytest.raises(ValidationError):
        DailyTasksPayloadV1.model_validate(
            {
                "version": "daily_tasks.v1",
                "date": "2026-08-11",
                "plan_title": "로드맵",
                "count": 1,
                "schedules": [
                    {
                        "id": str(SCHEDULE_ID),
                        "kind": "task",
                        "title": "과제",
                        "scheduled_at": "2026-08-11T01:00:00",
                        "status": "pending",
                    }
                ],
            }
        )

    malformed_summary = {
        "version": "roadmap_change.v1",
        "target": "schedule",
        "change_kind": "update",
        "affected_count": 1,
        "plan_id": str(PLAN_ID),
        "schedule_ids": [str(SCHEDULE_ID)],
        "before": {
            "id": str(SCHEDULE_ID),
            "title": "과제",
            "scheduled_at": "2026-08-11T01:00:00",
            "status": "pending",
        },
        "after": None,
    }
    with pytest.raises(ValidationError):
        RoadmapChangePayloadV1.model_validate(malformed_summary)
