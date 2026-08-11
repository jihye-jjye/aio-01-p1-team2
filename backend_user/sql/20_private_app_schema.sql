begin;

do $block$
begin
  if current_user = 'app_api' then
    raise exception '20_private_app_schema.sql must be run by a migration role, not app_api';
  end if;
end
$block$;

-- `app` is a server-only schema. Remove both existing and inherited access for
-- browser-facing roles without changing server-side role grants.
revoke all on schema app from public;
revoke all privileges on all tables in schema app from public;
revoke all privileges on all sequences in schema app from public;
revoke execute on all functions in schema app from public;

alter default privileges for role postgres in schema app
  revoke all privileges on tables from public;
alter default privileges for role postgres in schema app
  revoke all privileges on sequences from public;
alter default privileges for role postgres in schema app
  revoke execute on functions from public;

do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on schema app from anon';
    execute 'revoke all privileges on all tables in schema app from anon';
    execute 'revoke all privileges on all sequences in schema app from anon';
    execute 'revoke execute on all functions in schema app from anon';
    execute 'alter default privileges for role postgres in schema app '
      || 'revoke all privileges on tables from anon';
    execute 'alter default privileges for role postgres in schema app '
      || 'revoke all privileges on sequences from anon';
    execute 'alter default privileges for role postgres in schema app '
      || 'revoke execute on functions from anon';
  end if;

  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all on schema app from authenticated';
    execute 'revoke all privileges on all tables in schema app from authenticated';
    execute 'revoke all privileges on all sequences in schema app from authenticated';
    execute 'revoke execute on all functions in schema app from authenticated';
    execute 'alter default privileges for role postgres in schema app '
      || 'revoke all privileges on tables from authenticated';
    execute 'alter default privileges for role postgres in schema app '
      || 'revoke all privileges on sequences from authenticated';
    execute 'alter default privileges for role postgres in schema app '
      || 'revoke execute on functions from authenticated';
  end if;
end
$block$;

commit;
