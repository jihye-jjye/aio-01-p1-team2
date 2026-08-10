from html import escape
from datetime import date, timedelta
from uuid import uuid4

import streamlit as st

from clients.plan_client import (
    accept_proposal,
    complete_plan,
    create_plan_proposal,
    get_active_plan,
    get_pending_proposal,
    reject_proposal,
    update_task_status,
)
from core.api_client import BackendAPIError
from core.session import is_logged_in


STATUS_LABELS = {
    "completed": "✅ 완료",
    "pending": "☐ 진행 예정",
}


def apply_roadmap_style() -> None:
    """로드맵 화면에 프로젝트의 다크·핑크 테마를 적용합니다."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #080b16; color: #f4f0f7; }
        .block-container { max-width: 1050px; padding-top: 2rem; }
        .roadmap-header {
            padding: 18px 22px; margin-bottom: 18px;
            background: linear-gradient(135deg, #121522 0%, #0b0e19 100%);
            border: 1px solid #50314f; border-radius: 12px;
            box-shadow: 0 14px 34px rgba(0,0,0,.22);
        }
        .roadmap-kicker { color: #ff78c5; font-family: monospace; font-size: 13px; }
        .roadmap-title { color: #ffffff; font-size: 25px; font-weight: 900; margin-top: 6px; }
        .roadmap-copy { color: #cfc7d3; margin-top: 5px; }
        .overview-panel {
            padding: 20px 22px; margin-bottom: 18px;
            background: #10131f; border: 1px solid #353247; border-radius: 12px;
        }
        .overview-top { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
        .overview-label { color: #9a93a1; font-size: 12px; font-weight: 800; }
        .overview-title { color: #ffffff; font-size: 20px; font-weight: 900; margin-top: 5px; }
        .status-pill {
            color: #7ee787; background: #10241a; border: 1px solid #28623b;
            padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 800;
        }
        .progress-heading { display: flex; justify-content: space-between; margin-top: 20px; }
        .progress-name { color: #cfc7d3; font-size: 13px; }
        .progress-percent { color: #ff9fd5; font-size: 16px; font-weight: 900; }
        .progress-track { height: 10px; margin-top: 8px; background: #252337; border-radius: 999px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #8b5cf6, #ec4899); border-radius: 999px; }
        .overview-meta { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 17px; }
        .meta-chip { color: #d6ceda; background: #151827; border: 1px solid #353247; padding: 7px 10px; border-radius: 7px; font-size: 12px; }
        .goal-card {
            padding: 15px 18px; margin-bottom: 18px;
            background: #151222; border: 1px solid #353247;
            border-radius: 10px;
        }
        .goal-label { color: #9a93a1; font-size: 12px; font-weight: 700; }
        .goal-value { color: #ffffff; margin-top: 5px; font-size: 17px; font-weight: 800; }
        .roadmap-card {
            min-height: 170px; padding: 18px; margin-bottom: 13px;
            background: #10131f; border: 1px solid #353247;
            border-left: 4px solid #c02676; border-radius: 10px;
        }
        .roadmap-stage { color: #ff78c5; font-family: monospace; font-weight: 900; }
        .roadmap-card-title { color: #ffffff; font-size: 18px; font-weight: 900; margin-top: 8px; }
        .roadmap-description { color: #cfc7d3; margin-top: 9px; line-height: 1.6; }
        .roadmap-status {
            display: inline-block; margin-top: 14px; padding: 5px 9px;
            color: #ff9fd5; background: #211225;
            border: 1px solid #6f3159; border-radius: 999px; font-size: 12px;
        }
        .week-panel {
            padding: 20px; margin-top: 4px; background: #0d101b;
            border: 1px solid #353247; border-radius: 0 0 12px 12px;
        }
        .week-heading { display: flex; justify-content: space-between; gap: 15px; align-items: center; margin-bottom: 15px; }
        .week-title { color: #ff78c5; font-size: 18px; font-weight: 900; }
        .week-percent { color: #d6ceda; font-size: 13px; }
        .mission-row {
            display: grid; grid-template-columns: 36px minmax(0,1fr) auto auto;
            align-items: center; gap: 12px; padding: 13px 14px; margin-bottom: 9px;
            background: #111521; border: 1px solid #353247; border-radius: 9px;
        }
        .mission-check { color: #7ee787; font-size: 18px; text-align: center; }
        .mission-title { color: #ffffff; font-weight: 800; }
        .mission-time { color: #9a93a1; font-size: 12px; white-space: nowrap; }
        .mission-status { min-width: 78px; padding: 5px 8px; text-align: center; border-radius: 6px; font-size: 12px; font-weight: 800; }
        .status-completed { color: #7ee787; background: #10241a; border: 1px solid #28623b; }
        .status-pending { color: #aaa4b1; background: #1c1e2b; border: 1px solid #3d3f4e; }
        .coach-panel {
            display: grid; grid-template-columns: 82px 1fr; gap: 16px; align-items: center;
            margin-top: 18px; padding: 16px 18px; background: #141322;
            border: 1px solid #4b3656; border-radius: 12px;
        }
        .coach-avatar { font-size: 52px; text-align: center; }
        .coach-name { color: #ff9fd5; font-size: 12px; font-weight: 900; }
        .coach-message { color: #ffffff; line-height: 1.6; margin-top: 4px; }
        .week-summary {
            display: flex; justify-content: space-between; gap: 16px;
            align-items: flex-start; margin-bottom: 14px;
        }
        .week-summary-title { color: #ff78c5; font-size: 18px; font-weight: 900; }
        .week-summary-copy { color: #a9a3b0; font-size: 13px; margin-top: 5px; }
        .week-summary-count {
            color: #ffffff; background: #211225; border: 1px solid #6f3159;
            padding: 7px 10px; border-radius: 8px; font-size: 12px; white-space: nowrap;
        }
        .task-copy { padding: 3px 2px; }
        .task-date { color: #ff9fd5; font-family: monospace; font-size: 11px; font-weight: 800; }
        .task-title { color: #ffffff; font-size: 15px; font-weight: 900; margin-top: 5px; }
        .task-description { color: #aaa4b1; font-size: 13px; margin-top: 4px; line-height: 1.5; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #10131f; border-color: #353247 !important; border-radius: 10px;
        }
        div[data-baseweb="tab-list"] { gap: 6px; background: transparent; }
        button[data-baseweb="tab"] {
            color: #ff9fd5 !important; background: #151222 !important;
            border: 1px solid #50314f !important; border-radius: 8px 8px 0 0 !important;
            min-width: 105px; min-height: 44px;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #ffffff !important; background: #3a1833 !important;
            border-color: #ec4899 !important; box-shadow: inset 0 -3px 0 #ec4899;
        }
        @media (max-width: 720px) {
            .overview-top, .week-heading { align-items: flex-start; flex-direction: column; }
            .week-summary { flex-direction: column; }
            .mission-row { grid-template-columns: 30px 1fr; }
            .mission-time, .mission-status { grid-column: 2; justify-self: start; }
            .coach-panel { grid-template-columns: 1fr; text-align: center; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_state() -> None:
    """로드맵 조회와 중복 요청 방지에 필요한 화면 상태를 준비합니다."""

    defaults = {
        "roadmap_plan": None,
        "roadmap_proposal": None,
        "roadmap_loaded": False,
        "roadmap_busy": False,
        "roadmap_request_id": None,
        "roadmap_start_on": None,
        "roadmap_flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_error(error: BackendAPIError) -> None:
    """백엔드의 사용자용 오류 메시지를 화면 상단에 표시합니다."""

    if error.status_code == 401:
        st.error("로그인이 만료되었습니다. 다시 로그인해 주세요.")
    else:
        st.error(error.message)


def load_roadmap() -> None:
    """활성 계획을 우선 조회하고, 없으면 대기 중인 제안을 조회합니다."""

    try:
        st.session_state.roadmap_plan = get_active_plan(
            start_on=st.session_state.roadmap_start_on,
            days=28,
        )
        st.session_state.roadmap_proposal = None
    except BackendAPIError as error:
        if error.code != "PLAN_NOT_FOUND":
            raise
        st.session_state.roadmap_plan = None
        try:
            st.session_state.roadmap_proposal = get_pending_proposal(days=28)
        except BackendAPIError as pending_error:
            if pending_error.code != "PLAN_PROPOSAL_NOT_FOUND":
                raise
            st.session_state.roadmap_proposal = None
    st.session_state.roadmap_loaded = True


def render_overview(plan: dict) -> None:
    """백엔드가 계산한 활성 계획 진행률과 기간을 표시합니다."""

    progress = int(plan.get("percent", 0))
    title = escape(str(plan.get("title") or "나의 취업 로드맵"))
    summary = escape(str(plan.get("summary") or ""))
    starts_on = escape(str(plan.get("starts_on") or "-"))
    ends_on = escape(str(plan.get("ends_on") or "-"))
    completed = int(plan.get("completed_task_count", 0))
    total = int(plan.get("total_task_count", 0))
    st.markdown(
        f"""
        <section class="overview-panel">
            <div class="overview-top">
                <div><div class="overview-label">CURRENT QUEST</div>
                <div class="overview-title">{title}</div></div>
                <div class="status-pill">● {escape(str(plan.get("status", "active")))}</div>
            </div>
            <div class="roadmap-copy">{summary}</div>
            <div class="progress-heading"><span class="progress-name">전체 진행률</span>
                <span class="progress-percent">{progress}%</span></div>
            <div class="progress-track" role="progressbar" aria-label="전체 로드맵 진행률"
                 aria-valuemin="0" aria-valuemax="100" aria-valuenow="{progress}">
                <div class="progress-fill" style="width:{progress}%"></div>
            </div>
            <div class="overview-meta">
                <span class="meta-chip">📅 {starts_on} ~ {ends_on}</span>
                <span class="meta-chip">✅ 완료 {completed} / {total}</span>
                <span class="meta-chip">🗓 총 {len(plan.get("milestones") or [])}주 과정</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def tasks_for_milestone(plan: dict, milestone: dict) -> list[dict]:
    """현재 조회 구간의 날짜 중 선택한 주차에 속하는 미션을 모읍니다."""

    start = str(milestone.get("starts_on"))
    end = str(milestone.get("ends_on"))
    tasks = []
    for day in plan.get("days") or []:
        day_date = str(day.get("date"))
        if start <= day_date <= end:
            for task in day.get("tasks") or []:
                tasks.append(task)
    return tasks


def render_active_plan(plan: dict) -> None:
    """주차별 마일스톤과 실제 날짜별 미션을 표시합니다."""

    milestones = plan.get("milestones") or []
    if not milestones:
        st.info("표시할 주차별 계획이 없습니다.")
        return

    requested_start = str(plan.get("requested_start_on") or plan.get("starts_on"))
    requested_end = str(plan.get("requested_end_on") or plan.get("ends_on"))
    visible_milestones = [
        milestone
        for milestone in milestones
        if str(milestone.get("starts_on")) <= requested_end
        and str(milestone.get("ends_on")) >= requested_start
    ]
    if not visible_milestones:
        st.info("현재 조회 기간에 해당하는 주차 계획이 없습니다.")
        return

    tabs = st.tabs([
        f'{item.get("week_index", index + 1)}주차'
        for index, item in enumerate(visible_milestones)
    ])
    for tab, milestone in zip(tabs, visible_milestones):
        with tab:
            tasks = tasks_for_milestone(plan, milestone)
            completed_count = sum(
                1 for task in tasks if task.get("status") == "completed"
            )
            task_count = len(tasks)
            week_percent = (
                completed_count * 100 // task_count if task_count else 0
            )

            st.markdown(
                f"""
                <div class="week-summary">
                    <div>
                        <div class="week-summary-title">
                            {escape(str(milestone.get('week_index')))}주차 목표 ·
                            {escape(str(milestone.get('title') or '주차 목표'))}
                        </div>
                        <div class="week-summary-copy">
                            {escape(str(milestone.get('description') or ''))}<br>
                            {escape(str(milestone.get('starts_on')))} ~ {escape(str(milestone.get('ends_on')))}
                        </div>
                    </div>
                    <div class="week-summary-count">미션 {completed_count} / {task_count}</div>
                </div>
                <div class="progress-heading">
                    <span class="progress-name">이번 주 진행률</span>
                    <span class="progress-percent">{week_percent}%</span>
                </div>
                <div class="progress-track" role="progressbar" aria-label="주차 진행률"
                     aria-valuemin="0" aria-valuemax="100" aria-valuenow="{week_percent}">
                    <div class="progress-fill" style="width:{week_percent}%"></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not tasks:
                st.info("현재 조회한 날짜 구간에는 이 주차의 미션이 없습니다.")
                continue

            for task in tasks:
                status = str(task.get("status", "pending"))
                with st.container(border=True):
                    task_column, action_column = st.columns([5, 1.2])
                    with task_column:
                        st.markdown(
                            f"""
                            <div class="task-copy">
                                <div class="task-date">DAY {escape(str(task.get('plan_day', '-')))} · {escape(str(task.get('date', '-')))}</div>
                                <div class="task-title">{escape(str(task.get('title') or '미션'))}</div>
                                <div class="task-description">{escape(str(task.get('description') or ''))}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with action_column:
                        st.caption(STATUS_LABELS.get(status, "☐ 진행 예정"))
                        next_status = (
                            "pending" if status == "completed" else "completed"
                        )
                        button_label = (
                            "↩ 완료 취소" if status == "completed" else "✓ 미션 완료"
                        )
                        if st.button(
                            button_label,
                            key=f'task_{task.get("id")}',
                            use_container_width=True,
                            disabled=st.session_state.roadmap_busy,
                        ):
                            try:
                                st.session_state.roadmap_busy = True
                                result = update_task_status(
                                    plan["id"], task["id"], next_status
                                )
                                st.session_state.roadmap_flash = (
                                    "미션 상태를 변경했습니다."
                                )
                                st.session_state.roadmap_plan["percent"] = (
                                    result["percent"]
                                )
                                st.session_state.roadmap_loaded = False
                                st.rerun()
                            except BackendAPIError as error:
                                show_error(error)
                            finally:
                                st.session_state.roadmap_busy = False

            coach_message = (
                "이번 주 미션을 모두 클리어했어요. 다음 주 퀘스트도 이어서 도전해 볼까요? 🚀"
                if week_percent == 100
                else f"이번 주 미션을 {completed_count}개 완료했어요. 한 번에 하나씩 꾸준히 클리어해 봐요."
            )
            st.markdown(
                f"""
                <div class="coach-panel">
                    <div class="coach-avatar">🤖</div>
                    <div>
                        <div class="coach-name">AI CAREER ASSISTANT</div>
                        <div class="coach-message">{escape(coach_message)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    previous_column, period_column, next_column = st.columns([1, 2, 1])
    start_text = plan.get("requested_start_on")
    end_text = plan.get("requested_end_on")
    period_column.caption(f"조회 기간: {start_text} ~ {end_text}")
    if previous_column.button("← 이전 기간", disabled=not plan.get("has_previous")):
        previous_start = date.fromisoformat(str(start_text)) - timedelta(days=28)
        plan_start = date.fromisoformat(str(plan["starts_on"]))
        st.session_state.roadmap_start_on = str(max(previous_start, plan_start))
        st.session_state.roadmap_loaded = False
        st.rerun()
    if next_column.button("다음 기간 →", disabled=not plan.get("has_next")):
        st.session_state.roadmap_start_on = str(date.fromisoformat(str(end_text)) + timedelta(days=1))
        st.session_state.roadmap_loaded = False
        st.rerun()

    if (
        plan.get("total_task_count", 0) > 0
        and plan.get("total_task_count") == plan.get("completed_task_count")
    ):
        if st.button("로드맵 완료하기", type="primary", use_container_width=True):
            try:
                st.session_state.roadmap_plan = complete_plan(plan["id"])
                st.session_state.roadmap_flash = "로드맵을 완료했습니다!"
                st.rerun()
            except BackendAPIError as error:
                show_error(error)


def render_proposal(proposal: dict) -> None:
    """AI가 만든 계획 제안을 사용자가 승인하기 전에 검토하게 합니다."""

    st.markdown(
        '<div class="roadmap-kicker">❯ AI PLAN PROPOSAL</div>',
        unsafe_allow_html=True,
    )
    st.subheader(str(proposal.get("title") or "AI 맞춤 로드맵 제안"))
    st.write(proposal.get("summary") or "생성된 계획을 확인해 주세요.")
    summary_columns = st.columns(3)
    summary_columns[0].metric("계획 기간", f'{proposal.get("duration_days", 0)}일')
    summary_columns[1].metric("전체 미션", f'{proposal.get("total_task_count", 0)}개')
    summary_columns[2].metric(
        "제안 상태",
        str(proposal.get("decision_status", "pending")),
    )
    st.caption(
        f'{proposal.get("starts_on")} ~ {proposal.get("ends_on")} · '
        "승인하기 전에는 활성 로드맵에 반영되지 않습니다."
    )
    st.markdown("#### 주차별 목표")
    for milestone in proposal.get("milestones") or []:
        with st.expander(f'{milestone.get("week_index")}주차 · {milestone.get("title")}'):
            st.write(milestone.get("description") or "")
            st.caption(f'{milestone.get("starts_on")} ~ {milestone.get("ends_on")}')

    # 생성 성공 응답에는 기본적으로 계획 시작일부터 첫 7일의 미션이 포함됩니다.
    proposal_days = proposal.get("days") or []
    if proposal_days:
        st.markdown("#### 첫 주 미션 미리보기")
        for day in proposal_days:
            with st.container(border=True):
                st.markdown(f"**DAY {day.get('plan_day')} · {day.get('date')}**")
                for task in day.get("tasks") or []:
                    st.markdown(
                        f"- **{task.get('title', '미션')}**  \n"
                        f"  {task.get('description', '')}"
                    )

    accept_column, reject_column = st.columns(2)
    if accept_column.button("이 로드맵으로 시작", type="primary", use_container_width=True):
        try:
            st.session_state.roadmap_plan = accept_proposal(proposal["id"])
            st.session_state.roadmap_proposal = None
            st.session_state.roadmap_flash = "로드맵을 시작했습니다."
            st.rerun()
        except BackendAPIError as error:
            show_error(error)
    if reject_column.button("제안 거절", use_container_width=True):
        try:
            reject_proposal(proposal["id"])
            st.session_state.roadmap_proposal = None
            st.session_state.roadmap_loaded = False
            st.session_state.roadmap_flash = "로드맵 제안을 거절했습니다."
            st.rerun()
        except BackendAPIError as error:
            show_error(error)


def render_empty_state() -> None:
    """활성 계획과 대기 제안이 없을 때 생성 버튼을 표시합니다."""

    st.info("아직 생성된 취업 로드맵이 없습니다.")
    if st.button("AI 맞춤 로드맵 만들기", type="primary"):
        request_id = st.session_state.roadmap_request_id or str(uuid4())
        st.session_state.roadmap_request_id = request_id
        try:
            with st.spinner("프로필을 분석해 맞춤 로드맵을 만드는 중입니다..."):
                st.session_state.roadmap_proposal = create_plan_proposal(request_id)
            st.session_state.roadmap_request_id = None
            st.rerun()
        except BackendAPIError as error:
            # timeout·재시도 가능 오류는 같은 request_id로 다시 요청해야 합니다.
            show_error(error)
            if not error.retryable:
                st.session_state.roadmap_request_id = None


def main() -> None:
    apply_roadmap_style()
    initialize_state()

    if not is_logged_in():
        st.warning("로그인이 필요한 페이지입니다.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    st.markdown(
        """
        <div class="roadmap-header">
            <div class="roadmap-kicker">❯ 05 MY CAREER QUEST</div>
            <div class="roadmap-title">내 커리어, 이번 주도 레벨업!</div>
            <div class="roadmap-copy">막막한 취업 준비는 그만. 주차별 미션을 하나씩 클리어해 보세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    flash = st.session_state.pop("roadmap_flash", None)
    if flash:
        st.success(flash)

    if not st.session_state.roadmap_loaded:
        try:
            with st.spinner("로드맵을 불러오는 중입니다..."):
                load_roadmap()
        except BackendAPIError as error:
            show_error(error)
            if st.button("다시 불러오기"):
                st.session_state.roadmap_loaded = False
                st.rerun()
            return

    plan = st.session_state.roadmap_plan
    proposal = st.session_state.roadmap_proposal
    if plan:
        render_overview(plan)
        render_active_plan(plan)
    elif proposal:
        render_proposal(proposal)
    else:
        render_empty_state()

main()
