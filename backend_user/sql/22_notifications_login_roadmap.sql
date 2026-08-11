begin;

alter table app.notifications
  add column if not exists is_read boolean;

alter table app.notifications
  add column if not exists invalidated_at timestamptz;

update app.notifications
set is_read = (read_at is not null)
where is_read is distinct from (read_at is not null);

alter table app.notifications
  alter column is_read set default false,
  alter column is_read set not null;

alter table app.notifications
  drop constraint if exists notifications_read_state_check,
  drop constraint if exists notifications_type_check,
  drop constraint if exists notifications_reference_shape_check,
  drop constraint if exists notifications_plan_owner_fkey,
  drop constraint if exists notifications_schedule_item_owner_fkey;

alter table app.notifications
  add constraint notifications_read_state_check
    check (is_read = (read_at is not null)),
  add constraint notifications_type_check
    check (
      type in (
        'daily_tasks',
        'plan_ended',
        'interview_reminder',
        'check_in',
        'roadmap_changed'
      )
    ),
  add constraint notifications_reference_shape_check
    check (
      (
        type <> 'plan_ended'
        or plan_id is not null
        or payload ? 'plan_id'
      )
      and (
        type <> 'interview_reminder'
        or schedule_item_id is not null
        or payload ? 'schedule_item_id'
      )
    ),
  add constraint notifications_plan_owner_fkey
    foreign key (user_id, plan_id)
    references app.plans (user_id, id)
    on delete set null (plan_id),
  add constraint notifications_schedule_item_owner_fkey
    foreign key (user_id, schedule_item_id)
    references app.schedule_items (user_id, id)
    on delete set null (schedule_item_id);

drop index if exists app.notifications_unread_idx;
drop index if exists app.notifications_due_claim_idx;

create index if not exists notifications_unread_idx
  on app.notifications (user_id, available_at)
  where is_read = false and invalidated_at is null;

create index if not exists notifications_due_claim_idx
  on app.notifications (available_at, claimed_until)
  where is_read = false and invalidated_at is null;

create index if not exists notifications_plan_idx
  on app.notifications (user_id, plan_id)
  where plan_id is not null;

create index if not exists notifications_schedule_item_idx
  on app.notifications (user_id, schedule_item_id)
  where schedule_item_id is not null;

create or replace function app.preserve_notification_deleted_reference()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  if old.plan_id is not null and new.plan_id is null then
    new.payload := pg_catalog.jsonb_set(
      new.payload,
      '{plan_id}',
      pg_catalog.to_jsonb(old.plan_id),
      true
    );
  end if;
  if old.schedule_item_id is not null and new.schedule_item_id is null then
    new.payload := pg_catalog.jsonb_set(
      new.payload,
      '{schedule_item_id}',
      pg_catalog.to_jsonb(old.schedule_item_id),
      true
    );
  end if;
  return new;
end
$function$;

create or replace function app.produce_plan_notification()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
declare
  event_type text;
  event_operation text;
begin
  if tg_op = 'DELETE' then
    if old.status = 'active' then
      insert into app.notifications (
        user_id, plan_id, type, dedupe_key, payload
      ) values (
        old.user_id,
        null,
        'plan_ended',
        pg_catalog.format(
          'plan_ended:plan:%s:delete:%s',
          old.id,
          pg_catalog.gen_random_uuid()
        ),
        pg_catalog.jsonb_build_object(
          'version', 'plan_ended.v1',
          'ended_status', 'deleted',
          'final_progress', coalesce(old.final_progress, 0),
          'plan_id', old.id,
          'plan_title', old.title
        )
      );
    end if;
    return old;
  end if;

  if tg_op = 'INSERT' and new.status = 'active' then
    event_type := 'roadmap_changed';
    event_operation := 'activation';
  elsif tg_op = 'UPDATE'
    and new.status = 'active'
    and old.status is distinct from 'active' then
    event_type := 'roadmap_changed';
    event_operation := 'activation';
  elsif tg_op = 'UPDATE'
    and old.status = 'active'
    and new.status = 'active'
    and (
      old.title is distinct from new.title
      or old.summary is distinct from new.summary
      or old.goal_snapshot is distinct from new.goal_snapshot
      or old.starts_on is distinct from new.starts_on
      or old.ends_on is distinct from new.ends_on
      or old.total_task_count is distinct from new.total_task_count
    ) then
    event_type := 'roadmap_changed';
    event_operation := 'update';
  elsif tg_op = 'UPDATE'
    and old.status = 'active'
    and new.status is distinct from 'active' then
    event_type := 'plan_ended';
    event_operation := 'exit';
  else
    return new;
  end if;

  insert into app.notifications (
    user_id, plan_id, type, dedupe_key, payload
  ) values (
    new.user_id,
    new.id,
    event_type,
    pg_catalog.format(
      '%s:plan:%s:%s:%s',
      event_type,
      new.id,
      event_operation,
      pg_catalog.gen_random_uuid()
    ),
    case
      when event_type = 'plan_ended' then
        pg_catalog.jsonb_build_object(
          'version', 'plan_ended.v1',
          'ended_status', new.status,
          'final_progress', coalesce(new.final_progress, 0),
          'plan_id', new.id,
          'plan_title', new.title
        )
      else
        pg_catalog.jsonb_build_object(
          'version', 'roadmap_change.v1',
          'target', 'plan',
          'change_kind', event_operation,
          'affected_count', 1,
          'plan_id', new.id,
          'before', case
            when event_operation = 'activation' then null
            else pg_catalog.jsonb_build_object(
              'id', old.id,
              'title', old.title,
              'status', old.status,
              'starts_on', old.starts_on,
              'ends_on', old.ends_on,
              'total_task_count', old.total_task_count
            )
          end,
          'after', pg_catalog.jsonb_build_object(
            'id', new.id,
            'title', new.title,
            'status', new.status,
            'starts_on', new.starts_on,
            'ends_on', new.ends_on,
            'total_task_count', new.total_task_count
          )
        )
    end
  );

  return new;
end
$function$;

create or replace function app.produce_schedule_insert_notifications()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  insert into app.notifications (user_id, plan_id, type, dedupe_key, payload)
  select
    s.user_id,
    s.plan_id,
    'roadmap_changed',
    pg_catalog.format(
      'roadmap_changed:schedule:%s:insert:%s',
      s.plan_id,
      pg_catalog.gen_random_uuid()
    ),
    pg_catalog.jsonb_build_object(
      'version', 'roadmap_change.v1',
      'target', 'schedule',
      'change_kind', 'insert',
      'affected_count', pg_catalog.count(*),
      'plan_id', s.plan_id,
      'schedule_ids', pg_catalog.jsonb_agg(s.id order by s.id),
      'before', null,
      'after', case when pg_catalog.count(*) = 1 then
        pg_catalog.jsonb_agg(
          pg_catalog.jsonb_build_object(
            'id', s.id,
            'title', s.title,
            'scheduled_at', case when s.scheduled_at is null then null else
              pg_catalog.to_char(
                s.scheduled_at at time zone 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
              )
            end,
            'status', s.status
          ) order by s.id
        ) -> 0
      else null end
    )
  from inserted_rows s
  join app.plans p
    on p.user_id = s.user_id and p.id = s.plan_id
  where p.status = 'active'
  group by s.user_id, s.plan_id;

  return null;
end
$function$;

create or replace function app.produce_schedule_update_notifications()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  with changed as (
    select
      coalesce(n.id, o.id) as id,
      o.user_id as old_user_id,
      o.plan_id as old_plan_id,
      n.user_id as new_user_id,
      n.plan_id as new_plan_id,
      case when o.id is null then null else pg_catalog.jsonb_build_object(
        'id', o.id,
        'title', o.title,
        'scheduled_at', case when o.scheduled_at is null then null else
          pg_catalog.to_char(
            o.scheduled_at at time zone 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          )
        end,
        'status', o.status
      ) end as before_summary,
      case when n.id is null then null else pg_catalog.jsonb_build_object(
        'id', n.id,
        'title', n.title,
        'scheduled_at', case when n.scheduled_at is null then null else
          pg_catalog.to_char(
            n.scheduled_at at time zone 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          )
        end,
        'status', n.status
      ) end as after_summary
    from updated_old_rows o
    full join updated_new_rows n on n.id = o.id
    where o.id is null
      or n.id is null
      or (pg_catalog.to_jsonb(n) - 'updated_at')
        is distinct from (pg_catalog.to_jsonb(o) - 'updated_at')
  ),
  affected as (
    select
      c.id,
      p.user_id,
      p.id as plan_id,
      c.before_summary,
      c.after_summary
    from changed c
    join app.plans p
      on (
        (p.user_id = c.old_user_id and p.id = c.old_plan_id)
        or (p.user_id = c.new_user_id and p.id = c.new_plan_id)
      )
    where p.status = 'active'
  ),
  grouped as (
    select
      a.user_id,
      a.plan_id,
      pg_catalog.count(distinct a.id) as affected_count,
      pg_catalog.jsonb_agg(distinct a.id order by a.id) as schedule_ids,
      case when pg_catalog.count(distinct a.id) = 1
        then pg_catalog.jsonb_agg(a.before_summary order by a.id) -> 0
        else null
      end as before_summary,
      case when pg_catalog.count(distinct a.id) = 1
        then pg_catalog.jsonb_agg(a.after_summary order by a.id) -> 0
        else null
      end as after_summary
    from affected a
    group by a.user_id, a.plan_id
  )
  insert into app.notifications (user_id, plan_id, type, dedupe_key, payload)
  select
    g.user_id,
    g.plan_id,
    'roadmap_changed',
    pg_catalog.format(
      'roadmap_changed:schedule:%s:update:%s',
      g.plan_id,
      pg_catalog.gen_random_uuid()
    ),
    pg_catalog.jsonb_build_object(
      'version', 'roadmap_change.v1',
      'target', 'schedule',
      'change_kind', 'update',
      'affected_count', g.affected_count,
      'plan_id', g.plan_id,
      'schedule_ids', g.schedule_ids,
      'before', g.before_summary,
      'after', g.after_summary
    )
  from grouped g;

  return null;
end
$function$;

create or replace function app.produce_schedule_delete_notifications()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  insert into app.notifications (user_id, plan_id, type, dedupe_key, payload)
  select
    s.user_id,
    s.plan_id,
    'roadmap_changed',
    pg_catalog.format(
      'roadmap_changed:schedule:%s:delete:%s',
      s.plan_id,
      pg_catalog.gen_random_uuid()
    ),
    pg_catalog.jsonb_build_object(
      'version', 'roadmap_change.v1',
      'target', 'schedule',
      'change_kind', 'delete',
      'affected_count', pg_catalog.count(*),
      'plan_id', s.plan_id,
      'schedule_ids', pg_catalog.jsonb_agg(s.id order by s.id),
      'before', case when pg_catalog.count(*) = 1 then
        pg_catalog.jsonb_agg(
          pg_catalog.jsonb_build_object(
            'id', s.id,
            'title', s.title,
            'scheduled_at', case when s.scheduled_at is null then null else
              pg_catalog.to_char(
                s.scheduled_at at time zone 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
              )
            end,
            'status', s.status
          ) order by s.id
        ) -> 0
      else null end,
      'after', null
    )
  from deleted_rows s
  join app.plans p
    on p.user_id = s.user_id and p.id = s.plan_id
  where p.status = 'active'
  group by s.user_id, s.plan_id;

  return null;
end
$function$;

create or replace function app.sync_daily_task_notifications(p_user_id uuid)
returns table (upserted_count bigint, invalidated_count bigint)
language sql
security invoker
set search_path = ''
as $function$
  with window_bounds as (
    select pg_catalog.timezone('Asia/Seoul', pg_catalog.now())::date as starts_on
  ),
  desired as (
    select
      s.user_id,
      s.plan_id,
      pg_catalog.timezone('Asia/Seoul', s.scheduled_at)::date as task_date,
      'daily_tasks:' || s.plan_id::text || ':'
        || pg_catalog.to_char(
          pg_catalog.timezone('Asia/Seoul', s.scheduled_at)::date,
          'YYYY-MM-DD'
        ) as dedupe_key,
      pg_catalog.jsonb_build_object(
        'version', 'daily_tasks.v1',
        'date', pg_catalog.to_char(
          pg_catalog.timezone('Asia/Seoul', s.scheduled_at)::date,
          'YYYY-MM-DD'
        ),
        'plan_title', p.title,
        'count', pg_catalog.count(*),
        'schedules', pg_catalog.jsonb_agg(
          pg_catalog.jsonb_build_object(
            'id', s.id,
            'kind', s.kind,
            'title', s.title,
            'scheduled_at', pg_catalog.to_char(
              s.scheduled_at at time zone 'UTC',
              'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
            ),
            'status', s.status
          ) order by s.scheduled_at, s.id
        )
      ) as payload
    from app.schedule_items s
    join app.plans p
      on p.user_id = s.user_id and p.id = s.plan_id
    cross join window_bounds w
    where s.user_id = p_user_id
      and p.status = 'active'
      and s.status in ('pending', 'in_progress')
      and s.scheduled_at is not null
      and pg_catalog.timezone('Asia/Seoul', s.scheduled_at)::date
        between w.starts_on and w.starts_on + interval '6 days'
    group by s.user_id, s.plan_id, p.title,
      pg_catalog.timezone('Asia/Seoul', s.scheduled_at)::date
  ),
  upserted as (
    insert into app.notifications (
      user_id, plan_id, type, dedupe_key, available_at, payload
    )
    select
      d.user_id,
      d.plan_id,
      'daily_tasks',
      d.dedupe_key,
      pg_catalog.now(),
      d.payload
    from desired d
    on conflict (user_id, dedupe_key) do update
    set
      plan_id = excluded.plan_id,
      available_at = excluded.available_at,
      payload = excluded.payload,
      is_read = case
        when app.notifications.payload is distinct from excluded.payload
          or app.notifications.invalidated_at is not null
        then false
        else app.notifications.is_read
      end,
      read_at = case
        when app.notifications.payload is distinct from excluded.payload
          or app.notifications.invalidated_at is not null
        then null
        else app.notifications.read_at
      end,
      invalidated_at = null
    where app.notifications.type = 'daily_tasks'
    returning 1
  ),
  invalidated as (
    update app.notifications n
    set invalidated_at = pg_catalog.now()
    where n.user_id = p_user_id
      and n.type = 'daily_tasks'
      and n.invalidated_at is null
      and not exists (
        select 1 from desired d where d.dedupe_key = n.dedupe_key
      )
    returning 1
  )
  select
    (select pg_catalog.count(*) from upserted),
    (select pg_catalog.count(*) from invalidated)
$function$;

revoke all on function app.produce_plan_notification() from public;
revoke all on function app.preserve_notification_deleted_reference() from public;
revoke all on function app.produce_schedule_insert_notifications() from public;
revoke all on function app.produce_schedule_update_notifications() from public;
revoke all on function app.produce_schedule_delete_notifications() from public;
revoke all on function app.sync_daily_task_notifications(uuid) from public;

do $block$
declare
  blocked_role text;
begin
  foreach blocked_role in array array['anon', 'authenticated']
  loop
    if exists (select 1 from pg_roles where rolname = blocked_role) then
      execute pg_catalog.format(
        'revoke all on function app.produce_plan_notification() from %I', blocked_role
      );
      execute pg_catalog.format(
        'revoke all on function app.preserve_notification_deleted_reference() from %I',
        blocked_role
      );
      execute pg_catalog.format(
        'revoke all on function app.produce_schedule_insert_notifications() from %I',
        blocked_role
      );
      execute pg_catalog.format(
        'revoke all on function app.produce_schedule_update_notifications() from %I',
        blocked_role
      );
      execute pg_catalog.format(
        'revoke all on function app.produce_schedule_delete_notifications() from %I',
        blocked_role
      );
      execute pg_catalog.format(
        'revoke all on function app.sync_daily_task_notifications(uuid) from %I',
        blocked_role
      );
    end if;
  end loop;
end
$block$;

drop trigger if exists plans_produce_notification on app.plans;
create trigger plans_produce_notification
  after insert or update or delete on app.plans
  for each row execute function app.produce_plan_notification();

drop trigger if exists schedule_items_produce_insert_notifications on app.schedule_items;
create trigger schedule_items_produce_insert_notifications
  after insert on app.schedule_items
  referencing new table as inserted_rows
  for each statement execute function app.produce_schedule_insert_notifications();

drop trigger if exists schedule_items_produce_update_notifications on app.schedule_items;
create trigger schedule_items_produce_update_notifications
  after update on app.schedule_items
  referencing old table as updated_old_rows new table as updated_new_rows
  for each statement execute function app.produce_schedule_update_notifications();

drop trigger if exists schedule_items_produce_delete_notifications on app.schedule_items;
create trigger schedule_items_produce_delete_notifications
  after delete on app.schedule_items
  referencing old table as deleted_rows
  for each statement execute function app.produce_schedule_delete_notifications();

drop trigger if exists notifications_preserve_deleted_reference on app.notifications;
create trigger notifications_preserve_deleted_reference
  before update of plan_id, schedule_item_id on app.notifications
  for each row execute function app.preserve_notification_deleted_reference();

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


do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'app_runtime') then
    grant execute on function app.sync_daily_task_notifications(uuid) to app_runtime;
  end if;
end
$block$;

commit;
