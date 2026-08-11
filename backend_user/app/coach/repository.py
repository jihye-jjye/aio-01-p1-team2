from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from pydantic import ValidationError

from app.coach.errors import AssistantDataIntegrityError, IdempotencyKeyReusedError
from app.coach.models import (
    CareerCoachReportPersistenceResult,
    CareerCoachReportV1,
    ScheduleItemFact,
    ScheduleLookupToolResult,
    StoredCareerCoachReport,
)

KST = ZoneInfo("Asia/Seoul")
REPORT_SESSION_INDEX = "ai_results_one_career_coach_report_per_session_uidx"


class PsycopgCoachRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def lookup_schedule(
        self,
        *,
        user_id: UUID,
        range_start: date,
        range_end: date,
        observed_at: datetime,
    ) -> ScheduleLookupToolResult:
        starts_at = datetime.combine(range_start, time.min, tzinfo=KST).astimezone(UTC)
        ends_before = datetime.combine(
            range_end + timedelta(days=1),
            time.min,
            tzinfo=KST,
        ).astimezone(UTC)
        parameters = {
            "user_id": user_id,
            "starts_at": starts_at,
            "ends_before": ends_before,
        }
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select
                  p.id as plan_id,
                  p.title as plan_title,
                  si.id as item_id,
                  si.kind,
                  si.title as item_title,
                  si.description,
                  si.status as item_status,
                  si.scheduled_at,
                  si.plan_day,
                  si.slot
                from app.plans p
                left join app.schedule_items si
                  on si.user_id = %(user_id)s
                 and si.plan_id = p.id
                 and si.kind in ('milestone', 'task')
                 and si.status <> 'cancelled'
                 and si.scheduled_at >= %(starts_at)s
                 and si.scheduled_at < %(ends_before)s
                where p.user_id = %(user_id)s
                  and p.status = 'active'
                order by si.scheduled_at, si.plan_day nulls first,
                         si.slot nulls first, si.id
                """,
                parameters,
            )
            rows = list(await cursor.fetchall())

        if not rows:
            return ScheduleLookupToolResult(
                status="no_active_plan",
                observed_at=observed_at,
                range_start=range_start,
                range_end=range_end,
            )
        plan_id = rows[0].get("plan_id")
        plan_title = rows[0].get("plan_title")
        if plan_id is None or not isinstance(plan_title, str) or not plan_title.strip():
            raise AssistantDataIntegrityError()
        if any(
            row.get("plan_id") != plan_id or row.get("plan_title") != plan_title for row in rows
        ):
            raise AssistantDataIntegrityError()

        items: list[ScheduleItemFact] = []
        for row in rows:
            if row.get("item_id") is None:
                continue
            try:
                items.append(
                    ScheduleItemFact(
                        id=row["item_id"],
                        kind=row["kind"],
                        title=row["item_title"],
                        description=row.get("description"),
                        status=row["item_status"],
                        scheduled_at=row["scheduled_at"],
                        plan_day=row.get("plan_day"),
                        slot=row.get("slot"),
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                raise AssistantDataIntegrityError() from exc
        return ScheduleLookupToolResult(
            status="found" if items else "empty",
            observed_at=observed_at,
            range_start=range_start,
            range_end=range_end,
            plan_id=plan_id,
            plan_title=plan_title,
            items=items,
        )


class PsycopgCoachReportRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def find_by_request(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
    ) -> StoredCareerCoachReport | str | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select
                  id, user_id, request_id, kind, decision_status, saved_job_id,
                  applied_plan_id, decided_at, content, model_name, prompt_version,
                  created_at
                from app.ai_results
                where user_id = %(user_id)s
                  and request_id = %(request_id)s
                limit 1
                """,
                {"user_id": user_id, "request_id": str(request_id)},
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        if row.get("kind") != "career_coach_report":
            kind = row.get("kind")
            return str(kind) if kind is not None else "unknown"
        return self._stored(row)

    async def find_by_session(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> StoredCareerCoachReport | None:
        async with self._pool.connection() as connection:
            row = await self._fetch_by_session(
                connection,
                user_id=user_id,
                session_id=session_id,
            )
        return self._stored(row) if row is not None else None

    async def persist(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        report: CareerCoachReportV1,
    ) -> CareerCoachReportPersistenceResult:
        parameters = {
            "user_id": user_id,
            "request_id": str(request_id),
            "title": "AI 취업 코치 상담 보고서",
            "content": Jsonb(report.model_dump(mode="json")),
            "model_name": report.engine.model,
            "prompt_version": report.engine.prompt_version,
        }
        try:
            async with self._pool.connection() as connection, connection.transaction():
                cursor = await connection.execute(
                    """
                    insert into app.ai_results (
                      user_id, saved_job_id, applied_plan_id, kind, decision_status,
                      title, content, model_name, prompt_version, request_id, decided_at
                    ) values (
                      %(user_id)s, null, null, 'career_coach_report', 'not_applicable',
                      %(title)s, %(content)s, %(model_name)s, %(prompt_version)s,
                      %(request_id)s, null
                    )
                    on conflict (user_id, request_id) do nothing
                    returning
                      id, user_id, request_id, kind, decision_status, saved_job_id,
                      applied_plan_id, decided_at, content, model_name, prompt_version,
                      created_at
                    """,
                    parameters,
                )
                inserted = await cursor.fetchone()
                if inserted is not None:
                    return CareerCoachReportPersistenceResult(
                        result=self._stored(inserted),
                        created=True,
                    )
                request_cursor = await connection.execute(
                    """
                    select
                      id, user_id, request_id, kind, decision_status, saved_job_id,
                      applied_plan_id, decided_at, content, model_name, prompt_version,
                      created_at
                    from app.ai_results
                    where user_id = %(user_id)s
                      and request_id = %(request_id)s
                    for update
                    """,
                    parameters,
                )
                existing = await request_cursor.fetchone()
                if existing is None or existing.get("kind") != "career_coach_report":
                    raise IdempotencyKeyReusedError()
                stored = self._stored(existing)
                if (
                    stored.report.session_id != report.session_id
                    or stored.report.source_session_hash != report.source_session_hash
                ):
                    raise IdempotencyKeyReusedError()
                return CareerCoachReportPersistenceResult(result=stored, created=False)
        except UniqueViolation as exc:
            constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint != REPORT_SESSION_INDEX:
                raise
            winner = await self.find_by_session(user_id=user_id, session_id=report.session_id)
            if winner is None:
                raise AssistantDataIntegrityError() from exc
            return CareerCoachReportPersistenceResult(result=winner, created=False)

    @staticmethod
    async def _fetch_by_session(
        connection: Any,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> Mapping[str, Any] | None:
        cursor = await connection.execute(
            """
            select
              id, user_id, request_id, kind, decision_status, saved_job_id,
              applied_plan_id, decided_at, content, model_name, prompt_version,
              created_at
            from app.ai_results
            where user_id = %(user_id)s
              and kind = 'career_coach_report'
              and content ->> 'session_id' = %(session_id)s
            limit 1
            """,
            {"user_id": user_id, "session_id": str(session_id)},
        )
        return await cursor.fetchone()

    @staticmethod
    def _stored(row: Mapping[str, Any]) -> StoredCareerCoachReport:
        try:
            if (
                row.get("kind") != "career_coach_report"
                or row.get("decision_status") != "not_applicable"
                or row.get("saved_job_id") is not None
                or row.get("applied_plan_id") is not None
                or row.get("decided_at") is not None
            ):
                raise ValueError("invalid career coach report row")
            report = CareerCoachReportV1.model_validate(row["content"])
            if (
                row.get("model_name") != report.engine.model
                or row.get("prompt_version") != report.engine.prompt_version
            ):
                raise ValueError("career coach report engine mismatch")
            return StoredCareerCoachReport(
                id=row["id"],
                user_id=row["user_id"],
                request_id=UUID(str(row["request_id"])),
                report=report,
                created_at=row["created_at"],
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise AssistantDataIntegrityError() from exc
