begin;

do $block$
begin
  if current_user = 'app_api' then
    raise exception '21_career_coach_report_forbidden_key_check.sql must be run by a migration role, not app_api';
  end if;
end
$block$;

alter table app.ai_results
  drop constraint if exists ai_results_career_coach_report_content_check;

alter table app.ai_results
  add constraint ai_results_career_coach_report_content_check
    check (
      kind <> 'career_coach_report'
      or coalesce(
        content ?& array[
          'schema_version',
          'status',
          'session_id',
          'session_revision',
          'started_at_kst',
          'finalized_at_kst',
          'user_turn_count',
          'profile_snapshot',
          'assessment_snapshot',
          'profile_hash',
          'assessment_result_id',
          'assistant_style',
          'summary',
          'strengths',
          'improvements',
          'priority_actions',
          'evidence',
          'tool_snapshots',
          'excluded_tool_call_count',
          'excluded_tool_calls_hash',
          'engine',
          'redaction_version',
          'source_session_hash',
          'report_hash'
        ]
        and content - array[
          'schema_version',
          'status',
          'session_id',
          'session_revision',
          'started_at_kst',
          'finalized_at_kst',
          'user_turn_count',
          'profile_snapshot',
          'assessment_snapshot',
          'profile_hash',
          'assessment_result_id',
          'assistant_style',
          'summary',
          'strengths',
          'improvements',
          'priority_actions',
          'evidence',
          'tool_snapshots',
          'excluded_tool_call_count',
          'excluded_tool_calls_hash',
          'engine',
          'redaction_version',
          'source_session_hash',
          'report_hash'
        ]::text[] = '{}'::jsonb
        and jsonb_typeof(content -> 'schema_version') = 'string'
        and jsonb_typeof(content -> 'status') = 'string'
        and jsonb_typeof(content -> 'session_id') = 'string'
        and jsonb_typeof(content -> 'session_revision') = 'number'
        and jsonb_typeof(content -> 'started_at_kst') = 'string'
        and jsonb_typeof(content -> 'finalized_at_kst') = 'string'
        and jsonb_typeof(content -> 'user_turn_count') = 'number'
        and jsonb_typeof(content -> 'profile_snapshot') = 'object'
        and jsonb_typeof(content -> 'assessment_snapshot') = 'object'
        and jsonb_typeof(content -> 'profile_hash') = 'string'
        and jsonb_typeof(content -> 'assessment_result_id') = 'string'
        and jsonb_typeof(content -> 'assistant_style') = 'string'
        and jsonb_typeof(content -> 'summary') = 'string'
        and jsonb_typeof(content -> 'strengths') = 'array'
        and jsonb_typeof(content -> 'improvements') = 'array'
        and jsonb_typeof(content -> 'priority_actions') = 'array'
        and jsonb_typeof(content -> 'evidence') = 'array'
        and jsonb_typeof(content -> 'tool_snapshots') = 'array'
        and jsonb_typeof(content -> 'excluded_tool_call_count') = 'number'
        and jsonb_typeof(content -> 'engine') = 'object'
        and jsonb_typeof(content -> 'redaction_version') = 'string'
        and jsonb_typeof(content -> 'source_session_hash') = 'string'
        and jsonb_typeof(content -> 'report_hash') = 'string'
        and content ->> 'schema_version' = 'career-coach-report-v1'
        and content ->> 'status' = 'completed'
        and content ->> 'session_id' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        and content ->> 'assessment_result_id' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        and content ->> 'profile_hash' ~ '^[0-9a-f]{64}$'
        and content ->> 'source_session_hash' ~ '^[0-9a-f]{64}$'
        and content ->> 'report_hash' ~ '^[0-9a-f]{64}$'
        and (
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
        )
        and content ->> 'assistant_style' in ('friendly', 'direct')
        and btrim(content ->> 'started_at_kst') <> ''
        and btrim(content ->> 'finalized_at_kst') <> ''
        and btrim(content ->> 'summary') <> ''
        and btrim(content ->> 'redaction_version') <> ''
        and octet_length(content::text) <= 131072
        and not jsonb_path_exists(
          content,
          '$.** ? (@.type() == "object").keyvalue() ? (
            @.key == "transcript" ||
            @.key == "messages" ||
            @.key == "assistant_message" ||
            @.key == "raw_provider_response" ||
            @.key == "raw_response" ||
            @.key == "raw_prompt" ||
            @.key == "prompt" ||
            @.key == "posting_text" ||
            @.key == "extracted_data" ||
            @.key == "tool_results"
          )',
          '{}'::jsonb,
          true
        ),
        false
      )
    ) not valid;

alter table app.ai_results
  validate constraint ai_results_career_coach_report_content_check;

commit;
