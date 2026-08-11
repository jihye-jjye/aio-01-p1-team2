begin;

alter table app.profiles
  add column if not exists assessment_result_id uuid;

-- Normalize legacy baseline rows before validating the new content contract.
-- New application writes use a canonical SHA-256 snapshot hash; legacy rows get
-- a stable 64-character migration fingerprint so they remain traceable.
with normalized as (
  select
    ar.id,
    jsonb_build_object(
      'schema_version', 'profile-assessment-v1',
      'profile_snapshot', case
        when p.user_id is null then '{}'::jsonb
        else jsonb_build_object(
          'target_role', p.target_role,
          'skills', to_jsonb(p.skills),
          'experience_summary', p.experience_summary,
          'target_date', to_jsonb(p.target_date),
          'target_company', p.target_company,
          'preferred_environment', p.preferred_environment,
          'assistant_style', p.assistant_style,
          'daily_notification_time', to_jsonb(p.daily_notification_time)
        )
      end,
      'assessment', case
        when jsonb_typeof(ar.content -> 'assessment') = 'object'
          then ar.content -> 'assessment'
        else jsonb_build_object(
          'score', ar.content -> 'score',
          'level', ar.content -> 'level',
          'summary', coalesce(ar.content -> 'summary', '{}'::jsonb),
          'version', coalesce(ar.content ->> 'version', ar.prompt_version),
          'model_name', ar.model_name,
          'provider', case
            when ar.model_name like 'gemini-%' then 'google'
            else 'deterministic'
          end,
          'prompt_version', ar.prompt_version,
          'rubric_version', 'legacy-baseline-v1',
          'schema_version', 'profile-assessment-v1'
        )
      end,
      'draft_revision', coalesce(ar.content -> 'draft_revision', '0'::jsonb),
      'snapshot_hash', md5(ar.id::text || ar.content::text)
        || md5('profile-assessment:' || ar.id::text || ar.content::text),
      'metadata', coalesce(ar.content -> 'metadata', '{}'::jsonb)
    ) as content
  from app.ai_results ar
  left join app.profiles p on p.user_id = ar.user_id
  where ar.kind = 'profile_assessment'
    and not (
      ar.content ?& array[
        'schema_version',
        'profile_snapshot',
        'assessment',
        'draft_revision',
        'snapshot_hash'
      ]
    )
)
update app.ai_results ar
set content = normalized.content
from normalized
where ar.id = normalized.id;

with latest_assessment as (
  select distinct on (user_id)
    user_id,
    id
  from app.ai_results
  where kind = 'profile_assessment'
  order by user_id, created_at desc, id desc
)
update app.profiles p
set assessment_result_id = latest_assessment.id
from latest_assessment
where p.user_id = latest_assessment.user_id
  and p.assessment_score is not null
  and p.assessment_result_id is null;

alter table app.profiles
  drop constraint if exists profiles_assessment_pair_check;

alter table app.profiles
  add constraint profiles_assessment_pair_check
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
  ) not valid;

alter table app.profiles
  validate constraint profiles_assessment_pair_check;

do $block$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ai_results_profile_assessment_content_check'
      and conrelid = 'app.ai_results'::regclass
  ) then
    alter table app.ai_results
      add constraint ai_results_profile_assessment_content_check
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
      ) not valid;
  end if;
end
$block$;

alter table app.ai_results
  validate constraint ai_results_profile_assessment_content_check;

create unique index if not exists ai_results_user_id_id_unique
  on app.ai_results (user_id, id);

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
      deferrable initially immediate
      not valid;
  end if;
end
$block$;

alter table app.profiles
  validate constraint profiles_assessment_result_owner_fkey;

create index if not exists profiles_assessment_result_idx
  on app.profiles (user_id, assessment_result_id)
  where assessment_result_id is not null;

commit;
