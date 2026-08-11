begin;

create table if not exists app.notices (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  content text not null,
  is_pinned boolean not null default false,
  published_at timestamptz not null default now(),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint notices_title_check
    check (char_length(title) between 1 and 200 and btrim(title) <> ''),
  constraint notices_content_check
    check (char_length(content) between 1 and 10000 and btrim(content) <> ''),
  constraint notices_expiry_check
    check (expires_at is null or expires_at > published_at)
);

create index if not exists notices_published_lookup_idx
  on app.notices (is_pinned desc, published_at desc, id desc)
  include (expires_at);

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'notices_set_updated_at'
      and tgrelid = 'app.notices'::regclass
  ) then
    execute 'create trigger notices_set_updated_at
      before update on app.notices
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

revoke all privileges on app.notices from public;
revoke all privileges on app.notices from app_runtime;

do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all privileges on app.notices from anon';
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all privileges on app.notices from authenticated';
  end if;
end
$block$;

grant select on app.notices to app_runtime;

alter table app.notices enable row level security;

drop policy if exists app_runtime_select_notices on app.notices;

create policy app_runtime_select_notices
  on app.notices
  for select to app_runtime using (true);

analyze app.notices;

commit;
