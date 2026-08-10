from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import date, datetime
from typing import Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from app.plans.checkpoints import GenerationCheckpoint
from app.plans.errors import (
    ActivePlanExistsError,
    IdempotencyKeyReusedError,
    PlanGenerationTimeoutError,
    PlanNotFoundError,
    PlanProposalAlreadyPendingError,
    PlanProposalNotFoundError,
    PlanProposalNotPendingError,
    PlanTaskNotFoundError,
    TodayQuestNotFoundError,
)
from app.plans.generation import ProfilePlanGenerator, validate_horizon
from app.plans.models import ProfilePlanOutlineV1, ProfilePlanProposalV1, ProfilePlanTasksV1
from app.plans.records import (
    PlanGenerationPreflight,
    StoredPlan,
    StoredPlanProposal,
    StoredTaskUpdate,
    TodayQuestSnapshot,
)


class PlanCheckpointPort(Protocol):
    async def load(self, *, user_id: UUID, request_id: UUID) -> GenerationCheckpoint | None: ...

    async def initialize(self, checkpoint: GenerationCheckpoint) -> GenerationCheckpoint: ...

    async def save_outline(
        self, *, user_id: UUID, request_id: UUID, outline: ProfilePlanOutlineV1
    ) -> None: ...

    async def save_batch(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        index: int,
        batch: ProfilePlanTasksV1,
    ) -> None: ...

    async def save_proposal(
        self, *, user_id: UUID, request_id: UUID, proposal: ProfilePlanProposalV1
    ) -> None: ...


class PlanRequestLockPort(Protocol):
    def hold(self, *, user_id: UUID, request_id: UUID) -> AbstractAsyncContextManager[None]: ...


class PlanRepositoryPort(Protocol):
    async def find_by_request(
        self, *, user_id: UUID, request_id: UUID
    ) -> StoredPlanProposal | str | None: ...

    async def get_generation_preflight(self, *, user_id: UUID) -> PlanGenerationPreflight: ...

    async def persist_generated_proposal(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        proposal: ProfilePlanProposalV1,
        today: date,
    ) -> StoredPlanProposal: ...

    async def get_pending_proposal(self, *, user_id: UUID) -> StoredPlanProposal | None: ...

    async def get_proposal(
        self, *, user_id: UUID, proposal_id: UUID
    ) -> StoredPlanProposal | None: ...

    async def replace_pending_proposal(
        self,
        *,
        user_id: UUID,
        old_proposal_id: UUID,
        new_request_id: UUID,
        proposal: ProfilePlanProposalV1,
    ) -> StoredPlanProposal: ...


class PlanProposalService:
    def __init__(
        self,
        *,
        repository: PlanRepositoryPort,
        checkpoints: PlanCheckpointPort,
        request_lock: PlanRequestLockPort,
        generator: ProfilePlanGenerator,
        today_provider: Callable[[], date],
        generation_timeout_seconds: float = 270,
        generation_error_normalizer: Callable[[BaseExceptionGroup], Exception | None] | None = None,
    ) -> None:
        self._repository = repository
        self._checkpoints = checkpoints
        self._request_lock = request_lock
        self._generator = generator
        self._today_provider = today_provider
        self._generation_timeout_seconds = generation_timeout_seconds
        self._generation_error_normalizer = generation_error_normalizer

    async def create(self, *, user_id: UUID, request_id: UUID) -> StoredPlanProposal:
        durable = await self._resolve_durable(user_id=user_id, request_id=request_id)
        if durable is not None:
            return durable

        async with self._request_lock.hold(user_id=user_id, request_id=request_id):
            durable = await self._resolve_durable(user_id=user_id, request_id=request_id)
            if durable is not None:
                return durable

            checkpoint = await self._checkpoints.load(user_id=user_id, request_id=request_id)
            preflight_checked = False
            if checkpoint is None:
                prerequisites = await self._repository.get_generation_preflight(user_id=user_id)
                self._ensure_available(prerequisites, request_id=request_id)
                preflight_checked = True
                generated_on = self._today_provider()
                duration_days = validate_horizon(
                    generated_on, prerequisites.profile_snapshot.target_date
                )
                checkpoint = await self._checkpoints.initialize(
                    GenerationCheckpoint(
                        user_id=user_id,
                        request_id=request_id,
                        profile_snapshot=prerequisites.profile_snapshot,
                        profile_hash=prerequisites.profile_hash,
                        assessment_result_id=prerequisites.assessment_result_id,
                        assessment_score=prerequisites.assessment_score,
                        assessment_level=prerequisites.assessment_level,
                        assessment_summary=prerequisites.assessment_summary,
                        generated_on=generated_on,
                        starts_on=generated_on,
                        ends_on=prerequisites.profile_snapshot.target_date,
                        duration_days=duration_days,
                    )
                )

            proposal = checkpoint.proposal
            if proposal is None:
                if not preflight_checked:
                    prerequisites = await self._repository.get_generation_preflight(user_id=user_id)
                    self._ensure_available(prerequisites, request_id=request_id)

                async def outline_completed(value: ProfilePlanOutlineV1) -> None:
                    await self._checkpoints.save_outline(
                        user_id=user_id,
                        request_id=request_id,
                        outline=value,
                    )

                async def batch_completed(indexed_batch, value: ProfilePlanTasksV1) -> None:
                    await self._checkpoints.save_batch(
                        user_id=user_id,
                        request_id=request_id,
                        index=indexed_batch.index,
                        batch=value,
                    )

                try:
                    async with asyncio.timeout(self._generation_timeout_seconds):
                        proposal = await self._generator.generate(
                            user_id=user_id,
                            profile_snapshot=checkpoint.profile_snapshot,
                            profile_hash=checkpoint.profile_hash,
                            assessment_result_id=checkpoint.assessment_result_id,
                            assessment_score=checkpoint.assessment_score,
                            assessment_level=checkpoint.assessment_level,
                            assessment_summary=checkpoint.assessment_summary,
                            generated_on=checkpoint.generated_on,
                            cached_outline=checkpoint.outline,
                            cached_batches=checkpoint.batches,
                            outline_completed=outline_completed,
                            batch_completed=batch_completed,
                        )
                        await self._checkpoints.save_proposal(
                            user_id=user_id,
                            request_id=request_id,
                            proposal=proposal,
                        )
                except TimeoutError as exc:
                    raise PlanGenerationTimeoutError() from exc
                except BaseExceptionGroup as exc:
                    if self._generation_error_normalizer is None:
                        raise
                    normalized = self._generation_error_normalizer(exc)
                    if normalized is None:
                        raise
                    raise normalized from None

            return await self._repository.persist_generated_proposal(
                user_id=user_id,
                request_id=request_id,
                proposal=proposal,
                today=self._today_provider(),
            )

    async def get_pending(self, *, user_id: UUID) -> StoredPlanProposal:
        result = await self._repository.get_pending_proposal(user_id=user_id)
        if result is None:
            raise PlanProposalNotFoundError()
        return result

    async def get(self, *, user_id: UUID, proposal_id: UUID) -> StoredPlanProposal:
        result = await self._repository.get_proposal(user_id=user_id, proposal_id=proposal_id)
        if result is None:
            raise PlanProposalNotFoundError()
        return result

    async def revise(
        self, *, user_id: UUID, proposal_id: UUID, feedback: str, request_id: UUID
    ) -> StoredPlanProposal:
        existing = await self._repository.get_proposal(user_id=user_id, proposal_id=proposal_id)
        if existing is None:
            raise PlanProposalNotFoundError()
        if existing.decision_status != "pending":
            raise PlanProposalNotPendingError()

        async with self._request_lock.hold(user_id=user_id, request_id=request_id):
            durable = await self._repository.find_by_request(
                user_id=user_id, request_id=request_id
            )
            if durable is not None:
                if isinstance(durable, StoredPlanProposal):
                    return durable
                raise IdempotencyKeyReusedError()

            prerequisites = await self._repository.get_generation_preflight(user_id=user_id)

            try:
                async with asyncio.timeout(self._generation_timeout_seconds):
                    proposal = await self._generator.revise(
                        user_id=user_id,
                        existing_proposal=existing.content,
                        feedback=feedback,
                        assessment_score=prerequisites.assessment_score,
                        assessment_level=prerequisites.assessment_level,
                        assessment_summary=prerequisites.assessment_summary,
                    )
            except TimeoutError as exc:
                raise PlanGenerationTimeoutError() from exc
            except BaseExceptionGroup as exc:
                if self._generation_error_normalizer is None:
                    raise
                normalized = self._generation_error_normalizer(exc)
                if normalized is None:
                    raise
                raise normalized from None

            return await self._repository.replace_pending_proposal(
                user_id=user_id,
                old_proposal_id=proposal_id,
                new_request_id=request_id,
                proposal=proposal,
            )

    async def _resolve_durable(
        self, *, user_id: UUID, request_id: UUID
    ) -> StoredPlanProposal | None:
        result = await self._repository.find_by_request(user_id=user_id, request_id=request_id)
        if result is None:
            return None
        if not isinstance(result, StoredPlanProposal):
            raise IdempotencyKeyReusedError()
        return result

    @staticmethod
    def _ensure_available(prerequisites: PlanGenerationPreflight, *, request_id: UUID) -> None:
        if prerequisites.active_plan_exists:
            raise ActivePlanExistsError()
        if (
            prerequisites.pending_request_id is not None
            and prerequisites.pending_request_id != request_id
        ):
            raise PlanProposalAlreadyPendingError()


class PlanManagementRepositoryPort(Protocol):
    async def accept_proposal(self, *, user_id: UUID, proposal_id: UUID) -> StoredPlan | None: ...

    async def reject_proposal(
        self, *, user_id: UUID, proposal_id: UUID
    ) -> StoredPlanProposal | None: ...

    async def get_active_plan(self, *, user_id: UUID) -> StoredPlan | None: ...

    async def get_plan(self, *, user_id: UUID, plan_id: UUID) -> StoredPlan | None: ...

    async def set_task_status(
        self,
        *,
        user_id: UUID,
        plan_id: UUID,
        task_id: UUID,
        status: Literal["pending", "completed"],
    ) -> StoredTaskUpdate | None: ...

    async def complete_plan(self, *, user_id: UUID, plan_id: UUID) -> StoredPlan | None: ...

    async def get_today_quests(self, *, user_id: UUID) -> TodayQuestSnapshot: ...

    async def set_today_task_status(
        self,
        *,
        user_id: UUID,
        task_id: UUID,
        status: Literal["pending", "completed"],
    ) -> StoredTaskUpdate | None: ...


class PlanManagementService:
    def __init__(
        self,
        *,
        repository: PlanManagementRepositoryPort,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self._repository = repository
        self._today_provider = today_provider or (
            lambda: datetime.now(ZoneInfo("Asia/Seoul")).date()
        )

    def today(self) -> date:
        return self._today_provider()

    async def accept(self, *, user_id: UUID, proposal_id: UUID) -> StoredPlan:
        result = await self._repository.accept_proposal(user_id=user_id, proposal_id=proposal_id)
        if result is None:
            raise PlanProposalNotFoundError()
        return result

    async def reject(self, *, user_id: UUID, proposal_id: UUID) -> StoredPlanProposal:
        result = await self._repository.reject_proposal(user_id=user_id, proposal_id=proposal_id)
        if result is None:
            raise PlanProposalNotFoundError()
        return result

    async def get_active(self, *, user_id: UUID) -> StoredPlan:
        result = await self._repository.get_active_plan(user_id=user_id)
        if result is None:
            raise PlanNotFoundError()
        return result

    async def get(self, *, user_id: UUID, plan_id: UUID) -> StoredPlan:
        result = await self._repository.get_plan(user_id=user_id, plan_id=plan_id)
        if result is None:
            raise PlanNotFoundError()
        return result

    async def set_task_status(
        self,
        *,
        user_id: UUID,
        plan_id: UUID,
        task_id: UUID,
        status: Literal["pending", "completed"],
    ) -> StoredTaskUpdate:
        result = await self._repository.set_task_status(
            user_id=user_id, plan_id=plan_id, task_id=task_id, status=status
        )
        if result is None:
            raise PlanTaskNotFoundError()
        return result

    async def complete(self, *, user_id: UUID, plan_id: UUID) -> StoredPlan:
        result = await self._repository.complete_plan(user_id=user_id, plan_id=plan_id)
        if result is None:
            raise PlanNotFoundError()
        return result

    async def get_today_quests(self, *, user_id: UUID) -> TodayQuestSnapshot:
        return await self._repository.get_today_quests(user_id=user_id)

    async def set_today_task_status(
        self,
        *,
        user_id: UUID,
        task_id: UUID,
        status: Literal["pending", "completed"],
    ) -> StoredTaskUpdate:
        result = await self._repository.set_today_task_status(
            user_id=user_id,
            task_id=task_id,
            status=status,
        )
        if result is None:
            raise TodayQuestNotFoundError()
        return result
