import re
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
BOOTSTRAP = SQL_DIR / "06_ai_results.sql"
MIGRATION = SQL_DIR / "19_career_coach_report.sql"
PRIVATE_SCHEMA_MIGRATION = SQL_DIR / "20_private_app_schema.sql"
REPORT_CHECK_REPAIR_MIGRATION = SQL_DIR / "21_career_coach_report_forbidden_key_check.sql"

REPORT_KEYS = {
    "schema_version",
    "status",
    "session_id",
    "session_revision",
    "started_at_kst",
    "finalized_at_kst",
    "user_turn_count",
    "profile_snapshot",
    "assessment_snapshot",
    "profile_hash",
    "assessment_result_id",
    "assistant_style",
    "summary",
    "strengths",
    "improvements",
    "priority_actions",
    "evidence",
    "tool_snapshots",
    "excluded_tool_call_count",
    "excluded_tool_calls_hash",
    "engine",
    "redaction_version",
    "source_session_hash",
    "report_hash",
}

STRING_HASH_KEYS = {
    "profile_hash",
    "source_session_hash",
    "report_hash",
}

FORBIDDEN_KEYS = {
    "transcript",
    "messages",
    "assistant_message",
    "raw_provider_response",
    "raw_response",
    "raw_prompt",
    "prompt",
    "posting_text",
    "extracted_data",
    "tool_results",
}

EXISTING_KINDS = {
    "profile_assessment",
    "job_plan_proposal",
    "profile_plan_proposal",
    "document_review",
    "expected_questions",
    "interview_report",
}


def sql(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def report_constraint(source: str) -> str:
    match = re.search(
        r"constraint ai_results_career_coach_report_content_check\s+check\s*\((.*?)\n\s*\),?\n\s*constraint",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        match = re.search(
            r"add constraint ai_results_career_coach_report_content_check\s+check\s*\((.*?)\n\s*\)(?:\s+not valid)?;",
            source,
            flags=re.DOTALL,
        )
    assert match is not None
    return compact(match.group(1))


def test_bootstrap_and_migration_preserve_kinds_and_global_request_uniqueness() -> None:
    bootstrap = sql(BOOTSTRAP)
    migration = sql(MIGRATION)

    for source in (bootstrap, migration):
        assert "'career_coach_report'" in source
        for kind in EXISTING_KINDS:
            assert f"'{kind}'" in source

    assert "unique (user_id, request_id)" in compact(bootstrap)
    assert "drop constraint if exists ai_results_user_request_unique" not in migration
    assert "grant " not in bootstrap
    assert "grant " not in migration


def test_report_rows_have_fixed_non_decision_columns_in_both_paths() -> None:
    required = compact(
        """
        decision_status = 'not_applicable'
        and saved_job_id is null
        and applied_plan_id is null
        and decided_at is null
        """
    )

    for path in (BOOTSTRAP, MIGRATION):
        source = compact(sql(path))
        assert required in source
        assert "coalesce(" in source


def test_report_content_has_exact_top_level_keys_and_null_safe_type_checks() -> None:
    constraints = [
        report_constraint(sql(path))
        for path in (BOOTSTRAP, MIGRATION, REPORT_CHECK_REPAIR_MIGRATION)
    ]
    assert constraints[0] == constraints[1] == constraints[2]

    for path in (BOOTSTRAP, MIGRATION, REPORT_CHECK_REPAIR_MIGRATION):
        constraint = report_constraint(sql(path))

        required_match = re.search(
            r"content \?& array\[(.*?)\]\s+and content - array\[",
            constraint,
            flags=re.DOTALL,
        )
        assert required_match is not None
        assert set(re.findall(r"'([^']+)'", required_match.group(1))) == REPORT_KEYS

        allowed_match = re.search(
            r"content - array\[(.*?)\]::text\[\] = '\{\}'::jsonb",
            constraint,
            flags=re.DOTALL,
        )
        assert allowed_match is not None
        assert set(re.findall(r"'([^']+)'", allowed_match.group(1))) == REPORT_KEYS

        for key in REPORT_KEYS:
            assert f"'{key}'" in constraint
            if key != "excluded_tool_calls_hash":
                assert f"jsonb_typeof(content -> '{key}')" in constraint

        assert "content - array[" in constraint
        assert "]::text[] = '{}'::jsonb" in constraint
        assert "coalesce(" in constraint
        assert ", false" in constraint


def test_report_content_enforces_versions_values_identifiers_hashes_and_size() -> None:
    for path in (BOOTSTRAP, MIGRATION):
        constraint = report_constraint(sql(path))

        assert "content ->> 'schema_version' = 'career-coach-report-v1'" in constraint
        assert "content ->> 'status' = 'completed'" in constraint
        assert "content ->> 'assistant_style' in ('friendly', 'direct')" in constraint
        assert "content ->> 'session_id' ~" in constraint
        assert "content ->> 'assessment_result_id' ~" in constraint
        for key in STRING_HASH_KEYS:
            assert f"content ->> '{key}' ~ '^[0-9a-f]{{64}}$'" in constraint
        assert "octet_length(content::text) <= 131072" in constraint


def test_excluded_tool_calls_hash_is_null_only_when_no_calls_were_excluded() -> None:
    for path in (BOOTSTRAP, MIGRATION):
        constraint = report_constraint(sql(path))

        assert (
            compact(
                """
            (
              content -> 'excluded_tool_call_count' = '0'::jsonb
              and jsonb_typeof(content -> 'excluded_tool_calls_hash') = 'null'
            )
            or
            (
              content -> 'excluded_tool_call_count' > '0'::jsonb
              and jsonb_typeof(content -> 'excluded_tool_calls_hash') = 'string'
              and content ->> 'excluded_tool_calls_hash' ~ '^[0-9a-f]{64}$'
            )
            """
            )
            in constraint
        )


def test_report_content_recursively_rejects_sensitive_keys() -> None:
    for path in (BOOTSTRAP, MIGRATION, REPORT_CHECK_REPAIR_MIGRATION):
        constraint = report_constraint(sql(path))

        assert "jsonb_path_exists(" in constraint
        assert '$.** ? (@.type() == "object").keyvalue()' in constraint
        assert "$.**.keyvalue()" not in constraint
        for key in FORBIDDEN_KEYS:
            assert f'@.key == "{key}"' in constraint


def test_report_check_repair_migration_is_reentrant_and_changes_only_content_check() -> None:
    source = compact(sql(REPORT_CHECK_REPAIR_MIGRATION))

    assert "must be run by a migration role, not app_api" in source
    assert "drop constraint if exists ai_results_career_coach_report_content_check" in source
    assert "add constraint ai_results_career_coach_report_content_check" in source
    assert "validate constraint ai_results_career_coach_report_content_check" in source
    assert "ai_results_career_coach_report_row_check" not in source
    assert "drop index" not in source
    assert "drop trigger" not in source
    assert "grant " not in source


def test_report_session_uniqueness_index_is_exact_and_recreated_by_migration() -> None:
    exact_index = compact(
        """
        create unique index ai_results_one_career_coach_report_per_session_uidx
          on app.ai_results (user_id, (content ->> 'session_id'))
          where kind = 'career_coach_report'
        """
    )

    assert exact_index in compact(sql(BOOTSTRAP)).replace(
        "create unique index if not exists", "create unique index"
    )
    migration = compact(sql(MIGRATION))
    assert (
        "drop index if exists app.ai_results_one_career_coach_report_per_session_uidx" in migration
    )
    assert exact_index in migration


def test_migration_preflights_invalid_and_duplicate_existing_reports() -> None:
    migration = compact(sql(MIGRATION))

    assert "must be run by a migration role, not app_api" in migration
    assert "where kind = 'career_coach_report'" in migration
    assert "existing career_coach_report rows have invalid" in migration
    assert "group by user_id, (content ->> 'session_id') having count(*) > 1" in migration
    assert "duplicate career_coach_report session_id values" in migration
    assert "drop constraint if exists ai_results_career_coach_report_content_check" in migration
    assert "drop trigger if exists career_coach_report_update_guard on app.ai_results" in migration
    assert "create or replace function app.guard_career_coach_report_update()" in migration


def test_report_update_guard_is_security_invoker_null_search_path_and_update_only() -> None:
    for path in (BOOTSTRAP, MIGRATION):
        source = compact(sql(path))
        function_start = source.index(
            "create or replace function app.guard_career_coach_report_update()"
        )
        function_end = source.index("$function$;", function_start) + len("$function$;")
        function = source[function_start:function_end]

        assert "security invoker" in function
        assert "set search_path = ''" in function
        assert "old.kind = 'career_coach_report' or new.kind = 'career_coach_report'" in function
        assert "raise exception" in function
        assert "revoke all on function app.guard_career_coach_report_update() from public" in source
        assert (
            compact(
                """
            create trigger career_coach_report_update_guard
              before update on app.ai_results
              for each row execute function app.guard_career_coach_report_update()
            """
            )
            in source
        )
        trigger_start = source.index("create trigger career_coach_report_update_guard")
        trigger_end = source.index(";", trigger_start)
        trigger = source[trigger_start:trigger_end]
        assert "before insert or update" not in trigger
        assert "before delete" not in trigger


def test_private_app_schema_migration_removes_public_client_access_without_grants() -> None:
    source = compact(sql(PRIVATE_SCHEMA_MIGRATION))

    assert "must be run by a migration role, not app_api" in source
    assert "revoke all on schema app from public" in source
    assert "revoke all privileges on all tables in schema app from public" in source
    assert "revoke all privileges on all sequences in schema app from public" in source
    assert "revoke execute on all functions in schema app from public" in source
    for role in ("anon", "authenticated"):
        assert f"rolname = '{role}'" in source
        assert f"revoke all on schema app from {role}" in source
        assert f"revoke all privileges on all tables in schema app from {role}" in source
        assert f"revoke all privileges on all sequences in schema app from {role}" in source
        assert f"revoke execute on all functions in schema app from {role}" in source
    assert "alter default privileges for role postgres in schema app" in source
    assert "service_role" not in source
    assert "app_runtime" not in source
    assert "grant " not in source
