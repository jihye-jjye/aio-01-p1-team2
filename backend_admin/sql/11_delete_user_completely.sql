begin;

create or replace function app.delete_user_completely(
  target_user_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  account_row app.user_accounts%rowtype;
begin
  select *
  into account_row
  from app.user_accounts
  where id = target_user_id
  for update;

  if not found then
    return null;
  end if;

  if account_row.role = 'admin' then
    raise exception using
      errcode = 'P0001',
      message = 'ADMIN_ACCOUNT_DELETE_FORBIDDEN';
  end if;

  -- 선택적으로 설치되는 로그/피드백 테이블은 존재할 때만 정리한다.
  if to_regclass('app.feedback') is not null then
    execute 'delete from app.feedback where user_id = $1'
      using target_user_id;
  end if;

  delete from app.notifications
  where user_id = target_user_id;

  delete from app.schedule_items
  where user_id = target_user_id;

  -- profiles가 ai_results를 참조하므로 AI 결과보다 먼저 삭제한다.
  delete from app.profiles
  where user_id = target_user_id;

  -- plans와 ai_results 사이의 순환 참조를 끊는다.
  update app.plans
  set
    source_saved_job_id = null,
    proposal_result_id = null,
    previous_plan_id = null
  where user_id = target_user_id;

  update app.ai_results
  set
    applied_plan_id = null,
    decision_status = case
      when decision_status = 'applied' then 'failed'
      else decision_status
    end
  where user_id = target_user_id;

  delete from app.plans
  where user_id = target_user_id;

  delete from app.ai_results
  where user_id = target_user_id;

  delete from app.saved_jobs
  where user_id = target_user_id;

  -- 운영 로그는 분석을 위해 보존하되 삭제 사용자를 익명화한다.
  if to_regclass('app.ai_logs') is not null then
    execute 'update app.ai_logs set user_id = null where user_id = $1'
      using target_user_id;
  end if;

  delete from app.user_accounts
  where id = target_user_id;

  return to_jsonb(account_row) - 'password_hash';
end
$function$;

revoke all
  on function app.delete_user_completely(uuid)
  from public;

do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'app_runtime') then
    grant execute
      on function app.delete_user_completely(uuid)
      to app_runtime;
  end if;

  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute
      on function app.delete_user_completely(uuid)
      to service_role;
  end if;
end
$block$;

commit;
