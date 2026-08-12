begin;

create schema if not exists app;

revoke all on schema app from public;

do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on schema app from anon';
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all on schema app from authenticated';
  end if;
end
$block$;

create or replace function app.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  new.updated_at = now();
  return new;
end
$function$;

revoke all on function app.set_updated_at() from public;

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

commit;
