begin;

alter table app.user_accounts
  drop constraint if exists user_accounts_user_exp_check;

alter table app.user_accounts
  drop constraint if exists user_accounts_user_exp_nonnegative_check;

alter table app.user_accounts
  alter column user_exp type integer
  using user_exp::integer;

alter table app.user_accounts
  add constraint user_accounts_user_exp_nonnegative_check
  check (user_exp >= 0);

create table if not exists app.daily_goal_achievements (
  user_id uuid not null,
  plan_id uuid not null,
  plan_day smallint not null,
  goal_date date not null,
  achieved boolean not null default false,
  achieved_at timestamptz,
  exp_awarded smallint not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint daily_goal_achievements_pkey
    primary key (user_id, plan_id, plan_day),
  constraint daily_goal_achievements_user_plan_date_unique
    unique (user_id, plan_id, goal_date),
  constraint daily_goal_achievements_plan_owner_fkey
    foreign key (user_id, plan_id)
    references app.plans (user_id, id)
    on delete cascade,
  constraint daily_goal_achievements_plan_day_check
    check (plan_day > 0)
);

alter table app.daily_goal_achievements
  drop constraint if exists daily_goal_achievements_exp_awarded_check;

alter table app.daily_goal_achievements
  drop constraint if exists daily_goal_achievements_state_check;

update app.daily_goal_achievements
set exp_awarded = 20
where exp_awarded = 10;

alter table app.daily_goal_achievements
  add constraint daily_goal_achievements_exp_awarded_check
  check (exp_awarded in (0, 20));

alter table app.daily_goal_achievements
  add constraint daily_goal_achievements_state_check
  check (
    (
      achieved = true
      and achieved_at is not null
      and exp_awarded = 20
    )
    or
    (
      achieved = false
      and achieved_at is null
      and exp_awarded = 0
    )
  );

create index if not exists daily_goal_achievements_user_goal_date_idx
  on app.daily_goal_achievements (user_id, goal_date desc);

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'daily_goal_achievements_set_updated_at'
      and tgrelid = 'app.daily_goal_achievements'::regclass
  ) then
    execute 'create trigger daily_goal_achievements_set_updated_at
      before update on app.daily_goal_achievements
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

delete from app.daily_goal_achievements dga
where not exists (
  select 1
  from app.schedule_items si
  where si.user_id = dga.user_id
    and si.plan_id = dga.plan_id
    and si.plan_day = dga.plan_day
    and si.kind = 'task'
    and si.counts_toward_progress = true
);

with per_day as (
  select
    si.user_id,
    si.plan_id,
    si.plan_day,
    min((si.scheduled_at at time zone 'Asia/Seoul')::date) as goal_date,
    count(*) filter (where status = 'completed') = count(*) as achieved,
    max(completed_at) as last_completed_at
  from app.schedule_items si
  where si.kind = 'task'
    and si.counts_toward_progress = true
  group by si.user_id, si.plan_id, si.plan_day
)
insert into app.daily_goal_achievements (
  user_id,
  plan_id,
  plan_day,
  goal_date,
  achieved,
  achieved_at,
  exp_awarded
)
select
  user_id,
  plan_id,
  plan_day,
  goal_date,
  achieved,
  case when achieved then last_completed_at else null end,
  case when achieved then 20 else 0 end
from per_day
on conflict (user_id, plan_id, plan_day) do update
set goal_date = excluded.goal_date,
    achieved = excluded.achieved,
    achieved_at = excluded.achieved_at,
    exp_awarded = excluded.exp_awarded;

update app.user_accounts ua
set user_exp = case
  when ua.role = 'admin' then 0
  else (
    select coalesce(sum(dga.exp_awarded), 0)::integer
    from app.daily_goal_achievements dga
    where dga.user_id = ua.id
  )
end;

revoke all privileges on app.daily_goal_achievements from public;
revoke all privileges on app.daily_goal_achievements from app_runtime;

do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all privileges on app.daily_goal_achievements from anon';
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all privileges on app.daily_goal_achievements from authenticated';
  end if;
end
$block$;

grant select, insert, update
  on app.daily_goal_achievements
  to app_runtime;

alter table app.daily_goal_achievements enable row level security;

drop policy if exists app_runtime_full_access
  on app.daily_goal_achievements;

create policy app_runtime_full_access
  on app.daily_goal_achievements
  for all to app_runtime using (true) with check (true);

analyze app.daily_goal_achievements;
analyze app.user_accounts;

commit;
