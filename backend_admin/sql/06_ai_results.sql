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
  constraint ai_results_saved_job_owner_fkey
    foreign key (user_id, saved_job_id)
    references app.saved_jobs (user_id, id)
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
        'document_review',
        'expected_questions',
        'interview_report'
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
  constraint ai_results_proposal_decision_check
    check (
      (
        kind = 'job_plan_proposal'
        and decision_status in ('pending', 'accepted', 'rejected', 'applied', 'failed')
        and saved_job_id is not null
      )
      or
      (
        kind <> 'job_plan_proposal'
        and decision_status = 'not_applicable'
        and applied_plan_id is null
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
  on app.ai_results (user_id, saved_job_id)
  where saved_job_id is not null;

create index if not exists ai_results_applied_plan_idx
  on app.ai_results (user_id, applied_plan_id)
  where applied_plan_id is not null;

create index if not exists ai_results_pending_proposal_idx
  on app.ai_results (user_id, created_at)
  where kind = 'job_plan_proposal'
    and decision_status = 'pending';

do $block$
begin
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
