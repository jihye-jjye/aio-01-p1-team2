from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.notifications.errors import NotificationDataIntegrityError

NotificationType = Literal[
    "daily_tasks",
    "roadmap_changed",
    "plan_ended",
    "interview_reminder",
    "check_in",
]
ScheduleKind = Literal["milestone", "task", "interview"]
PlanStatus = Literal["draft", "rejected", "completed", "expired", "superseded", "deleted"]


class StrictNotificationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DailyTaskScheduleV1(StrictNotificationModel):
    id: UUID
    kind: ScheduleKind
    title: str = Field(min_length=1, max_length=200)
    scheduled_at: AwareDatetime
    status: Literal["pending", "in_progress"]


class DailyTasksPayloadV1(StrictNotificationModel):
    version: Literal["daily_tasks.v1"]
    date: date
    plan_title: str = Field(min_length=1, max_length=200)
    count: int = Field(ge=1)
    schedules: list[DailyTaskScheduleV1] = Field(min_length=1)
    plan_id: UUID | None = None

    @model_validator(mode="after")
    def count_matches_schedules(self) -> DailyTasksPayloadV1:
        if self.count != len(self.schedules):
            raise ValueError("count must match schedules")
        return self


class RoadmapChangeSummaryV1(StrictNotificationModel):
    id: UUID
    title: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=40)
    scheduled_at: AwareDatetime | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    total_task_count: int | None = Field(default=None, ge=0)


class RoadmapChangePayloadV1(StrictNotificationModel):
    version: Literal["roadmap_change.v1"]
    target: Literal["plan", "schedule"]
    change_kind: Literal["activation", "update", "insert", "delete"]
    affected_count: int = Field(ge=1)
    plan_id: UUID
    schedule_ids: list[UUID] | None = None
    before: RoadmapChangeSummaryV1 | None = None
    after: RoadmapChangeSummaryV1 | None = None

    @model_validator(mode="after")
    def validate_target_shape(self) -> RoadmapChangePayloadV1:
        if self.target == "plan" and self.schedule_ids is not None:
            raise ValueError("plan changes cannot contain schedule_ids")
        if self.target == "schedule" and (
            not self.schedule_ids or len(self.schedule_ids) != self.affected_count
        ):
            raise ValueError("schedule_ids must match affected_count")
        return self


class PlanEndedPayloadV1(StrictNotificationModel):
    version: Literal["plan_ended.v1"]
    ended_status: PlanStatus
    final_progress: int = Field(ge=0, le=100)
    plan_id: UUID
    plan_title: str = Field(min_length=1, max_length=200)


class LegacyNotificationPayloadV1(StrictNotificationModel):
    version: Literal["legacy.v1"] = "legacy.v1"
    data: dict[str, Any]


NotificationPayload = Annotated[
    DailyTasksPayloadV1 | RoadmapChangePayloadV1 | PlanEndedPayloadV1 | LegacyNotificationPayloadV1,
    Field(discriminator="version"),
]


class StoredNotification(StrictNotificationModel):
    id: UUID
    type: NotificationType
    plan_id: UUID | None
    schedule_item_id: UUID | None
    available_at: AwareDatetime
    is_read: bool
    read_at: AwareDatetime | None
    payload: dict[str, Any]
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_read_state(self) -> StoredNotification:
        if self.is_read != (self.read_at is not None):
            raise ValueError("is_read must match read_at")
        return self


class NotificationFeedSnapshot(StrictNotificationModel):
    window_start: date
    window_end: date
    upcoming: list[StoredNotification]
    changes: list[StoredNotification]
    unread_count: int = Field(ge=0)


class NotificationView(StrictNotificationModel):
    id: UUID
    type: NotificationType
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2_000)
    plan_id: UUID | None
    schedule_item_id: UUID | None
    available_at: AwareDatetime
    is_read: bool
    read_at: AwareDatetime | None
    payload: NotificationPayload


class NotificationFeed(StrictNotificationModel):
    window_start: date
    window_end: date
    upcoming: list[NotificationView] = Field(max_length=7)
    changes: list[NotificationView] = Field(max_length=50)
    unread_count: int = Field(ge=0)


def parse_notification_payload(notification: StoredNotification) -> NotificationPayload:
    """Validate a stored payload against the contract selected by its row type."""
    try:
        if notification.type == "daily_tasks":
            return DailyTasksPayloadV1.model_validate(notification.payload)
        if notification.type == "roadmap_changed":
            return RoadmapChangePayloadV1.model_validate(notification.payload)
        if notification.type == "plan_ended":
            return PlanEndedPayloadV1.model_validate(notification.payload)
        return LegacyNotificationPayloadV1(data=notification.payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise NotificationDataIntegrityError() from exc
