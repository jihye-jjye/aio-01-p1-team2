begin;

create table if not exists app.plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
    references app.user_accounts (id) on delete cascade,
  source_saved_job_id uuid,
  proposal_result_id uuid,
  previous_plan_id uuid,
  title text not null,
  summary text,
  goal_snapshot jsonb not null default '{}'::jsonb,
  starts_on date not null,
  ends_on date not null,
  total_task_count integer not null default 0,
  final_progress smallint,
  status text not null default 'draft',
  restart_offer_status text not null default 'not_due',
  source_request_id text not null,
  activated_at timestamptz,
  ended_at timestamptz,
  restart_prompted_at timestamptz,
  restart_decided_at timestamptz,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint plans_user_id_id_unique
    unique (user_id, id),
  constraint plans_user_source_request_unique
    unique (user_id, source_request_id),
  constraint plans_source_saved_job_owner_fkey
    foreign key (user_id, source_saved_job_id)
    references app.saved_jobs (user_id, id)
    on delete restrict,
  constraint plans_previous_plan_owner_fkey
    foreign key (user_id, previous_plan_id)
    references app.plans (user_id, id)
    on delete restrict,
  constraint plans_title_not_blank_check
    check (btrim(title) <> ''),
  constraint plans_source_request_not_blank_check
    check (btrim(source_request_id) <> ''),
  constraint plans_goal_snapshot_object_check
    check (jsonb_typeof(goal_snapshot) = 'object'),
  constraint plans_date_range_check
    check (ends_on >= starts_on),
  constraint plans_total_task_count_check
    check (
      total_task_count >= 0
      and (
        status in ('draft', 'rejected')
        or total_task_count > 0
      )
    ),
  constraint plans_final_progress_range_check
    check (final_progress between 0 and 100),
  constraint plans_status_check
    check (
      status in (
        'draft',
        'active',
        'completed',
        'expired',
        'superseded',
        'rejected'
      )
    ),
  constraint plans_restart_offer_status_check
    check (
      restart_offer_status in ('not_due', 'pending', 'accepted', 'declined')
    ),
  constraint plans_activation_state_check
    check (
      (status in ('draft', 'rejected') and activated_at is null)
      or
      (status in ('active', 'completed', 'expired', 'superseded') and activated_at is not null)
    ),
  constraint plans_terminal_state_check
    check (
      (
        status in ('completed', 'expired', 'superseded')
        and ended_at is not null
        and final_progress is not null
      )
      or
      (
        status in ('draft', 'active', 'rejected')
        and ended_at is null
        and final_progress is null
      )
    ),
  constraint plans_terminal_progress_check
    check (
      (status <> 'completed' or final_progress = 100)
      and (status <> 'expired' or final_progress < 100)
    ),
  constraint plans_restart_lifecycle_check
    check (
      (
        status in ('completed', 'expired')
        and restart_offer_status in ('pending', 'accepted', 'declined')
      )
      or
      (
        status not in ('completed', 'expired')
        and restart_offer_status = 'not_due'
      )
    ),
  constraint plans_restart_decision_time_check
    check (
      (
        restart_offer_status in ('not_due', 'pending')
        and restart_decided_at is null
      )
      or
      (
        restart_offer_status in ('accepted', 'declined')
        and restart_decided_at is not null
      )
    ),
  constraint plans_ended_after_activation_check
    check (ended_at is null or ended_at >= activated_at),
  constraint plans_previous_plan_not_self_check
    check (previous_plan_id is null or previous_plan_id <> id)
);

create unique index if not exists plans_one_active_per_user_uidx
  on app.plans (user_id)
  where status = 'active';

create unique index if not exists plans_one_successor_per_previous_uidx
  on app.plans (previous_plan_id)
  where previous_plan_id is not null
    and status <> 'rejected';

create unique index if not exists plans_proposal_result_uidx
  on app.plans (proposal_result_id)
  where proposal_result_id is not null;

create index if not exists plans_source_saved_job_idx
  on app.plans (user_id, source_saved_job_id)
  where source_saved_job_id is not null;

create index if not exists plans_previous_plan_idx
  on app.plans (user_id, previous_plan_id)
  where previous_plan_id is not null;

create index if not exists plans_active_ends_on_idx
  on app.plans (ends_on, user_id)
  where status = 'active';

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'plans_set_updated_at'
      and tgrelid = 'app.plans'::regclass
  ) then
    execute 'create trigger plans_set_updated_at
      before update on app.plans
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
