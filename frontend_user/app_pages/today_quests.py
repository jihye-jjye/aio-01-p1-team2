"""오늘 완료할 취업 준비 미션과 EXP를 보여주는 페이지입니다."""

import streamlit as st

from clients.quest_client import get_today_quests, update_today_quest
from core.api_client import BackendAPIError
from core.session import is_logged_in


def initialize_state() -> None:
    """페이지에서 사용할 화면 상태를 처음 한 번만 만듭니다."""

    defaults = {
        "today_quests_data": None,
        "today_quests_loaded": False,
        "today_quests_busy": False,
        "today_quests_flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clamp_percent(value: object) -> int:
    """진행률을 Streamlit progress 범위인 0~100으로 제한합니다."""

    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def show_error(error: BackendAPIError) -> None:
    """API 오류를 사용자용 메시지로 보여줍니다."""

    messages = {
        "TODAY_QUEST_NOT_FOUND": "변경할 오늘의 할 일을 찾을 수 없어요.",
        "PLAN_DATA_INTEGRITY_ERROR": "할 일 정보를 확인하는 중 문제가 발생했어요.",
        "SERVICE_UNAVAILABLE": "서버에 잠시 연결할 수 없어요.",
    }

    if error.status_code == 401:
        st.error("로그인이 만료되었습니다. 다시 로그인해 주세요.")
        return

    st.error(messages.get(error.code, error.message))


def load_today_quests() -> None:
    """백엔드에서 오늘 할 일 정보를 불러옵니다."""

    st.session_state.today_quests_data = get_today_quests()
    st.session_state.today_quests_loaded = True


def render_header(today: dict) -> None:
    """페이지 제목과 날짜, 누적 EXP를 보여줍니다."""

    title_column, exp_column = st.columns([4, 1])

    with title_column:
        st.caption("TODAY'S CAREER QUEST")
        st.title("오늘의 할 일")
        st.caption("오늘의 작은 미션을 완료하고 취업 목표에 한 걸음 더 가까워지세요.")

    with exp_column:
        # EXP는 프론트에서 계산하지 않고 백엔드 응답값을 그대로 표시합니다.
        st.metric("누적 EXP", f'{int(today.get("user_exp") or 0)} EXP')

    st.caption(f'기준 날짜 · {today.get("date", "-")}')


def render_progress(today: dict, flash_message: str | None = None) -> None:
    """오늘 완료한 할 일 개수, 진행률, 완료 메시지를 보여줍니다."""

    completed = int(today.get("completed_count") or 0)
    total = int(today.get("total_count") or 0)
    percent = clamp_percent(today.get("percent"))

    with st.container(border=True):
        left_column, right_column = st.columns([4, 1])
        left_column.subheader(str(today.get("plan_title") or "오늘의 커리어 미션"))
        right_column.metric("완료", f"{completed} / {total}")

        st.progress(percent / 100)
        st.caption(f"오늘 진행률 {percent}%")

        # 완료 결과 메시지는 페이지 상단이 아니라 오늘 진행률 카드 안에 표시합니다.
        if flash_message:
            st.success(flash_message)

        if today.get("achieved"):
            earned_exp = int(today.get("earned_exp") or 0)
            if not flash_message:
                st.success(f"오늘의 미션 완료! +{earned_exp} EXP")
        else:
            st.caption("오늘의 모든 할 일을 완료하면 20 EXP를 받을 수 있어요.")


def change_quest_status(quest: dict) -> None:
    """선택한 할 일의 상태를 서버에 저장하고 화면을 다시 불러옵니다."""

    current_status = str(quest.get("status") or "pending")
    next_status = "pending" if current_status == "completed" else "completed"

    try:
        st.session_state.today_quests_busy = True
        with st.spinner("할 일 상태를 반영하고 있어요..."):
            result = update_today_quest(str(quest["id"]), next_status)

        # 서버가 요청한 상태를 실제로 반영했는지 응답값으로 확인합니다.
        if result.get("status") != next_status:
            raise BackendAPIError(
                "INVALID_RESPONSE",
                "할 일 상태가 정상적으로 반영되지 않았습니다.",
            )

        # exp_delta는 이번 요청으로 실제 변경된 EXP입니다.
        exp_delta = int(result.get("exp_delta") or 0)
        if exp_delta > 0:
            message = f"오늘의 모든 미션 완료! +{exp_delta} EXP"
        elif exp_delta < 0:
            message = f"완료 취소로 {exp_delta} EXP가 반영되었어요."
        elif next_status == "completed":
            message = "할 일을 완료했어요."
        else:
            message = "할 일을 완료 전 상태로 되돌렸어요."

        st.session_state.today_quests_flash = message
        st.session_state.today_quests_loaded = False

        # 로드맵 화면은 plan 응답을 세션에 보관합니다.
        # 완료 또는 완료 취소 후 기존 값을 지워야 전체 완료 개수를 다시 조회합니다.
        st.session_state.roadmap_plan = None
        st.session_state.roadmap_loaded = False
        st.rerun()
    except BackendAPIError as error:
        show_error(error)
    finally:
        st.session_state.today_quests_busy = False


def render_quest_card(quest: dict, index: int) -> None:
    """오늘 할 일 한 개를 카드 형태로 보여줍니다."""

    status = str(quest.get("status") or "pending")
    is_completed = status == "completed"

    with st.container(border=True):
        content_column, button_column = st.columns([5, 1.3])

        with content_column:
            icon = "✅" if is_completed else "▫️"
            st.write(f'**{icon} {quest.get("title") or f"할 일 {index}"}**')
            description = str(quest.get("description") or "")
            if description:
                st.caption(description)

            if is_completed:
                st.success("완료")
            else:
                st.caption("진행 전")

        with button_column:
            label = "완료 취소" if is_completed else "완료하기"
            if st.button(
                label,
                key=f'today_quest_{quest.get("id", index)}',
                type="primary" if not is_completed else "secondary",
                use_container_width=True,
                disabled=st.session_state.today_quests_busy,
            ):
                change_quest_status(quest)


def render_empty_state(today: dict) -> None:
    """활성 로드맵 또는 오늘 할 일이 없을 때 안내합니다."""

    with st.container(border=True):
        if not today.get("plan_id"):
            st.subheader("진행 중인 로드맵이 없어요")
            st.caption("로드맵을 시작하면 오늘 해야 할 미션이 이곳에 표시됩니다.")
        else:
            st.subheader("오늘 예정된 할 일이 없어요")
            st.caption("오늘은 잠시 쉬어가도 좋아요. 전체 계획은 로드맵에서 확인하세요.")

    if st.button("로드맵으로 이동", use_container_width=True):
        st.switch_page("app_pages/roadmap.py")


def render_profile_required() -> None:
    """취업 프로필이 없는 사용자에게 AI 프로필 작성을 안내합니다."""

    st.caption("TODAY'S CAREER QUEST")
    st.title("오늘의 할 일")

    with st.container(border=True):
        st.subheader("취업 프로필을 먼저 만들어 주세요")
        st.caption(
            "AI가 목표와 경험을 알아야 나에게 맞는 로드맵과 오늘의 퀘스트를 만들 수 있어요."
        )
        if st.button(
            "프로필 완성하러가기",
            type="primary",
            use_container_width=True,
        ):
            st.switch_page("app_pages/onboarding.py")


def render_content(today: dict, flash_message: str | None = None) -> None:
    """조회 결과에 맞는 오늘 할 일 화면을 보여줍니다."""

    render_header(today)
    st.divider()

    quests = today.get("quests") or []
    if not quests:
        render_empty_state(today)
        return

    render_progress(today, flash_message)
    st.subheader("오늘의 퀘스트")

    for index, quest in enumerate(quests, start=1):
        render_quest_card(quest, index)

    st.caption("EXP는 개별 할 일마다 지급되지 않고, 오늘의 모든 할 일을 완료하면 지급됩니다.")


def main() -> None:
    """로그인 상태와 API 결과에 따라 오늘 할 일 페이지를 보여줍니다."""

    initialize_state()

    if not is_logged_in():
        st.warning("로그인이 필요한 페이지입니다.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    flash_message = st.session_state.pop("today_quests_flash", None)

    if not st.session_state.today_quests_loaded:
        try:
            with st.spinner("오늘의 할 일을 불러오고 있어요..."):
                load_today_quests()
        except BackendAPIError as error:
            if error.code in {"PROFILE_NOT_FOUND", "ONBOARDING_REQUIRED"}:
                render_profile_required()
                return

            show_error(error)
            if st.button("다시 불러오기"):
                st.session_state.today_quests_loaded = False
                st.rerun()
            return

    render_content(st.session_state.today_quests_data or {}, flash_message)


main()
