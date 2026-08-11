begin;

create table if not exists app.notices (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  content text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint notices_title_not_blank_check
    check (btrim(title) <> ''),

  constraint notices_title_length_check
    check (char_length(title) <= 200),

  constraint notices_content_not_blank_check
    check (btrim(content) <> ''),

  constraint notices_content_length_check
    check (char_length(content) <= 20000)
);

create index if not exists notices_created_at_idx
  on app.notices (created_at desc);

create index if not exists notices_title_idx
  on app.notices (title);

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

commit;