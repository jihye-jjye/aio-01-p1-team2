begin;

create or replace function app.get_admin_dashboard(
  period_days integer default 7
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
as $function$
declare
  generated_at_value timestamptz := now();
  today_value date := timezone('Asia/Seoul', now())::date;
  start_date_value date;
  start_at_value timestamptz;
  tomorrow_at_value timestamptz;
  result_value jsonb;
begin
  if period_days is null or period_days < 1 or period_days > 90 then
    raise exception using
      errcode = '22023',
      message = 'period_days must be between 1 and 90';
  end if;

  start_date_value := today_value - (period_days - 1);
  start_at_value := start_date_value::timestamp at time zone 'Asia/Seoul';
  tomorrow_at_value := (today_value + 1)::timestamp at time zone 'Asia/Seoul';

  with
  user_metrics as (
    select
      count(*)::bigint as total_users,
      count(*) filter (where ua.is_active)::bigint as active_accounts,
      count(*) filter (where not ua.is_active)::bigint as inactive_accounts,
      count(*) filter (
        where ua.created_at >= start_at_value
          and ua.created_at <= generated_at_value
      )::bigint as new_users
    from app.user_accounts ua
    where ua.role = 'user'
  ),
  onboarding_metrics as (
    select
      count(p.user_id)::bigint as profile_count,
      count(*) filter (
        where p.onboarding_completed_at is not null
      )::bigint as completed_count
    from app.user_accounts ua
    left join app.profiles p on p.user_id = ua.id
    where ua.role = 'user'
  ),
  assessment_metrics as (
    select
      count(*) filter (
        where p.assessment_score is not null
      )::bigint as assessed_users,
      coalesce(round(avg(p.assessment_score)::numeric, 2), 0)::numeric
        as average_score,
      count(*) filter (
        where p.assessment_level = 'beginner'
      )::bigint as beginner,
      count(*) filter (
        where p.assessment_level = 'intermediate'
      )::bigint as intermediate,
      count(*) filter (
        where p.assessment_level = 'advanced'
      )::bigint as advanced
    from app.user_accounts ua
    join app.profiles p on p.user_id = ua.id
    where ua.role = 'user'
  ),
  roadmap_metrics as (
    select
      count(distinct p.user_id)::bigint as users_with_plans,
      count(*) filter (where p.status = 'draft')::bigint as draft,
      count(*) filter (where p.status = 'active')::bigint as active,
      count(*) filter (where p.status = 'completed')::bigint as completed,
      count(*) filter (where p.status = 'expired')::bigint as expired,
      count(*) filter (where p.status = 'superseded')::bigint as superseded,
      count(*) filter (where p.status = 'rejected')::bigint as rejected
    from app.plans p
    join app.user_accounts ua on ua.id = p.user_id
    where ua.role = 'user'
  ),
  progress_quest_metrics as (
    select
      count(*)::bigint as total,
      count(*) filter (where si.status = 'completed')::bigint as completed,
      count(*) filter (where si.status = 'in_progress')::bigint as in_progress,
      count(*) filter (where si.status = 'pending')::bigint as pending
    from app.schedule_items si
    join app.user_accounts ua on ua.id = si.user_id
    where ua.role = 'user'
      and si.kind = 'task'
      and si.counts_toward_progress = true
      and si.status <> 'cancelled'
  ),
  today_quest_metrics as (
    select
      count(*) filter (
        where si.scheduled_at >= today_value::timestamp at time zone 'Asia/Seoul'
          and si.scheduled_at < tomorrow_at_value
      )::bigint as scheduled_today,
      count(*) filter (
        where si.completed_at >= today_value::timestamp at time zone 'Asia/Seoul'
          and si.completed_at < tomorrow_at_value
      )::bigint as completed_today,
      count(*) filter (
        where si.scheduled_at < generated_at_value
          and si.status in ('pending', 'in_progress')
      )::bigint as overdue,
      count(*) filter (
        where si.kind = 'interview'
          and si.scheduled_at >= today_value::timestamp at time zone 'Asia/Seoul'
          and si.scheduled_at < tomorrow_at_value
      )::bigint as interviews_today
    from app.schedule_items si
    join app.user_accounts ua on ua.id = si.user_id
    where ua.role = 'user'
  ),
  signup_dates as (
    select generate_series(
      start_date_value::timestamp,
      today_value::timestamp,
      interval '1 day'
    )::date as signup_date
  ),
  daily_signup_counts as (
    select
      timezone('Asia/Seoul', ua.created_at)::date as signup_date,
      count(*)::bigint as signup_count
    from app.user_accounts ua
    where ua.role = 'user'
      and ua.created_at >= start_at_value
      and ua.created_at <= generated_at_value
    group by timezone('Asia/Seoul', ua.created_at)::date
  ),
  daily_signups_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'date', sd.signup_date,
          'count', coalesce(dsc.signup_count, 0)
        )
        order by sd.signup_date
      ),
      '[]'::jsonb
    ) as items
    from signup_dates sd
    left join daily_signup_counts dsc
      on dsc.signup_date = sd.signup_date
  ),
  recent_users_json as (
    select coalesce(
      jsonb_agg(to_jsonb(recent_user) order by recent_user.created_at desc),
      '[]'::jsonb
    ) as items
    from (
      select
        ua.id,
        ua.login_id,
        ua.is_active,
        ua.user_exp,
        p.target_role,
        (p.onboarding_completed_at is not null) as onboarding_completed,
        ua.created_at
      from app.user_accounts ua
      left join app.profiles p on p.user_id = ua.id
      where ua.role = 'user'
      order by ua.created_at desc
      limit 5
    ) recent_user
  )
  select jsonb_build_object(
    'generated_at', generated_at_value,
    'period', jsonb_build_object(
      'days', period_days,
      'start_at', start_at_value,
      'end_at', generated_at_value
    ),
    'users', jsonb_build_object(
      'total_users', um.total_users,
      'active_accounts', um.active_accounts,
      'inactive_accounts', um.inactive_accounts,
      'new_users', um.new_users
    ),
    'onboarding', jsonb_build_object(
      'profile_count', om.profile_count,
      'completed_count', om.completed_count,
      'incomplete_count', um.total_users - om.completed_count,
      'completion_rate', case
        when um.total_users = 0 then 0
        else round(om.completed_count::numeric * 100 / um.total_users, 2)
      end
    ),
    'assessment', jsonb_build_object(
      'assessed_users', am.assessed_users,
      'average_score', am.average_score,
      'level_distribution', jsonb_build_object(
        'beginner', am.beginner,
        'intermediate', am.intermediate,
        'advanced', am.advanced
      )
    ),
    'roadmaps', jsonb_build_object(
      'users_with_plans', rm.users_with_plans,
      'active_plans', rm.active,
      'completed_plans', rm.completed,
      'expired_plans', rm.expired,
      'status_distribution', jsonb_build_object(
        'draft', rm.draft,
        'active', rm.active,
        'completed', rm.completed,
        'expired', rm.expired,
        'superseded', rm.superseded,
        'rejected', rm.rejected
      )
    ),
    'quests', jsonb_build_object(
      'total', pqm.total,
      'completed', pqm.completed,
      'in_progress', pqm.in_progress,
      'pending', pqm.pending,
      'completion_rate', case
        when pqm.total = 0 then 0
        else round(pqm.completed::numeric * 100 / pqm.total, 2)
      end,
      'scheduled_today', tqm.scheduled_today,
      'completed_today', tqm.completed_today,
      'overdue', tqm.overdue,
      'interviews_today', tqm.interviews_today
    ),
    'daily_signups', dsj.items,
    'recent_users', ruj.items
  )
  into result_value
  from user_metrics um
  cross join onboarding_metrics om
  cross join assessment_metrics am
  cross join roadmap_metrics rm
  cross join progress_quest_metrics pqm
  cross join today_quest_metrics tqm
  cross join daily_signups_json dsj
  cross join recent_users_json ruj;

  return result_value;
end
$function$;

revoke all
  on function app.get_admin_dashboard(integer)
  from public;

do $block$
begin
  if exists (select 1 from pg_roles where rolname = 'app_runtime') then
    grant execute
      on function app.get_admin_dashboard(integer)
      to app_runtime;
  end if;

  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute
      on function app.get_admin_dashboard(integer)
      to service_role;
  end if;
end
$block$;

commit;
