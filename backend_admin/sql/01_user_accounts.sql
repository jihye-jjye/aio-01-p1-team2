begin;

create table if not exists app.user_accounts (
  id uuid primary key default gen_random_uuid(),
  role text not null default 'user',
  login_id text not null,
  password_hash text not null,
  user_exp smallint not null default 0,
  last_login_at timestamptz,
  is_active boolean not null default true,
  failed_login_count smallint not null default 0,
  locked_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint user_accounts_role_check
    check (role in ('user', 'admin')),
  constraint user_accounts_login_id_length_check
    check (char_length(login_id) between 4 and 50),
  constraint user_accounts_login_id_format_check
    check (login_id ~ '^[a-z0-9._-]+$'),
  constraint user_accounts_user_exp_check
    check (user_exp between 0 and 100),
  constraint user_accounts_admin_exp_check
    check (role <> 'admin' or user_exp = 0),
  constraint user_accounts_failed_login_count_check
    check (failed_login_count >= 0),
  constraint user_accounts_user_id_unique
    unique (id)
);

create unique index if not exists user_accounts_login_id_lower_uidx
  on app.user_accounts (lower(login_id));

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'user_accounts_set_updated_at'
      and tgrelid = 'app.user_accounts'::regclass
  ) then
    execute 'create trigger user_accounts_set_updated_at
      before update on app.user_accounts
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
