from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.plans.models import (
    Hex64,
    ProfilePlanOutlineV1,
    ProfilePlanProposalV1,
    ProfilePlanTasksV1,
    StrictPlanModel,
    validate_exact_days,
    validate_milestones,
)
from app.profiles.models import ProfileOnboardingData


class GenerationCheckpoint(StrictPlanModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    checkpoint_version: Literal["plan-generation-checkpoint-v1"] = "plan-generation-checkpoint-v1"
    kind: Literal["profile_plan_proposal"] = "profile_plan_proposal"
    user_id: UUID
    request_id: UUID
    profile_snapshot: ProfileOnboardingData
    profile_hash: Hex64
    assessment_result_id: UUID
    assessment_score: int = Field(ge=0, le=100)
    assessment_level: Literal["beginner", "intermediate", "advanced"]
    assessment_summary: dict[str, Any]
    generated_on: date
    starts_on: date
    ends_on: date
    duration_days: int = Field(ge=1, le=365)
    outline: ProfilePlanOutlineV1 | None = None
    batches: dict[int, ProfilePlanTasksV1] = Field(default_factory=dict)
    proposal: ProfilePlanProposalV1 | None = None

    @model_validator(mode="after")
    def validate_frozen_context(self) -> GenerationCheckpoint:
        if self.generated_on != self.starts_on:
            raise ValueError("generated_on must equal starts_on")
        if self.ends_on != self.profile_snapshot.target_date:
            raise ValueError("ends_on must equal profile target_date")
        if self.duration_days != (self.ends_on - self.starts_on).days + 1:
            raise ValueError("duration_days does not match frozen dates")
        if self.outline is not None:
            validate_milestones(self.outline.milestones, self.starts_on, self.ends_on)
        expected_batch_count = (self.duration_days + 27) // 28
        if any(index < 0 or index >= expected_batch_count for index in self.batches):
            raise ValueError("checkpoint contains an unexpected batch index")
        for index, batch in self.batches.items():
            batch_start = self.starts_on + timedelta(days=index * 28)
            batch_length = min(28, self.duration_days - index * 28)
            expected_dates = tuple(
                batch_start + timedelta(days=offset) for offset in range(batch_length)
            )
            validate_exact_days(expected_dates, batch.days)
        if self.proposal is not None:
            if (
                self.proposal.profile_snapshot != self.profile_snapshot
                or self.proposal.profile_hash != self.profile_hash
                or self.proposal.assessment_result_id != self.assessment_result_id
                or self.proposal.generated_on != self.generated_on
                or self.proposal.starts_on != self.starts_on
                or self.proposal.ends_on != self.ends_on
            ):
                raise ValueError("proposal does not match frozen checkpoint context")
            if self.outline is None or set(self.batches) != set(range(expected_batch_count)):
                raise ValueError("complete proposal requires every checkpoint artifact")
            if (
                self.proposal.title != self.outline.title
                or self.proposal.summary != self.outline.summary
                or self.proposal.milestones != self.outline.milestones
            ):
                raise ValueError("proposal does not match checkpoint outline")
            checkpoint_days = [
                day for index in range(expected_batch_count) for day in self.batches[index].days
            ]
            if self.proposal.days != checkpoint_days:
                raise ValueError("proposal does not match checkpoint batches")
        return self
