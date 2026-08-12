begin;

do $block$
begin
  if current_user = 'app_api' then
    raise exception '17_profile_plan_saved_job.sql must be run by a migration role, not app_api';
  end if;
end
$block$;

alter table app.ai_results
  drop constraint if exists ai_results_proposal_decision_check,
  drop constraint if exists ai_results_profile_plan_proposal_saved_job_check;

alter table app.ai_results
  add constraint ai_results_proposal_decision_check
    check (
      (
        kind = 'job_plan_proposal'
        and decision_status in ('pending', 'accepted', 'rejected', 'applied', 'failed')
        and saved_job_id is not null
      )
      or
      (
        kind = 'profile_plan_proposal'
        and decision_status in ('pending', 'applied', 'rejected')
      )
      or
      (
        kind not in ('job_plan_proposal', 'profile_plan_proposal')
        and decision_status = 'not_applicable'
        and applied_plan_id is null
      )
    ),
  add constraint ai_results_profile_plan_proposal_saved_job_check
    check (
      kind <> 'profile_plan_proposal'
      or (
        saved_job_id is null
        and (
          not (content ? 'saved_job_snapshot')
          or content -> 'saved_job_snapshot' = 'null'::jsonb
        )
      )
      or (
        saved_job_id is not null
        and jsonb_typeof(content -> 'saved_job_snapshot') = 'object'
        and content -> 'saved_job_snapshot' ->> 'id' = saved_job_id::text
      )
    ) not valid;

alter table app.ai_results
  validate constraint ai_results_profile_plan_proposal_saved_job_check;

commit;
