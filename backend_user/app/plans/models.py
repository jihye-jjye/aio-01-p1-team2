from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.profiles.models import ProfileOnboardingData
from app.structured import StructuredOutputValidationError

PROFILE_PLAN_OUTLINE_VERSION = "profile-plan-outline-v1"
PROFILE_PLAN_TASKS_VERSION = "profile-plan-tasks-v1"
PROFILE_PLAN_PROPOSAL_VERSION = "profile-plan-proposal-v1"

NonBlank200 = Annotated[str, Field(min_length=1, max_length=200)]
NonBlank2000 = Annotated[str, Field(min_length=1, max_length=2000)]
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StrictPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfilePlanGenerationContext(StrictPlanModel):
    profile_snapshot: ProfileOnboardingData
    profile_hash: Hex64
    assessment_result_id: UUID
    assessment_score: int = Field(ge=0, le=100)
    assessment_level: Literal["beginner", "intermediate", "advanced"]
    assessment_summary: dict[str, Any]
    generated_on: date
    target_date: date

    @model_validator(mode="after")
    def validate_snapshot_target_date(self) -> ProfilePlanGenerationContext:
        if self.target_date != self.profile_snapshot.target_date:
            raise ValueError("target_date must equal profile_snapshot.target_date")
        return self


class ProfilePlanMilestone(StrictPlanModel):
    week_index: int = Field(ge=1, le=53)
    starts_on: date
    ends_on: date
    title: NonBlank200
    description: NonBlank2000


class ProfilePlanOutlineV1(StrictPlanModel):
    title: NonBlank200
    summary: NonBlank2000
    milestones: list[ProfilePlanMilestone] = Field(min_length=1, max_length=53)


class ProfilePlanTask(StrictPlanModel):
    title: NonBlank200
    description: NonBlank2000


class ProfilePlanDay(StrictPlanModel):
    date: date
    tasks: list[ProfilePlanTask] = Field(min_length=1, max_length=3)


class ProfilePlanTasksV1(StrictPlanModel):
    days: list[ProfilePlanDay] = Field(min_length=1, max_length=28)


class ProfilePlanEngine(StrictPlanModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    provider: Literal["google"] = "google"
    model: Literal["gemini-3.6-flash"] = "gemini-3.6-flash"
    api_version: Literal["v1"] = "v1"
    store: Literal[False] = False
    thinking_level: Literal["medium"] = "medium"
    outline_prompt_version: Literal["profile-plan-outline-v1"] = PROFILE_PLAN_OUTLINE_VERSION
    tasks_prompt_version: Literal["profile-plan-tasks-v1"] = PROFILE_PLAN_TASKS_VERSION


class ProfilePlanProposalV1(StrictPlanModel):
    schema_version: Literal["profile-plan-proposal-v1"] = PROFILE_PLAN_PROPOSAL_VERSION
    profile_snapshot: ProfileOnboardingData
    profile_hash: Hex64
    assessment_result_id: UUID
    generated_on: date
    starts_on: date
    ends_on: date
    duration_days: int = Field(ge=1, le=365)
    title: NonBlank200
    summary: NonBlank2000
    milestones: list[ProfilePlanMilestone] = Field(min_length=1, max_length=53)
    days: list[ProfilePlanDay] = Field(min_length=1, max_length=365)
    total_task_count: int = Field(ge=1, le=1095)
    proposal_hash: Hex64
    engine: ProfilePlanEngine

    @model_validator(mode="after")
    def validate_server_contract(self) -> ProfilePlanProposalV1:
        if self.starts_on != self.generated_on:
            raise ValueError("starts_on must equal generated_on")
        if self.ends_on != self.profile_snapshot.target_date:
            raise ValueError("ends_on must equal profile_snapshot.target_date")
        expected_duration = (self.ends_on - self.starts_on).days + 1
        if self.duration_days != expected_duration or not 1 <= expected_duration <= 365:
            raise ValueError("duration_days does not match the inclusive date range")
        expected_dates = tuple(
            self.starts_on + timedelta(days=offset) for offset in range(expected_duration)
        )
        try:
            validate_exact_days(expected_dates, self.days)
            validate_milestones(self.milestones, self.starts_on, self.ends_on)
        except StructuredOutputValidationError as exc:
            raise ValueError(str(exc)) from exc
        expected_total = sum(len(day.tasks) for day in self.days)
        if self.total_task_count != expected_total:
            raise ValueError("total_task_count does not match tasks")
        expected_hash = profile_plan_proposal_hash(
            self.model_dump(mode="json", exclude={"proposal_hash"})
        )
        if self.proposal_hash != expected_hash:
            raise ValueError("proposal_hash does not match canonical proposal content")
        return self


def validate_milestones(
    milestones: list[ProfilePlanMilestone], starts_on: date, ends_on: date
) -> None:
    duration_days = (ends_on - starts_on).days + 1
    expected_count = (duration_days + 6) // 7
    invalid_windows: list[tuple[int, date, date]] = []
    for position, milestone in enumerate(milestones, start=1):
        expected_start = starts_on + timedelta(days=(position - 1) * 7)
        expected_end = min(expected_start + timedelta(days=6), ends_on)
        if (
            milestone.week_index != position
            or milestone.starts_on != expected_start
            or milestone.ends_on != expected_end
        ):
            invalid_windows.append((position, expected_start, expected_end))
    if len(milestones) != expected_count or invalid_windows:
        raise StructuredOutputValidationError(
            "milestone_schedule",
            details={
                "actual_count": len(milestones),
                "expected_count": expected_count,
                "invalid_windows": invalid_windows,
            },
        )


def validate_exact_days(expected_dates: tuple[date, ...], days: list[ProfilePlanDay]) -> None:
    actual_dates = [day.date for day in days]
    expected_set = set(expected_dates)
    counts = Counter(actual_dates)
    missing = sorted(expected_set - set(actual_dates))
    duplicate = sorted(item for item, count in counts.items() if count > 1)
    unexpected = sorted(set(actual_dates) - expected_set)
    order_invalid = actual_dates != list(expected_dates)
    if (
        missing
        or duplicate
        or unexpected
        or len(actual_dates) != len(expected_dates)
        or order_invalid
    ):
        raise StructuredOutputValidationError(
            "day_schedule",
            details={
                "missing": missing,
                "duplicate": duplicate,
                "unexpected": unexpected,
                "out_of_range": unexpected,
                "actual_count": len(actual_dates),
                "expected_count": len(expected_dates),
                "order_invalid": order_invalid,
            },
        )


def profile_plan_proposal_hash(content_without_hash: dict[str, Any]) -> str:
    canonical = json.dumps(
        content_without_hash,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
