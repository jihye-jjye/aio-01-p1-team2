from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.plans.models import Hex64, ProfilePlanProposalV1, StrictPlanModel
from app.profiles.models import ProfileOnboardingData
from app.saved_jobs.models import SavedJobView


class StoredPlanProposal(StrictPlanModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: UUID
    user_id: UUID
    request_id: UUID
    saved_job_id: UUID | None = None
    decision_status: Literal["pending", "applied", "rejected"]
    content: ProfilePlanProposalV1
    model_name: str
    prompt_version: Literal["profile-plan-proposal-v1"]
    applied_plan_id: UUID | None
    decided_at: datetime | None
    created_at: datetime

    @model_validator(mode="after")
    def validate_storage_metadata(self) -> StoredPlanProposal:
        snapshot_id = (
            self.content.saved_job_snapshot.id
            if self.content.saved_job_snapshot is not None
            else None
        )
        if self.saved_job_id != snapshot_id:
            raise ValueError("stored saved_job_id does not match proposal snapshot")
        if self.model_name != self.content.engine.model:
            raise ValueError("stored model_name does not match proposal engine")
        if self.decision_status == "pending" and (
            self.applied_plan_id is not None or self.decided_at is not None
        ):
            raise ValueError("pending proposal cannot have terminal metadata")
        if self.decision_status == "rejected" and (
            self.applied_plan_id is not None or self.decided_at is None
        ):
            raise ValueError("rejected proposal metadata is inconsistent")
        if self.decision_status == "applied" and (
            self.applied_plan_id is None or self.decided_at is None
        ):
            raise ValueError("applied proposal metadata is incomplete")
        return self


class PlanGenerationPreflight(StrictPlanModel):
    profile_snapshot: ProfileOnboardingData
    profile_hash: Hex64
    assessment_result_id: UUID
    assessment_score: int = Field(ge=0, le=100)
    assessment_level: Literal["beginner", "intermediate", "advanced"]
    assessment_summary: dict[str, Any]
    saved_job_snapshot: SavedJobView | None = None
    active_plan_exists: bool = False
    pending_request_id: UUID | None = None


class PlanScheduleItem(StrictPlanModel):
    id: UUID
    kind: Literal["milestone", "task", "interview"]
    title: str
    description: str | None
    scheduled_at: datetime | None
    remind_at: datetime | None
    status: Literal["pending", "in_progress", "completed", "cancelled"]
    plan_day: int | None
    slot: int | None
    detail_status: Literal["outline", "ready"]
    counts_toward_progress: bool
    metadata: dict[str, Any]
    completed_at: datetime | None


class DailyGoalAchievement(StrictPlanModel):
    user_id: UUID
    plan_id: UUID
    plan_day: int = Field(gt=0)
    goal_date: date
    achieved: bool
    achieved_at: datetime | None
    exp_awarded: Literal[0, 20]

    @model_validator(mode="after")
    def validate_state(self) -> DailyGoalAchievement:
        if self.achieved:
            if self.achieved_at is None or self.exp_awarded != 20:
                raise ValueError("achieved daily goal metadata is inconsistent")
        elif self.achieved_at is not None or self.exp_awarded != 0:
            raise ValueError("pending daily goal metadata is inconsistent")
        return self


class StoredPlan(StrictPlanModel):
    id: UUID
    user_id: UUID
    proposal: StoredPlanProposal
    title: str
    summary: str | None
    goal_snapshot: dict[str, Any]
    starts_on: date
    ends_on: date
    total_task_count: int
    status: Literal["draft", "active", "completed", "expired", "superseded", "rejected"]
    activated_at: datetime | None
    ended_at: datetime | None
    restart_offer_status: Literal["not_due", "pending", "accepted", "declined"]
    restart_prompted_at: datetime | None
    schedule_items: list[PlanScheduleItem]
    daily_goal_achievements: list[DailyGoalAchievement]
    user_exp: int = Field(ge=0)
    view_today: date | None = None


class StoredTaskUpdate(StrictPlanModel):
    task: PlanScheduleItem
    task_date: date
    completed_task_count: int
    total_task_count: int
    day_completed_task_count: int
    day_total_task_count: int
    achieved: bool
    achieved_at: datetime | None
    earned_exp: Literal[0, 20]
    exp_delta: Literal[-20, 0, 20]
    user_exp: int = Field(ge=0)


class TodayQuestSnapshot(StrictPlanModel):
    date: date
    plan_id: UUID | None
    plan_title: str | None
    tasks: list[PlanScheduleItem]
    achievement: DailyGoalAchievement | None
    user_exp: int = Field(ge=0)


class PlanSummarySnapshot(StrictPlanModel):
    plans: list[StoredPlan]
    user_exp: int = Field(ge=0)
