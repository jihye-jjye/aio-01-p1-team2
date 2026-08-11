from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.coach.models import ScheduleLookupArguments

KST = ZoneInfo("Asia/Seoul")


class ScheduleRangeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedScheduleRange:
    start_on: date
    end_on: date

    @property
    def day_count(self) -> int:
        return (self.end_on - self.start_on).days + 1


def resolve_schedule_range(
    arguments: ScheduleLookupArguments,
    *,
    reference_at: datetime,
) -> ResolvedScheduleRange:
    if (
        not isinstance(reference_at, datetime)
        or reference_at.tzinfo is None
        or reference_at.utcoffset() is None
    ):
        raise ScheduleRangeError("기준 시각에는 timezone 정보가 필요합니다.")

    today = reference_at.astimezone(KST).date()
    if arguments.period == "today":
        result = ResolvedScheduleRange(today, today)
    elif arguments.period == "tomorrow":
        tomorrow = today + timedelta(days=1)
        result = ResolvedScheduleRange(tomorrow, tomorrow)
    elif arguments.period in {"this_week", "next_week"}:
        monday = today - timedelta(days=today.weekday())
        if arguments.period == "next_week":
            monday += timedelta(days=7)
        result = ResolvedScheduleRange(monday, monday + timedelta(days=6))
    else:
        if arguments.start_on is None or arguments.end_on is None:
            raise ScheduleRangeError("명시 기간이 완전하지 않습니다.")
        result = ResolvedScheduleRange(arguments.start_on, arguments.end_on)

    if result.end_on < result.start_on:
        raise ScheduleRangeError("조회 종료일은 시작일보다 빠를 수 없습니다.")
    if result.day_count > 28:
        raise ScheduleRangeError("일정 조회 기간은 양 끝을 포함해 최대 28일입니다.")
    return result
