from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ConfigDict

from app.plans.errors import PlanDataIntegrityError, PlanWindowOutOfRangeError
from app.plans.models import StrictPlanModel
from app.plans.records import (
    DailyGoalAchievement,
    PlanScheduleItem,
    StoredPlan,
    StoredPlanProposal,
    StoredTaskUpdate,
    TodayQuestSnapshot,
)


class PlanProposalMilestoneView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    week_index: int
    starts_on: date
    ends_on: date
    title: str
    description: str


class PlanProposalTaskView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    slot: int
    title: str
    description: str


class PlanProposalDayView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    plan_day: int
    date: date
    tasks: list[PlanProposalTaskView]


class PlanProposalView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    request_id: UUID
    decision_status: Literal["pending", "applied", "rejected"]
    title: str
    summary: str
    generated_on: date
    starts_on: date
    ends_on: date
    duration_days: int
    milestones: list[PlanProposalMilestoneView]
    days: list[PlanProposalDayView]
    total_task_count: int
    proposal_hash: str
    profile_hash: str
    assessment_result_id: UUID
    schema_version: Literal["profile-plan-proposal-v1"]
    model_name: str
    prompt_version: Literal["profile-plan-proposal-v1"]
    api_version: str
    outline_prompt_version: str
    tasks_prompt_version: str
    applied_plan_id: UUID | None
    decided_at: datetime | None
    created_at: datetime
    requested_start_on: date
    requested_end_on: date
    has_previous: bool
    has_next: bool


def build_plan_proposal_view(
    stored: StoredPlanProposal, *, start_on: date | None, days: int = 7
) -> PlanProposalView:
    proposal = stored.content
    requested_start = start_on or proposal.starts_on
    if not proposal.starts_on <= requested_start <= proposal.ends_on:
        raise PlanWindowOutOfRangeError()
    requested_end = min(requested_start + timedelta(days=days - 1), proposal.ends_on)
    day_views = [
        PlanProposalDayView(
            plan_day=index,
            date=day.date,
            tasks=[
                PlanProposalTaskView(
                    slot=slot,
                    title=task.title,
                    description=task.description,
                )
                for slot, task in enumerate(day.tasks, start=1)
            ],
        )
        for index, day in enumerate(proposal.days, start=1)
        if requested_start <= day.date <= requested_end
    ]
    return PlanProposalView(
        id=stored.id,
        request_id=stored.request_id,
        decision_status=stored.decision_status,
        title=proposal.title,
        summary=proposal.summary,
        generated_on=proposal.generated_on,
        starts_on=proposal.starts_on,
        ends_on=proposal.ends_on,
        duration_days=proposal.duration_days,
        milestones=[
            PlanProposalMilestoneView.model_validate(item.model_dump())
            for item in proposal.milestones
        ],
        days=day_views,
        total_task_count=proposal.total_task_count,
        proposal_hash=proposal.proposal_hash,
        profile_hash=proposal.profile_hash,
        assessment_result_id=proposal.assessment_result_id,
        schema_version=proposal.schema_version,
        model_name=stored.model_name,
        prompt_version=stored.prompt_version,
        api_version=proposal.engine.api_version,
        outline_prompt_version=proposal.engine.outline_prompt_version,
        tasks_prompt_version=proposal.engine.tasks_prompt_version,
        applied_plan_id=stored.applied_plan_id,
        decided_at=stored.decided_at,
        created_at=stored.created_at,
        requested_start_on=requested_start,
        requested_end_on=requested_end,
        has_previous=requested_start > proposal.starts_on,
        has_next=requested_end < proposal.ends_on,
    )


class PlanMilestoneView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    week_index: int
    starts_on: date
    ends_on: date
    scheduled_at: datetime
    title: str
    description: str


class PlanTaskView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    plan_day: int
    slot: int
    date: date
    scheduled_at: datetime
    title: str
    description: str
    status: Literal["pending", "completed"]
    completed_at: datetime | None


class PlanDayView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    plan_day: int
    date: date
    tasks: list[PlanTaskView]
    completed_task_count: int
    total_task_count: int
    achieved: bool
    achieved_at: datetime | None
    earned_exp: Literal[0, 20]


class PlanView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    proposal_result_id: UUID
    proposal_hash: str
    profile_hash: str
    assessment_result_id: UUID
    title: str
    summary: str
    starts_on: date
    ends_on: date
    duration_days: int
    status: Literal["draft", "active", "completed", "expired", "superseded", "rejected"]
    milestones: list[PlanMilestoneView]
    days: list[PlanDayView]
    total_task_count: int
    completed_task_count: int
    percent: int
    user_exp: int
    schema_version: Literal["profile-plan-proposal-v1"]
    model_name: str
    prompt_version: Literal["profile-plan-proposal-v1"]
    api_version: str
    outline_prompt_version: str
    tasks_prompt_version: str
    activated_at: datetime
    ended_at: datetime | None
    restart_offer_status: Literal["not_due", "pending", "accepted", "declined"]
    restart_prompted_at: datetime | None
    requested_start_on: date
    requested_end_on: date
    has_previous: bool
    has_next: bool


class TaskUpdateView(PlanTaskView):
    completed_task_count: int
    total_task_count: int
    percent: int
    day_completed_task_count: int
    day_total_task_count: int
    achieved: bool
    achieved_at: datetime | None
    earned_exp: Literal[0, 20]
    exp_delta: Literal[-20, 0, 20]
    user_exp: int


class TodayQuestView(StrictPlanModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    plan_id: UUID | None
    plan_title: str | None
    quests: list[PlanTaskView]
    completed_count: int
    total_count: int
    percent: int
    achieved: bool
    earned_exp: Literal[0, 20]
    user_exp: int


def _matches_frozen_schedule(
    value: datetime, *, expected_date: date, expected_time: time | None
) -> bool:
    if value.tzinfo is None:
        raise PlanDataIntegrityError()
    local = value.astimezone(ZoneInfo("Asia/Seoul"))
    return local.date() == expected_date and (
        expected_time is None or local.timetz().replace(tzinfo=None) == expected_time
    )


def _task_view(
    item: PlanScheduleItem,
    *,
    expected_date: date,
    expected_time: time | None = None,
) -> PlanTaskView:
    if (
        item.kind != "task"
        or not item.counts_toward_progress
        or item.plan_day is None
        or item.slot is None
        or item.scheduled_at is None
        or item.description is None
        or item.status not in ("pending", "completed")
        or (item.status == "completed") != (item.completed_at is not None)
        or item.remind_at is not None
        or item.detail_status != "ready"
        or not _matches_frozen_schedule(
            item.scheduled_at,
            expected_date=expected_date,
            expected_time=expected_time,
        )
    ):
        raise PlanDataIntegrityError()
    return PlanTaskView(
        id=item.id,
        plan_day=item.plan_day,
        slot=item.slot,
        date=expected_date,
        scheduled_at=item.scheduled_at,
        title=item.title,
        description=item.description,
        status=item.status,
        completed_at=item.completed_at,
    )


def _validated_projection(
    stored: StoredPlan,
) -> tuple[list[PlanMilestoneView], list[PlanTaskView], int]:
    proposal = stored.proposal.content
    if (
        stored.proposal.decision_status != "applied"
        or stored.proposal.applied_plan_id != stored.id
        or stored.title != proposal.title
        or stored.summary != proposal.summary
        or stored.starts_on != proposal.starts_on
        or stored.ends_on != proposal.ends_on
        or stored.total_task_count != proposal.total_task_count
        or stored.total_task_count <= 0
        or stored.goal_snapshot != proposal.profile_snapshot.model_dump(mode="json")
        or stored.activated_at is None
    ):
        raise PlanDataIntegrityError()

    milestone_items = [item for item in stored.schedule_items if item.kind == "milestone"]
    task_items = [
        item
        for item in stored.schedule_items
        if item.kind == "task" and item.counts_toward_progress
    ]
    if len(milestone_items) + len(task_items) != len(stored.schedule_items):
        raise PlanDataIntegrityError()
    if (
        len(milestone_items) != len(proposal.milestones)
        or len(task_items) != proposal.total_task_count
    ):
        raise PlanDataIntegrityError()
    if len({item.id for item in stored.schedule_items}) != len(stored.schedule_items):
        raise PlanDataIntegrityError()

    by_week: dict[int, PlanScheduleItem] = {}
    for item in milestone_items:
        week = item.metadata.get("week_index")
        if not isinstance(week, int) or week in by_week:
            raise PlanDataIntegrityError()
        by_week[week] = item
    milestone_views: list[PlanMilestoneView] = []
    for expected in proposal.milestones:
        item = by_week.get(expected.week_index)
        if (
            item is None
            or item.counts_toward_progress
            or item.plan_day is not None
            or item.slot is not None
            or item.scheduled_at is None
            or item.remind_at is not None
            or item.status != "pending"
            or item.completed_at is not None
            or item.detail_status != "ready"
            or item.title != expected.title
            or item.description != expected.description
            or item.metadata.get("starts_on") != expected.starts_on.isoformat()
            or item.metadata.get("ends_on") != expected.ends_on.isoformat()
            or not _matches_frozen_schedule(
                item.scheduled_at,
                expected_date=expected.ends_on,
                expected_time=proposal.profile_snapshot.daily_notification_time,
            )
        ):
            raise PlanDataIntegrityError()
        milestone_views.append(
            PlanMilestoneView(
                id=item.id,
                week_index=expected.week_index,
                starts_on=expected.starts_on,
                ends_on=expected.ends_on,
                scheduled_at=item.scheduled_at,
                title=item.title,
                description=item.description,
            )
        )

    by_position: dict[tuple[int, int], PlanScheduleItem] = {}
    for item in task_items:
        if item.plan_day is None or item.slot is None:
            raise PlanDataIntegrityError()
        key = (item.plan_day, item.slot)
        if key in by_position:
            raise PlanDataIntegrityError()
        by_position[key] = item
    task_views: list[PlanTaskView] = []
    for plan_day, day in enumerate(proposal.days, start=1):
        for slot, expected in enumerate(day.tasks, start=1):
            item = by_position.get((plan_day, slot))
            if (
                item is None
                or item.title != expected.title
                or item.description != expected.description
            ):
                raise PlanDataIntegrityError()
            task_views.append(
                _task_view(
                    item,
                    expected_date=day.date,
                    expected_time=proposal.profile_snapshot.daily_notification_time,
                )
            )
    if len(task_views) != len(task_items):
        raise PlanDataIntegrityError()
    completed = sum(item.status == "completed" for item in task_views)
    if stored.status == "active" and (
        stored.ended_at is not None
        or stored.restart_offer_status != "not_due"
        or stored.restart_prompted_at is not None
    ):
        raise PlanDataIntegrityError()
    if stored.status == "completed" and (
        completed != stored.total_task_count
        or stored.ended_at is None
        or stored.restart_offer_status not in ("pending", "accepted", "declined")
        or stored.restart_prompted_at is None
    ):
        raise PlanDataIntegrityError()
    return milestone_views, task_views, completed


def build_plan_view(
    stored: StoredPlan, *, start_on: date | None, days: int = 7, today: date
) -> PlanView:
    proposal = stored.proposal.content
    milestones, tasks, completed = _validated_projection(stored)
    achievements = _validated_daily_achievements(stored, tasks)
    requested_start = start_on or min(max(today, stored.starts_on), stored.ends_on)
    if not stored.starts_on <= requested_start <= stored.ends_on:
        raise PlanWindowOutOfRangeError()
    requested_end = min(requested_start + timedelta(days=days - 1), stored.ends_on)
    tasks_by_day: dict[int, list[PlanTaskView]] = {}
    for task in tasks:
        if requested_start <= task.date <= requested_end:
            tasks_by_day.setdefault(task.plan_day, []).append(task)
    day_views: list[PlanDayView] = []
    for index, day in enumerate(proposal.days, start=1):
        if not requested_start <= day.date <= requested_end:
            continue
        day_tasks = tasks_by_day.get(index, [])
        achievement = achievements[index]
        day_views.append(
            PlanDayView(
                plan_day=index,
                date=day.date,
                tasks=day_tasks,
                completed_task_count=sum(task.status == "completed" for task in day_tasks),
                total_task_count=len(day_tasks),
                achieved=achievement.achieved,
                achieved_at=achievement.achieved_at,
                earned_exp=achievement.exp_awarded,
            )
        )
    return PlanView(
        id=stored.id,
        proposal_result_id=stored.proposal.id,
        proposal_hash=proposal.proposal_hash,
        profile_hash=proposal.profile_hash,
        assessment_result_id=proposal.assessment_result_id,
        title=stored.title,
        summary=proposal.summary,
        starts_on=stored.starts_on,
        ends_on=stored.ends_on,
        duration_days=(stored.ends_on - stored.starts_on).days + 1,
        status=stored.status,
        milestones=milestones,
        days=day_views,
        total_task_count=stored.total_task_count,
        completed_task_count=completed,
        percent=completed * 100 // stored.total_task_count,
        user_exp=stored.user_exp,
        schema_version=proposal.schema_version,
        model_name=stored.proposal.model_name,
        prompt_version=stored.proposal.prompt_version,
        api_version=proposal.engine.api_version,
        outline_prompt_version=proposal.engine.outline_prompt_version,
        tasks_prompt_version=proposal.engine.tasks_prompt_version,
        activated_at=stored.activated_at,
        ended_at=stored.ended_at,
        restart_offer_status=stored.restart_offer_status,
        restart_prompted_at=stored.restart_prompted_at,
        requested_start_on=requested_start,
        requested_end_on=requested_end,
        has_previous=requested_start > stored.starts_on,
        has_next=requested_end < stored.ends_on,
    )


def build_task_update_view(update: StoredTaskUpdate) -> TaskUpdateView:
    task = _task_view(update.task, expected_date=update.task_date)
    if (
        update.total_task_count <= 0
        or not 0 <= update.completed_task_count <= update.total_task_count
        or update.day_total_task_count <= 0
        or not 0 <= update.day_completed_task_count <= update.day_total_task_count
        or update.achieved != (update.day_completed_task_count == update.day_total_task_count)
        or update.earned_exp != (20 if update.achieved else 0)
        or (update.achieved_at is not None) != update.achieved
    ):
        raise PlanDataIntegrityError()
    return TaskUpdateView(
        **task.model_dump(),
        completed_task_count=update.completed_task_count,
        total_task_count=update.total_task_count,
        percent=update.completed_task_count * 100 // update.total_task_count,
        day_completed_task_count=update.day_completed_task_count,
        day_total_task_count=update.day_total_task_count,
        achieved=update.achieved,
        achieved_at=update.achieved_at,
        earned_exp=update.earned_exp,
        exp_delta=update.exp_delta,
        user_exp=update.user_exp,
    )


def build_today_quest_view(snapshot: TodayQuestSnapshot) -> TodayQuestView:
    if (snapshot.plan_id is None) != (snapshot.plan_title is None):
        raise PlanDataIntegrityError()
    if snapshot.plan_id is None:
        if snapshot.tasks or snapshot.achievement is not None:
            raise PlanDataIntegrityError()
        return TodayQuestView(
            date=snapshot.date,
            plan_id=None,
            plan_title=None,
            quests=[],
            completed_count=0,
            total_count=0,
            percent=0,
            achieved=False,
            earned_exp=0,
            user_exp=snapshot.user_exp,
        )
    if not snapshot.tasks:
        if snapshot.achievement is not None:
            raise PlanDataIntegrityError()
        return TodayQuestView(
            date=snapshot.date,
            plan_id=snapshot.plan_id,
            plan_title=snapshot.plan_title,
            quests=[],
            completed_count=0,
            total_count=0,
            percent=0,
            achieved=False,
            earned_exp=0,
            user_exp=snapshot.user_exp,
        )
    quests = [_task_view(item, expected_date=snapshot.date) for item in snapshot.tasks]
    achievement = snapshot.achievement
    plan_days = {item.plan_day for item in quests}
    if (
        achievement is None
        or achievement.plan_id != snapshot.plan_id
        or achievement.goal_date != snapshot.date
        or plan_days != {achievement.plan_day}
    ):
        raise PlanDataIntegrityError()
    completed = sum(item.status == "completed" for item in quests)
    total = len(quests)
    achieved = completed == total
    achieved_at = (
        max(item.completed_at for item in quests if item.completed_at is not None)
        if achieved
        else None
    )
    if (
        achievement.achieved != achieved
        or achievement.achieved_at != achieved_at
        or achievement.exp_awarded != (20 if achieved else 0)
    ):
        raise PlanDataIntegrityError()
    return TodayQuestView(
        date=snapshot.date,
        plan_id=snapshot.plan_id,
        plan_title=snapshot.plan_title,
        quests=quests,
        completed_count=completed,
        total_count=total,
        percent=completed * 100 // total,
        achieved=achievement.achieved,
        earned_exp=achievement.exp_awarded,
        user_exp=snapshot.user_exp,
    )


def _validated_daily_achievements(
    stored: StoredPlan, tasks: list[PlanTaskView]
) -> dict[int, DailyGoalAchievement]:
    proposal = stored.proposal.content
    achievements = stored.daily_goal_achievements
    if len(achievements) != len(proposal.days):
        raise PlanDataIntegrityError()
    by_day = {achievement.plan_day: achievement for achievement in achievements}
    if len(by_day) != len(achievements):
        raise PlanDataIntegrityError()
    for plan_day, day in enumerate(proposal.days, start=1):
        achievement = by_day.get(plan_day)
        day_tasks = [task for task in tasks if task.plan_day == plan_day]
        if (
            achievement is None
            or achievement.user_id != stored.user_id
            or achievement.plan_id != stored.id
            or achievement.goal_date != day.date
            or not day_tasks
        ):
            raise PlanDataIntegrityError()
        achieved = all(task.status == "completed" for task in day_tasks)
        achieved_at = (
            max(task.completed_at for task in day_tasks if task.completed_at is not None)
            if achieved
            else None
        )
        if (
            achievement.achieved != achieved
            or achievement.achieved_at != achieved_at
            or achievement.exp_awarded != (20 if achieved else 0)
        ):
            raise PlanDataIntegrityError()
    return by_day
