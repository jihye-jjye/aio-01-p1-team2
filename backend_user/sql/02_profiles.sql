begin;

create table if not exists app.profiles (
  user_id uuid primary key
    references app.user_accounts (id) on delete cascade,
  target_role text,
  skills text[] not null default '{}',
  experience_summary text,
  target_date date,
  target_company text,
  preferred_environment text,
  assistant_style text not null default 'friendly',
  daily_notification_time time without time zone,
  assessment_score smallint,
  assessment_level text,
  assessment_summary jsonb,
  assessed_at timestamptz,
  assessment_version text,
  assessment_result_id uuid,
  onboarding_completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint profiles_assistant_style_check
    check (assistant_style in ('friendly', 'direct')),
  constraint profiles_assessment_score_check
    check (assessment_score between 0 and 100),
  constraint profiles_assessment_level_check
    check (
      assessment_level is null
      or assessment_level in ('beginner', 'intermediate', 'advanced')
    ),
  constraint profiles_assessment_pair_check
    check (
      (
        assessment_score is null
        and assessment_level is null
        and assessment_summary is null
        and assessed_at is null
        and assessment_version is null
        and assessment_result_id is null
      )
      or
      (
        assessment_score is not null
        and assessment_level is not null
        and assessment_summary is not null
        and assessed_at is not null
        and assessment_version is not null
        and assessment_result_id is not null
      )
    ),
  constraint profiles_assessment_summary_object_check
    check (
      assessment_summary is null
      or jsonb_typeof(assessment_summary) = 'object'
    ),
  constraint profiles_skills_count_check
    check (cardinality(skills) between 0 and 20),
  constraint profiles_onboarding_complete_check
    check (
      onboarding_completed_at is null
      or (
        target_role is not null
        and btrim(target_role) <> ''
        and cardinality(skills) > 0
        and experience_summary is not null
        and btrim(experience_summary) <> ''
        and target_date is not null
        and preferred_environment is not null
        and btrim(preferred_environment) <> ''
        and daily_notification_time is not null
        and assessment_score is not null
        and assessment_level is not null
        and assessment_summary is not null
        and assessed_at is not null
        and assessment_version is not null
        and btrim(assessment_version) <> ''
        and assessment_result_id is not null
      )
    )
);

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'profiles_set_updated_at'
      and tgrelid = 'app.profiles'::regclass
  ) then
    execute 'create trigger profiles_set_updated_at
      before update on app.profiles
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
