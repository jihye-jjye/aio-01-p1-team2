begin;

do $block$
declare
  runtime_role record;
  api_role record;
begin
  select *
  into runtime_role
  from pg_roles
  where rolname = 'app_runtime';

  if not found then
    create role app_runtime nologin;
  elsif runtime_role.rolsuper
    or runtime_role.rolcreatedb
    or runtime_role.rolcreaterole
    or runtime_role.rolcanlogin
    or runtime_role.rolreplication
    or runtime_role.rolbypassrls
  then
    raise exception 'existing role app_runtime has unsafe attributes';
  end if;

  select *
  into api_role
  from pg_roles
  where rolname = 'app_api';

  if not found then
    create role app_api login inherit;
  elsif api_role.rolsuper
    or api_role.rolcreatedb
    or api_role.rolcreaterole
    or not api_role.rolcanlogin
    or not api_role.rolinherit
    or api_role.rolreplication
    or api_role.rolbypassrls
  then
    raise exception 'existing role app_api has unsafe attributes';
  end if;
end
$block$;

grant app_runtime to app_api;
revoke all on schema app from app_runtime;
revoke all privileges on all tables in schema app from app_runtime;
grant usage on schema app to app_runtime;

grant select
  on app.user_accounts
  to app_runtime;

grant insert (login_id, password_hash, user_name)
  on app.user_accounts
  to app_runtime;

grant update (
  login_id,
  user_name,
  password_hash,
  user_exp,
  last_login_at,
  is_active,
  failed_login_count,
  locked_until
)
  on app.user_accounts
  to app_runtime;

grant delete
  on app.user_accounts
  to app_runtime;

grant select, insert, update, delete
  on app.profiles
  to app_runtime;

grant select, insert, update, delete
  on app.saved_jobs
  to app_runtime;

grant select, insert, update, delete
  on app.plans, app.schedule_items, app.ai_results, app.notifications
  to app_runtime;

grant execute
  on function app.sync_daily_task_notifications(uuid)
  to app_runtime;

-- Keep RLS enabled as a role boundary. Per-user ownership remains enforced by
-- FastAPI because every backend request shares the app_api database role.
do $block$
declare
  table_name text;
begin
  foreach table_name in array array[
    'user_accounts',
    'profiles',
    'saved_jobs',
    'plans',
    'schedule_items',
    'ai_results',
    'notifications'
  ]
  loop
    execute format('alter table app.%I enable row level security', table_name);
    execute format(
      'drop policy if exists app_runtime_full_access on app.%I',
      table_name
    );
    execute format(
      'create policy app_runtime_full_access on app.%I '
      || 'for all to app_runtime using (true) with check (true)',
      table_name
    );
  end loop;
end
$block$;

alter role app_api set statement_timeout = '15s';
alter role app_api set idle_in_transaction_session_timeout = '15s';

commit;
