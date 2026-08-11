import os
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.test_assistant_repository import report

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
BOOTSTRAP_AND_MIGRATIONS = (
    "00_bootstrap.sql",
    "01_user_accounts.sql",
    "02_profiles.sql",
    "03_saved_jobs.sql",
    "04_plans.sql",
    "05_schedule_items.sql",
    "06_ai_results.sql",
    "07_notifications.sql",
    "08_cross_table_constraints.sql",
    "09_runtime_grants.sql",
    "12_daily_goal_achievements.sql",
    "13_user_accounts_user_name.sql",
    "14_notices.sql",
    "15_daily_goal_exp_20.sql",
    "16_global_saved_jobs.sql",
    "17_profile_plan_saved_job.sql",
    "18_user_account_management.sql",
    "19_career_coach_report.sql",
    "20_private_app_schema.sql",
    "21_career_coach_report_forbidden_key_check.sql",
    "22_notifications_login_roadmap.sql",
)
USER_A = UUID("a0000000-0000-0000-0000-000000000001")
USER_B = UUID("b0000000-0000-0000-0000-000000000001")


def _sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _insert_report(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    user_id: UUID,
    request_id: str,
    content: dict[str, object],
) -> None:
    connection.execute(
        """
        insert into app.ai_results (
          user_id, saved_job_id, applied_plan_id, kind, decision_status,
          title, content, model_name, prompt_version, request_id, decided_at
        ) values (
          %s, null, null, 'career_coach_report', 'not_applicable',
          'Career coach report', %s, 'gemini-3.6-flash',
          'career-coach-report-v1', %s, null
        )
        """,
        (user_id, Jsonb(content), request_id),
    )


def test_career_coach_report_migration_and_database_guards() -> None:
    database_url = os.getenv("PLAN_SQL_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set PLAN_SQL_TEST_DATABASE_URL to opt in to PostgreSQL SQL tests")

    with psycopg.connect(database_url, autocommit=True) as connection:
        database_name = connection.execute("select current_database()").fetchone()[0]
        if not str(database_name).startswith("ai_job_coach_test_"):
            pytest.fail(
                "refusing to mutate PostgreSQL database whose name does not begin "
                "with ai_job_coach_test_"
            )

        try:
            connection.execute("drop schema if exists app cascade")
            for name in BOOTSTRAP_AND_MIGRATIONS:
                connection.execute(_sql(name))

            connection.execute(_sql("21_career_coach_report_forbidden_key_check.sql"))
            connection.execute(
                """
                insert into app.user_accounts (id, login_id, user_name, password_hash)
                values
                  (%s, 'coach_user_a', 'A', 'hash'),
                  (%s, 'coach_user_b', 'B', 'hash')
                """,
                (USER_A, USER_B),
            )
            valid = report().model_dump(mode="json")
            _insert_report(
                connection,
                user_id=USER_A,
                request_id="coach-report-a",
                content=valid,
            )

            connection.execute(_sql("19_career_coach_report.sql"))

            with pytest.raises(psycopg.errors.UniqueViolation):
                _insert_report(
                    connection,
                    user_id=USER_A,
                    request_id="coach-report-a-duplicate-session",
                    content=valid,
                )

            _insert_report(
                connection,
                user_id=USER_B,
                request_id="coach-report-b",
                content=valid,
            )

            invalid = {**valid, "status": "draft"}
            with pytest.raises(psycopg.errors.CheckViolation):
                _insert_report(
                    connection,
                    user_id=USER_A,
                    request_id="coach-report-invalid-status",
                    content=invalid,
                )

            forbidden_cases = []
            root_forbidden = deepcopy(valid)
            root_forbidden["session_id"] = "00000000-0000-0000-0000-000000000101"
            root_forbidden["transcript"] = None
            forbidden_cases.append(root_forbidden)

            nested_forbidden = deepcopy(valid)
            nested_forbidden["session_id"] = "00000000-0000-0000-0000-000000000102"
            nested_forbidden["assessment_snapshot"]["summary"] = {"transcript": None}
            forbidden_cases.append(nested_forbidden)

            array_forbidden = deepcopy(valid)
            array_forbidden["session_id"] = "00000000-0000-0000-0000-000000000103"
            array_forbidden["assessment_snapshot"]["summary"] = {"items": [{"transcript": None}]}
            forbidden_cases.append(array_forbidden)

            for index, forbidden in enumerate(forbidden_cases):
                with pytest.raises(psycopg.errors.CheckViolation):
                    _insert_report(
                        connection,
                        user_id=USER_A,
                        request_id=f"coach-report-forbidden-{index}",
                        content=forbidden,
                    )

            with pytest.raises(psycopg.errors.RaiseException):
                connection.execute(
                    """
                    update app.ai_results
                    set title = title
                    where user_id = %s and request_id = 'coach-report-a'
                    """,
                    (USER_A,),
                )

            connection.execute(
                """
                delete from app.ai_results
                where user_id = %s and request_id = 'coach-report-a'
                """,
                (USER_A,),
            )
        finally:
            connection.execute("drop schema if exists app cascade")
