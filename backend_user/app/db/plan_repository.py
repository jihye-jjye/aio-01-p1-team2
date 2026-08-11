from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, time
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from pydantic import ValidationError

from app.api.errors import ProfileNotFoundError
from app.plans.errors import (
    ActivePlanExistsError,
    IdempotencyKeyReusedError,
    PlanDataIntegrityError,
    PlanNotActiveError,
    PlanNotCompleteError,
    PlanProfileChangedError,
    PlanProposalAlreadyPendingError,
    PlanProposalNotPendingError,
    PlanProposalStaleError,
    PlanSavedJobNotFoundError,
)
from app.plans.models import ProfilePlanProposalV1
from app.plans.records import (
    DailyGoalAchievement,
    PlanGenerationPreflight,
    PlanScheduleItem,
    PlanSummarySnapshot,
    StoredPlan,
    StoredPlanProposal,
    StoredTaskUpdate,
    TodayQuestSnapshot,
)
from app.profiles.models import ProfileOnboardingData
from app.saved_jobs.models import SavedJobView


class PsycopgPlanProposalRepository:
    def __init__(
        self,
        pool: AsyncConnectionPool,
        *,
        today_provider: Callable[[], date],
    ) -> None:
        self._pool = pool
        self._today_provider = today_provider

    async def find_by_request(
        self, *, user_id: UUID, request_id: UUID
    ) -> StoredPlanProposal | str | None:
        async with self._pool.connection() as connection:
            row = await self._fetch_request_row(
                connection, user_id=user_id, request_id=request_id, lock=False
            )
        return self._resolve_row(row)

    async def get_generation_preflight(
        self,
        *,
        user_id: UUID,
        saved_job_id: UUID | None = None,
    ) -> PlanGenerationPreflight:
        async with self._pool.connection() as connection:
            profile_cursor = await connection.execute(
                """
                select
                  p.target_role, p.skills, p.experience_summary, p.target_date,
                  p.target_company, p.preferred_environment, p.daily_notification_time,
                  p.assistant_style, p.assessment_result_id, p.assessment_score,
                  p.assessment_level, p.assessment_summary,
                  ar.content ->> 'snapshot_hash' as profile_hash
                from app.profiles p
                join app.ai_results ar
                  on ar.user_id = p.user_id and ar.id = p.assessment_result_id
                 and ar.kind = 'profile_assessment'
                 and (ar.content ->> 'snapshot_hash') ~ '^[0-9a-f]{64}$'
                where p.user_id = %(user_id)s
                  and p.onboarding_completed_at is not null
                  and p.assessment_result_id is not null
                """,
                {"user_id": user_id},
            )
            profile_row = await profile_cursor.fetchone()
            if profile_row is None:
                raise ProfileNotFoundError
            saved_job_row = None
            if saved_job_id is not None:
                saved_job_cursor = await connection.execute(
                    """
                    select
                      id, source_type, source_url, source_key, company_name,
                      job_title, deadline, posting_text, extracted_data,
                      created_at, updated_at
                    from app.saved_jobs
                    where id = %(saved_job_id)s
                    """,
                    {"saved_job_id": saved_job_id},
                )
                saved_job_row = await saved_job_cursor.fetchone()
                if saved_job_row is None:
                    raise PlanSavedJobNotFoundError()
            active_cursor = await connection.execute(
                """
                select id from app.plans
                where user_id = %(user_id)s and status = 'active'
                limit 1
                """,
                {"user_id": user_id},
            )
            active = await active_cursor.fetchone()
            pending_cursor = await connection.execute(
                """
                select request_id from app.ai_results
                where user_id = %(user_id)s
                  and kind = 'profile_plan_proposal'
                  and decision_status = 'pending'
                limit 1
                """,
                {"user_id": user_id},
            )
            pending = await pending_cursor.fetchone()
        return self._preflight(
            profile_row,
            active=active is not None,
            pending=pending,
            saved_job_row=saved_job_row,
        )

    async def persist_generated_proposal(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        proposal: ProfilePlanProposalV1,
        today: date,
        saved_job_id: UUID | None = None,
    ) -> StoredPlanProposal:
        parameters: dict[str, Any] = {
            "user_id": user_id,
            "request_id": str(request_id),
            "kind": "profile_plan_proposal",
            "decision_status": "pending",
            "saved_job_id": saved_job_id,
            "title": proposal.title,
            "content": Jsonb(proposal.model_dump(mode="json")),
            "model_name": proposal.engine.model,
            "prompt_version": "profile-plan-proposal-v1",
        }
        try:
            async with self._pool.connection() as connection, connection.transaction():
                profile_cursor = await connection.execute(
                    """
                    select
                      p.target_role, p.skills, p.experience_summary, p.target_date,
                      p.target_company, p.preferred_environment, p.daily_notification_time,
                      p.assistant_style, p.assessment_result_id, p.assessment_score,
                      p.assessment_level, p.assessment_summary,
                      ar.content ->> 'snapshot_hash' as profile_hash
                    from app.profiles p
                    join app.ai_results ar
                      on ar.user_id = p.user_id and ar.id = p.assessment_result_id
                     and ar.kind = 'profile_assessment'
                     and (ar.content ->> 'snapshot_hash') ~ '^[0-9a-f]{64}$'
                    where p.user_id = %(user_id)s
                      and p.onboarding_completed_at is not null
                    for update of p
                    """,
                    parameters,
                )
                profile_row = await profile_cursor.fetchone()
                if profile_row is None:
                    raise ProfileNotFoundError

                request_row = await self._fetch_request_row(
                    connection, user_id=user_id, request_id=request_id, lock=True
                )
                if request_row is not None:
                    return self._resolve_persistence_winner(request_row, proposal)

                active_cursor = await connection.execute(
                    """
                    select id from app.plans
                    where user_id = %(user_id)s and status = 'active'
                    for update
                    """,
                    parameters,
                )
                active = await active_cursor.fetchone()
                if active is not None:
                    raise ActivePlanExistsError()

                pending_cursor = await connection.execute(
                    """
                    select id, request_id from app.ai_results
                    where user_id = %(user_id)s
                      and kind = 'profile_plan_proposal'
                      and decision_status = 'pending'
                    for update
                    """,
                    parameters,
                )
                pending = await pending_cursor.fetchone()
                if pending is not None and UUID(str(pending["request_id"])) != request_id:
                    raise PlanProposalAlreadyPendingError()

                locked_today = self._today_provider()
                try:
                    proposal = ProfilePlanProposalV1.model_validate(
                        proposal.model_dump(mode="json")
                    )
                except ValidationError as exc:
                    raise PlanDataIntegrityError() from exc
                self._validate_current_profile(
                    profile_row,
                    proposal=proposal,
                    today=locked_today,
                )
                proposal_saved_job_id = (
                    proposal.saved_job_snapshot.id
                    if proposal.saved_job_snapshot is not None
                    else None
                )
                if proposal_saved_job_id != saved_job_id:
                    raise PlanDataIntegrityError()
                parameters.update(
                    title=proposal.title,
                    content=Jsonb(proposal.model_dump(mode="json")),
                    model_name=proposal.engine.model,
                )

                insert_cursor = await connection.execute(
                    """
                    insert into app.ai_results (
                      user_id, saved_job_id, applied_plan_id, kind, decision_status,
                      title, content, model_name, prompt_version, request_id, decided_at
                    ) values (
                      %(user_id)s, %(saved_job_id)s, null, %(kind)s, %(decision_status)s,
                      %(title)s, %(content)s, %(model_name)s, %(prompt_version)s,
                      %(request_id)s, null
                    )
                    on conflict (user_id, request_id) do nothing
                    returning
                      id, user_id, saved_job_id, request_id, kind, decision_status, content,
                      model_name, prompt_version, applied_plan_id, decided_at, created_at
                    """,
                    parameters,
                )
                inserted = await insert_cursor.fetchone()
                if inserted is not None:
                    return self._stored(inserted)

                winner = await self._fetch_request_row(
                    connection, user_id=user_id, request_id=request_id, lock=True
                )
                if winner is None:
                    raise PlanDataIntegrityError()
                return self._resolve_persistence_winner(winner, proposal)
        except UniqueViolation as exc:
            constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint == "ai_results_one_pending_profile_plan_proposal_uidx":
                raise PlanProposalAlreadyPendingError() from exc
            if constraint == "ai_results_user_request_unique":
                raise IdempotencyKeyReusedError() from exc
            raise

    async def get_proposal(self, *, user_id: UUID, proposal_id: UUID) -> StoredPlanProposal | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select
                  id, user_id, saved_job_id, request_id, kind, decision_status, content,
                  model_name, prompt_version, applied_plan_id, decided_at, created_at
                from app.ai_results
                where user_id = %(user_id)s and id = %(proposal_id)s
                  and kind = 'profile_plan_proposal'
                """,
                {"user_id": user_id, "proposal_id": proposal_id},
            )
            row = await cursor.fetchone()
        if row is None or row.get("kind") != "profile_plan_proposal":
            return None
        return self._stored(row)

    async def replace_pending_proposal(
        self,
        *,
        user_id: UUID,
        old_proposal_id: UUID,
        new_request_id: UUID,
        proposal: ProfilePlanProposalV1,
    ) -> StoredPlanProposal:
        parameters: dict[str, Any] = {
            "user_id": user_id,
            "old_proposal_id": old_proposal_id,
            "new_request_id": str(new_request_id),
            "kind": "profile_plan_proposal",
            "decision_status": "pending",
            "saved_job_id": (
                proposal.saved_job_snapshot.id
                if proposal.saved_job_snapshot is not None
                else None
            ),
            "title": proposal.title,
            "content": Jsonb(proposal.model_dump(mode="json")),
            "model_name": proposal.engine.model,
            "prompt_version": "profile-plan-proposal-v1",
        }
        try:
            async with self._pool.connection() as connection, connection.transaction():
                profile_cursor = await connection.execute(
                    """
                    select
                      p.target_role, p.skills, p.experience_summary, p.target_date,
                      p.target_company, p.preferred_environment, p.daily_notification_time,
                      p.assistant_style, p.assessment_result_id, p.assessment_score,
                      p.assessment_level, p.assessment_summary,
                      ar.content ->> 'snapshot_hash' as profile_hash
                    from app.profiles p
                    join app.ai_results ar
                      on ar.user_id = p.user_id and ar.id = p.assessment_result_id
                     and ar.kind = 'profile_assessment'
                     and (ar.content ->> 'snapshot_hash') ~ '^[0-9a-f]{64}$'
                    where p.user_id = %(user_id)s
                      and p.onboarding_completed_at is not null
                    for update of p
                    """,
                    parameters,
                )
                profile_row = await profile_cursor.fetchone()
                if profile_row is None:
                    raise ProfileNotFoundError

                proposal_cursor = await connection.execute(
                    """
                    select id, saved_job_id, decision_status, content
                    from app.ai_results
                    where user_id = %(user_id)s
                      and id = %(old_proposal_id)s
                      and kind = 'profile_plan_proposal'
                    for update
                    """,
                    parameters,
                )
                old_row = await proposal_cursor.fetchone()
                if old_row is None:
                    raise PlanProposalNotPendingError()
                if old_row["decision_status"] != "pending":
                    raise PlanProposalNotPendingError()
                if old_row.get("saved_job_id") != parameters["saved_job_id"]:
                    raise PlanDataIntegrityError()

                active_cursor = await connection.execute(
                    """
                    select id from app.plans
                    where user_id = %(user_id)s and status = 'active'
                    for update
                    """,
                    parameters,
                )
                active = await active_cursor.fetchone()
                if active is not None:
                    raise ActivePlanExistsError()

                try:
                    proposal = ProfilePlanProposalV1.model_validate(
                        proposal.model_dump(mode="json")
                    )
                except ValidationError as exc:
                    raise PlanDataIntegrityError() from exc

                await connection.execute(
                    """
                    update app.ai_results
                    set decision_status = 'rejected', decided_at = now()
                    where user_id = %(user_id)s
                      and id = %(old_proposal_id)s
                      and kind = 'profile_plan_proposal'
                      and decision_status = 'pending'
                    """,
                    parameters,
                )

                insert_cursor = await connection.execute(
                    """
                    insert into app.ai_results (
                      user_id, saved_job_id, applied_plan_id, kind, decision_status,
                      title, content, model_name, prompt_version, request_id, decided_at
                    ) values (
                      %(user_id)s, %(saved_job_id)s, null, %(kind)s, %(decision_status)s,
                      %(title)s, %(content)s, %(model_name)s, %(prompt_version)s,
                      %(new_request_id)s, null
                    )
                    returning
                      id, user_id, saved_job_id, request_id, kind, decision_status, content,
                      model_name, prompt_version, applied_plan_id, decided_at, created_at
                    """,
                    parameters,
                )
                inserted = await insert_cursor.fetchone()
                if inserted is None:
                    raise PlanDataIntegrityError()
                return self._stored(inserted)
        except UniqueViolation as exc:
            constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint == "ai_results_one_pending_profile_plan_proposal_uidx":
                raise PlanProposalAlreadyPendingError() from exc
            if constraint == "ai_results_user_request_unique":
                raise IdempotencyKeyReusedError() from exc
            raise

    async def get_pending_proposal(self, *, user_id: UUID) -> StoredPlanProposal | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select
                  id, user_id, saved_job_id, request_id, kind, decision_status, content,
                  model_name, prompt_version, applied_plan_id, decided_at, created_at
                from app.ai_results
                where user_id = %(user_id)s
                  and kind = 'profile_plan_proposal'
                  and decision_status = 'pending'
                limit 1
                """,
                {"user_id": user_id},
            )
            row = await cursor.fetchone()
        if row is None or row.get("kind") != "profile_plan_proposal":
            return None
        return self._stored(row)

    async def accept_proposal(self, *, user_id: UUID, proposal_id: UUID) -> StoredPlan | None:
        parameters: dict[str, Any] = {"user_id": user_id, "proposal_id": proposal_id}
        try:
            async with self._pool.connection() as connection, connection.transaction():
                profile_cursor = await connection.execute(
                    """
                    select
                      p.target_role, p.skills, p.experience_summary, p.target_date,
                      p.target_company, p.preferred_environment, p.daily_notification_time,
                      p.assistant_style, p.assessment_result_id, p.assessment_score,
                      p.assessment_level, p.assessment_summary,
                      ua.role as account_role, ua.user_exp,
                      ar.content ->> 'snapshot_hash' as profile_hash
                    from app.profiles p
                    join app.user_accounts ua on ua.id = p.user_id
                    join app.ai_results ar
                      on ar.user_id = p.user_id and ar.id = p.assessment_result_id
                     and ar.kind = 'profile_assessment'
                     and (ar.content ->> 'snapshot_hash') ~ '^[0-9a-f]{64}$'
                    where p.user_id = %(user_id)s
                      and p.onboarding_completed_at is not null
                    for update of p
                    """,
                    parameters,
                )
                profile_row = await profile_cursor.fetchone()
                if profile_row is None:
                    return None

                proposal_row = await self._fetch_proposal_row(
                    connection,
                    user_id=user_id,
                    proposal_id=proposal_id,
                    lock=True,
                )
                if proposal_row is None:
                    return None
                stored_proposal = self._stored(proposal_row)
                if stored_proposal.decision_status == "applied":
                    if stored_proposal.applied_plan_id is None:
                        raise PlanDataIntegrityError()
                    plan_row = await self._fetch_owned_plan_row(
                        connection,
                        user_id=user_id,
                        plan_id=stored_proposal.applied_plan_id,
                        active_only=False,
                        lock=True,
                    )
                    if plan_row is None:
                        raise PlanDataIntegrityError()
                    view_today = self._today_provider()
                    items = await self._fetch_schedule_rows(
                        connection,
                        user_id=user_id,
                        plan_id=stored_proposal.applied_plan_id,
                        lock=False,
                    )
                    achievement_rows = await self._fetch_achievement_rows(
                        connection,
                        user_id=user_id,
                        plan_id=stored_proposal.applied_plan_id,
                        lock=False,
                    )
                    return self._stored_plan(
                        plan_row,
                        items,
                        achievement_rows,
                        view_today=view_today,
                    )
                if stored_proposal.decision_status != "pending":
                    raise PlanProposalNotPendingError()

                active_cursor = await connection.execute(
                    """
                    select id from app.plans
                    where user_id = %(user_id)s and status = 'active'
                    for update
                    """,
                    parameters,
                )
                active = await active_cursor.fetchone()

                locked_today = self._today_provider()
                try:
                    proposal = ProfilePlanProposalV1.model_validate(
                        stored_proposal.content.model_dump(mode="json")
                    )
                except ValidationError as exc:
                    raise PlanDataIntegrityError() from exc
                self._validate_current_profile(profile_row, proposal=proposal, today=locked_today)
                notification_time = profile_row.get("daily_notification_time")
                if notification_time is None:
                    raise PlanDataIntegrityError()
                if active is not None:
                    raise ActivePlanExistsError()

                parameters.update(
                    proposal_result_id=proposal_id,
                    title=proposal.title,
                    summary=proposal.summary,
                    goal_snapshot=Jsonb(proposal.profile_snapshot.model_dump(mode="json")),
                    starts_on=proposal.starts_on,
                    ends_on=proposal.ends_on,
                    total_task_count=proposal.total_task_count,
                    source_request_id=f"profile-plan-proposal:{proposal_id}",
                    source_saved_job_id=stored_proposal.saved_job_id,
                    notification_time=notification_time,
                )
                plan_cursor = await connection.execute(
                    """
                    insert into app.plans (
                      user_id, source_saved_job_id, proposal_result_id, previous_plan_id,
                      title, summary, goal_snapshot, starts_on, ends_on, total_task_count,
                      final_progress, status, restart_offer_status, source_request_id,
                      activated_at, ended_at, restart_prompted_at
                    ) values (
                      %(user_id)s, %(source_saved_job_id)s, %(proposal_result_id)s, null,
                      %(title)s, %(summary)s, %(goal_snapshot)s, %(starts_on)s, %(ends_on)s,
                      %(total_task_count)s, null, 'active', 'not_due', %(source_request_id)s,
                      now(), null, null
                    )
                    returning
                      id, user_id, title, summary, goal_snapshot, starts_on, ends_on,
                      total_task_count, status, activated_at, ended_at,
                      restart_offer_status, restart_prompted_at
                    """,
                    parameters,
                )
                plan_row = await plan_cursor.fetchone()
                if plan_row is None:
                    raise PlanDataIntegrityError()
                plan_id = UUID(str(plan_row["id"]))
                projected = self._projection_payload(proposal)
                schedule_cursor = await connection.execute(
                    """
                    with projected as (
                      select *
                      from jsonb_to_recordset(%(items)s::jsonb) as x(
                        kind text, title text, description text, local_date text,
                        plan_day smallint, slot smallint,
                        counts_toward_progress boolean, metadata jsonb
                      )
                    )
                    insert into app.schedule_items (
                      user_id, plan_id, saved_job_id, kind, title, description,
                      scheduled_at, remind_at, status, plan_day, slot, detail_status,
                      counts_toward_progress, metadata, completed_at
                    )
                    select
                      %(user_id)s, %(plan_id)s, null, x.kind, x.title, x.description,
                      (x.local_date::date + %(notification_time)s::time)
                        at time zone 'Asia/Seoul',
                      null, 'pending', x.plan_day, x.slot, 'ready',
                      x.counts_toward_progress, x.metadata, null
                    from projected x
                    returning
                      id, kind, title, description, scheduled_at, remind_at, status,
                      plan_day, slot, detail_status, counts_toward_progress, metadata,
                      completed_at
                    """,
                    {**parameters, "plan_id": plan_id, "items": Jsonb(projected)},
                )
                item_rows = await schedule_cursor.fetchall()
                items = [self._schedule_item(row) for row in item_rows]
                self._validate_projected_rows(proposal, items)

                day_payload = [
                    {"plan_day": plan_day, "goal_date": day.date.isoformat()}
                    for plan_day, day in enumerate(proposal.days, start=1)
                ]
                achievement_cursor = await connection.execute(
                    """
                    with projected_days as (
                      select *
                      from jsonb_to_recordset(%(days)s::jsonb) as x(
                        plan_day smallint, goal_date date
                      )
                    )
                    insert into app.daily_goal_achievements (
                      user_id, plan_id, plan_day, goal_date, achieved,
                      achieved_at, exp_awarded
                    )
                    select
                      %(user_id)s, %(plan_id)s, x.plan_day, x.goal_date,
                      false, null, 0
                    from projected_days x
                    returning
                      user_id, plan_id, plan_day, goal_date, achieved, achieved_at,
                      exp_awarded
                    """,
                    {**parameters, "plan_id": plan_id, "days": Jsonb(day_payload)},
                )
                achievement_rows = await achievement_cursor.fetchall()
                achievements = [self._daily_goal_achievement(row) for row in achievement_rows]
                self._validate_daily_achievements(
                    proposal,
                    items,
                    achievements,
                    user_id=user_id,
                    plan_id=plan_id,
                )

                decision_cursor = await connection.execute(
                    """
                    update app.ai_results
                    set decision_status = 'applied', applied_plan_id = %(plan_id)s,
                        decided_at = now()
                    where user_id = %(user_id)s and id = %(proposal_id)s
                      and kind = 'profile_plan_proposal'
                      and decision_status = 'pending'
                    returning
                      id, user_id, saved_job_id, request_id, kind, decision_status, content,
                      model_name, prompt_version, applied_plan_id, decided_at, created_at
                    """,
                    {**parameters, "plan_id": plan_id},
                )
                applied_row = await decision_cursor.fetchone()
                if applied_row is None:
                    raise PlanDataIntegrityError()
                applied = self._stored(applied_row)
                plan_row = {
                    **plan_row,
                    "account_role": profile_row.get("account_role"),
                    "user_exp": profile_row.get("user_exp"),
                }
                return self._stored_plan_from_parts(
                    plan_row,
                    applied,
                    items,
                    achievements,
                    view_today=locked_today,
                )
        except UniqueViolation as exc:
            constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint == "plans_one_active_per_user_uidx":
                raise ActivePlanExistsError() from exc
            if constraint in {
                "plans_user_source_request_unique",
                "plans_proposal_result_uidx",
                "schedule_items_progress_slot_uidx",
                "daily_goal_achievements_pkey",
                "daily_goal_achievements_user_plan_date_unique",
            }:
                raise PlanDataIntegrityError() from exc
            raise

    async def reject_proposal(
        self, *, user_id: UUID, proposal_id: UUID
    ) -> StoredPlanProposal | None:
        parameters = {"user_id": user_id, "proposal_id": proposal_id}
        async with self._pool.connection() as connection, connection.transaction():
            profile_cursor = await connection.execute(
                """
                select user_id from app.profiles
                where user_id = %(user_id)s
                for update
                """,
                parameters,
            )
            if await profile_cursor.fetchone() is None:
                return None
            row = await self._fetch_proposal_row(
                connection, user_id=user_id, proposal_id=proposal_id, lock=True
            )
            if row is None:
                return None
            stored = self._stored(row)
            if stored.decision_status == "rejected":
                return stored
            if stored.decision_status != "pending":
                raise PlanProposalNotPendingError()
            cursor = await connection.execute(
                """
                update app.ai_results
                set decision_status = 'rejected', applied_plan_id = null, decided_at = now()
                where user_id = %(user_id)s and id = %(proposal_id)s
                  and kind = 'profile_plan_proposal'
                  and decision_status = 'pending'
                returning
                  id, user_id, saved_job_id, request_id, kind, decision_status, content,
                  model_name, prompt_version, applied_plan_id, decided_at, created_at
                """,
                parameters,
            )
            rejected = await cursor.fetchone()
            if rejected is None:
                raise PlanDataIntegrityError()
            return self._stored(rejected)

    async def get_active_plan(self, *, user_id: UUID) -> StoredPlan | None:
        async with self._pool.connection() as connection:
            row = await self._fetch_owned_plan_row(
                connection, user_id=user_id, plan_id=None, active_only=True, lock=False
            )
            if row is None:
                return None
            items = await self._fetch_schedule_rows(
                connection, user_id=user_id, plan_id=UUID(str(row["id"])), lock=False
            )
            achievements = await self._fetch_achievement_rows(
                connection,
                user_id=user_id,
                plan_id=UUID(str(row["id"])),
                lock=False,
            )
        return self._stored_plan(row, items, achievements)

    async def get_plan(self, *, user_id: UUID, plan_id: UUID) -> StoredPlan | None:
        async with self._pool.connection() as connection:
            row = await self._fetch_owned_plan_row(
                connection,
                user_id=user_id,
                plan_id=plan_id,
                active_only=False,
                lock=False,
            )
            if row is None:
                return None
            items = await self._fetch_schedule_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=False
            )
            achievements = await self._fetch_achievement_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=False
            )
        return self._stored_plan(row, items, achievements)

    async def list_plans(self, *, user_id: UUID) -> PlanSummarySnapshot:
        async with self._pool.connection() as connection:
            plan_rows = await self._fetch_owned_plan_rows(connection, user_id=user_id)
            user_exp = await self._fetch_read_user_exp(connection, user_id=user_id)
            plans: list[StoredPlan] = []
            for row in plan_rows:
                plan_id = UUID(str(row["id"]))
                items = await self._fetch_schedule_rows(
                    connection, user_id=user_id, plan_id=plan_id, lock=False
                )
                achievements = await self._fetch_achievement_rows(
                    connection, user_id=user_id, plan_id=plan_id, lock=False
                )
                plans.append(self._stored_plan(row, items, achievements))
        return PlanSummarySnapshot(plans=plans, user_exp=user_exp)

    async def get_today_quests(self, *, user_id: UUID) -> TodayQuestSnapshot:
        async with self._pool.connection() as connection, connection.transaction():
            today = self._today_provider()
            plan_row = await self._fetch_owned_plan_row(
                connection,
                user_id=user_id,
                plan_id=None,
                active_only=True,
                lock=True,
            )
            if plan_row is None:
                user_exp = await self._fetch_read_user_exp(
                    connection, user_id=user_id
                )
                return TodayQuestSnapshot(
                    date=today,
                    plan_id=None,
                    plan_title=None,
                    tasks=[],
                    achievement=None,
                    user_exp=user_exp,
                )

            plan_id = UUID(str(plan_row["id"]))
            user_exp = await self._fetch_read_user_exp(connection, user_id=user_id)
            starts_on = plan_row.get("starts_on")
            ends_on = plan_row.get("ends_on")
            if not isinstance(starts_on, date) or not isinstance(ends_on, date):
                raise PlanDataIntegrityError()
            if not starts_on <= today <= ends_on:
                return TodayQuestSnapshot(
                    date=today,
                    plan_id=plan_id,
                    plan_title=str(plan_row["title"]),
                    tasks=[],
                    achievement=None,
                    user_exp=user_exp,
                )

            progress_rows = await self._fetch_progress_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=False
            )
            proposal = self._proposal_from_plan_row(plan_row).content
            progress = [self._schedule_item(row) for row in progress_rows]
            self._validate_progress_rows(proposal, plan_row, progress)
            plan_day = (today - starts_on).days + 1
            tasks = [item for item in progress if item.plan_day == plan_day]
            if not tasks:
                raise PlanDataIntegrityError()

            achievement_cursor = await connection.execute(
                """
                select
                  user_id, plan_id, plan_day, goal_date, achieved, achieved_at,
                  exp_awarded
                from app.daily_goal_achievements
                where user_id = %(user_id)s and plan_id = %(plan_id)s
                  and plan_day = %(plan_day)s
                """,
                {"user_id": user_id, "plan_id": plan_id, "plan_day": plan_day},
            )
            achievement_row = await achievement_cursor.fetchone()
            if achievement_row is None:
                raise PlanDataIntegrityError()
            achievement = self._daily_goal_achievement(achievement_row)
            self._validate_daily_goal(
                achievement,
                user_id=user_id,
                plan_id=plan_id,
                plan_day=plan_day,
                goal_date=today,
                tasks=tasks,
            )
            return TodayQuestSnapshot(
                date=today,
                plan_id=plan_id,
                plan_title=str(plan_row["title"]),
                tasks=tasks,
                achievement=achievement,
                user_exp=user_exp,
            )

    async def set_task_status(
        self,
        *,
        user_id: UUID,
        plan_id: UUID,
        task_id: UUID,
        status: Literal["pending", "completed"],
    ) -> StoredTaskUpdate | None:
        return await self._set_task_status(
            user_id=user_id,
            plan_id=plan_id,
            task_id=task_id,
            status=status,
            today_only=False,
        )

    async def set_today_task_status(
        self,
        *,
        user_id: UUID,
        task_id: UUID,
        status: Literal["pending", "completed"],
    ) -> StoredTaskUpdate | None:
        return await self._set_task_status(
            user_id=user_id,
            plan_id=None,
            task_id=task_id,
            status=status,
            today_only=True,
        )

    async def _set_task_status(
        self,
        *,
        user_id: UUID,
        plan_id: UUID | None,
        task_id: UUID,
        status: Literal["pending", "completed"],
        today_only: bool,
    ) -> StoredTaskUpdate | None:
        parameters: dict[str, Any] = {
            "user_id": user_id,
            "plan_id": plan_id,
            "task_id": task_id,
            "status": status,
        }
        async with self._pool.connection() as connection, connection.transaction():
            required_goal_date = self._today_provider() if today_only else None
            plan_row = await self._fetch_owned_plan_row(
                connection,
                user_id=user_id,
                plan_id=plan_id,
                active_only=today_only,
                lock=True,
            )
            if plan_row is None:
                return None
            plan_id = UUID(str(plan_row["id"]))
            parameters["plan_id"] = plan_id
            task_cursor = await connection.execute(
                """
                select
                  si.id, si.kind, si.title, si.description, si.scheduled_at,
                  si.remind_at, si.status, si.plan_day, si.slot, si.detail_status,
                  si.counts_toward_progress, si.metadata, si.completed_at
                from app.schedule_items si
                where si.user_id = %(user_id)s and si.plan_id = %(plan_id)s
                  and si.id = %(task_id)s and si.kind = 'task'
                  and si.counts_toward_progress = true
                for update
                """,
                parameters,
            )
            task_row = await task_cursor.fetchone()
            if task_row is None:
                return None
            task = self._schedule_item(task_row)
            if required_goal_date is not None:
                if task.scheduled_at is None or task.scheduled_at.tzinfo is None:
                    raise PlanDataIntegrityError()
                if task.scheduled_at.astimezone(ZoneInfo("Asia/Seoul")).date() != required_goal_date:
                    return None
            if task.status not in ("pending", "completed") or (
                (task.status == "completed") != (task.completed_at is not None)
            ):
                raise PlanDataIntegrityError()
            if task.status != status:
                if plan_row.get("status") != "active":
                    raise PlanNotActiveError()
                update_cursor = await connection.execute(
                    """
                    update app.schedule_items
                    set status = %(status)s,
                        completed_at = case when %(status)s = 'completed' then now() else null end
                    where user_id = %(user_id)s and plan_id = %(plan_id)s
                      and id = %(task_id)s and kind = 'task'
                      and counts_toward_progress = true
                    returning
                      id, kind, title, description, scheduled_at, remind_at, status,
                      plan_day, slot, detail_status, counts_toward_progress, metadata,
                      completed_at
                    """,
                    parameters,
                )
                updated = await update_cursor.fetchone()
                if updated is None:
                    raise PlanDataIntegrityError()
                task = self._schedule_item(updated)
            progress_rows = await self._fetch_progress_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=True
            )
            proposal = self._proposal_from_plan_row(plan_row).content
            progress = [self._schedule_item(row) for row in progress_rows]
            completed = self._validate_progress_rows(proposal, plan_row, progress)
            matching_task = next((item for item in progress if item.id == task.id), None)
            if matching_task is None or matching_task.plan_day is None:
                raise PlanDataIntegrityError()
            task = matching_task
            task_date = proposal.days[task.plan_day - 1].date
            if required_goal_date is not None and task_date != required_goal_date:
                raise PlanDataIntegrityError()
            achievement_cursor = await connection.execute(
                """
                select
                  user_id, plan_id, plan_day, goal_date, achieved, achieved_at,
                  exp_awarded
                from app.daily_goal_achievements
                where user_id = %(user_id)s and plan_id = %(plan_id)s
                  and plan_day = %(plan_day)s
                for update
                """,
                {**parameters, "plan_day": task.plan_day},
            )
            achievement_row = await achievement_cursor.fetchone()
            if achievement_row is None:
                raise PlanDataIntegrityError()
            achievement = self._daily_goal_achievement(achievement_row)

            previous_day_tasks = [
                task_row_item if task_row_item.id != task.id else self._schedule_item(task_row)
                for task_row_item in progress
                if task_row_item.plan_day == task.plan_day
            ]
            current_day_tasks = [
                task_row_item
                for task_row_item in progress
                if task_row_item.plan_day == task.plan_day
            ]
            self._validate_daily_goal(
                achievement,
                user_id=user_id,
                plan_id=plan_id,
                plan_day=task.plan_day,
                goal_date=task_date,
                tasks=previous_day_tasks,
            )
            day_completed = sum(item.status == "completed" for item in current_day_tasks)
            day_total = len(current_day_tasks)
            if day_total == 0:
                raise PlanDataIntegrityError()
            achieved = day_completed == day_total
            exp_delta = (int(achieved) - int(achievement.achieved)) * 20
            if exp_delta not in (-20, 0, 20):
                raise PlanDataIntegrityError()

            account_cursor = await connection.execute(
                """
                select id, role, user_exp
                from app.user_accounts
                where id = %(user_id)s
                for update
                """,
                parameters,
            )
            account_row = await account_cursor.fetchone()
            user_exp = self._validated_user_exp(account_row, user_id=user_id)
            if user_exp + exp_delta < 0:
                raise PlanDataIntegrityError()

            if exp_delta:
                achieved_at = (
                    max(
                        item.completed_at
                        for item in current_day_tasks
                        if item.completed_at is not None
                    )
                    if achieved
                    else None
                )
                transition_parameters = {
                    **parameters,
                    "plan_day": task.plan_day,
                    "old_achieved": achievement.achieved,
                    "old_achieved_at": achievement.achieved_at,
                    "old_exp_awarded": achievement.exp_awarded,
                    "achieved": achieved,
                    "achieved_at": achieved_at,
                    "exp_awarded": 20 if achieved else 0,
                    "exp_delta": exp_delta,
                }
                achievement_update_cursor = await connection.execute(
                    """
                    update app.daily_goal_achievements
                    set achieved = %(achieved)s,
                        achieved_at = %(achieved_at)s,
                        exp_awarded = %(exp_awarded)s
                    where user_id = %(user_id)s and plan_id = %(plan_id)s
                      and plan_day = %(plan_day)s
                      and achieved = %(old_achieved)s
                      and achieved_at is not distinct from %(old_achieved_at)s
                      and exp_awarded = %(old_exp_awarded)s
                    returning
                      user_id, plan_id, plan_day, goal_date, achieved, achieved_at,
                      exp_awarded
                    """,
                    transition_parameters,
                )
                updated_achievement_row = await achievement_update_cursor.fetchone()
                if updated_achievement_row is None:
                    raise PlanDataIntegrityError()
                achievement = self._daily_goal_achievement(updated_achievement_row)

                account_update_cursor = await connection.execute(
                    """
                    update app.user_accounts
                    set user_exp = user_exp + %(exp_delta)s
                    where id = %(user_id)s and role = 'user'
                      and user_exp + %(exp_delta)s >= 0
                    returning id, role, user_exp
                    """,
                    transition_parameters,
                )
                updated_account_row = await account_update_cursor.fetchone()
                user_exp = self._validated_user_exp(updated_account_row, user_id=user_id)

            self._validate_daily_goal(
                achievement,
                user_id=user_id,
                plan_id=plan_id,
                plan_day=task.plan_day,
                goal_date=task_date,
                tasks=current_day_tasks,
            )
            return StoredTaskUpdate(
                task=task,
                task_date=task_date,
                completed_task_count=completed,
                total_task_count=int(plan_row["total_task_count"]),
                day_completed_task_count=day_completed,
                day_total_task_count=day_total,
                achieved=achievement.achieved,
                achieved_at=achievement.achieved_at,
                earned_exp=achievement.exp_awarded,
                exp_delta=exp_delta,
                user_exp=user_exp,
            )

    async def complete_plan(self, *, user_id: UUID, plan_id: UUID) -> StoredPlan | None:
        parameters = {"user_id": user_id, "plan_id": plan_id}
        async with self._pool.connection() as connection, connection.transaction():
            plan_row = await self._fetch_owned_plan_row(
                connection,
                user_id=user_id,
                plan_id=plan_id,
                active_only=False,
                lock=True,
            )
            if plan_row is None:
                return None
            if plan_row.get("status") == "completed":
                items = await self._fetch_schedule_rows(
                    connection, user_id=user_id, plan_id=plan_id, lock=False
                )
                achievements = await self._fetch_achievement_rows(
                    connection, user_id=user_id, plan_id=plan_id, lock=False
                )
                return self._stored_plan(plan_row, items, achievements)
            if plan_row.get("status") != "active":
                raise PlanNotActiveError()
            progress_rows = await self._fetch_progress_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=True
            )
            proposal = self._proposal_from_plan_row(plan_row).content
            progress = [self._schedule_item(row) for row in progress_rows]
            completed = self._validate_progress_rows(proposal, plan_row, progress)
            total = int(plan_row["total_task_count"])
            if completed != total:
                raise PlanNotCompleteError(
                    details={
                        "completed_task_count": completed,
                        "total_task_count": total,
                    }
                )
            full_rows = await self._fetch_schedule_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=True
            )
            items = [self._schedule_item(row) for row in full_rows]
            self._validate_projected_rows(proposal, items, allow_completed_tasks=True)
            update_cursor = await connection.execute(
                """
                update app.plans
                set status = 'completed', final_progress = 100, ended_at = now(),
                    restart_offer_status = 'pending', restart_prompted_at = now()
                where user_id = %(user_id)s and id = %(plan_id)s and status = 'active'
                returning
                  id, user_id, title, summary, goal_snapshot, starts_on, ends_on,
                  total_task_count, status, activated_at, ended_at,
                  restart_offer_status, restart_prompted_at
                """,
                parameters,
            )
            completed_row = await update_cursor.fetchone()
            if completed_row is None:
                raise PlanDataIntegrityError()
            achievement_rows = await self._fetch_achievement_rows(
                connection, user_id=user_id, plan_id=plan_id, lock=False
            )
            completed_row = {
                **completed_row,
                "account_role": plan_row.get("account_role"),
                "user_exp": plan_row.get("user_exp"),
            }
            return self._stored_plan_from_parts(
                completed_row,
                self._proposal_from_plan_row(plan_row),
                items,
                [self._daily_goal_achievement(row) for row in achievement_rows],
            )

    @staticmethod
    async def _fetch_proposal_row(
        connection: Any, *, user_id: UUID, proposal_id: UUID, lock: bool
    ) -> Mapping[str, Any] | None:
        cursor = await connection.execute(
            f"""
            select
              id, user_id, saved_job_id, request_id, kind, decision_status, content,
              model_name, prompt_version, applied_plan_id, decided_at, created_at
            from app.ai_results
            where user_id = %(user_id)s and id = %(proposal_id)s
              and kind = 'profile_plan_proposal'
            {"for update" if lock else ""}
            """,
            {"user_id": user_id, "proposal_id": proposal_id},
        )
        return await cursor.fetchone()

    @staticmethod
    async def _fetch_owned_plan_row(
        connection: Any,
        *,
        user_id: UUID,
        plan_id: UUID | None,
        active_only: bool,
        lock: bool,
    ) -> Mapping[str, Any] | None:
        cursor = await connection.execute(
            f"""
            select
              p.id, p.user_id, p.title, p.summary, p.goal_snapshot,
              p.starts_on, p.ends_on, p.total_task_count, p.status,
              p.activated_at, p.ended_at, p.restart_offer_status,
              p.restart_prompted_at, ua.role as account_role, ua.user_exp,
              ar.id as proposal_id,
              ar.saved_job_id as proposal_saved_job_id,
              ar.request_id as proposal_request_id,
              ar.decision_status as proposal_decision_status,
              ar.content as proposal_content,
              ar.model_name as proposal_model_name,
              ar.prompt_version as proposal_prompt_version,
              ar.applied_plan_id as proposal_applied_plan_id,
              ar.decided_at as proposal_decided_at,
              ar.created_at as proposal_created_at
            from app.plans p
            join app.ai_results ar
              on ar.user_id = p.user_id and ar.id = p.proposal_result_id
             and ar.kind = 'profile_plan_proposal'
             and ar.decision_status = 'applied'
             and ar.applied_plan_id = p.id
            join app.user_accounts ua on ua.id = p.user_id
            where p.user_id = %(user_id)s
              {"and p.id = %(plan_id)s" if plan_id is not None else ""}
              {"and p.status = 'active'" if active_only else ""}
            {"for update of p" if lock else ""}
            """,
            {"user_id": user_id, "plan_id": plan_id},
        )
        return await cursor.fetchone()

    @staticmethod
    async def _fetch_owned_plan_rows(
        connection: Any,
        *,
        user_id: UUID,
    ) -> list[Mapping[str, Any]]:
        cursor = await connection.execute(
            """
            select
              p.id, p.user_id, p.title, p.summary, p.goal_snapshot,
              p.starts_on, p.ends_on, p.total_task_count, p.status,
              p.activated_at, p.ended_at, p.restart_offer_status,
              p.restart_prompted_at, ua.role as account_role, ua.user_exp,
              ar.id as proposal_id,
              ar.request_id as proposal_request_id,
              ar.decision_status as proposal_decision_status,
              ar.content as proposal_content,
              ar.model_name as proposal_model_name,
              ar.prompt_version as proposal_prompt_version,
              ar.applied_plan_id as proposal_applied_plan_id,
              ar.decided_at as proposal_decided_at,
              ar.created_at as proposal_created_at
            from app.plans p
            join app.ai_results ar
              on ar.user_id = p.user_id and ar.id = p.proposal_result_id
             and ar.kind = 'profile_plan_proposal'
             and ar.decision_status = 'applied'
             and ar.applied_plan_id = p.id
            join app.user_accounts ua on ua.id = p.user_id
            where p.user_id = %(user_id)s
            order by p.created_at desc, p.id desc
            """,
            {"user_id": user_id},
        )
        return list(await cursor.fetchall())

    @staticmethod
    async def _fetch_schedule_rows(
        connection: Any, *, user_id: UUID, plan_id: UUID, lock: bool
    ) -> list[Mapping[str, Any]]:
        cursor = await connection.execute(
            f"""
            select
              id, kind, title, description, scheduled_at, remind_at, status,
              plan_day, slot, detail_status, counts_toward_progress, metadata,
              completed_at
            from app.schedule_items
            where user_id = %(user_id)s and plan_id = %(plan_id)s
            order by kind, plan_day nulls first, slot nulls first, id
            {"for update" if lock else ""}
            """,
            {"user_id": user_id, "plan_id": plan_id},
        )
        return list(await cursor.fetchall())

    @staticmethod
    async def _fetch_achievement_rows(
        connection: Any, *, user_id: UUID, plan_id: UUID, lock: bool
    ) -> list[Mapping[str, Any]]:
        cursor = await connection.execute(
            f"""
            select
              user_id, plan_id, plan_day, goal_date, achieved, achieved_at,
              exp_awarded
            from app.daily_goal_achievements
            where user_id = %(user_id)s and plan_id = %(plan_id)s
            order by plan_day
            {"for update" if lock else ""}
            """,
            {"user_id": user_id, "plan_id": plan_id},
        )
        return list(await cursor.fetchall())

    @staticmethod
    async def _fetch_progress_rows(
        connection: Any, *, user_id: UUID, plan_id: UUID, lock: bool
    ) -> list[Mapping[str, Any]]:
        cursor = await connection.execute(
            f"""
            select
              id, kind, title, description, scheduled_at, remind_at, status,
              plan_day, slot, detail_status, counts_toward_progress, metadata,
              completed_at
            from app.schedule_items
            where user_id = %(user_id)s and plan_id = %(plan_id)s
              and kind = 'task' and counts_toward_progress = true
            order by plan_day, slot, id
            {"for update" if lock else ""}
            """,
            {"user_id": user_id, "plan_id": plan_id},
        )
        return list(await cursor.fetchall())

    @staticmethod
    def _projection_payload(proposal: ProfilePlanProposalV1) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for milestone in proposal.milestones:
            payload.append(
                {
                    "kind": "milestone",
                    "title": milestone.title,
                    "description": milestone.description,
                    "local_date": milestone.ends_on.isoformat(),
                    "plan_day": None,
                    "slot": None,
                    "counts_toward_progress": False,
                    "metadata": {
                        "week_index": milestone.week_index,
                        "starts_on": milestone.starts_on.isoformat(),
                        "ends_on": milestone.ends_on.isoformat(),
                    },
                }
            )
        for plan_day, day in enumerate(proposal.days, start=1):
            for slot, task in enumerate(day.tasks, start=1):
                payload.append(
                    {
                        "kind": "task",
                        "title": task.title,
                        "description": task.description,
                        "local_date": day.date.isoformat(),
                        "plan_day": plan_day,
                        "slot": slot,
                        "counts_toward_progress": True,
                        "metadata": {},
                    }
                )
        return payload

    @staticmethod
    def _schedule_item(row: Mapping[str, Any]) -> PlanScheduleItem:
        try:
            return PlanScheduleItem.model_validate(row)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    @staticmethod
    def _daily_goal_achievement(row: Mapping[str, Any]) -> DailyGoalAchievement:
        try:
            return DailyGoalAchievement.model_validate(row)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    @staticmethod
    def _validated_user_exp(row: Mapping[str, Any] | None, *, user_id: UUID) -> int:
        if row is None or row.get("id") != user_id or row.get("role") != "user":
            raise PlanDataIntegrityError()
        value = row.get("user_exp")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PlanDataIntegrityError()
        return value

    @staticmethod
    def _validated_read_user_exp(row: Mapping[str, Any] | None, *, user_id: UUID) -> int:
        if row is None or row.get("id") != user_id or row.get("role") not in ("user", "admin"):
            raise PlanDataIntegrityError()
        value = row.get("user_exp")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PlanDataIntegrityError()
        if row.get("role") == "admin" and value != 0:
            raise PlanDataIntegrityError()
        return value

    @staticmethod
    async def _fetch_read_user_exp(connection: Any, *, user_id: UUID) -> int:
        account_cursor = await connection.execute(
            """
            select id, role, user_exp
            from app.user_accounts
            where id = %(user_id)s
            """,
            {"user_id": user_id},
        )
        return PsycopgPlanProposalRepository._validated_read_user_exp(
            await account_cursor.fetchone(), user_id=user_id
        )

    @staticmethod
    def _validate_daily_goal(
        achievement: DailyGoalAchievement,
        *,
        user_id: UUID,
        plan_id: UUID,
        plan_day: int,
        goal_date: date,
        tasks: list[PlanScheduleItem],
    ) -> None:
        if (
            achievement.user_id != user_id
            or achievement.plan_id != plan_id
            or achievement.plan_day != plan_day
            or achievement.goal_date != goal_date
            or not tasks
        ):
            raise PlanDataIntegrityError()
        expected_achieved = all(task.status == "completed" for task in tasks)
        expected_achieved_at = (
            max(task.completed_at for task in tasks if task.completed_at is not None)
            if expected_achieved
            else None
        )
        if (
            achievement.achieved != expected_achieved
            or achievement.achieved_at != expected_achieved_at
            or achievement.exp_awarded != (20 if expected_achieved else 0)
        ):
            raise PlanDataIntegrityError()

    @classmethod
    def _validate_projected_rows(
        cls,
        proposal: ProfilePlanProposalV1,
        items: list[PlanScheduleItem],
        *,
        allow_completed_tasks: bool = False,
    ) -> None:
        expected = cls._projection_payload(proposal)
        if len(items) != len(expected):
            raise PlanDataIntegrityError()
        for item in items:
            if (
                item.scheduled_at is None
                or item.remind_at is not None
                or item.detail_status != "ready"
            ):
                raise PlanDataIntegrityError()
            if item.kind == "milestone" and (
                item.status != "pending" or item.completed_at is not None
            ):
                raise PlanDataIntegrityError()
            if item.kind == "task" and (
                item.status
                not in (("pending", "completed") if allow_completed_tasks else ("pending",))
                or (item.status == "completed") != (item.completed_at is not None)
            ):
                raise PlanDataIntegrityError()
        actual_keys = {
            (
                item.kind,
                item.plan_day,
                item.slot,
                item.title,
                item.description,
                item.counts_toward_progress,
            )
            for item in items
        }
        expected_keys = {
            (
                item["kind"],
                item["plan_day"],
                item["slot"],
                item["title"],
                item["description"],
                item["counts_toward_progress"],
            )
            for item in expected
        }
        if actual_keys != expected_keys:
            raise PlanDataIntegrityError()
        milestone_metadata = {
            (
                item.metadata.get("week_index"),
                item.metadata.get("starts_on"),
                item.metadata.get("ends_on"),
            )
            for item in items
            if item.kind == "milestone"
        }
        expected_metadata = {
            (
                item.week_index,
                item.starts_on.isoformat(),
                item.ends_on.isoformat(),
            )
            for item in proposal.milestones
        }
        if milestone_metadata != expected_metadata:
            raise PlanDataIntegrityError()
        milestone_by_week = {
            item.metadata.get("week_index"): item for item in items if item.kind == "milestone"
        }
        for expected_milestone in proposal.milestones:
            item = milestone_by_week.get(expected_milestone.week_index)
            if item is None or not cls._matches_frozen_schedule(
                item,
                expected_date=expected_milestone.ends_on,
                expected_time=proposal.profile_snapshot.daily_notification_time,
            ):
                raise PlanDataIntegrityError()
        task_by_position = {
            (item.plan_day, item.slot): item for item in items if item.kind == "task"
        }
        for plan_day, day in enumerate(proposal.days, start=1):
            for slot, _task in enumerate(day.tasks, start=1):
                item = task_by_position.get((plan_day, slot))
                if (
                    item is None
                    or item.metadata != {}
                    or not cls._matches_frozen_schedule(
                        item,
                        expected_date=day.date,
                        expected_time=proposal.profile_snapshot.daily_notification_time,
                    )
                ):
                    raise PlanDataIntegrityError()

    @staticmethod
    def _matches_frozen_schedule(
        item: PlanScheduleItem, *, expected_date: date, expected_time: time
    ) -> bool:
        if item.scheduled_at is None or item.scheduled_at.tzinfo is None:
            raise PlanDataIntegrityError()
        local = item.scheduled_at.astimezone(ZoneInfo("Asia/Seoul"))
        return (
            local.date() == expected_date and local.timetz().replace(tzinfo=None) == expected_time
        )

    @staticmethod
    def _proposal_from_plan_row(row: Mapping[str, Any]) -> StoredPlanProposal:
        try:
            return StoredPlanProposal.model_validate(
                {
                    "id": row["proposal_id"],
                    "user_id": row["user_id"],
                    "request_id": row["proposal_request_id"],
                    "saved_job_id": row.get("proposal_saved_job_id"),
                    "decision_status": row["proposal_decision_status"],
                    "content": row["proposal_content"],
                    "model_name": row["proposal_model_name"],
                    "prompt_version": row["proposal_prompt_version"],
                    "applied_plan_id": row["proposal_applied_plan_id"],
                    "decided_at": row["proposal_decided_at"],
                    "created_at": row["proposal_created_at"],
                }
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    @classmethod
    def _stored_plan(
        cls,
        row: Mapping[str, Any],
        item_rows: list[Mapping[str, Any]],
        achievement_rows: list[Mapping[str, Any]],
        *,
        view_today: date | None = None,
    ) -> StoredPlan:
        return cls._stored_plan_from_parts(
            row,
            cls._proposal_from_plan_row(row),
            [cls._schedule_item(item) for item in item_rows],
            [cls._daily_goal_achievement(item) for item in achievement_rows],
            view_today=view_today,
        )

    @classmethod
    def _stored_plan_from_parts(
        cls,
        row: Mapping[str, Any],
        proposal: StoredPlanProposal,
        items: list[PlanScheduleItem],
        achievements: list[DailyGoalAchievement],
        *,
        view_today: date | None = None,
    ) -> StoredPlan:
        try:
            if row.get("account_role") != "user":
                raise PlanDataIntegrityError()
            user_exp = row["user_exp"]
            if isinstance(user_exp, bool) or not isinstance(user_exp, int) or user_exp < 0:
                raise PlanDataIntegrityError()
            cls._validate_daily_achievements(
                proposal.content,
                items,
                achievements,
                user_id=UUID(str(row["user_id"])),
                plan_id=UUID(str(row["id"])),
            )
            return StoredPlan.model_validate(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "proposal": proposal,
                    "title": row["title"],
                    "summary": row.get("summary"),
                    "goal_snapshot": row["goal_snapshot"],
                    "starts_on": row["starts_on"],
                    "ends_on": row["ends_on"],
                    "total_task_count": row["total_task_count"],
                    "status": row["status"],
                    "activated_at": row.get("activated_at"),
                    "ended_at": row.get("ended_at"),
                    "restart_offer_status": row["restart_offer_status"],
                    "restart_prompted_at": row.get("restart_prompted_at"),
                    "schedule_items": items,
                    "daily_goal_achievements": achievements,
                    "user_exp": user_exp,
                    "view_today": view_today,
                }
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    @classmethod
    def _validate_daily_achievements(
        cls,
        proposal: ProfilePlanProposalV1,
        items: list[PlanScheduleItem],
        achievements: list[DailyGoalAchievement],
        *,
        user_id: UUID,
        plan_id: UUID,
    ) -> None:
        if len(achievements) != len(proposal.days):
            raise PlanDataIntegrityError()
        by_day = {achievement.plan_day: achievement for achievement in achievements}
        if len(by_day) != len(achievements):
            raise PlanDataIntegrityError()
        for plan_day, day in enumerate(proposal.days, start=1):
            achievement = by_day.get(plan_day)
            if achievement is None:
                raise PlanDataIntegrityError()
            tasks = [
                item
                for item in items
                if item.kind == "task" and item.counts_toward_progress and item.plan_day == plan_day
            ]
            cls._validate_daily_goal(
                achievement,
                user_id=user_id,
                plan_id=plan_id,
                plan_day=plan_day,
                goal_date=day.date,
                tasks=tasks,
            )

    @staticmethod
    def _validate_progress_rows(
        proposal: ProfilePlanProposalV1,
        plan_row: Mapping[str, Any],
        items: list[PlanScheduleItem],
    ) -> int:
        try:
            total = int(plan_row["total_task_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanDataIntegrityError() from exc
        if total <= 0 or total != proposal.total_task_count or len(items) != total:
            raise PlanDataIntegrityError()
        by_position: dict[tuple[int, int], PlanScheduleItem] = {}
        for item in items:
            if (
                item.kind != "task"
                or not item.counts_toward_progress
                or item.plan_day is None
                or item.slot is None
                or item.status not in ("pending", "completed")
                or (item.status == "completed") != (item.completed_at is not None)
                or item.remind_at is not None
                or item.detail_status != "ready"
                or item.metadata != {}
            ):
                raise PlanDataIntegrityError()
            key = (item.plan_day, item.slot)
            if key in by_position:
                raise PlanDataIntegrityError()
            by_position[key] = item
        for plan_day, day in enumerate(proposal.days, start=1):
            for slot, task in enumerate(day.tasks, start=1):
                item = by_position.get((plan_day, slot))
                if (
                    item is None
                    or item.title != task.title
                    or item.description != task.description
                    or not PsycopgPlanProposalRepository._matches_frozen_schedule(
                        item,
                        expected_date=day.date,
                        expected_time=proposal.profile_snapshot.daily_notification_time,
                    )
                ):
                    raise PlanDataIntegrityError()
        completed = sum(item.status == "completed" for item in items)
        if plan_row.get("status") == "completed" and completed != total:
            raise PlanDataIntegrityError()
        return completed

    @staticmethod
    async def _fetch_request_row(
        connection: Any, *, user_id: UUID, request_id: UUID, lock: bool
    ) -> Mapping[str, Any] | None:
        cursor = await connection.execute(
            f"""
            select
              id, user_id, saved_job_id, request_id, kind, decision_status, content,
              model_name, prompt_version, applied_plan_id, decided_at, created_at
            from app.ai_results
            where user_id = %(user_id)s and request_id = %(request_id)s
            {"for update" if lock else ""}
            """,
            {"user_id": user_id, "request_id": str(request_id)},
        )
        return await cursor.fetchone()

    def _resolve_row(self, row: Mapping[str, Any] | None) -> StoredPlanProposal | str | None:
        if row is None:
            return None
        if row.get("kind") != "profile_plan_proposal":
            return str(row.get("kind"))
        return self._stored(row)

    def _resolve_persistence_winner(
        self, row: Mapping[str, Any], proposal: ProfilePlanProposalV1
    ) -> StoredPlanProposal:
        if row.get("kind") != "profile_plan_proposal":
            raise IdempotencyKeyReusedError()
        content = row.get("content")
        if (
            not isinstance(content, Mapping)
            or content.get("proposal_hash") != proposal.proposal_hash
        ):
            raise IdempotencyKeyReusedError()
        winner = self._stored(row)
        if winner.content != proposal:
            raise IdempotencyKeyReusedError()
        return winner

    @staticmethod
    def _stored(row: Mapping[str, Any]) -> StoredPlanProposal:
        try:
            return StoredPlanProposal.model_validate(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "request_id": row["request_id"],
                    "saved_job_id": row.get("saved_job_id"),
                    "decision_status": row["decision_status"],
                    "content": row["content"],
                    "model_name": row["model_name"],
                    "prompt_version": row["prompt_version"],
                    "applied_plan_id": row.get("applied_plan_id"),
                    "decided_at": row.get("decided_at"),
                    "created_at": row["created_at"],
                }
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    @staticmethod
    def _preflight(
        row: Mapping[str, Any],
        *,
        active: bool,
        pending: Mapping[str, Any] | None,
        saved_job_row: Mapping[str, Any] | None = None,
    ) -> PlanGenerationPreflight:
        try:
            snapshot = ProfileOnboardingData.model_validate(row)
            return PlanGenerationPreflight(
                profile_snapshot=snapshot,
                profile_hash=row["profile_hash"],
                assessment_result_id=row["assessment_result_id"],
                assessment_score=row["assessment_score"],
                assessment_level=row["assessment_level"],
                assessment_summary=row["assessment_summary"],
                saved_job_snapshot=(
                    SavedJobView.model_validate(saved_job_row)
                    if saved_job_row is not None
                    else None
                ),
                active_plan_exists=active,
                pending_request_id=pending["request_id"] if pending is not None else None,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc

    @staticmethod
    def _validate_current_profile(
        row: Mapping[str, Any], *, proposal: ProfilePlanProposalV1, today: date
    ) -> None:
        try:
            current_snapshot = ProfileOnboardingData.model_validate(row)
            same_profile = (
                current_snapshot == proposal.profile_snapshot
                and row["profile_hash"] == proposal.profile_hash
                and UUID(str(row["assessment_result_id"])) == proposal.assessment_result_id
                and current_snapshot.target_date == proposal.ends_on
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlanDataIntegrityError() from exc
        if not same_profile:
            raise PlanProfileChangedError()
        if proposal.generated_on != today or proposal.starts_on != today:
            raise PlanProposalStaleError()
