import re
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
FRESH = SQL_DIR / "07_notifications.sql"
MIGRATION = SQL_DIR / "22_notifications_login_roadmap.sql"


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def test_fresh_and_incremental_paths_expose_the_same_notification_contract() -> None:
    fresh = _compact(_sql(FRESH))
    migration = _compact(_sql(MIGRATION))
    for source in (fresh, migration):
        assert "invalidated_at timestamptz" in source
        assert "constraint notifications_read_state_check" in source
        assert "is_read = (read_at is not null)" in source
        assert "'roadmap_changed'" in source
        for notification_type in (
            "daily_tasks",
            "plan_ended",
            "interview_reminder",
            "check_in",
        ):
            assert f"'{notification_type}'" in source
    assert "is_read boolean not null default false" in fresh
    assert "add column if not exists is_read boolean" in migration
    assert "alter column is_read set default false" in migration
    assert "alter column is_read set not null" in migration
    assert "notifications_user_dedupe_key_unique" in fresh
    assert "claim_token uuid" in fresh
    assert "claimed_until timestamptz" in fresh
    assert "constraint notifications_read_time_check" in fresh
    assert "read_at is null or read_at >= created_at" in fresh
    assert "drop column" not in migration
    assert "drop constraint if exists notifications_read_time_check" not in migration


def test_incremental_migration_backfills_before_enforcing_read_state() -> None:
    source = _compact(_sql(MIGRATION))
    add_column = source.index("add column if not exists is_read boolean")
    backfill = source.index("set is_read = (read_at is not null)")
    enforce = source.index("alter column is_read set not null")
    assert add_column < backfill < enforce
    assert "drop constraint if exists notifications_read_state_check" in source
    assert "drop constraint if exists notifications_type_check" in source


def test_unread_and_claim_indexes_ignore_read_and_invalidated_rows() -> None:
    predicate = "where is_read = false and invalidated_at is null"
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "drop index if exists app.notifications_unread_idx" in source
        assert "drop index if exists app.notifications_due_claim_idx" in source
        assert source.count(predicate) >= 2
        assert "notifications_plan_idx" in source
        assert "notifications_schedule_item_idx" in source


def test_plan_producer_covers_activation_meaningful_change_and_exit() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "create or replace function app.produce_plan_notification()" in source
        assert "new.status = 'active'" in source
        assert "old.status is distinct from 'active'" in source
        assert "old.title is distinct from new.title" in source
        assert "'roadmap_changed'" in source
        assert "'plan_ended'" in source
        assert "'final_progress', coalesce(new.final_progress, 0)" in source
        assert "'ended_status', new.status" in source


def test_schedule_producers_are_separate_statement_triggers_with_transition_tables() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "for each statement" in source
        assert "referencing new table as inserted_rows" in source
        assert "referencing old table as updated_old_rows new table as updated_new_rows" in source
        assert "referencing old table as deleted_rows" in source
        assert "create or replace function app.produce_schedule_insert_notifications()" in source
        assert "create or replace function app.produce_schedule_update_notifications()" in source
        assert "create or replace function app.produce_schedule_delete_notifications()" in source
        assert "pg_catalog.to_jsonb(n) - 'updated_at'" in source
        assert "pg_catalog.to_jsonb(o) - 'updated_at'" in source
        assert "p.status = 'active'" in source
        assert "group by" in source
        assert "'change_kind', 'insert'" in source
        assert "'change_kind', 'update'" in source
        assert "'change_kind', 'delete'" in source


def test_login_sync_contract_is_kst_scoped_atomic_and_reopens_changed_rows() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert (
            "create or replace function app.sync_daily_task_notifications(p_user_id uuid)" in source
        )
        assert "timezone('asia/seoul', pg_catalog.now())::date" in source
        assert "interval '6 days'" in source
        assert "s.status in ('pending', 'in_progress')" in source
        assert "p.status = 'active'" in source
        assert "s.scheduled_at is not null" in source
        assert "daily_tasks:" in source
        assert "order by s.scheduled_at, s.id" in source
        assert "on conflict (user_id, dedupe_key) do update" in source
        assert "app.notifications.payload is distinct from excluded.payload" in source
        assert "app.notifications.invalidated_at is not null" in source
        assert "invalidated_at = null" in source
        assert "set invalidated_at = pg_catalog.now()" in source
        assert "n.user_id = p_user_id" in source


def test_trigger_functions_are_invoker_safe_and_not_directly_executable() -> None:
    function_names = (
        "preserve_notification_deleted_reference",
        "produce_plan_notification",
        "produce_schedule_insert_notifications",
        "produce_schedule_update_notifications",
        "produce_schedule_delete_notifications",
        "sync_daily_task_notifications",
    )
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert source.count("security invoker set search_path = ''") >= len(function_names)
        for name in function_names:
            signature = f"app.{name}(" + (
                "uuid)" if name == "sync_daily_task_notifications" else ")"
            )
            assert f"revoke all on function {signature} from public" in source
        assert "array['anon', 'authenticated']" in source
        assert "rolname = blocked_role" in source


def test_incremental_migration_replaces_objects_by_stable_name() -> None:
    source = _compact(_sql(MIGRATION))
    assert "add column if not exists" in source
    assert "create or replace function" in source
    assert source.count("drop trigger if exists") >= 4
    assert "create index if not exists" in source
    assert "grant execute on function app.sync_daily_task_notifications(uuid)" in source


def test_fresh_and_incremental_paths_share_exact_runtime_objects() -> None:
    fresh = _sql(FRESH)
    migration = _sql(MIGRATION)
    marker = "drop index if exists app.notifications_unread_idx;"
    migration_grant = (
        "do $block$\nbegin\n  if exists (select 1 from pg_roles where rolname = 'app_runtime')"
    )
    fresh_runtime = fresh[fresh.index(marker) : fresh.rindex("commit;")].strip()
    migration_runtime = migration[
        migration.index(marker) : migration.index(migration_grant)
    ].strip()
    assert migration_runtime == fresh_runtime


def test_delete_events_keep_deleted_identifiers_only_in_payload() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "if tg_op = 'delete'" in source
        assert "'change_kind', 'delete'" in source
        assert "'ended_status', 'deleted'" in source
        assert "type <> 'plan_ended' or plan_id is not null or payload ? 'plan_id'" in source
        delete_function = source[
            source.index(
                "create or replace function app.produce_schedule_delete_notifications()"
            ) : source.index("create or replace function app.sync_daily_task_notifications")
        ]
        assert "select s.user_id, s.plan_id, 'roadmap_changed'" in delete_function


def test_owned_notification_foreign_keys_null_only_the_deleted_entity_id() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "on delete set null (plan_id)" in source
        assert "on delete set null (schedule_item_id)" in source
        assert "create or replace function app.preserve_notification_deleted_reference()" in source
        assert "new.payload := pg_catalog.jsonb_set(" in source
        assert "'{plan_id}'" in source
        assert "'{schedule_item_id}'" in source
        assert "before update of plan_id, schedule_item_id on app.notifications" in source
    migration = _compact(_sql(MIGRATION))
    assert "drop constraint if exists notifications_plan_owner_fkey" in migration
    assert "drop constraint if exists notifications_schedule_item_owner_fkey" in migration


def test_plan_cleanup_source_reference_updates_are_not_roadmap_changes() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        plan_function = source[
            source.index(
                "create or replace function app.produce_plan_notification()"
            ) : source.index(
                "create or replace function app.produce_schedule_insert_notifications()"
            )
        ]
        assert "old.title is distinct from new.title" in plan_function
        assert "old.goal_snapshot is distinct from new.goal_snapshot" in plan_function
        assert "old.starts_on is distinct from new.starts_on" in plan_function
        assert "old.ends_on is distinct from new.ends_on" in plan_function
        assert "old.total_task_count is distinct from new.total_task_count" in plan_function
        assert "pg_catalog.to_jsonb(new) - 'updated_at'" not in plan_function
        assert "proposal_result_id is distinct from" not in plan_function
        assert "previous_plan_id is distinct from" not in plan_function


def test_change_and_plan_end_payloads_match_typed_api_contract() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "'version', 'roadmap_change.v1'" in source
        assert "'target', 'plan'" in source
        assert "'target', 'schedule'" in source
        assert "'change_kind', event_operation" in source
        assert "'affected_count', 1" in source
        assert "'affected_count', pg_catalog.count(*)" in source
        assert "'version', 'plan_ended.v1'" in source
        assert "'ended_status', new.status" in source
        assert "'ended_status', 'deleted'" in source
        assert "'final_progress', coalesce(new.final_progress, 0)" in source
        assert "'plan_event.v1'" not in source
        assert "'schedule_change.v1'" not in source


def test_nonterminal_active_exit_has_typed_zero_final_progress() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "'final_progress', coalesce(new.final_progress, 0)" in source


def test_migration_backfill_does_not_rewrite_consistent_rows_on_rerun() -> None:
    source = _compact(_sql(MIGRATION))
    assert "set is_read = (read_at is not null) where is_read is distinct from" in source
    assert "(read_at is not null)" in source


def test_daily_payload_timestamp_is_session_timezone_independent() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        assert "'count', pg_catalog.count(*)" in source
        assert "s.scheduled_at at time zone 'utc'" in source
        assert 'yyyy-mm-dd"t"hh24:mi:ss.us"z"' in source


def test_runtime_grant_follows_public_and_client_role_revocations() -> None:
    migration = _compact(_sql(MIGRATION))
    public_revoke = migration.index(
        "revoke all on function app.sync_daily_task_notifications(uuid) from public"
    )
    client_revoke = migration.index(
        "revoke all on function app.sync_daily_task_notifications(uuid) from %i"
    )
    runtime_grant = migration.index(
        "grant execute on function app.sync_daily_task_notifications(uuid) to app_runtime"
    )
    assert public_revoke < client_revoke < runtime_grant


def test_single_schedule_changes_have_directly_typed_before_after_summaries() -> None:
    for source in map(_compact, (_sql(FRESH), _sql(MIGRATION))):
        insert_function = source[
            source.index(
                "create or replace function app.produce_schedule_insert_notifications()"
            ) : source.index(
                "create or replace function app.produce_schedule_update_notifications()"
            )
        ]
        update_function = source[
            source.index(
                "create or replace function app.produce_schedule_update_notifications()"
            ) : source.index(
                "create or replace function app.produce_schedule_delete_notifications()"
            )
        ]
        delete_function = source[
            source.index(
                "create or replace function app.produce_schedule_delete_notifications()"
            ) : source.index("create or replace function app.sync_daily_task_notifications")
        ]

        assert "'before', null" in insert_function
        assert "'after', case when pg_catalog.count(*) = 1" in insert_function
        assert "'before', case when pg_catalog.count(*) = 1" in delete_function
        assert "'after', null" in delete_function
        assert "before_summary" in update_function
        assert "after_summary" in update_function
        assert "'before', g.before_summary" in update_function
        assert "'after', g.after_summary" in update_function
        for function in (insert_function, update_function, delete_function):
            assert "'id'" in function
            assert "'title'" in function
            assert "'scheduled_at'" in function
            assert "'status'" in function
            assert 'yyyy-mm-dd"t"hh24:mi:ss.us"z"' in function
