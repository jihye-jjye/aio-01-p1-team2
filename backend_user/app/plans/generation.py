from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.plans.errors import PlanHorizonTooLongError, PlanTargetDateExpiredError
from app.plans.models import (
    PROFILE_PLAN_PROPOSAL_VERSION,
    ProfilePlanEngine,
    ProfilePlanGenerationContext,
    ProfilePlanOutlineV1,
    ProfilePlanProposalV1,
    ProfilePlanTasksV1,
    profile_plan_proposal_hash,
    validate_exact_days,
    validate_milestones,
)
from app.profiles.models import ProfileOnboardingData


class PlanGenerationError(RuntimeError):
    pass


class PlanDateBatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=0, le=13)
    starts_on: date
    ends_on: date
    expected_dates: tuple[date, ...] = Field(min_length=1, max_length=28)


class PlanOutlinePort(Protocol):
    @property
    def engine(self) -> ProfilePlanEngine: ...

    async def generate_outline(
        self,
        *,
        user_id: UUID,
        context: ProfilePlanGenerationContext,
    ) -> ProfilePlanOutlineV1: ...


class PlanTaskPort(Protocol):
    @property
    def engine(self) -> ProfilePlanEngine: ...

    async def generate_task_batch(
        self,
        *,
        user_id: UUID,
        context: ProfilePlanGenerationContext,
        outline: ProfilePlanOutlineV1,
        batch: PlanDateBatch,
    ) -> ProfilePlanTasksV1: ...


class PlanRevisionPort(Protocol):
    async def revise_outline(
        self,
        *,
        user_id: UUID,
        context: ProfilePlanGenerationContext,
        existing_proposal: ProfilePlanProposalV1,
        feedback: str,
    ) -> ProfilePlanOutlineV1: ...


type OutlineCompleted = Callable[[ProfilePlanOutlineV1], Awaitable[None]]
type BatchCompleted = Callable[[PlanDateBatch, ProfilePlanTasksV1], Awaitable[None]]


def kst_today(clock: Callable[[], datetime] | None = None) -> date:
    now = clock() if clock is not None else datetime.now(UTC)
    return now.astimezone(ZoneInfo("Asia/Seoul")).date()


def validate_horizon(generated_on: date, target_date: date) -> int:
    if target_date < generated_on:
        raise PlanTargetDateExpiredError("프로필 목표일이 이미 지났습니다.")
    duration_days = (target_date - generated_on).days + 1
    if duration_days > 365:
        raise PlanHorizonTooLongError("프로필 계획 기간은 최대 365일입니다.")
    return duration_days


def build_date_batches(starts_on: date, ends_on: date) -> list[PlanDateBatch]:
    duration_days = validate_horizon(starts_on, ends_on)
    dates = tuple(starts_on + timedelta(days=offset) for offset in range(duration_days))
    return [
        PlanDateBatch(
            index=index,
            starts_on=batch_dates[0],
            ends_on=batch_dates[-1],
            expected_dates=batch_dates,
        )
        for index, offset in enumerate(range(0, duration_days, 28))
        if (batch_dates := dates[offset : offset + 28])
    ]


class ProfilePlanGenerator:
    def __init__(
        self,
        *,
        outline_port: PlanOutlinePort,
        task_port: PlanTaskPort,
        revision_port: PlanRevisionPort | None = None,
        today_provider: Callable[[], date] = kst_today,
    ) -> None:
        self._outline_port = outline_port
        self._task_port = task_port
        self._revision_port = revision_port
        self._today_provider = today_provider
        if outline_port.engine != task_port.engine:
            raise PlanGenerationError("outline and task provider provenance must match")
        self._engine = ProfilePlanEngine.model_validate(task_port.engine.model_dump(mode="json"))

    async def generate(
        self,
        *,
        user_id: UUID,
        profile_snapshot: ProfileOnboardingData,
        profile_hash: str,
        assessment_result_id: UUID,
        assessment_score: int,
        assessment_level: Literal["beginner", "intermediate", "advanced"],
        assessment_summary: dict[str, Any],
        generated_on: date | None = None,
        cached_outline: ProfilePlanOutlineV1 | None = None,
        cached_batches: Mapping[int, ProfilePlanTasksV1] | None = None,
        outline_completed: OutlineCompleted | None = None,
        batch_completed: BatchCompleted | None = None,
    ) -> ProfilePlanProposalV1:
        plan_start = generated_on or self._today_provider()
        duration_days = validate_horizon(plan_start, profile_snapshot.target_date)
        context = ProfilePlanGenerationContext(
            profile_snapshot=profile_snapshot,
            profile_hash=profile_hash,
            assessment_result_id=assessment_result_id,
            assessment_score=assessment_score,
            assessment_level=assessment_level,
            assessment_summary=assessment_summary,
            generated_on=plan_start,
            target_date=profile_snapshot.target_date,
        )
        batches = build_date_batches(plan_start, profile_snapshot.target_date)

        if cached_outline is None:
            outline = await self._outline_port.generate_outline(user_id=user_id, context=context)
            validate_milestones(outline.milestones, plan_start, profile_snapshot.target_date)
            if outline_completed is not None:
                await outline_completed(outline)
        else:
            validate_milestones(cached_outline.milestones, plan_start, profile_snapshot.target_date)
            outline = cached_outline

        batch_by_index = {batch.index: batch for batch in batches}
        cached = dict(cached_batches or {})
        unexpected_indexes = sorted(set(cached) - set(batch_by_index))
        if unexpected_indexes:
            raise StructuredPlanCacheError(f"unexpected cached batch indexes: {unexpected_indexes}")

        results: dict[int, ProfilePlanTasksV1] = {}
        for index, result in cached.items():
            validate_exact_days(batch_by_index[index].expected_dates, result.days)
            results[index] = result

        semaphore = asyncio.Semaphore(3)

        async def generate_batch(batch: PlanDateBatch) -> None:
            async with semaphore:
                result = await self._task_port.generate_task_batch(
                    user_id=user_id,
                    context=context,
                    outline=outline,
                    batch=batch,
                )
            validate_exact_days(batch.expected_dates, result.days)
            results[batch.index] = result
            if batch_completed is not None:
                await batch_completed(batch, result)

        async with asyncio.TaskGroup() as task_group:
            for batch in batches:
                if batch.index not in results:
                    task_group.create_task(generate_batch(batch))

        ordered_days = [day for batch in batches for day in results[batch.index].days]
        validate_exact_days(
            tuple(plan_start + timedelta(days=offset) for offset in range(duration_days)),
            ordered_days,
        )
        total_task_count = sum(len(day.tasks) for day in ordered_days)
        content: dict[str, Any] = {
            "schema_version": PROFILE_PLAN_PROPOSAL_VERSION,
            "profile_snapshot": profile_snapshot.model_dump(mode="json"),
            "profile_hash": profile_hash,
            "assessment_result_id": str(assessment_result_id),
            "generated_on": plan_start.isoformat(),
            "starts_on": plan_start.isoformat(),
            "ends_on": profile_snapshot.target_date.isoformat(),
            "duration_days": duration_days,
            "title": outline.title,
            "summary": outline.summary,
            "milestones": [item.model_dump(mode="json") for item in outline.milestones],
            "days": [item.model_dump(mode="json") for item in ordered_days],
            "total_task_count": total_task_count,
            "engine": self._engine.model_dump(mode="json"),
        }
        return ProfilePlanProposalV1(
            **content,
            proposal_hash=profile_plan_proposal_hash(content),
        )

    async def revise(
        self,
        *,
        user_id: UUID,
        existing_proposal: ProfilePlanProposalV1,
        feedback: str,
        assessment_score: int = 0,
        assessment_level: Literal["beginner", "intermediate", "advanced"] = "beginner",
        assessment_summary: dict[str, Any] | None = None,
        outline_completed: OutlineCompleted | None = None,
        batch_completed: BatchCompleted | None = None,
    ) -> ProfilePlanProposalV1:
        if self._revision_port is None:
            raise PlanGenerationError("revision_port is not configured")

        profile_snapshot = existing_proposal.profile_snapshot
        profile_hash = existing_proposal.profile_hash
        assessment_result_id = existing_proposal.assessment_result_id
        plan_start = existing_proposal.generated_on

        duration_days = validate_horizon(plan_start, profile_snapshot.target_date)
        context = ProfilePlanGenerationContext(
            profile_snapshot=profile_snapshot,
            profile_hash=profile_hash,
            assessment_result_id=assessment_result_id,
            assessment_score=assessment_score,
            assessment_level=assessment_level,
            assessment_summary=assessment_summary or {},
            generated_on=plan_start,
            target_date=profile_snapshot.target_date,
        )
        batches = build_date_batches(plan_start, profile_snapshot.target_date)

        outline = await self._revision_port.revise_outline(
            user_id=user_id,
            context=context,
            existing_proposal=existing_proposal,
            feedback=feedback,
        )
        validate_milestones(outline.milestones, plan_start, profile_snapshot.target_date)
        if outline_completed is not None:
            await outline_completed(outline)

        results: dict[int, ProfilePlanTasksV1] = {}
        semaphore = asyncio.Semaphore(3)

        async def generate_batch(batch: PlanDateBatch) -> None:
            async with semaphore:
                result = await self._task_port.generate_task_batch(
                    user_id=user_id,
                    context=context,
                    outline=outline,
                    batch=batch,
                )
            validate_exact_days(batch.expected_dates, result.days)
            results[batch.index] = result
            if batch_completed is not None:
                await batch_completed(batch, result)

        async with asyncio.TaskGroup() as task_group:
            for batch in batches:
                task_group.create_task(generate_batch(batch))

        ordered_days = [day for batch in batches for day in results[batch.index].days]
        validate_exact_days(
            tuple(plan_start + timedelta(days=offset) for offset in range(duration_days)),
            ordered_days,
        )
        total_task_count = sum(len(day.tasks) for day in ordered_days)
        content: dict[str, Any] = {
            "schema_version": PROFILE_PLAN_PROPOSAL_VERSION,
            "profile_snapshot": profile_snapshot.model_dump(mode="json"),
            "profile_hash": profile_hash,
            "assessment_result_id": str(assessment_result_id),
            "generated_on": plan_start.isoformat(),
            "starts_on": plan_start.isoformat(),
            "ends_on": profile_snapshot.target_date.isoformat(),
            "duration_days": duration_days,
            "title": outline.title,
            "summary": outline.summary,
            "milestones": [item.model_dump(mode="json") for item in outline.milestones],
            "days": [item.model_dump(mode="json") for item in ordered_days],
            "total_task_count": total_task_count,
            "engine": self._engine.model_dump(mode="json"),
        }
        return ProfilePlanProposalV1(
            **content,
            proposal_hash=profile_plan_proposal_hash(content),
        )


class StructuredPlanCacheError(PlanGenerationError):
    pass


ProfilePlanGenerationOrchestrator = ProfilePlanGenerator
