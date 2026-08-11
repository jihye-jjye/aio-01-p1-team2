"""사용자의 취업 로드맵"""

from datetime import date
from uuid import uuid4

import streamlit as st

from clients.plan_client import (
    accept_proposal,
    create_plan_proposal,
    get_active_plan,
    get_pending_proposal,
    reject_proposal,
)
from core.api_client import BackendAPIError
from core.session import is_logged_in
from core.styles import apply_user_page_background, render_page_header


# 한 번에 최대 28일 조회
DETAIL_WINDOW_DAYS = 28

# 화면에서는 사용자가 성장 흐름을 쉽게 이해할 수 있도록 4단계로 보여줍니다.
CAREER_STAGES = (
    ("01", "FOUNDATION", "직무 기초"),
    ("02", "SKILL", "실무 역량"),
    ("03", "PORTFOLIO", "포트폴리오"),
    ("04", "APPLICATION", "지원 / 면접"),
)


def initialize_state() -> None:
    """로드맵 화면에서 사용하는 세션 값을 처음 한 번만 만듭니다."""

    defaults = {
        "roadmap_plan": None,
        "roadmap_proposal": None,
        "roadmap_loaded": False,
        "roadmap_busy": False,
        "roadmap_request_id": None,
        "roadmap_flash": None,
        # 사용자가 누른 4단계 카드 번호를 기억합니다.
        "roadmap_selected_stage": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clamp_percent(value: object) -> int:
    """진행률을 0부터 100 사이의 정수로 바꿉니다."""

    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def show_error(error: BackendAPIError) -> None:
    """백엔드 오류를 사용자가 이해하기 쉬운 문장으로 보여줍니다."""

    messages = {
        "PROFILE_NOT_FOUND": "로드맵을 만들려면 취업 프로필을 먼저 완성해 주세요.",
        "PLAN_TARGET_DATE_EXPIRED": "목표 취업일이 지났어요. 프로필에서 목표일을 수정해 주세요.",
        "PLAN_HORIZON_TOO_LONG": "계획 기간은 최대 365일까지 설정할 수 있어요.",
        "PLAN_PROFILE_CHANGED": "프로필이 변경되었어요. 새 로드맵을 만들어 주세요.",
        "PLAN_PROPOSAL_STALE": "제안의 유효 기간이 지났어요. 다시 생성해 주세요.",
        "ACTIVE_PLAN_EXISTS": "이미 진행 중인 로드맵이 있어요.",
    }

    if error.status_code == 401:
        st.error("로그인이 만료되었습니다. 다시 로그인해 주세요.")
        return

    st.error(messages.get(error.code, error.message))
    if error.code == "PROFILE_NOT_FOUND":
        if st.button("프로필 완성하러가기", type="primary"):
            st.switch_page("app_pages/onboarding.py")


def load_roadmap() -> None:
    """활성 로드맵을 조회하고, 없으면 검토 중인 제안을 조회합니다."""

    try:
        st.session_state.roadmap_plan = get_active_plan(days=DETAIL_WINDOW_DAYS)
        st.session_state.roadmap_proposal = None
    except BackendAPIError as error:
        if error.code != "PLAN_NOT_FOUND":
            raise

        st.session_state.roadmap_plan = None
        try:
            st.session_state.roadmap_proposal = get_pending_proposal(
                days=DETAIL_WINDOW_DAYS
            )
        except BackendAPIError as pending_error:
            if pending_error.code != "PLAN_PROPOSAL_NOT_FOUND":
                raise
            st.session_state.roadmap_proposal = None

    st.session_state.roadmap_loaded = True


def get_d_day(ends_on: object) -> str:
    """로드맵 종료일까지 남은 날짜를 D-day 문구로 바꿉니다."""

    try:
        remaining_days = (date.fromisoformat(str(ends_on)) - date.today()).days
    except ValueError:
        return "D-day 미정"

    if remaining_days > 0:
        return f"D-{remaining_days}"
    if remaining_days == 0:
        return "D-DAY"
    return f"D+{abs(remaining_days)}"


def split_milestones(plan: dict) -> list[list[dict]]:
    """백엔드 마일스톤을 순서대로 화면용 4단계에 나눕니다."""

    stage_items: list[list[dict]] = [[], [], [], []]
    milestones = plan.get("milestones") or []

    for index, milestone in enumerate(milestones):
        # 마일스톤 개수가 4개보다 많거나 적어도 네 구간에 고르게 배치합니다.
        stage_index = min((index * 4) // len(milestones), 3)
        stage_items[stage_index].append(milestone)

    return stage_items


def stage_progress(overall_percent: int, stage_index: int) -> int:
    """전체 진행률을 화면용 4단계 진행률로 변환합니다."""

    # 중요: 백엔드에는 단계별 진행률 값이 없기 때문에 전체 진행률을
    # FOUNDATION, SKILL, PORTFOLIO, APPLICATION의 4구간으로 등분합니다.
    # 예: 전체 32%라면 1단계는 100%, 2단계는 28%, 나머지는 0%입니다.
    # 이 값은 화면에서 현재 위치를 쉽게 보여주기 위한 표시값이며,
    # 실제 전체 진행률은 백엔드가 반환한 plan["percent"]를 그대로 사용합니다.
    return clamp_percent(overall_percent * 4 - stage_index * 100)


def render_header() -> None:
    """페이지 제목을 보여줍니다."""

    render_page_header(
        "MY CAREER QUEST",
        "나의 취업 로드맵",
        "내 커리어 루트, 지금 어디쯤인지 한눈에 체크해요.",
    )


def render_summary(plan: dict, is_proposal: bool = False) -> None:
    """로드맵의 전체 진행 상황을 보여줍니다."""

    with st.container(border=True):
        title_column, day_column = st.columns([4, 1])

        with title_column:
            st.subheader(str(plan.get("title") or "나의 취업 로드맵"))
            st.caption(str(plan.get("summary") or "목표까지 이어지는 맞춤 성장 계획"))

        with day_column:
            st.metric("목표 취업일", get_d_day(plan.get("ends_on")))

        # 제안은 아직 시작 전이므로 진행률을 0으로 표시합니다.
        percent = 0 if is_proposal else clamp_percent(plan.get("percent"))
        completed = 0 if is_proposal else int(plan.get("completed_task_count") or 0)
        total = int(plan.get("total_task_count") or 0)

        st.write(f"**전체 진행률 {percent}%**")
        st.progress(percent / 100)

        period_column, task_column = st.columns(2)
        period_column.metric(
            "계획 기간",
            f'{plan.get("starts_on", "-")} ~ {plan.get("ends_on", "-")}',
        )
        task_column.metric("완료한 할 일", f"{completed} / {total}")

        # 활성 로드맵에서만 오늘의 퀘스트 페이지로 이동할 수 있습니다.
        if not is_proposal:
            empty_column, quest_button_column = st.columns([4, 1.4])
            with quest_button_column:
                if st.button(
                    "퀘스트 진행하러 가기 →",
                    key="go_to_today_quests",
                    type="primary",
                    use_container_width=True,
                ):
                    st.switch_page("app_pages/today_quests.py")


def render_stages(plan: dict, is_proposal: bool = False) -> list[list[dict]]:
    """4단계 카드를 가로로 보여주고 선택한 단계 번호를 저장합니다."""

    overall_percent = 0 if is_proposal else clamp_percent(plan.get("percent"))
    stage_items = split_milestones(plan)
    st.subheader("CAREER JOURNEY")
    st.caption("완료한 단계와 현재 위치, 앞으로의 계획을 순서대로 확인하세요.")

    # 좌우에 빈 열을 두고, 가운데 열 안에 4단계 카드를 배치합니다.
    # 화면이 넓어져도 카드 묶음이 페이지 중앙을 유지합니다.
    left_space, center_area, right_space = st.columns([0.4, 9.2, 0.4])
    with center_area:
        # 카드 4개와 카드 사이 화살표 3개를 각각 별도의 열에 배치합니다.
        stage_columns = st.columns([4, 0.7, 4, 0.7, 4, 0.7, 4])
        current_stage_found = False

        for stage_index, stage in enumerate(CAREER_STAGES):
            stage_column = stage_columns[stage_index * 2]
            number, english_title, korean_title = stage
            progress = stage_progress(overall_percent, stage_index)
            is_current = not is_proposal and not current_stage_found and progress < 100
            is_selected = st.session_state.roadmap_selected_stage == stage_index

            if is_current:
                current_stage_found = True

            with stage_column:
                with st.container(border=True):
                    st.caption(f"{number} · {english_title}")
                    st.subheader(korean_title)
                    st.progress(progress / 100)
                    st.caption(f"단계 진행률 {progress}%")

                    if progress == 100:
                        state_text = "완료"
                    elif is_current:
                        state_text = "현재 단계"
                    else:
                        state_text = "예정"

                    button_label = f"✓ {state_text}" if is_selected else state_text
                    if st.button(
                        button_label,
                        key=f"select_roadmap_stage_{stage_index}",
                        use_container_width=True,
                    ):
                        st.session_state.roadmap_selected_stage = stage_index
                        st.rerun()

            # 마지막 카드를 제외한 카드 오른쪽에 다음 단계 방향을 표시합니다.
            if stage_index < len(CAREER_STAGES) - 1:
                arrow_column = stage_columns[stage_index * 2 + 1]
                with arrow_column:
                    st.write("")
                    st.write("")
                    st.markdown("### →")

    return stage_items


def tasks_for_selected_stage(plan: dict, milestones: list[dict]) -> list[dict]:
    """선택한 단계 기간 안에 포함된 할 일을 찾습니다."""

    tasks = []
    for milestone in milestones:
        starts_on = str(milestone.get("starts_on") or "")
        ends_on = str(milestone.get("ends_on") or "")

        for day_item in plan.get("days") or []:
            day_text = str(day_item.get("date") or "")
            if starts_on <= day_text <= ends_on:
                tasks.extend(day_item.get("tasks") or [])

    return tasks


def render_stage_detail(plan: dict, stage_items: list[list[dict]]) -> None:
    """사용자가 선택한 단계의 마일스톤과 할 일을 아래에 보여줍니다."""

    selected_index = int(st.session_state.roadmap_selected_stage)
    selected_index = max(0, min(3, selected_index))
    number, english_title, korean_title = CAREER_STAGES[selected_index]
    milestones = stage_items[selected_index]

    st.subheader("선택한 단계 상세")
    with st.container(border=True):
        st.caption(f"{number} · {english_title}")
        st.subheader(korean_title)

        if not milestones:
            st.info("이 단계에 등록된 세부 계획이 아직 없어요.")
        else:
            for milestone in milestones:
                week = milestone.get("week_index")
                title = milestone.get("title") or "성장 목표"
                label = f"WEEK {week} · {title}" if week else title

                st.write(f"**{label}**")
                if milestone.get("description"):
                    st.caption(str(milestone["description"]))
                st.caption(
                    f'{milestone.get("starts_on", "-")} ~ '
                    f'{milestone.get("ends_on", "-")}'
                )

            tasks = tasks_for_selected_stage(plan, milestones)
            if tasks:
                st.write("**이 단계의 할 일**")
                for task in tasks:
                    icon = "✅" if task.get("status") == "completed" else "▫️"
                    st.write(f'{icon} {task.get("title") or "할 일"}')

    st.caption("할 일 완료와 EXP 확인은 ‘오늘 할 일’ 페이지에서 진행합니다.")


def render_active_plan(plan: dict) -> None:
    """사용자가 진행 중인 로드맵을 보여줍니다."""

    render_summary(plan)
    st.divider()
    stage_items = render_stages(plan)
    st.divider()
    render_stage_detail(plan, stage_items)


def render_proposal(proposal: dict) -> None:
    """AI가 만든 로드맵 제안을 확인하고 시작하거나 새 제안을 요청합니다."""

    proposal_id = proposal.get("id") or proposal.get("proposal_id")
    apply_column, reject_column = st.columns(2)

    with apply_column:
        if st.button(
            "이 로드맵으로 시작하기",
            type="primary",
            use_container_width=True,
            disabled=not proposal_id or st.session_state.roadmap_busy,
        ):
            try:
                st.session_state.roadmap_busy = True
                with st.spinner("로드맵을 적용하고 있어요..."):
                    plan = accept_proposal(str(proposal_id))
                st.session_state.roadmap_plan = plan
                st.session_state.roadmap_proposal = None
                st.session_state.roadmap_request_id = None

                # 계획 수락 전 조회한 '오늘 할 일 없음' 결과가 남아 있으면
                # 새 계획의 일정이 생성돼도 이전 캐시가 계속 표시됩니다.
                # 다음 진입에서 현재 사용자의 퀘스트를 다시 조회하도록 초기화합니다.
                st.session_state.today_quests_data = None
                st.session_state.today_quests_loaded = False
                st.session_state.today_quests_flash = None
                st.session_state.today_quests_user_id = None
                st.session_state.roadmap_flash = "로드맵이 적용되었어요."
                st.rerun()
            except BackendAPIError as error:
                show_error(error)
            finally:
                st.session_state.roadmap_busy = False

    with reject_column:
        if st.button(
            "새로운 로드맵 제안받기",
            use_container_width=True,
            disabled=not proposal_id or st.session_state.roadmap_busy,
        ):
            try:
                st.session_state.roadmap_busy = True
                with st.spinner("새로운 로드맵을 준비하고 있어요..."):
                    reject_proposal(str(proposal_id))
                st.session_state.roadmap_proposal = None
                st.session_state.roadmap_request_id = None
                st.session_state.roadmap_flash = "새로운 로드맵 제안을 받을 수 있어요."
                st.rerun()
            except BackendAPIError as error:
                show_error(error)
            finally:
                st.session_state.roadmap_busy = False

    st.divider()
    st.info("AI가 프로필을 분석해 로드맵 초안을 만들었어요. 확인 후 시작해 주세요.")
    render_summary(proposal, is_proposal=True)
    st.divider()
    stage_items = render_stages(proposal, is_proposal=True)
    st.divider()
    render_stage_detail(proposal, stage_items)


def render_empty_state() -> None:
    """로드맵과 제안이 없을 때 생성 버튼을 보여줍니다."""

    with st.container(border=True):
        st.subheader("아직 생성된 로드맵이 없어요")
        st.caption("프로필과 AI 진단 결과를 기준으로 맞춤 계획을 만들 수 있어요.")

    request_id = st.session_state.roadmap_request_id
    label = "같은 요청으로 다시 시도" if request_id else "AI 맞춤 로드맵 만들기"

    if st.button(label, type="primary", use_container_width=True):
        request_id = request_id or str(uuid4())
        st.session_state.roadmap_request_id = request_id

        try:
            st.session_state.roadmap_busy = True
            with st.spinner("프로필을 분석해 로드맵을 만들고 있어요..."):
                proposal = create_plan_proposal(request_id)
            st.session_state.roadmap_proposal = proposal
            st.session_state.roadmap_request_id = None
            st.session_state.roadmap_loaded = True
            st.rerun()
        except BackendAPIError as error:
            show_error(error)
            if not error.retryable:
                st.session_state.roadmap_request_id = None
        finally:
            st.session_state.roadmap_busy = False


def main() -> None:
    """로그인 상태와 API 결과에 따라 알맞은 로드맵 화면을 보여줍니다."""

    initialize_state()
    apply_user_page_background()

    if not is_logged_in():
        st.warning("로그인이 필요한 페이지입니다.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    render_header()

    flash_message = st.session_state.pop("roadmap_flash", None)
    if flash_message:
        st.success(flash_message)

    if not st.session_state.roadmap_loaded:
        try:
            with st.spinner("로드맵을 불러오고 있어요..."):
                load_roadmap()
        except BackendAPIError as error:
            show_error(error)
            if st.button("다시 불러오기"):
                st.session_state.roadmap_loaded = False
                st.rerun()
            return

    if st.session_state.roadmap_plan:
        render_active_plan(st.session_state.roadmap_plan)
    elif st.session_state.roadmap_proposal:
        render_proposal(st.session_state.roadmap_proposal)
    else:
        render_empty_state()


main()
