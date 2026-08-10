begin;

create table if not exists app.saved_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
    references app.user_accounts (id) on delete cascade,
  source_type text not null,
  source_url text,
  source_key text not null,
  company_name text not null,
  job_title text not null,
  deadline date,
  posting_text text not null,
  extracted_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint saved_jobs_user_id_id_unique
    unique (user_id, id),
  constraint saved_jobs_user_source_key_unique
    unique (user_id, source_key),
  constraint saved_jobs_source_type_check
    check (source_type in ('url', 'pasted_text')),
  constraint saved_jobs_source_url_check
    check (
      (source_type <> 'url' or source_url is not null)
      and (source_url is null or btrim(source_url) <> '')
    ),
  constraint saved_jobs_source_key_not_blank_check
    check (btrim(source_key) <> ''),
  constraint saved_jobs_company_name_not_blank_check
    check (btrim(company_name) <> ''),
  constraint saved_jobs_job_title_not_blank_check
    check (btrim(job_title) <> ''),
  constraint saved_jobs_posting_text_not_blank_check
    check (btrim(posting_text) <> ''),
  constraint saved_jobs_extracted_data_object_check
    check (jsonb_typeof(extracted_data) = 'object')
);

create index if not exists saved_jobs_deadline_idx
  on app.saved_jobs (user_id, deadline)
  where deadline is not null;

do $block$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'saved_jobs_set_updated_at'
      and tgrelid = 'app.saved_jobs'::regclass
  ) then
    execute 'create trigger saved_jobs_set_updated_at
      before update on app.saved_jobs
      for each row execute function app.set_updated_at()';
  end if;
end
$block$;

commit;
