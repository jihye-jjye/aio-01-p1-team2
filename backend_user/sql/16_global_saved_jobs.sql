begin;

alter table app.plans
  drop constraint if exists plans_source_saved_job_owner_fkey,
  drop constraint if exists plans_source_saved_job_fkey;

alter table app.schedule_items
  drop constraint if exists schedule_items_saved_job_owner_fkey,
  drop constraint if exists schedule_items_saved_job_fkey;

alter table app.ai_results
  drop constraint if exists ai_results_saved_job_owner_fkey,
  drop constraint if exists ai_results_saved_job_fkey;

create temporary table saved_job_canonical_map
on commit drop
as
select
  id as previous_id,
  first_value(id) over (
    partition by source_key
    order by created_at, id
  ) as canonical_id
from app.saved_jobs;

update app.plans as p
set source_saved_job_id = mapping.canonical_id
from saved_job_canonical_map as mapping
where p.source_saved_job_id = mapping.previous_id
  and mapping.previous_id <> mapping.canonical_id;

update app.schedule_items as si
set saved_job_id = mapping.canonical_id
from saved_job_canonical_map as mapping
where si.saved_job_id = mapping.previous_id
  and mapping.previous_id <> mapping.canonical_id;

update app.ai_results as ar
set saved_job_id = mapping.canonical_id
from saved_job_canonical_map as mapping
where ar.saved_job_id = mapping.previous_id
  and mapping.previous_id <> mapping.canonical_id;

delete from app.saved_jobs as sj
using saved_job_canonical_map as mapping
where sj.id = mapping.previous_id
  and mapping.previous_id <> mapping.canonical_id;

alter table app.saved_jobs
  drop constraint if exists saved_jobs_user_id_id_unique,
  drop constraint if exists saved_jobs_user_source_key_unique,
  drop constraint if exists saved_jobs_source_key_unique,
  drop column if exists user_id;

alter table app.saved_jobs
  add constraint saved_jobs_source_key_unique unique (source_key);

drop index if exists app.saved_jobs_deadline_idx;

create index saved_jobs_deadline_idx
  on app.saved_jobs (deadline, id)
  where deadline is not null;

drop index if exists app.plans_source_saved_job_idx;
drop index if exists app.schedule_items_saved_job_idx;
drop index if exists app.ai_results_saved_job_idx;

create index plans_source_saved_job_idx
  on app.plans (source_saved_job_id, user_id)
  where source_saved_job_id is not null;

create index schedule_items_saved_job_idx
  on app.schedule_items (saved_job_id, user_id)
  where saved_job_id is not null;

create index ai_results_saved_job_idx
  on app.ai_results (saved_job_id, user_id)
  where saved_job_id is not null;

alter table app.plans
  add constraint plans_source_saved_job_fkey
  foreign key (source_saved_job_id)
  references app.saved_jobs (id)
  on delete restrict;

alter table app.schedule_items
  add constraint schedule_items_saved_job_fkey
  foreign key (saved_job_id)
  references app.saved_jobs (id)
  on delete restrict;

alter table app.ai_results
  add constraint ai_results_saved_job_fkey
  foreign key (saved_job_id)
  references app.saved_jobs (id)
  on delete restrict;

commit;
