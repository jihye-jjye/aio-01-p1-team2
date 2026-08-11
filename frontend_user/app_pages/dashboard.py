"""로그인한 사용자의 취업 준비 현황을 모아 보여주는 대시보드입니다."""

from datetime import date

import streamlit as st

from clients.auth_client import get_profile
from clients.plan_client import get_active_plan
from clients.quest_client import get_today_quests
from core.api_client import BackendAPIError
from core.notification_popup import render_notification_popup
from core.session import is_logged_in
from core.styles import apply_user_page_background, render_page_header


def clamp_percent(value: object) -> int:
    """진행률을 0부터 100 사이의 정수로 바꿉니다."""

    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def get_character_level(profile: dict) -> tuple[str, str]:
    """AI 진단 점수를 임시 4단계 캐릭터 상태로 바꿉니다."""

    # 프로필 페이지와 같은 임시 기준입니다.
    # 실제 캐릭터 이미지와 점수 기준이 확정되면 이 부분만 변경하면 됩니다.
    score = clamp_percent(profile.get("assessment_score"))
    if score <= 25:
        return "🌱", "1단계 · 새싹"
    if score <= 50:
        return "🌿", "2단계 · 성장"
    if score <= 75:
        return "🔥", "3단계 · 도전"
    return "🏆", "4단계 · 전문가"


def get_d_day(target_date: object) -> str:
    """목표 취업일까지 남은 날짜를 D-day로 표시합니다."""

    try:
        remaining_days = (date.fromisoformat(str(target_date)) - date.today()).days
    except ValueError:
        return "목표일 미정"

    if remaining_days > 0:
        return f"D-{remaining_days}"
    if remaining_days == 0:
        return "D-DAY"
    return f"D+{abs(remaining_days)}"


def load_dashboard_data() -> tuple[dict, dict, dict | None]:
    """프로필, 오늘의 퀘스트, 활성 로드맵을 조회합니다."""

    profile = st.session_state.get("profile")
    if not profile:
        profile = get_profile()
        st.session_state.profile = profile

    today = get_today_quests()

    try:
        plan = get_active_plan(days=7)
    except BackendAPIError as error:
        if error.code != "PLAN_NOT_FOUND":
            raise
        plan = None

    return profile, today, plan


def render_header(profile: dict) -> None:
    """캐릭터와 사용자 인사를 한 줄 헤더로 보여줍니다."""

    user = st.session_state.get("user") or {}
    # 백엔드 GET /auth/me에 user_name이 없는 동안은 login_id를 안전한 대체값으로 사용합니다.
    user_name = user.get("user_name") or user.get("login_id") or "사용자"
    character, level = get_character_level(profile)

    with st.container(border=True):
        character_column, greeting_column, profile_column = st.columns(
            [0.7, 4, 1.2],
            vertical_alignment="center",
        )
        # 추후 취업 프로필의 성장 단계별 캐릭터 GIF로 교체할 영역입니다.
        character_column.markdown(f"# {character}")
        greeting_column.subheader(f"안녕하세요, {user_name}님 👋")
        greeting_column.caption(f"{level} · 오늘도 한 칸 성장해 볼까요?")

        with profile_column:
            if st.button(
                "⚙️ 사용자 설정",
                help="로그인 ID와 사용자 이름 수정",
                use_container_width=True,
            ):
                st.switch_page("app_pages/account_settings.py")


def render_quest_card(today: dict) -> None:
    """오늘 할 일의 완료 개수와 진행률을 보여줍니다."""

    completed = int(today.get("completed_count") or 0)
    total = int(today.get("total_count") or 0)
    percent = clamp_percent(today.get("percent"))
    # 고정 높이를 사용하지 않아 작은 화면에서도 내부 스크롤이 생기지 않게 합니다.
    with st.container(border=True):
        st.caption("TODAY QUEST")
        st.subheader(f"{completed} / {total} 완료")
        st.progress(percent / 100)
        st.caption(f"오늘 {percent}% 클리어")

        if total == 0:
            st.info("오늘은 퀘스트가 없어요. 잠깐 쉬어가도 좋아요.")
        elif today.get("achieved"):
            st.success("오늘 퀘스트 올 클리어! ✨")
        else:
            st.caption("오늘 할 일, 가볍게 하나씩 시작해 봐요.")

        if st.button(
            "퀘스트 보기",
            type="primary",
            use_container_width=True,
        ):
            st.switch_page("app_pages/today_quests.py")


def render_overview(profile: dict, today: dict, plan: dict | None) -> None:
    """로드맵과 취업 목표를 세 개의 핵심 지표로 보여줍니다."""

    roadmap_percent = clamp_percent(plan.get("percent")) if plan else 0
    roadmap_completed = int(plan.get("completed_task_count") or 0) if plan else 0
    roadmap_total = int(plan.get("total_task_count") or 0) if plan else 0
    # 오늘의 퀘스트는 오른쪽 카드에서 보여주므로 이 카드에서 중복하지 않습니다.
    # 고정 높이를 제거해 내부 스크롤 없이 내용 전체가 보이게 합니다.
    with st.container(border=True):
        st.subheader("진행 현황 한눈에 보기")
        columns = st.columns([1, 1.4, 1])

        with columns[0]:
            st.caption("ROADMAP")
            st.metric("전체 진행률", f"{roadmap_percent}%")
            st.progress(roadmap_percent / 100)
            st.caption(f"{roadmap_completed} / {roadmap_total} 퀘스트 클리어")

        with columns[1]:
            st.caption("CAREER GOAL")
            st.metric("🎯 목표 직무", profile.get("target_role") or "미정")
            st.caption("지금 내가 달리는 방향")

        with columns[2]:
            st.caption("JOB D-DAY")
            st.metric("📅 남은 기간", get_d_day(profile.get("target_date")))
            st.caption(str(profile.get("target_date") or "날짜 미정"))


def render_quick_menu(plan: dict | None) -> None:
    """자주 사용하는 사용자 기능을 카드 형태로 연결합니다."""

    st.subheader("빠른 메뉴")
    job_column, roadmap_column, profile_column, chatbot_column = st.columns(4)

    with job_column:
        with st.container(border=True, height=205):
            st.write("**💼 AI 추천 공고**")
            st.caption("AI가 고른 나만의 커리어 픽")
            if st.button("추천 공고 보기", key="dashboard_jobs", use_container_width=True):
                st.switch_page("app_pages/jobs.py")

    with roadmap_column:
        with st.container(border=True, height=205):
            st.write("**🗺️ 나의 취업 로드맵**")
            if plan:
                st.caption(f'지금 {clamp_percent(plan.get("percent"))}% 진행 중')
                button_label = "로드맵 확인"
            else:
                st.caption("내 커리어 루트, 지금 만들어 봐요")
                button_label = "로드맵 만들기"
            if st.button(button_label, key="dashboard_roadmap", use_container_width=True):
                st.switch_page("app_pages/roadmap.py")

    with profile_column:
        with st.container(border=True, height=205):
            st.write("**👤 나의 취업 프로필**")
            st.caption("내 목표와 스킬을 한눈에 체크")
            if st.button("프로필 보기", key="dashboard_profile", use_container_width=True):
                st.switch_page("app_pages/profile.py")

    with chatbot_column:
        with st.container(border=True, height=205):
            st.write("**🤖 AI 커리어 코치**")
            st.caption("막히는 순간, AI 코치에게 바로 물어봐요")
            if st.button("AI와 대화하기", key="dashboard_chat", use_container_width=True):
                st.switch_page("app_pages/assistant.py")


def render_dashboard(profile: dict, today: dict, plan: dict | None) -> None:
    """참고 이미지와 같은 순서로 대시보드 카드를 배치합니다."""

    apply_user_page_background()
    render_page_header(
        "HOME · DASHBOARD",
        "나의 커리어 홈",
        "오늘의 미션부터 목표까지, 지금 필요한 것만 빠르게 체크해요.",
    )
    render_header(profile)
    render_notification_popup()

    overview_column, quest_column = st.columns([3, 1.2])
    with overview_column:
        render_overview(profile, today, plan)
    with quest_column:
        render_quest_card(today)

    render_quick_menu(plan)


def main() -> None:
    """로그인 여부와 API 조회 결과에 따라 대시보드를 표시합니다."""

    if not is_logged_in():
        st.warning("로그인이 필요한 페이지입니다.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    try:
        with st.spinner("나의 취업 준비 현황을 불러오고 있어요..."):
            profile, today, plan = load_dashboard_data()
    except BackendAPIError as error:
        if error.code == "PROFILE_NOT_FOUND":
            st.info("대시보드를 이용하려면 취업 프로필을 먼저 완성해 주세요.")
            if st.button("프로필 완성하러가기", type="primary"):
                st.switch_page("app_pages/onboarding.py")
            return

        st.error(error.message)
        if st.button("다시 불러오기"):
            st.rerun()
        return

    render_dashboard(profile, today, plan)


main()
