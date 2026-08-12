begin;

create table if not exists app.ai_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
    references app.user_accounts (id) on delete cascade,
  saved_job_id uuid,
  applied_plan_id uuid,
  kind text not null,
  decision_status text not null default 'not_applicable',
  title text not null,
  content jsonb not null,
  model_name text not null,
  prompt_version text not null,
  request_id text not null,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint ai_results_user_id_id_unique
    unique (user_id, id),
  constraint ai_results_user_request_unique
    unique (user_id, request_id),
  constraint ai_results_saved_job_fkey
    foreign key (saved_job_id)
    references app.saved_jobs (id)
    on delete restrict,
  constraint ai_results_applied_plan_owner_fkey
    foreign key (user_id, applied_plan_id)
    references app.plans (user_id, id)
    on delete restrict,
  constraint ai_results_kind_check
    check (
      kind in (
        'profile_assessment',
        'job_plan_proposal',
        'profile_plan_proposal',
        'document_review',
        'expected_questions',
        'interview_report',
        'career_coach_report'
      )
    ),
  constraint ai_results_decision_status_check
    check (
      decision_status in (
        'not_applicable',
        'pending',
        'accepted',
        'rejected',
        'applied',
        'failed'
      )
    ),
  constraint ai_results_title_not_blank_check
    check (btrim(title) <> ''),
  constraint ai_results_model_name_not_blank_check
    check (btrim(model_name) <> ''),
  constraint ai_results_prompt_version_not_blank_check
    check (btrim(prompt_version) <> ''),
  constraint ai_results_request_id_not_blank_check
    check (btrim(request_id) <> ''),
  constraint ai_results_content_object_check
    check (jsonb_typeof(content) = 'object'),
  constraint ai_results_profile_assessment_content_check
    check (
      kind <> 'profile_assessment'
      or (
        content ?& array[
          'schema_version',
          'profile_snapshot',
          'assessment',
          'draft_revision',
          'snapshot_hash'
        ]
        and jsonb_typeof(content -> 'schema_version') = 'string'
        and jsonb_typeof(content -> 'profile_snapshot') = 'object'
        and jsonb_typeof(content -> 'assessment') = 'object'
        and jsonb_typeof(content -> 'draft_revision') = 'number'
        and jsonb_typeof(content -> 'snapshot_hash') = 'string'
        and btrim(content ->> 'snapshot_hash') <> ''
      )
    ),
  constraint ai_results_profile_plan_proposal_content_check
    check (
      kind <> 'profile_plan_proposal'
      or (
        content ?& array[
          'schema_version',
          'profile_hash',
          'assessment_result_id',
          'generated_on',
          'starts_on',
          'ends_on',
          'title',
          'summary',
          'proposal_hash',
          'profile_snapshot',
          'engine',
          'milestones',
          'days',
          'duration_days',
          'total_task_count'
        ]
        and jsonb_typeof(content -> 'schema_version') = 'string'
        and jsonb_typeof(content -> 'profile_hash') = 'string'
        and jsonb_typeof(content -> 'assessment_result_id') = 'string'
        and jsonb_typeof(content -> 'generated_on') = 'string'
        and jsonb_typeof(content -> 'starts_on') = 'string'
        and jsonb_typeof(content -> 'ends_on') = 'string'
        and jsonb_typeof(content -> 'title') = 'string'
        and jsonb_typeof(content -> 'summary') = 'string'
        and jsonb_typeof(content -> 'proposal_hash') = 'string'
        and jsonb_typeof(content -> 'profile_snapshot') = 'object'
        and jsonb_typeof(content -> 'engine') = 'object'
        and jsonb_typeof(content -> 'milestones') = 'array'
        and jsonb_typeof(content -> 'days') = 'array'
        and jsonb_typeof(content -> 'duration_days') = 'number'
        and jsonb_typeof(content -> 'total_task_count') = 'number'
        and btrim(content ->> 'schema_version') <> ''
        and btrim(content ->> 'profile_hash') <> ''
        and btrim(content ->> 'assessment_result_id') <> ''
        and btrim(content ->> 'generated_on') <> ''
        and btrim(content ->> 'starts_on') <> ''
        and btrim(content ->> 'ends_on') <> ''
        and btrim(content ->> 'title') <> ''
        and btrim(content ->> 'summary') <> ''
        and btrim(content ->> 'proposal_hash') <> ''
      )
    ),
  constraint ai_results_career_coach_report_row_check
    check (
      kind <> 'career_coach_report'
      or coalesce(
        decision_status = 'not_applicable'
        and saved_job_id is null
        and applied_plan_id is null
        and decided_at is null,
        false
      )
    ),
  constraint ai_results_career_coach_report_content_check
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
    ),
  constraint ai_results_proposal_decision_check
    check (
      (
        kind = 'job_plan_proposal'
        and decision_status in ('pending', 'accepted', 'rejected', 'applied', 'failed')
        and saved_job_id is not null
      )
      or
      (
        kind = 'profile_plan_proposal'
        and decision_status in ('pending', 'applied', 'rejected')
      )
      or
      (
        kind not in ('job_plan_proposal', 'profile_plan_proposal')
        and decision_status = 'not_applicable'
        and applied_plan_id is null
      )
    ),
  constraint ai_results_profile_plan_proposal_saved_job_check
    check (
      kind <> 'profile_plan_proposal'
      or (
        saved_job_id is null
        and (
          not (content ? 'saved_job_snapshot')
          or content -> 'saved_job_snapshot' = 'null'::jsonb
        )
      )
      or (
        saved_job_id is not null
        and jsonb_typeof(content -> 'saved_job_snapshot') = 'object'
        and content -> 'saved_job_snapshot' ->> 'id' = saved_job_id::text
      )
    ),
  constraint ai_results_decision_time_check
    check (
      (
        decision_status in ('not_applicable', 'pending')
        and decided_at is null
      )
      or
      (
        decision_status in ('accepted', 'rejected', 'applied', 'failed')
        and decided_at is not null
      )
    ),
  constraint ai_results_applied_plan_check
    check (
      (decision_status = 'applied' and applied_plan_id is not null)
      or
      (decision_status <> 'applied' and applied_plan_id is null)
    )
);

create index if not exists ai_results_saved_job_idx
  on app.ai_results (saved_job_id, user_id)
  where saved_job_id is not null;

create index if not exists ai_results_applied_plan_idx
  on app.ai_results (user_id, applied_plan_id)
  where applied_plan_id is not null;

create index if not exists ai_results_pending_proposal_idx
  on app.ai_results (user_id, created_at)
  where kind = 'job_plan_proposal'
    and decision_status = 'pending';

create unique index if not exists ai_results_one_pending_profile_plan_proposal_uidx
  on app.ai_results (user_id)
  where kind = 'profile_plan_proposal'
    and decision_status = 'pending';

create unique index if not exists ai_results_one_career_coach_report_per_session_uidx
  on app.ai_results (user_id, (content ->> 'session_id'))
  where kind = 'career_coach_report';

create or replace function app.guard_career_coach_report_update()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  if old.kind = 'career_coach_report' or new.kind = 'career_coach_report' then
    raise exception 'career_coach_report rows are immutable';
  end if;

  return new;
end
$function$;

revoke all on function app.guard_career_coach_report_update() from public;

drop trigger if exists career_coach_report_update_guard on app.ai_results;

create trigger career_coach_report_update_guard
  before update on app.ai_results
  for each row execute function app.guard_career_coach_report_update();

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'profile_plan_proposal_lifecycle_guard'
      and tgrelid = 'app.ai_results'::regclass
  ) then
    execute 'create trigger profile_plan_proposal_lifecycle_guard
      before insert or update on app.ai_results
      for each row execute function app.guard_profile_plan_proposal_lifecycle()';
  end if;

  if not exists (
    select 1
    from pg_trigger
    where tgname = 'ai_results_set_updated_at'
      and tgrelid = 'app.ai_results'::regclass
  ) then
    execute 'create trigger ai_results_set_updated_at
      before update on app.ai_results
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
