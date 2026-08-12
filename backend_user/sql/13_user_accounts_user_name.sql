begin;

do $block$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'app'
      and table_name = 'user_accounts'
      and column_name = 'user_name'
  ) then
    alter table app.user_accounts
      add column user_name text not null default '';
  end if;
end
$block$;

commit;
