begin;

do $block$
begin
  if current_user = 'app_api' then
    raise exception '11_profile_plan_proposals.sql must be run by a migration role, not app_api';
  end if;

  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'app'
      and table_name = 'profiles'
      and column_name = 'assessment_result_id'
  ) then
    raise exception 'profiles.assessment_result_id is absent; apply 10_profile_assessment_link.sql first';
  end if;

  if exists (
    select 1
    from app.ai_results
    where kind = 'profile_plan_proposal'
      and saved_job_id is not null
  ) then
    raise exception 'existing profile_plan_proposal rows must have saved_job_id null';
  end if;

  if exists (
    select 1
    from app.ai_results
    where kind = 'profile_plan_proposal'
      and decision_status not in ('pending', 'applied', 'rejected')
  ) then
    raise exception 'existing profile_plan_proposal rows have an invalid decision_status';
  end if;

  if exists (
    select 1
    from app.ai_results
    where kind = 'profile_plan_proposal'
      and not coalesce(
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
        and btrim(content ->> 'proposal_hash') <> '',
        false
      )
  ) then
    raise exception 'existing profile_plan_proposal rows have invalid content';
  end if;

  if exists (
    select 1
    from app.plans p
    where p.proposal_result_id is not null
      and not exists (
        select 1
        from app.ai_results ar
        where ar.id = p.proposal_result_id
          and ar.user_id = p.user_id
      )
  ) then
    raise exception 'plans.proposal_result_id references a missing or different-user ai_results row';
  end if;

  if exists (
    select 1
    from app.plans
    where proposal_result_id is not null
    group by proposal_result_id
    having count(*) > 1
  ) then
    raise exception 'duplicate proposal_result_id values in app.plans';
  end if;

  if exists (
    select 1
    from app.ai_results
    where kind = 'profile_plan_proposal'
      and decision_status = 'pending'
    group by user_id
    having count(*) > 1
  ) then
    raise exception 'duplicate pending profile_plan_proposal rows in app.ai_results';
  end if;
end
$block$;

alter table app.ai_results
  drop constraint if exists ai_results_kind_check,
  drop constraint if exists ai_results_proposal_decision_check,
  drop constraint if exists ai_results_profile_plan_proposal_content_check;

alter table app.ai_results
  add constraint ai_results_kind_check
    check (
      kind in (
        'profile_assessment',
        'job_plan_proposal',
        'profile_plan_proposal',
        'document_review',
        'expected_questions',
        'interview_report'
      )
    ),
  add constraint ai_results_proposal_decision_check
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
        and saved_job_id is null
      )
      or
      (
        kind not in ('job_plan_proposal', 'profile_plan_proposal')
        and decision_status = 'not_applicable'
        and applied_plan_id is null
      )
    );

alter table app.ai_results
  add constraint ai_results_profile_plan_proposal_content_check
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
    ) not valid;

alter table app.ai_results
  validate constraint ai_results_profile_plan_proposal_content_check;

drop index if exists app.ai_results_one_pending_profile_plan_proposal_uidx;

drop index if exists app.plans_proposal_result_uidx;

drop index if exists app.plans_proposal_result_idx;

create unique index ai_results_one_pending_profile_plan_proposal_uidx
  on app.ai_results (user_id)
  where kind = 'profile_plan_proposal'
    and decision_status = 'pending';

create unique index plans_proposal_result_uidx
  on app.plans (proposal_result_id)
  where proposal_result_id is not null;

create or replace function app.guard_profile_plan_proposal_lifecycle()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  if tg_op = 'INSERT' then
    if new.kind = 'profile_plan_proposal' and new.decision_status <> 'pending' then
      raise exception 'profile_plan_proposal must be inserted as pending';
    end if;
    return new;
  end if;

  if (old.kind = 'profile_plan_proposal' or new.kind = 'profile_plan_proposal')
     and old.kind is distinct from new.kind then
    raise exception 'profile_plan_proposal kind is immutable';
  end if;

  if old.kind = 'profile_plan_proposal' then
    if old.id is distinct from new.id
       or old.user_id is distinct from new.user_id
       or old.saved_job_id is distinct from new.saved_job_id
       or old.title is distinct from new.title
       or old.content is distinct from new.content
       or old.model_name is distinct from new.model_name
       or old.prompt_version is distinct from new.prompt_version
       or old.request_id is distinct from new.request_id
       or old.created_at is distinct from new.created_at then
      raise exception 'profile_plan_proposal immutable content changed';
    end if;

    if old.decision_status is distinct from new.decision_status
       and not (
         old.decision_status = 'pending'
         and new.decision_status in ('applied', 'rejected')
       ) then
      raise exception 'profile_plan_proposal lifecycle transition is invalid';
    end if;

    if old.decision_status in ('applied', 'rejected')
       and (
         old.applied_plan_id is distinct from new.applied_plan_id
         or old.decided_at is distinct from new.decided_at
       ) then
      raise exception 'profile_plan_proposal terminal decision is immutable';
    end if;
  end if;

  return new;
end
$function$;

revoke all on function app.guard_profile_plan_proposal_lifecycle() from public;

drop trigger if exists profile_plan_proposal_lifecycle_guard on app.ai_results;

create trigger profile_plan_proposal_lifecycle_guard
  before insert or update on app.ai_results
  for each row execute function app.guard_profile_plan_proposal_lifecycle();

commit;
