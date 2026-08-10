begin;

create table if not exists app.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
    references app.user_accounts (id) on delete cascade,
  plan_id uuid,
  schedule_item_id uuid,
  type text not null,
  dedupe_key text not null,
  available_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb,
  claim_token uuid,
  claimed_until timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint notifications_user_id_id_unique
    unique (user_id, id),
  constraint notifications_user_dedupe_key_unique
    unique (user_id, dedupe_key),
  constraint notifications_plan_owner_fkey
    foreign key (user_id, plan_id)
    references app.plans (user_id, id)
    on delete restrict,
  constraint notifications_schedule_item_owner_fkey
    foreign key (user_id, schedule_item_id)
    references app.schedule_items (user_id, id)
    on delete restrict,
  constraint notifications_type_check
    check (
      type in (
        'daily_tasks',
        'plan_ended',
        'interview_reminder',
        'check_in'
      )
    ),
  constraint notifications_dedupe_key_not_blank_check
    check (btrim(dedupe_key) <> ''),
  constraint notifications_payload_object_check
    check (jsonb_typeof(payload) = 'object'),
  constraint notifications_claim_pair_check
    check (
      (claim_token is null and claimed_until is null)
      or
      (claim_token is not null and claimed_until is not null)
    ),
  constraint notifications_read_time_check
    check (read_at is null or read_at >= created_at),
  constraint notifications_reference_shape_check
    check (
      (type <> 'plan_ended' or plan_id is not null)
      and (type <> 'interview_reminder' or schedule_item_id is not null)
    )
);

create index if not exists notifications_unread_idx
  on app.notifications (user_id, available_at)
  where read_at is null;

create index if not exists notifications_due_claim_idx
  on app.notifications (available_at, claimed_until)
  where read_at is null;

create index if not exists notifications_plan_idx
  on app.notifications (user_id, plan_id)
  where plan_id is not null;

create index if not exists notifications_schedule_item_idx
  on app.notifications (user_id, schedule_item_id)
  where schedule_item_id is not null;

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'notifications_set_updated_at'
      and tgrelid = 'app.notifications'::regclass
  ) then
    execute 'create trigger notifications_set_updated_at
      before update on app.notifications
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
