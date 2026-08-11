from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.auth.errors import LoginIdAlreadyExistsError
from app.auth.models import AccountAuthRecord, AccountSummary, CreatedUserIdentity
from app.profiles.models import ProfileAssessment, ProfileOnboardingData, ProfileRecord


class OnboardingSnapshotConflictError(RuntimeError):
    pass


def profile_snapshot_hash(
    profile: ProfileOnboardingData,
    assessment: ProfileAssessment,
    *,
    draft_revision: int,
) -> str:
    canonical = json.dumps(
        {
            "assessment": assessment.model_dump(mode="json"),
            "draft_revision": draft_revision,
            "profile_snapshot": profile.model_dump(mode="json"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class PsycopgAccountRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create_user(
        self,
        normalized_login_id: str,
        password_hash: str,
        user_name: str,
    ) -> CreatedUserIdentity:
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    """
                    insert into app.user_accounts (login_id, password_hash, user_name)
                    values (%(login_id)s, %(password_hash)s, %(user_name)s)
                    returning id, role, login_id
                    """,
                    {
                        "login_id": normalized_login_id,
                        "password_hash": password_hash,
                        "user_name": user_name,
                    },
                )
                row = await cursor.fetchone()
        except UniqueViolation as exc:
            raise LoginIdAlreadyExistsError from exc
        if row is None:
            raise RuntimeError("생성된 사용자 정보를 반환하지 못했습니다.")
        return CreatedUserIdentity.model_validate(row)

    async def get_for_login(self, normalized_login_id: str) -> AccountAuthRecord | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select
                  id,
                  role,
                  login_id,
                  password_hash,
                  is_active,
                  failed_login_count,
                  locked_until
                from app.user_accounts
                where lower(login_id) = %(login_id)s
                limit 1
                """,
                {"login_id": normalized_login_id},
            )
            row = await cursor.fetchone()
        return AccountAuthRecord.model_validate(row) if row is not None else None

    async def is_active(self, account_id: UUID) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select id
                from app.user_accounts
                where id = %(account_id)s
                  and is_active = true
                limit 1
                """,
                {"account_id": account_id},
            )
            return await cursor.fetchone() is not None

    async def update_account(
        self,
        account_id: UUID,
        *,
        login_id: str | None,
        user_name: str | None,
    ) -> AccountSummary | None:
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    """
                    update app.user_accounts
                    set
                      login_id = coalesce(%(login_id)s, login_id),
                      user_name = coalesce(%(user_name)s, user_name)
                    where id = %(account_id)s
                      and is_active = true
                    returning id as user_id, login_id, user_name
                    """,
                    {
                        "account_id": account_id,
                        "login_id": login_id,
                        "user_name": user_name,
                    },
                )
                row = await cursor.fetchone()
        except UniqueViolation as exc:
            raise LoginIdAlreadyExistsError from exc
        return AccountSummary.model_validate(row) if row is not None else None

    async def delete_account(self, account_id: UUID) -> bool:
        parameters = {"account_id": account_id}
        async with self._pool.connection() as connection, connection.transaction():
            cursor = await connection.execute(
                """
                select id
                from app.user_accounts
                where id = %(account_id)s
                for update
                """,
                parameters,
            )
            if await cursor.fetchone() is None:
                return False

            await connection.execute(
                "delete from app.notifications where user_id = %(account_id)s",
                parameters,
            )
            await connection.execute(
                "delete from app.schedule_items where user_id = %(account_id)s",
                parameters,
            )
            await connection.execute(
                "delete from app.daily_goal_achievements where user_id = %(account_id)s",
                parameters,
            )
            await connection.execute(
                "delete from app.profiles where user_id = %(account_id)s",
                parameters,
            )
            await connection.execute(
                """
                update app.plans
                set proposal_result_id = null, previous_plan_id = null
                where user_id = %(account_id)s
                """,
                parameters,
            )
            await connection.execute(
                "delete from app.ai_results where user_id = %(account_id)s",
                parameters,
            )
            await connection.execute(
                "delete from app.plans where user_id = %(account_id)s",
                parameters,
            )
            cursor = await connection.execute(
                """
                delete from app.user_accounts
                where id = %(account_id)s
                returning id
                """,
                parameters,
            )
            return await cursor.fetchone() is not None

    async def record_failed_login(self, account_id: UUID, *, now: datetime) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                """
                update app.user_accounts
                set
                  failed_login_count = case
                    when locked_until is not null and locked_until <= %(now)s then 1
                    else least(failed_login_count + 1, 32767)
                  end,
                  locked_until = case
                    when locked_until is not null and locked_until <= %(now)s then null
                    when failed_login_count + 1 >= 5 then %(locked_until)s
                    else locked_until
                  end
                where id = %(account_id)s
                  and (locked_until is null or locked_until <= %(now)s)
                """,
                {
                    "account_id": account_id,
                    "now": now,
                    "locked_until": now + timedelta(minutes=15),
                },
            )

    async def record_successful_login(self, account_id: UUID, *, now: datetime) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                update app.user_accounts
                set
                  last_login_at = %(now)s,
                  failed_login_count = 0,
                  locked_until = null
                where id = %(account_id)s
                  and is_active = true
                  and (locked_until is null or locked_until <= %(now)s)
                returning id
                """,
                {"account_id": account_id, "now": now},
            )
            return await cursor.fetchone() is not None


class PsycopgProfileRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save_onboarding(
        self,
        *,
        user_id: UUID,
        profile: ProfileOnboardingData,
        assessment: ProfileAssessment,
        request_id: UUID,
        draft_revision: int,
    ) -> ProfileRecord:
        snapshot_hash = profile_snapshot_hash(profile, assessment, draft_revision=draft_revision)
        assessment_data = assessment.model_dump(mode="json")
        assessment_content = {
            "schema_version": assessment.schema_version,
            "profile_snapshot": profile.model_dump(mode="json"),
            "assessment": assessment_data,
            "draft_revision": draft_revision,
            "snapshot_hash": snapshot_hash,
            "metadata": {
                "user_id": str(user_id),
                "request_id": str(request_id),
                "generated_at": datetime.now(UTC).isoformat(),
            },
        }
        assessment_source = {
            "provider": assessment.provider,
            "model": assessment.model_name,
            "prompt_version": assessment.prompt_version,
            "rubric_version": assessment.rubric_version,
        }
        parameters: dict[str, Any] = {
            "user_id": user_id,
            "request_id": str(request_id),
            "model_name": assessment.model_name,
            "assessment_version": assessment.version,
            "prompt_version": assessment.prompt_version,
            "assessment_content": Jsonb(assessment_content),
            "assessment_source": Jsonb(assessment_source),
            "target_role": profile.target_role,
            "skills": profile.skills,
            "experience_summary": profile.experience_summary,
            "target_date": profile.target_date,
            "target_company": profile.target_company,
            "preferred_environment": profile.preferred_environment,
            "assistant_style": profile.assistant_style,
            "daily_notification_time": profile.daily_notification_time,
            "assessment_score": assessment.score,
            "assessment_level": assessment.level,
            "assessment_summary": Jsonb(assessment.summary),
            "draft_revision": draft_revision,
            "snapshot_hash": snapshot_hash,
        }

        async with self._pool.connection() as connection, connection.transaction():
            result_cursor = await connection.execute(
                """
                    insert into app.ai_results (
                      user_id,
                      kind,
                      decision_status,
                      title,
                      content,
                      model_name,
                      prompt_version,
                      request_id
                    )
                    values (
                      %(user_id)s,
                      'profile_assessment',
                      'not_applicable',
                      '온보딩 준비 수준 진단',
                      %(assessment_content)s,
                      %(model_name)s,
                      %(prompt_version)s,
                      %(request_id)s
                    )
                    on conflict (user_id, request_id) do nothing
                    returning id
                    """,
                parameters,
            )
            result_row = await result_cursor.fetchone()
            if result_row is None:
                existing_cursor = await connection.execute(
                    """
                    select id, content
                    from app.ai_results
                    where user_id = %(user_id)s
                      and request_id = %(request_id)s
                    limit 1
                    """,
                    parameters,
                )
                existing = await existing_cursor.fetchone()
                if existing is None or existing["content"].get("snapshot_hash") != snapshot_hash:
                    raise OnboardingSnapshotConflictError(
                        "같은 request_id에 다른 온보딩 snapshot이 저장되어 있습니다."
                    )
                stored = await self._get_by_user_id(connection, user_id)
                if stored is None or stored.assessment_result_id != existing["id"]:
                    raise OnboardingSnapshotConflictError(
                        "기존 진단 결과와 연결된 프로필을 찾을 수 없습니다."
                    )
                return stored

            assessment_result_id = result_row["id"]
            parameters["assessment_result_id"] = assessment_result_id

            profile_cursor = await connection.execute(
                """
                    insert into app.profiles (
                      user_id,
                      target_role,
                      skills,
                      experience_summary,
                      target_date,
                      target_company,
                      preferred_environment,
                      assistant_style,
                      daily_notification_time,
                      assessment_score,
                      assessment_level,
                      assessment_summary,
                      assessment_result_id,
                      assessed_at,
                      assessment_version,
                      onboarding_completed_at
                    )
                    values (
                      %(user_id)s,
                      %(target_role)s,
                      %(skills)s,
                      %(experience_summary)s,
                      %(target_date)s,
                      %(target_company)s,
                      %(preferred_environment)s,
                      %(assistant_style)s,
                      %(daily_notification_time)s,
                      %(assessment_score)s,
                      %(assessment_level)s,
                      %(assessment_summary)s,
                      %(assessment_result_id)s,
                      now(),
                      %(assessment_version)s,
                      now()
                    )
                    on conflict (user_id) do update set
                      target_role = excluded.target_role,
                      skills = excluded.skills,
                      experience_summary = excluded.experience_summary,
                      target_date = excluded.target_date,
                      target_company = excluded.target_company,
                      preferred_environment = excluded.preferred_environment,
                      assistant_style = excluded.assistant_style,
                      daily_notification_time = excluded.daily_notification_time,
                      assessment_score = excluded.assessment_score,
                      assessment_level = excluded.assessment_level,
                      assessment_summary = excluded.assessment_summary,
                      assessment_result_id = excluded.assessment_result_id,
                      assessed_at = excluded.assessed_at,
                      assessment_version = excluded.assessment_version,
                      onboarding_completed_at = excluded.onboarding_completed_at
                    returning
                      user_id,
                      target_role,
                      skills,
                      experience_summary,
                      target_date,
                      target_company,
                      preferred_environment,
                      assistant_style,
                      daily_notification_time,
                      assessment_score,
                      assessment_level,
                      assessment_summary,
                      assessment_version,
                      assessed_at,
                      onboarding_completed_at,
                      assessment_result_id,
                      %(assessment_source)s::jsonb as assessment_source,
                      %(draft_revision)s::integer as draft_revision,
                      %(snapshot_hash)s::text as snapshot_hash
                    """,
                parameters,
            )
            row = await profile_cursor.fetchone()
            if row is None:
                raise RuntimeError("저장된 온보딩 프로필을 반환하지 못했습니다.")
            return ProfileRecord.model_validate(row)

    async def get_by_user_id(self, user_id: UUID) -> ProfileRecord | None:
        async with self._pool.connection() as connection:
            return await self._get_by_user_id(connection, user_id)

    @staticmethod
    async def _get_by_user_id(connection: Any, user_id: UUID) -> ProfileRecord | None:
        cursor = await connection.execute(
            """
                select
                  p.user_id,
                  p.target_role,
                  p.skills,
                  p.experience_summary,
                  p.target_date,
                  p.target_company,
                  p.preferred_environment,
                  p.assistant_style,
                  p.daily_notification_time,
                  p.assessment_score,
                  p.assessment_level,
                  p.assessment_summary,
                  p.assessment_version,
                  p.assessed_at,
                  p.onboarding_completed_at,
                  p.assessment_result_id,
                  (ar.content ->> 'draft_revision')::integer as draft_revision,
                  ar.content ->> 'snapshot_hash' as snapshot_hash,
                  case
                    when p.assessment_result_id is null then null
                    else jsonb_build_object(
                      'provider', ar.content #>> '{assessment,provider}',
                      'model', ar.model_name,
                      'prompt_version', ar.prompt_version,
                      'rubric_version', ar.content #>> '{assessment,rubric_version}'
                    )
                  end as assessment_source
                from app.profiles p
                left join app.ai_results ar
                  on ar.user_id = p.user_id
                 and ar.id = p.assessment_result_id
                where p.user_id = %(user_id)s
                """,
            {"user_id": user_id},
        )
        row = await cursor.fetchone()
        return ProfileRecord.model_validate(row) if row is not None else None
