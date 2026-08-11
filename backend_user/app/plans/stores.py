from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import LockError

from app.plans.checkpoints import GenerationCheckpoint
from app.plans.errors import (
    PlanCheckpointExpiredError,
    PlanDataIntegrityError,
    PlanGenerationInProgressError,
)
from app.plans.models import ProfilePlanOutlineV1, ProfilePlanProposalV1, ProfilePlanTasksV1

CHECKPOINT_TTL_SECONDS = 3600
INITIALIZE_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 then
  return 0
end
for index = 2, #ARGV, 2 do
  redis.call('HSET', KEYS[1], ARGV[index], ARGV[index + 1])
end
redis.call('EXPIRE', KEYS[1], ARGV[1])
return 1
"""
WRITE_IF_EXISTS_SCRIPT = """
-- checkpoint-write-if-exists
if redis.call('EXISTS', KEYS[1]) == 0 then
  return 0
end
for index = 2, #ARGV, 2 do
  redis.call('HSET', KEYS[1], ARGV[index], ARGV[index + 1])
end
redis.call('EXPIRE', KEYS[1], ARGV[1])
return 1
"""


class RedisPlanGenerationStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def load(self, *, user_id: UUID, request_id: UUID) -> GenerationCheckpoint | None:
        raw = await self._redis.hgetall(self._key(user_id, request_id))
        if not raw:
            return None
        try:
            fields = self._decode_mapping(raw)
            frozen_names = {
                "checkpoint_version",
                "kind",
                "user_id",
                "request_id",
                "profile_snapshot",
                "profile_hash",
                "assessment_result_id",
                "assessment_score",
                "assessment_level",
                "assessment_summary",
                "saved_job_snapshot",
                "generated_on",
                "starts_on",
                "ends_on",
                "duration_days",
                "outline",
                "proposal",
            }
            unexpected = {
                name
                for name in fields
                if name not in frozen_names and re.fullmatch(r"batch:\d{4}", name) is None
            }
            if unexpected:
                raise ValueError("unexpected checkpoint fields")
            batches = {
                int(name.removeprefix("batch:")): ProfilePlanTasksV1.model_validate_json(value)
                for name, value in fields.items()
                if name.startswith("batch:")
            }
            checkpoint = GenerationCheckpoint(
                checkpoint_version=fields["checkpoint_version"],
                kind=fields["kind"],
                user_id=fields["user_id"],
                request_id=fields["request_id"],
                profile_snapshot=json.loads(fields["profile_snapshot"]),
                profile_hash=fields["profile_hash"],
                assessment_result_id=fields["assessment_result_id"],
                assessment_score=fields["assessment_score"],
                assessment_level=fields["assessment_level"],
                assessment_summary=json.loads(fields["assessment_summary"]),
                saved_job_snapshot=(
                    json.loads(fields["saved_job_snapshot"])
                    if "saved_job_snapshot" in fields
                    else None
                ),
                generated_on=fields["generated_on"],
                starts_on=fields["starts_on"],
                ends_on=fields["ends_on"],
                duration_days=fields["duration_days"],
                outline=(
                    ProfilePlanOutlineV1.model_validate_json(fields["outline"])
                    if "outline" in fields
                    else None
                ),
                batches=batches,
                proposal=(
                    ProfilePlanProposalV1.model_validate_json(fields["proposal"])
                    if "proposal" in fields
                    else None
                ),
            )
            if checkpoint.user_id != user_id or checkpoint.request_id != request_id:
                raise ValueError("checkpoint identity mismatch")
            return checkpoint
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    async def initialize(self, checkpoint: GenerationCheckpoint) -> GenerationCheckpoint:
        existing = await self.load(user_id=checkpoint.user_id, request_id=checkpoint.request_id)
        if existing is not None:
            return existing
        values = self._frozen_fields(checkpoint)
        arguments = [item for name, value in values.items() for item in (name, value)]
        created = await self._redis.eval(
            INITIALIZE_SCRIPT,
            1,
            self._key(checkpoint.user_id, checkpoint.request_id),
            CHECKPOINT_TTL_SECONDS,
            *arguments,
        )
        if int(created) == 1:
            return checkpoint
        existing = await self.load(user_id=checkpoint.user_id, request_id=checkpoint.request_id)
        if existing is None:
            raise PlanDataIntegrityError()
        return existing

    @staticmethod
    def _frozen_fields(checkpoint: GenerationCheckpoint) -> dict[str, str]:
        fields = {
            "checkpoint_version": checkpoint.checkpoint_version,
            "kind": checkpoint.kind,
            "user_id": str(checkpoint.user_id),
            "request_id": str(checkpoint.request_id),
            "profile_snapshot": checkpoint.profile_snapshot.model_dump_json(),
            "profile_hash": checkpoint.profile_hash,
            "assessment_result_id": str(checkpoint.assessment_result_id),
            "assessment_score": str(checkpoint.assessment_score),
            "assessment_level": checkpoint.assessment_level,
            "assessment_summary": json.dumps(
                checkpoint.assessment_summary,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "generated_on": checkpoint.generated_on.isoformat(),
            "starts_on": checkpoint.starts_on.isoformat(),
            "ends_on": checkpoint.ends_on.isoformat(),
            "duration_days": str(checkpoint.duration_days),
        }
        if checkpoint.saved_job_snapshot is not None:
            fields["saved_job_snapshot"] = checkpoint.saved_job_snapshot.model_dump_json()
        return fields

    async def save_outline(
        self, *, user_id: UUID, request_id: UUID, outline: ProfilePlanOutlineV1
    ) -> None:
        await self._write(user_id, request_id, {"outline": outline.model_dump_json()})

    async def save_batch(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        index: int,
        batch: ProfilePlanTasksV1,
    ) -> None:
        await self._write(
            user_id,
            request_id,
            {f"batch:{index:04d}": batch.model_dump_json()},
        )

    async def save_proposal(
        self, *, user_id: UUID, request_id: UUID, proposal: ProfilePlanProposalV1
    ) -> None:
        current = await self.load(user_id=user_id, request_id=request_id)
        if current is None:
            raise PlanCheckpointExpiredError()
        try:
            GenerationCheckpoint.model_validate(
                {**current.model_dump(mode="json"), "proposal": proposal.model_dump(mode="json")}
            )
        except ValidationError as exc:
            raise PlanDataIntegrityError() from exc
        await self._write(user_id, request_id, {"proposal": proposal.model_dump_json()})

    async def _write(self, user_id: UUID, request_id: UUID, mapping: Mapping[str, str]) -> None:
        key = self._key(user_id, request_id)
        arguments = [item for name, value in mapping.items() for item in (name, value)]
        written = await self._redis.eval(
            WRITE_IF_EXISTS_SCRIPT,
            1,
            key,
            CHECKPOINT_TTL_SECONDS,
            *arguments,
        )
        if int(written) != 1:
            raise PlanCheckpointExpiredError()

    @staticmethod
    def _decode_mapping(raw: Mapping[Any, Any]) -> dict[str, str]:
        return {
            key.decode() if isinstance(key, bytes) else str(key): (
                value.decode() if isinstance(value, bytes) else str(value)
            )
            for key, value in raw.items()
        }

    @staticmethod
    def _key(user_id: UUID, request_id: UUID) -> str:
        return f"plan-generation:v1:{user_id}:{request_id}"


class RedisPlanGenerationLock:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @asynccontextmanager
    async def hold(self, *, user_id: UUID, request_id: UUID) -> AsyncIterator[None]:
        lock = self._redis.lock(
            f"plan-generation:v1:lock:{user_id}:{request_id}",
            timeout=300,
            blocking_timeout=2,
            raise_on_release_error=False,
        )
        try:
            async with lock:
                yield
        except LockError as exc:
            raise PlanGenerationInProgressError() from exc
