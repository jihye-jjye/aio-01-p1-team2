begin;

do $block$
begin
  if current_user = 'app_api' then
    raise exception '18_user_account_management.sql must be run by a migration role, not app_api';
  end if;

  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'app'
      and table_name = 'user_accounts'
      and column_name = 'user_name'
  ) then
    raise exception 'user_accounts.user_name is absent; apply 13_user_accounts_user_name.sql first';
  end if;

  if not exists (
    select 1
    from pg_roles
    where rolname = 'app_runtime'
  ) then
    raise exception 'app_runtime role is absent; apply 09_runtime_grants.sql first';
  end if;
end
$block$;

update app.user_accounts
set user_name = ''
where user_name is null;

alter table app.user_accounts
  alter column user_name set default '';

alter table app.user_accounts
  alter column user_name set not null;

grant insert (user_name)
  on app.user_accounts
  to app_runtime;

grant update (login_id, user_name)
  on app.user_accounts
  to app_runtime;

grant delete
  on app.user_accounts,
     app.profiles,
     app.plans,
     app.schedule_items,
     app.ai_results,
     app.notifications,
     app.daily_goal_achievements
  to app_runtime;

commit;
