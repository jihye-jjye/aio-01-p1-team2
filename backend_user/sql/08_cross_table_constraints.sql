begin;

create unique index if not exists ai_results_user_id_id_unique
  on app.ai_results (user_id, id);

do $block$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'plans_proposal_result_owner_fkey'
      and conrelid = 'app.plans'::regclass
  ) then
    alter table app.plans
      add constraint plans_proposal_result_owner_fkey
      foreign key (user_id, proposal_result_id)
      references app.ai_results (user_id, id)
      on delete restrict
      deferrable initially immediate;
  end if;
end
$block$;

do $block$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'profiles_assessment_result_owner_fkey'
      and conrelid = 'app.profiles'::regclass
  ) then
    alter table app.profiles
      add constraint profiles_assessment_result_owner_fkey
      foreign key (user_id, assessment_result_id)
      references app.ai_results (user_id, id)
      on delete restrict
      deferrable initially immediate;
  end if;
end
$block$;

create index if not exists profiles_assessment_result_idx
  on app.profiles (user_id, assessment_result_id)
  where assessment_result_id is not null;

commit;
