import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
import pytest

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
BASE_SQL = tuple(
    f"{number:02d}_{name}.sql"
    for number, name in (
        (0, "bootstrap"),
        (1, "user_accounts"),
        (2, "profiles"),
        (3, "saved_jobs"),
        (4, "plans"),
        (5, "schedule_items"),
        (6, "ai_results"),
    )
)
USER_A = UUID("a0000000-0000-0000-0000-000000000001")
USER_B = UUID("b0000000-0000-0000-0000-000000000001")
SCHEDULE_LOW = UUID("10000000-0000-0000-0000-000000000001")
SCHEDULE_HIGH = UUID("10000000-0000-0000-0000-000000000002")
SCHEDULE_LATER = UUID("10000000-0000-0000-0000-000000000003")
SCHEDULE_LAST = UUID("10000000-0000-0000-0000-000000000004")
SCHEDULE_BEFORE = UUID("10000000-0000-0000-0000-000000000005")
SCHEDULE_AFTER = UUID("10000000-0000-0000-0000-000000000006")

LEGACY_NOTIFICATIONS_SQL = """
begin;
create table app.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references app.user_accounts (id) on delete cascade,
  plan_id uuid,
  schedule_item_id uuid,
  type text not null,
  dedupe_key text not null,
  available_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb,
  claim_token uuid,
  claimed_until timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint notifications_user_id_id_unique unique (user_id, id),
  constraint notifications_user_dedupe_key_unique unique (user_id, dedupe_key),
  constraint notifications_plan_owner_fkey foreign key (user_id, plan_id)
    references app.plans (user_id, id) on delete restrict,
  constraint notifications_schedule_item_owner_fkey foreign key (user_id, schedule_item_id)
    references app.schedule_items (user_id, id) on delete restrict,
  constraint notifications_type_check check (
    type in ('daily_tasks', 'plan_ended', 'interview_reminder', 'check_in')
  ),
  constraint notifications_dedupe_key_not_blank_check check (btrim(dedupe_key) <> ''),
  constraint notifications_payload_object_check check (jsonb_typeof(payload) = 'object'),
  constraint notifications_claim_pair_check check (
    (claim_token is null and claimed_until is null)
    or (claim_token is not null and claimed_until is not null)
  ),
  constraint notifications_read_time_check check (read_at is null or read_at >= created_at),
  constraint notifications_reference_shape_check check (
    (type <> 'plan_ended' or plan_id is not null)
    and (type <> 'interview_reminder' or schedule_item_id is not null)
  )
);
create index notifications_unread_idx on app.notifications (user_id, available_at)
  where read_at is null;
create index notifications_due_claim_idx on app.notifications (available_at, claimed_until)
  where read_at is null;
create index notifications_plan_idx on app.notifications (user_id, plan_id)
  where plan_id is not null;
create index notifications_schedule_item_idx on app.notifications (user_id, schedule_item_id)
  where schedule_item_id is not null;
create trigger notifications_set_updated_at before update on app.notifications
  for each row execute function app.set_updated_at();
commit;
"""


def _sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _runtime_grants_for_disposable_test() -> str:
    source = _sql("09_runtime_grants.sql")
    shared_role_mutations = (
        "grant app_runtime to app_api;",
        "alter role app_api set statement_timeout = '15s';",
        "alter role app_api set idle_in_transaction_session_timeout = '15s';",
    )
    for statement in shared_role_mutations:
        if source.lower().count(statement.lower()) != 1:
            raise AssertionError(f"expected one shared-role mutation in sql/09: {statement}")
        source = source.replace(statement, "-- shared role mutation omitted in disposable test")
    return source


def test_disposable_runtime_grants_do_not_mutate_shared_role_state() -> None:
    production = _sql("09_runtime_grants.sql")
    disposable = _runtime_grants_for_disposable_test()

    assert "grant app_runtime to app_api;" in production.lower()
    assert "alter role app_api set statement_timeout" in production.lower()
    assert "alter role app_api set idle_in_transaction_session_timeout" in production.lower()
    assert "grant app_runtime to app_api;" not in disposable.lower()
    assert "alter role app_api set statement_timeout" not in disposable.lower()
    assert "alter role app_api set idle_in_transaction_session_timeout" not in disposable.lower()
    assert "on function app.sync_daily_task_notifications(uuid)" in disposable.lower()
    assert "enable row level security" in disposable.lower()


def _database_url() -> str:
    database_url = os.getenv("PLAN_SQL_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set PLAN_SQL_TEST_DATABASE_URL to opt in to PostgreSQL SQL tests")
    return database_url


def _assert_safe(connection: psycopg.Connection[tuple[object, ...]]) -> None:
    database_name = connection.execute("select current_database()").fetchone()[0]
    if not str(database_name).startswith("ai_job_coach_test_"):
        pytest.fail(
            "refusing to mutate PostgreSQL database whose name does not begin "
            "with ai_job_coach_test_"
        )


def _role_exists(connection: psycopg.Connection[tuple[object, ...]], role: str) -> bool:
    return connection.execute(
        "select exists (select 1 from pg_roles where rolname = %s)", (role,)
    ).fetchone()[0]


def _shared_role_state(
    connection: psycopg.Connection[tuple[object, ...]],
) -> dict[str, list[tuple[object, ...]]]:
    return {
        "roles": connection.execute(
            """
            select rolname, rolconfig
            from pg_catalog.pg_roles
            where rolname in ('app_runtime', 'app_api')
            order by rolname
            """
        ).fetchall(),
        "membership": connection.execute(
            """
            select parent.rolname, member.rolname, pg_catalog.to_jsonb(membership)
            from pg_catalog.pg_auth_members membership
            join pg_catalog.pg_roles parent on parent.oid = membership.roleid
            join pg_catalog.pg_roles member on member.oid = membership.member
            where parent.rolname = 'app_runtime' and member.rolname = 'app_api'
            """
        ).fetchall(),
    }


def _ensure_optional_client_roles(
    connection: psycopg.Connection[tuple[object, ...]],
    existed: dict[str, bool],
) -> None:
    for role in ("anon", "authenticated"):
        if not existed[role]:
            connection.execute(f'create role "{role}" nologin')


def _cleanup_test_roles(
    connection: psycopg.Connection[tuple[object, ...]],
    existed: dict[str, bool],
    expected_shared_state: dict[str, list[tuple[object, ...]]],
) -> None:
    connection.rollback()
    connection.execute("drop schema if exists app cascade")
    if not existed.get("app_api", True) and _role_exists(connection, "app_api"):
        connection.execute("drop role app_api")
    if not existed.get("app_runtime", True) and _role_exists(connection, "app_runtime"):
        connection.execute("drop role app_runtime")
    for role in ("anon", "authenticated"):
        if not existed.get(role, True) and _role_exists(connection, role):
            connection.execute(f'drop role "{role}"')
    assert _shared_role_state(connection) == expected_shared_state


def test_cleanup_test_roles_rolls_back_before_cleanup_sql() -> None:
    class EmptyRows:
        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    class FakeConnection:
        def __init__(self) -> None:
            self.events: list[str] = []

        def rollback(self) -> None:
            self.events.append("rollback")

        def execute(self, query: str, params: tuple[object, ...] | None = None) -> EmptyRows:
            assert self.events and self.events[0] == "rollback"
            self.events.append("execute")
            return EmptyRows()

    connection = FakeConnection()
    _cleanup_test_roles(
        connection,  # type: ignore[arg-type]
        {
            "app_api": True,
            "app_runtime": True,
            "anon": True,
            "authenticated": True,
        },
        {"roles": [], "membership": []},
    )

    assert connection.events == ["rollback", "execute", "execute", "execute"]


def _bootstrap(connection: psycopg.Connection[tuple[object, ...]]) -> None:
    connection.execute("drop schema if exists app cascade")
    for name in BASE_SQL:
        connection.execute(_sql(name))
    connection.execute(_sql("07_notifications.sql"))


def _bootstrap_legacy(connection: psycopg.Connection[tuple[object, ...]]) -> None:
    connection.execute("drop schema if exists app cascade")
    for name in BASE_SQL:
        connection.execute(_sql(name))
    connection.execute(LEGACY_NOTIFICATIONS_SQL)


def _notification_catalog(
    connection: psycopg.Connection[tuple[object, ...]],
) -> dict[str, list[tuple[object, ...]]]:
    return {
        "columns": connection.execute(
            """
            select a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
              a.attnotnull, pg_catalog.pg_get_expr(d.adbin, d.adrelid)
            from pg_catalog.pg_attribute a
            left join pg_catalog.pg_attrdef d
              on d.adrelid = a.attrelid and d.adnum = a.attnum
            where a.attrelid = 'app.notifications'::regclass
              and a.attnum > 0 and not a.attisdropped
            order by a.attname
            """
        ).fetchall(),
        "constraints": connection.execute(
            """
            select conname, pg_catalog.pg_get_constraintdef(oid)
            from pg_catalog.pg_constraint
            where conrelid = 'app.notifications'::regclass
            order by conname
            """
        ).fetchall(),
        "indexes": connection.execute(
            """
            select indexname, indexdef
            from pg_catalog.pg_indexes
            where schemaname = 'app' and tablename = 'notifications'
            order by indexname
            """
        ).fetchall(),
        "triggers": connection.execute(
            """
            select c.relname, t.tgname, pg_catalog.pg_get_triggerdef(t.oid)
            from pg_catalog.pg_trigger t
            join pg_catalog.pg_class c on c.oid = t.tgrelid
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'app'
              and c.relname in ('plans', 'schedule_items', 'notifications')
              and not t.tgisinternal
              and t.tgname like '%notification%'
            order by c.relname, t.tgname
            """
        ).fetchall(),
        "functions": connection.execute(
            """
            select p.proname, pg_catalog.pg_get_functiondef(p.oid)
            from pg_catalog.pg_proc p
            join pg_catalog.pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'app'
              and p.proname in (
                'produce_plan_notification',
                'preserve_notification_deleted_reference',
                'produce_schedule_insert_notifications',
                'produce_schedule_update_notifications',
                'produce_schedule_delete_notifications',
                'sync_daily_task_notifications'
              )
            order by p.proname
            """
        ).fetchall(),
        "function_acls": connection.execute(
            """
            select p.proname,
              case when acl.grantee = 0 then 'PUBLIC'
                else pg_catalog.pg_get_userbyid(acl.grantee)
              end as grantee,
              acl.privilege_type
            from pg_catalog.pg_proc p
            join pg_catalog.pg_namespace n on n.oid = p.pronamespace
            cross join lateral pg_catalog.aclexplode(
              coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))
            ) acl
            where n.nspname = 'app'
              and p.proname in (
                'preserve_notification_deleted_reference',
                'produce_plan_notification',
                'produce_schedule_insert_notifications',
                'produce_schedule_update_notifications',
                'produce_schedule_delete_notifications',
                'sync_daily_task_notifications'
              )
            order by p.proname, grantee, acl.privilege_type
            """
        ).fetchall(),
        "table_security": connection.execute(
            """
            select c.relrowsecurity, c.relforcerowsecurity
            from pg_catalog.pg_class c
            where c.oid = 'app.notifications'::regclass
            """
        ).fetchall(),
        "policies": connection.execute(
            """
            select policyname, roles, cmd, qual, with_check
            from pg_catalog.pg_policies
            where schemaname = 'app' and tablename = 'notifications'
            order by policyname
            """
        ).fetchall(),
    }


def _insert_user(
    connection: psycopg.Connection[tuple[object, ...]], user_id: UUID, login: str
) -> None:
    connection.execute(
        """
        insert into app.user_accounts (id, login_id, user_name, password_hash)
        values (%s, %s, %s, 'hash')
        """,
        (user_id, login, login),
    )


def _insert_plan(
    connection: psycopg.Connection[tuple[object, ...]],
    user_id: UUID,
    title: str,
    request_id: str,
    *,
    active: bool = True,
) -> UUID:
    return connection.execute(
        """
        insert into app.plans (
          user_id, title, starts_on, ends_on, total_task_count, status,
          source_request_id, activated_at
        ) values (
          %s, %s, current_date, current_date + 14, %s, %s, %s,
          case when %s then now() else null end
        )
        returning id
        """,
        (user_id, title, 1 if active else 0, "active" if active else "draft", request_id, active),
    ).fetchone()[0]


def _insert_schedule(
    connection: psycopg.Connection[tuple[object, ...]],
    user_id: UUID,
    plan_id: UUID,
    title: str,
    day_offset: int,
    *,
    status: str = "pending",
) -> UUID:
    return connection.execute(
        """
        insert into app.schedule_items (
          user_id, plan_id, kind, title, status, scheduled_at
        ) values (
          %s, %s, 'task', %s, %s,
          (
            timezone('Asia/Seoul', now())::date + %s + time '12:00'
          ) at time zone 'Asia/Seoul'
        )
        returning id
        """,
        (user_id, plan_id, title, status, day_offset),
    ).fetchone()[0]


def test_notification_producers_sync_and_guards() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        try:
            _bootstrap(connection)
            _insert_user(connection, USER_A, "notify_user_a")
            _insert_user(connection, USER_B, "notify_user_b")
            plan_a = _insert_plan(connection, USER_A, "Plan A", "plan-a")
            plan_b = _insert_plan(connection, USER_B, "Plan B", "plan-b")
            draft_b = _insert_plan(
                connection, USER_B, "Inactive plan", "inactive-plan", active=False
            )

            activation = connection.execute(
                """
                select payload from app.notifications
                where user_id = %s and type = 'roadmap_changed'
                order by created_at limit 1
                """,
                (USER_A,),
            ).fetchone()[0]
            assert activation["change_kind"] == "activation"

            _insert_schedule(connection, USER_B, draft_b, "Inactive schedule", 0)
            assert (
                connection.execute(
                    """
                    select count(*) from app.notifications
                    where user_id = %s and payload ->> 'plan_id' = %s
                    """,
                    (USER_B, str(draft_b)),
                ).fetchone()[0]
                == 0
            )

            before = connection.execute(
                "select count(*) from app.notifications where user_id = %s", (USER_A,)
            ).fetchone()[0]
            connection.execute(
                "update app.plans set updated_at = updated_at where id = %s", (plan_a,)
            )
            assert (
                connection.execute(
                    "select count(*) from app.notifications where user_id = %s", (USER_A,)
                ).fetchone()[0]
                == before
            )
            connection.execute(
                "update app.plans set title = 'Plan A changed' where id = %s", (plan_a,)
            )
            assert (
                connection.execute(
                    """
                select payload ->> 'change_kind' from app.notifications
                where user_id = %s and type = 'roadmap_changed'
                order by created_at desc limit 1
                """,
                    (USER_A,),
                ).fetchone()[0]
                == "update"
            )

            connection.execute(
                """
                insert into app.schedule_items (user_id, plan_id, kind, title, scheduled_at)
                select %s, %s, 'task', title,
                  (timezone('Asia/Seoul', now())::date + time '12:00') at time zone 'Asia/Seoul'
                from (values ('Bulk one'), ('Bulk two')) as rows(title)
                """,
                (USER_A, plan_a),
            )
            bulk_payload = connection.execute(
                """
                select payload from app.notifications
                where user_id = %s and payload ->> 'change_kind' = 'insert'
                order by created_at desc limit 1
                """,
                (USER_A,),
            ).fetchone()[0]
            assert bulk_payload["affected_count"] == 2
            assert bulk_payload["before"] is None
            assert bulk_payload["after"] is None

            schedule_a = _insert_schedule(connection, USER_A, plan_a, "Today", 0)
            update_events = connection.execute(
                """
                select count(*) from app.notifications
                where user_id = %s and payload ->> 'change_kind' = 'update'
                """,
                (USER_A,),
            ).fetchone()[0]
            connection.execute(
                "update app.schedule_items set updated_at = updated_at where id = %s", (schedule_a,)
            )
            assert (
                connection.execute(
                    """
                    select count(*) from app.notifications
                    where user_id = %s and payload ->> 'change_kind' = 'update'
                    """,
                    (USER_A,),
                ).fetchone()[0]
                == update_events
            )
            connection.execute(
                "update app.schedule_items set status = 'in_progress' where id = %s", (schedule_a,)
            )
            last_day = _insert_schedule(connection, USER_A, plan_a, "Last day", 6)
            _insert_schedule(connection, USER_A, plan_a, "Outside", 7)
            _insert_schedule(connection, USER_A, plan_a, "Closed", 1, status="cancelled")
            schedule_b = _insert_schedule(connection, USER_B, plan_b, "Other user", 0)

            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            summaries = connection.execute(
                """
                select dedupe_key, payload from app.notifications
                where user_id = %s and type = 'daily_tasks' and invalidated_at is null
                order by dedupe_key
                """,
                (USER_A,),
            ).fetchall()
            assert len(summaries) == 2
            assert all(row[0].startswith(f"daily_tasks:{plan_a}:") for row in summaries)
            assert all(
                entry["id"] != str(schedule_b) for row in summaries for entry in row[1]["schedules"]
            )

            today_key = next(
                row[0]
                for row in summaries
                if row[1]["date"]
                == str(
                    connection.execute("select timezone('Asia/Seoul', now())::date").fetchone()[0]
                )
            )
            connection.execute(
                """
                update app.notifications set is_read = true, read_at = now()
                where user_id = %s and dedupe_key = %s
                """,
                (USER_A, today_key),
            )
            read_at = connection.execute(
                "select read_at from app.notifications where user_id = %s and dedupe_key = %s",
                (USER_A, today_key),
            ).fetchone()[0]
            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            assert connection.execute(
                "select is_read, read_at from app.notifications where user_id = %s and dedupe_key = %s",
                (USER_A, today_key),
            ).fetchone() == (True, read_at)

            connection.execute(
                "update app.schedule_items set title = 'Today changed' where id = %s", (schedule_a,)
            )
            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            assert connection.execute(
                """
                select is_read, read_at, invalidated_at from app.notifications
                where user_id = %s and dedupe_key = %s
                """,
                (USER_A, today_key),
            ).fetchone() == (False, None, None)

            connection.execute(
                """
                update app.notifications
                set is_read = true, read_at = now(), invalidated_at = now()
                where user_id = %s and dedupe_key = %s
                """,
                (USER_A, today_key),
            )
            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            assert connection.execute(
                """
                select is_read, read_at, invalidated_at from app.notifications
                where user_id = %s and dedupe_key = %s
                """,
                (USER_A, today_key),
            ).fetchone() == (False, None, None)

            connection.execute("delete from app.schedule_items where id = %s", (schedule_a,))
            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            assert (
                connection.execute(
                    """
                select invalidated_at is not null from app.notifications
                where user_id = %s and dedupe_key = %s
                """,
                    (USER_A, today_key),
                ).fetchone()[0]
                is False
            )  # Other open rows remain in today's summary.

            last_day_key = next(
                row[0]
                for row in summaries
                if row[1]["date"]
                != str(
                    connection.execute("select timezone('Asia/Seoul', now())::date").fetchone()[0]
                )
            )
            connection.execute("delete from app.schedule_items where id = %s", (last_day,))
            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            assert (
                connection.execute(
                    """
                select invalidated_at is not null from app.notifications
                where user_id = %s and dedupe_key = %s
                """,
                    (USER_A, last_day_key),
                ).fetchone()[0]
                is True
            )

            with pytest.raises(psycopg.errors.CheckViolation):
                connection.execute(
                    """
                    update app.notifications set is_read = true, read_at = null
                    where user_id = %s and dedupe_key = %s
                    """,
                    (USER_A, today_key),
                )

            connection.execute(
                """
                alter table app.notifications add constraint notifications_test_reject_changes
                check (type <> 'roadmap_changed') not valid
                """
            )
            with pytest.raises(psycopg.errors.CheckViolation):
                connection.execute(
                    """
                    insert into app.schedule_items (user_id, plan_id, kind, title)
                    values (%s, %s, 'task', 'must roll back')
                    """,
                    (USER_A, plan_a),
                )
            assert (
                connection.execute(
                    "select count(*) from app.schedule_items where title = 'must roll back'"
                ).fetchone()[0]
                == 0
            )
            connection.execute(
                "alter table app.notifications drop constraint notifications_test_reject_changes"
            )

            # Deleted schedule IDs are payload-only; the still-live plan FK is retained.
            connection.execute("delete from app.notifications where user_id = %s", (USER_A,))
            connection.execute("delete from app.schedule_items where user_id = %s", (USER_A,))
            deleted_event = connection.execute(
                """
                select plan_id, payload from app.notifications
                where user_id = %s and payload ->> 'change_kind' = 'delete' limit 1
                """,
                (USER_A,),
            ).fetchone()
            assert deleted_event[0] == plan_a
            assert deleted_event[1]["plan_id"] == str(plan_a)
            connection.execute(
                """
                update app.plans
                set status = 'superseded', ended_at = now(), final_progress = 50
                where id = %s
                """,
                (plan_a,),
            )
            plan_end = connection.execute(
                """
                select plan_id, payload from app.notifications
                where user_id = %s and type = 'plan_ended' limit 1
                """,
                (USER_A,),
            ).fetchone()
            assert plan_end[0] == plan_a
            assert plan_end[1]["ended_status"] == "superseded"
            connection.execute("delete from app.plans where id = %s", (plan_a,))
            assert (
                connection.execute(
                    """
                select plan_id from app.notifications
                where user_id = %s and type = 'plan_ended' limit 1
                """,
                    (USER_A,),
                ).fetchone()[0]
                is None
            )

            direct_delete = _insert_plan(connection, USER_A, "Direct delete", "direct-delete")
            connection.execute("delete from app.plans where id = %s", (direct_delete,))
            direct_event = connection.execute(
                """
                select plan_id, payload from app.notifications
                where user_id = %s and type = 'plan_ended'
                  and payload ->> 'ended_status' = 'deleted'
                """,
                (USER_A,),
            ).fetchone()
            assert direct_event[0] is None
            assert direct_event[1]["ended_status"] == "deleted"
        finally:
            connection.execute("drop schema if exists app cascade")


def test_direct_plan_delete_with_existing_activation_notification_succeeds() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        try:
            _bootstrap(connection)
            _insert_user(connection, USER_A, "direct_delete_a")
            plan_id = _insert_plan(connection, USER_A, "Direct", "direct-delete-existing")

            assert (
                connection.execute(
                    """
                select plan_id from app.notifications
                where user_id = %s and type = 'roadmap_changed'
                """,
                    (USER_A,),
                ).fetchone()[0]
                == plan_id
            )

            connection.execute("delete from app.plans where id = %s", (plan_id,))

            rows = connection.execute(
                """
                select type, plan_id, payload from app.notifications
                where user_id = %s order by created_at, type
                """,
                (USER_A,),
            ).fetchall()
            assert len(rows) == 2
            assert all(row[1] is None for row in rows)
            assert rows[-1][0] == "plan_ended"
            assert rows[-1][2]["plan_id"] == str(plan_id)
            assert rows[-1][2]["ended_status"] == "deleted"
        finally:
            connection.execute("drop schema if exists app cascade")


@pytest.mark.parametrize("exit_status", ("draft", "rejected"))
def test_nonterminal_active_plan_exit_uses_zero_final_progress(exit_status: str) -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        try:
            _bootstrap(connection)
            _insert_user(connection, USER_A, "nonterminal_exit_a")
            plan_id = _insert_plan(connection, USER_A, "Return to draft", "nonterminal-exit")
            connection.execute("delete from app.notifications where user_id = %s", (USER_A,))

            connection.execute(
                """
                update app.plans
                set status = %s, activated_at = null
                where id = %s
                """,
                (exit_status, plan_id),
            )

            plan_end = connection.execute(
                """
                select plan_id, payload from app.notifications
                where user_id = %s and type = 'plan_ended'
                """,
                (USER_A,),
            ).fetchone()
            assert plan_end[0] == plan_id
            assert plan_end[1]["version"] == "plan_ended.v1"
            assert plan_end[1]["ended_status"] == exit_status
            assert type(plan_end[1]["final_progress"]) is int
            assert plan_end[1]["final_progress"] == 0
        finally:
            connection.execute("drop schema if exists app cascade")


def test_single_schedule_insert_update_delete_payloads_have_typed_summaries() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        try:
            _bootstrap(connection)
            _insert_user(connection, USER_A, "schedule_summary_a")
            plan_id = _insert_plan(connection, USER_A, "Summary", "schedule-summary")
            connection.execute("delete from app.notifications")

            schedule_id = _insert_schedule(connection, USER_A, plan_id, "Original", 0)
            inserted = connection.execute(
                """
                select payload from app.notifications
                where payload ->> 'change_kind' = 'insert'
                """
            ).fetchone()[0]
            assert inserted["affected_count"] == 1
            assert inserted["before"] is None
            assert inserted["after"] == {
                "id": str(schedule_id),
                "title": "Original",
                "scheduled_at": inserted["after"]["scheduled_at"],
                "status": "pending",
            }
            assert inserted["after"]["scheduled_at"].endswith("Z")

            connection.execute(
                """
                update app.schedule_items
                set title = 'Updated', status = 'in_progress',
                  scheduled_at = scheduled_at + interval '1 hour'
                where id = %s
                """,
                (schedule_id,),
            )
            updated = connection.execute(
                """
                select payload from app.notifications
                where payload ->> 'change_kind' = 'update'
                order by created_at desc limit 1
                """
            ).fetchone()[0]
            assert updated["affected_count"] == 1
            assert updated["before"]["id"] == str(schedule_id)
            assert updated["before"]["title"] == "Original"
            assert updated["before"]["status"] == "pending"
            assert updated["after"]["id"] == str(schedule_id)
            assert updated["after"]["title"] == "Updated"
            assert updated["after"]["status"] == "in_progress"
            assert updated["before"]["scheduled_at"] != updated["after"]["scheduled_at"]

            connection.execute("delete from app.schedule_items where id = %s", (schedule_id,))
            deleted = connection.execute(
                """
                select payload from app.notifications
                where payload ->> 'change_kind' = 'delete'
                order by created_at desc limit 1
                """
            ).fetchone()[0]
            assert deleted["affected_count"] == 1
            assert deleted["before"]["id"] == str(schedule_id)
            assert deleted["before"]["title"] == "Updated"
            assert deleted["before"]["status"] == "in_progress"
            assert deleted["after"] is None
        finally:
            connection.execute("drop schema if exists app cascade")


def test_repository_account_cleanup_sequence_succeeds_without_new_blocking_fk() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        role_existed = {role: _role_exists(connection, role) for role in ("app_runtime", "app_api")}
        shared_role_state = _shared_role_state(connection)
        try:
            _bootstrap(connection)
            connection.execute(_sql("08_cross_table_constraints.sql"))
            connection.execute(_runtime_grants_for_disposable_test())
            connection.execute(_sql("12_daily_goal_achievements.sql"))
            _insert_user(connection, USER_A, "account_cleanup_a")
            proposal_id = connection.execute(
                """
                insert into app.ai_results (
                  user_id, kind, decision_status, title, content,
                  model_name, prompt_version, request_id
                ) values (
                  %s, 'job_plan_proposal', 'pending', 'Proposal', '{}'::jsonb,
                  'test-model', 'v1', 'cleanup-proposal'
                ) returning id
                """,
                (USER_A,),
            ).fetchone()[0]
            plan_id = _insert_plan(connection, USER_A, "Cleanup", "cleanup-plan")
            connection.execute(
                "update app.plans set proposal_result_id = %s where id = %s",
                (proposal_id, plan_id),
            )
            _insert_schedule(connection, USER_A, plan_id, "Cleanup schedule", 0)
            connection.execute("insert into app.profiles (user_id) values (%s)", (USER_A,))
            connection.execute(
                """
                insert into app.daily_goal_achievements (
                  user_id, plan_id, plan_day, goal_date
                ) values (%s, %s, 1, current_date)
                """,
                (USER_A, plan_id),
            )

            with connection.transaction():
                assert (
                    connection.execute(
                        "select id from app.user_accounts where id = %s for update", (USER_A,)
                    ).fetchone()[0]
                    == USER_A
                )
                connection.execute("delete from app.notifications where user_id = %s", (USER_A,))
                connection.execute("delete from app.schedule_items where user_id = %s", (USER_A,))
                connection.execute(
                    "delete from app.daily_goal_achievements where user_id = %s", (USER_A,)
                )
                connection.execute("delete from app.profiles where user_id = %s", (USER_A,))
                before_cleanup_update = connection.execute(
                    "select count(*) from app.notifications where user_id = %s", (USER_A,)
                ).fetchone()[0]
                connection.execute(
                    """
                    update app.plans
                    set proposal_result_id = null, previous_plan_id = null
                    where user_id = %s
                    """,
                    (USER_A,),
                )
                assert (
                    connection.execute(
                        "select count(*) from app.notifications where user_id = %s", (USER_A,)
                    ).fetchone()[0]
                    == before_cleanup_update
                )
                connection.execute("delete from app.ai_results where user_id = %s", (USER_A,))
                connection.execute("delete from app.plans where user_id = %s", (USER_A,))
                assert (
                    connection.execute(
                        "delete from app.user_accounts where id = %s returning id", (USER_A,)
                    ).fetchone()[0]
                    == USER_A
                )

            assert (
                connection.execute(
                    "select count(*) from app.user_accounts where id = %s", (USER_A,)
                ).fetchone()[0]
                == 0
            )
            assert (
                connection.execute(
                    "select count(*) from app.daily_goal_achievements where user_id = %s", (USER_A,)
                ).fetchone()[0]
                == 0
            )
            assert (
                connection.execute(
                    "select count(*) from app.profiles where user_id = %s", (USER_A,)
                ).fetchone()[0]
                == 0
            )
        finally:
            _cleanup_test_roles(connection, role_existed, shared_role_state)


def test_statement_triggers_cover_zero_rows_multiple_groups_and_active_group_movement() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        try:
            _bootstrap(connection)
            _insert_user(connection, USER_A, "statement_group_a")
            _insert_user(connection, USER_B, "statement_group_b")
            active_a = _insert_plan(connection, USER_A, "Active A", "active-a")
            active_b = _insert_plan(connection, USER_B, "Active B", "active-b")
            draft_b = _insert_plan(connection, USER_B, "Draft B", "draft-b", active=False)
            connection.execute("delete from app.notifications")

            connection.execute(
                """
                insert into app.schedule_items (user_id, plan_id, kind, title)
                values
                  (%s, %s, 'task', 'Group A'),
                  (%s, %s, 'task', 'Group B')
                """,
                (USER_A, active_a, USER_B, active_b),
            )
            grouped = connection.execute(
                """
                select user_id, plan_id, payload ->> 'change_kind'
                from app.notifications order by user_id
                """
            ).fetchall()
            assert grouped == [(USER_A, active_a, "insert"), (USER_B, active_b, "insert")]

            before_zero = connection.execute("select count(*) from app.notifications").fetchone()[0]
            connection.execute("update app.schedule_items set title = title where false")
            assert (
                connection.execute("select count(*) from app.notifications").fetchone()[0]
                == before_zero
            )

            moving_id = _insert_schedule(connection, USER_B, draft_b, "Moving", 0)
            connection.execute("delete from app.notifications")
            connection.execute(
                "update app.schedule_items set plan_id = %s where id = %s",
                (active_b, moving_id),
            )
            into_group = connection.execute(
                "select plan_id, payload from app.notifications"
            ).fetchone()
            assert into_group[0] == active_b
            assert into_group[1]["change_kind"] == "update"
            assert into_group[1]["before"]["id"] == str(moving_id)
            assert into_group[1]["after"]["id"] == str(moving_id)
            connection.execute("delete from app.notifications")
            connection.execute(
                "update app.schedule_items set plan_id = %s where id = %s",
                (draft_b, moving_id),
            )
            out_group = connection.execute(
                "select plan_id, payload from app.notifications"
            ).fetchone()
            assert out_group[0] == active_b
            assert out_group[1]["change_kind"] == "update"
            assert out_group[1]["before"]["id"] == str(moving_id)
            assert out_group[1]["after"]["id"] == str(moving_id)
        finally:
            connection.execute("drop schema if exists app cascade")


def test_kst_window_exact_boundaries_order_and_utc_payload() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        try:
            _bootstrap(connection)
            connection.execute("set timezone = 'America/Los_Angeles'")
            _insert_user(connection, USER_A, "kst_boundary_a")
            plan_id = _insert_plan(connection, USER_A, "KST", "kst-boundary")
            kst_today = connection.execute("select timezone('Asia/Seoul', now())::date").fetchone()[
                0
            ]
            rows = connection.execute(
                """
                insert into app.schedule_items (
                  id, user_id, plan_id, kind, title, scheduled_at
                ) values
                  (%s, %s, %s, 'task', 'Tie high',
                    (%s::date + time '00:00:00') at time zone 'Asia/Seoul'),
                  (%s, %s, %s, 'task', 'Tie low',
                    (%s::date + time '00:00:00') at time zone 'Asia/Seoul'),
                  (%s, %s, %s, 'task', 'Today later',
                    (%s::date + time '00:00:01') at time zone 'Asia/Seoul'),
                  (%s, %s, %s, 'task', 'Last instant',
                    (%s::date + 6 + time '23:59:59.999999') at time zone 'Asia/Seoul'),
                  (%s, %s, %s, 'task', 'Before window',
                    (%s::date - 1 + time '23:59:59.999999') at time zone 'Asia/Seoul'),
                  (%s, %s, %s, 'task', 'After window',
                    (%s::date + 7 + time '00:00:00') at time zone 'Asia/Seoul')
                returning id, title
                """,
                (
                    SCHEDULE_HIGH,
                    USER_A,
                    plan_id,
                    kst_today,
                    SCHEDULE_LOW,
                    USER_A,
                    plan_id,
                    kst_today,
                    SCHEDULE_LATER,
                    USER_A,
                    plan_id,
                    kst_today,
                    SCHEDULE_LAST,
                    USER_A,
                    plan_id,
                    kst_today,
                    SCHEDULE_BEFORE,
                    USER_A,
                    plan_id,
                    kst_today,
                    SCHEDULE_AFTER,
                    USER_A,
                    plan_id,
                    kst_today,
                ),
            ).fetchall()
            ids = {title: row_id for row_id, title in rows}
            connection.execute("select * from app.sync_daily_task_notifications(%s)", (USER_A,))
            payloads = connection.execute(
                """
                select payload from app.notifications
                where user_id = %s and type = 'daily_tasks'
                order by payload ->> 'date'
                """,
                (USER_A,),
            ).fetchall()
            assert [payload[0]["date"] for payload in payloads] == [
                kst_today.isoformat(),
                (kst_today + timedelta(days=6)).isoformat(),
            ]
            today = payloads[0][0]
            assert today["count"] == 3
            assert [item["id"] for item in today["schedules"]] == [
                str(ids["Tie low"]),
                str(ids["Tie high"]),
                str(ids["Today later"]),
            ]
            expected_utc = datetime.combine(
                kst_today, time(0, 0), ZoneInfo("Asia/Seoul")
            ).astimezone(UTC)
            assert today["schedules"][0]["scheduled_at"] == (
                expected_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            )
            last = payloads[1][0]
            expected_last_utc = datetime.combine(
                kst_today + timedelta(days=6),
                time(23, 59, 59, 999999),
                ZoneInfo("Asia/Seoul"),
            ).astimezone(UTC)
            assert last["count"] == 1
            assert last["schedules"][0]["id"] == str(ids["Last instant"])
            assert last["schedules"][0]["scheduled_at"] == (
                expected_last_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            )
            serialized_ids = {item["id"] for row in payloads for item in row[0]["schedules"]}
            assert str(ids["Before window"]) not in serialized_ids
            assert str(ids["After window"]) not in serialized_ids
        finally:
            connection.execute("drop schema if exists app cascade")


def test_legacy_migration_backfill_catalog_parity_privileges_and_rerun_timestamp() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_safe(connection)
        role_existed = {
            role: _role_exists(connection, role)
            for role in ("app_runtime", "app_api", "anon", "authenticated")
        }
        shared_role_state = _shared_role_state(connection)
        try:
            _ensure_optional_client_roles(connection, role_existed)
            _bootstrap(connection)
            connection.execute(_runtime_grants_for_disposable_test())
            fresh_catalog = _notification_catalog(connection)
            runtime_execute = {
                name
                for name, grantee, privilege in fresh_catalog["function_acls"]
                if grantee == "app_runtime" and privilege == "EXECUTE"
            }
            assert runtime_execute == {"sync_daily_task_notifications"}
            for blocked_role in ("PUBLIC", "anon", "authenticated"):
                assert not {
                    name
                    for name, grantee, privilege in fresh_catalog["function_acls"]
                    if grantee == blocked_role and privilege == "EXECUTE"
                }

            _bootstrap_legacy(connection)
            connection.execute(
                """
                create function app.sync_daily_task_notifications(uuid)
                returns table (upserted_count bigint, invalidated_count bigint)
                language sql security invoker set search_path = ''
                as 'select 0::bigint, 0::bigint'
                """
            )
            connection.execute(
                "revoke all on function app.sync_daily_task_notifications(uuid) from public"
            )
            for role in ("anon", "authenticated"):
                connection.execute(
                    f'revoke all on function app.sync_daily_task_notifications(uuid) from "{role}"'
                )
            connection.execute(_runtime_grants_for_disposable_test())
            connection.execute("drop function app.sync_daily_task_notifications(uuid)")
            _insert_user(connection, USER_A, "legacy_migrate_a")
            connection.execute(
                """
                insert into app.notifications (
                  user_id, type, dedupe_key, read_at, created_at, updated_at
                ) values
                  (%s, 'check_in', 'legacy-unread', null,
                    '2025-01-01T00:00:00Z', '2025-01-02T00:00:00Z'),
                  (%s, 'check_in', 'legacy-read', '2025-01-03T00:00:00Z',
                    '2025-01-01T00:00:00Z', '2025-01-02T00:00:00Z')
                """,
                (USER_A, USER_A),
            )
            connection.execute(_sql("22_notifications_login_roadmap.sql"))
            assert connection.execute(
                "select dedupe_key, is_read from app.notifications order by dedupe_key"
            ).fetchall() == [("legacy-read", True), ("legacy-unread", False)]
            first_updated = connection.execute(
                "select dedupe_key, updated_at from app.notifications order by dedupe_key"
            ).fetchall()
            migrated_catalog = _notification_catalog(connection)
            assert migrated_catalog == fresh_catalog
            assert {
                name
                for name, grantee, privilege in migrated_catalog["function_acls"]
                if grantee == "app_runtime" and privilege == "EXECUTE"
            } == {"sync_daily_task_notifications"}
            for blocked_role in ("PUBLIC", "anon", "authenticated"):
                assert not {
                    name
                    for name, grantee, privilege in migrated_catalog["function_acls"]
                    if grantee == blocked_role and privilege == "EXECUTE"
                }

            connection.execute(_sql("22_notifications_login_roadmap.sql"))
            assert (
                connection.execute(
                    "select dedupe_key, updated_at from app.notifications order by dedupe_key"
                ).fetchall()
                == first_updated
            )
            public_execute = connection.execute(
                """
                select count(*)
                from pg_catalog.pg_proc p
                join pg_catalog.pg_namespace n on n.oid = p.pronamespace
                cross join lateral pg_catalog.aclexplode(
                  coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))
                ) acl
                where n.nspname = 'app'
                  and p.proname like '%notification%'
                  and acl.grantee = 0
                  and acl.privilege_type = 'EXECUTE'
                """
            ).fetchone()[0]
            assert public_execute == 0
        finally:
            _cleanup_test_roles(connection, role_existed, shared_role_state)


def test_concurrent_login_sync_keeps_one_row_per_plan_day_and_migration_reruns() -> None:
    database_url = _database_url()
    with psycopg.connect(database_url, autocommit=True) as setup:
        _assert_safe(setup)
        try:
            _bootstrap(setup)
            _insert_user(setup, USER_A, "concurrent_a")
            plan_id = _insert_plan(setup, USER_A, "Concurrent", "concurrent-plan")
            _insert_schedule(setup, USER_A, plan_id, "Concurrent task", 0)
            setup.execute(_sql("22_notifications_login_roadmap.sql"))
            setup.execute(_sql("22_notifications_login_roadmap.sql"))

            def sync() -> None:
                with psycopg.connect(database_url, autocommit=True) as connection:
                    connection.execute(
                        "select * from app.sync_daily_task_notifications(%s)", (USER_A,)
                    ).fetchone()

            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(lambda _: sync(), range(2)))

            assert (
                setup.execute(
                    """
                select count(*) from app.notifications
                where user_id = %s and type = 'daily_tasks'
                """,
                    (USER_A,),
                ).fetchone()[0]
                == 1
            )
        finally:
            setup.execute("drop schema if exists app cascade")
