begin;

alter table app.daily_goal_achievements
  drop constraint if exists daily_goal_achievements_exp_awarded_check;

alter table app.daily_goal_achievements
  drop constraint if exists daily_goal_achievements_state_check;

update app.daily_goal_achievements
set exp_awarded = 20
where exp_awarded = 10;

alter table app.daily_goal_achievements
  add constraint daily_goal_achievements_exp_awarded_check
  check (exp_awarded in (0, 20));

alter table app.daily_goal_achievements
  add constraint daily_goal_achievements_state_check
  check (
    (
      achieved = true
      and achieved_at is not null
      and exp_awarded = 20
    )
    or
    (
      achieved = false
      and achieved_at is null
      and exp_awarded = 0
    )
  );

update app.user_accounts ua
set user_exp = case
  when ua.role = 'admin' then 0
  else (
    select coalesce(sum(dga.exp_awarded), 0)::integer
    from app.daily_goal_achievements dga
    where dga.user_id = ua.id
  )
end;

analyze app.daily_goal_achievements;
analyze app.user_accounts;

commit;
