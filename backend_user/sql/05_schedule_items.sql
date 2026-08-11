begin;

create table if not exists app.schedule_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
    references app.user_accounts (id) on delete cascade,
  plan_id uuid,
  saved_job_id uuid,
  kind text not null,
  title text not null,
  description text,
  scheduled_at timestamptz,
  remind_at timestamptz,
  status text not null default 'pending',
  plan_day smallint,
  slot smallint,
  detail_status text not null default 'outline',
  counts_toward_progress boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint schedule_items_user_id_id_unique
    unique (user_id, id),
  constraint schedule_items_plan_owner_fkey
    foreign key (user_id, plan_id)
    references app.plans (user_id, id)
    on delete restrict,
  constraint schedule_items_saved_job_fkey
    foreign key (saved_job_id)
    references app.saved_jobs (id)
    on delete restrict,
  constraint schedule_items_kind_check
    check (kind in ('milestone', 'task', 'interview')),
  constraint schedule_items_status_check
    check (status in ('pending', 'in_progress', 'completed', 'cancelled')),
  constraint schedule_items_detail_status_check
    check (detail_status in ('outline', 'ready')),
  constraint schedule_items_title_not_blank_check
    check (btrim(title) <> ''),
  constraint schedule_items_plan_slot_check
    check (
      (plan_day is null and slot is null)
      or
      (
        plan_id is not null
        and plan_day is not null
        and slot is not null
        and plan_day > 0
        and slot > 0
      )
    ),
  constraint schedule_items_progress_shape_check
    check (
      not counts_toward_progress
      or (
        kind = 'task'
        and plan_id is not null
        and plan_day is not null
        and slot is not null
        and status <> 'cancelled'
      )
    ),
  constraint schedule_items_completion_time_check
    check (
      (status = 'completed' and completed_at is not null)
      or
      (status <> 'completed' and completed_at is null)
    ),
  constraint schedule_items_reminder_time_check
    check (
      remind_at is null
      or (scheduled_at is not null and remind_at <= scheduled_at)
    ),
  constraint schedule_items_metadata_object_check
    check (jsonb_typeof(metadata) = 'object')
);

create unique index if not exists schedule_items_progress_slot_uidx
  on app.schedule_items (plan_id, plan_day, slot)
  where kind = 'task'
    and counts_toward_progress = true
    and status <> 'cancelled';

create index if not exists schedule_items_plan_idx
  on app.schedule_items (user_id, plan_id)
  where plan_id is not null;

create index if not exists schedule_items_saved_job_idx
  on app.schedule_items (saved_job_id, user_id)
  where saved_job_id is not null;

create index if not exists schedule_items_open_schedule_idx
  on app.schedule_items (user_id, scheduled_at)
  where status in ('pending', 'in_progress');

create index if not exists schedule_items_due_reminder_idx
  on app.schedule_items (remind_at, user_id)
  where remind_at is not null
    and status in ('pending', 'in_progress');

create index if not exists schedule_items_progress_count_idx
  on app.schedule_items (plan_id, status)
  where kind = 'task'
    and counts_toward_progress = true;

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'schedule_items_set_updated_at'
      and tgrelid = 'app.schedule_items'::regclass
  ) then
    execute 'create trigger schedule_items_set_updated_at
      before update on app.schedule_items
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
