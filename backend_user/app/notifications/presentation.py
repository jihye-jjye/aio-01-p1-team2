from __future__ import annotations

from app.notifications.models import (
    DailyTasksPayloadV1,
    NotificationView,
    PlanEndedPayloadV1,
    RoadmapChangePayloadV1,
    StoredNotification,
    parse_notification_payload,
)


def _daily_copy(payload: DailyTasksPayloadV1) -> tuple[str, str]:
    title = f"{payload.date.month}월 {payload.date.day}일 로드맵 일정"
    schedule_titles = ", ".join(item.title for item in payload.schedules[:3])
    if payload.count > 3:
        schedule_titles = f"{schedule_titles} 외 {payload.count - 3}개"
    return title, f"{payload.plan_title}: {schedule_titles}"


def _roadmap_copy(payload: RoadmapChangePayloadV1) -> tuple[str, str]:
    action = {
        "activation": "활성화",
        "insert": "추가",
        "update": "변경",
        "delete": "삭제",
    }[payload.change_kind]
    target = "로드맵" if payload.target == "plan" else "로드맵 일정"
    title = f"{target}이 {action}되었습니다"
    summary = payload.after or payload.before
    if summary is not None:
        message = summary.title
    else:
        message = f"{payload.affected_count}건의 {target} 변경을 확인해보세요."
    return title, message


def _plan_ended_copy(payload: PlanEndedPayloadV1) -> tuple[str, str]:
    status = {
        "draft": "초안 전환",
        "rejected": "거절",
        "completed": "완료",
        "expired": "만료",
        "superseded": "교체",
        "deleted": "삭제",
    }[payload.ended_status]
    return (
        "로드맵이 종료되었습니다",
        f"{payload.plan_title}: {status}, 최종 진행률 {payload.final_progress}%",
    )


def _legacy_copy(notification_type: str) -> tuple[str, str]:
    if notification_type == "interview_reminder":
        return "면접 일정 알림", "예정된 면접 일정을 확인해보세요."
    return "로드맵 체크인", "로드맵 진행 상황을 확인해보세요."


def build_notification_view(notification: StoredNotification) -> NotificationView:
    payload = parse_notification_payload(notification)
    plan_id = notification.plan_id
    schedule_item_id = notification.schedule_item_id

    if isinstance(payload, DailyTasksPayloadV1):
        title, message = _daily_copy(payload)
        plan_id = plan_id or payload.plan_id
    elif isinstance(payload, RoadmapChangePayloadV1):
        title, message = _roadmap_copy(payload)
        plan_id = plan_id or payload.plan_id
        if schedule_item_id is None and payload.affected_count == 1 and payload.schedule_ids:
            schedule_item_id = payload.schedule_ids[0]
    elif isinstance(payload, PlanEndedPayloadV1):
        title, message = _plan_ended_copy(payload)
        plan_id = plan_id or payload.plan_id
    else:
        title, message = _legacy_copy(notification.type)

    return NotificationView(
        id=notification.id,
        type=notification.type,
        title=title,
        message=message,
        plan_id=plan_id,
        schedule_item_id=schedule_item_id,
        available_at=notification.available_at,
        is_read=notification.is_read,
        read_at=notification.read_at,
        payload=payload,
    )
