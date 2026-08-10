#onboarding.py 로그인 후 ai 채팅으로 사용자의 기본 취업 목표 세팅

import re
from datetime import date, time as datetime_time
from html import escape

import streamlit as st

from clients.auth_client import get_profile
from clients.onboarding_client import (
    confirm_onboarding,
    restart_onboarding,
    retry_pending,
    send_message,
    start_onboarding,
)
from core.api_client import BackendAPIError
from core.session import clear_auth_state


PROFILE_LABELS = {
    "target_role": "목표 직무",
    "skills": "보유 기술",
    "experience_summary": "경험 요약",
    "target_date": "목표 취업일",
    "target_company": "희망 기업",
    "preferred_environment": "선호 근무 환경",
    "daily_notification_time": "알림 시간",
    "assistant_style": "AI 답변 스타일",
}

PROFILE_ICONS = {
    "target_role": "🎯",
    "skills": "🛠️",
    "experience_summary": "📁",
    "target_date": "📅",
    "target_company": "🏢",
    "preferred_environment": "🌿",
    "daily_notification_time": "⏰",
    "assistant_style": "🤖",
}

DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_notification_time(value: str) -> bool:
    """일반 시간과 백엔드가 반환하는 ISO 시간 형식을 모두 검사합니다.

    허용 예: 09:30, 09:30:00, 09:30:00.000Z, 09:30:00+09:00
    """

    if not re.fullmatch(
        r"\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?",
        value,
    ):
        return False

    # Python에서는 Z 대신 +00:00으로 바꾸면 ISO 시간으로 검사할 수 있습니다.
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime_time.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def validate_draft_profile(draft: dict) -> list[str]:
    """AI가 만든 프로필에서 확정 전에 확인해야 할 의심 값을 찾습니다."""

    errors: list[str] = []
    experience = str(draft.get("experience_summary") or "").strip()
    target_date = str(draft.get("target_date") or "").strip()
    notification_time = str(draft.get("daily_notification_time") or "").strip()
    skills = draft.get("skills")

    # 경력 요약은 자연어여야 하므로 날짜 하나만 들어오면 AI 오해 가능성이 큽니다.
    if DATE_ONLY_PATTERN.fullmatch(experience):
        errors.append(
            "경험 요약이 날짜 형식으로 작성되었습니다. "
            "예: ‘관련 경력 2년’처럼 자연어로 수정해 주세요."
        )

    if not isinstance(skills, list) or not skills:
        errors.append("보유 기술이 목록 형태로 입력되지 않았습니다.")

    try:
        parsed_target_date = date.fromisoformat(target_date)
        if parsed_target_date <= date.today():
            errors.append("목표 취업일은 오늘 이후 날짜여야 합니다.")
    except ValueError:
        errors.append("목표 취업일이 YYYY-MM-DD 형식이 아닙니다.")

    if notification_time and not is_valid_notification_time(notification_time):
        errors.append(
            "알림 시간이 올바르지 않습니다. 예: 09:30 또는 09:30:00"
        )

    if draft.get("assistant_style") not in {"friendly", "direct"}:
        errors.append("AI 답변 스타일은 friendly 또는 direct여야 합니다.")

    return errors


def initialize_state() -> None:
    """온보딩 진행 중 필요한 화면 상태를 최초 한 번만 만듭니다."""

    defaults = {
        "onboarding_latest": None,
        "onboarding_pending": None,
        "onboarding_submitting": False,
        "onboarding_messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_response(
    response: dict,
    pending: dict | None = None,
    user_text: str | None = None,
) -> None:
    """백엔드 최신 응답과 화면에 표시할 대화 기록을 저장합니다."""

    # 백엔드 계약에 따라 이전 응답과 merge하지 않고 전체를 교체합니다.
    st.session_state.onboarding_latest = response
    st.session_state.onboarding_pending = pending
    if user_text:
        st.session_state.onboarding_messages.append(
            {"role": "user", "content": user_text}
        )
    assistant_message = response.get("assistant_message")
    if assistant_message:
        st.session_state.onboarding_messages.append(
            {"role": "assistant", "content": assistant_message}
        )


def apply_onboarding_style() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #080b16; color: #f4f0f7; }
        .block-container { max-width: 1050px; padding-top: 2rem; }
        .terminal-header {
            padding: 15px 20px; color: #f1b1dc; border: 1px solid #50314f;
            border-radius: 7px 7px 0 0; font-family: monospace;
            font-size: 17px; font-weight: 800;
        }
        .terminal-controls { float: right; color: #777487; letter-spacing: 4px; }
        .diagnosis-copy { color: #d4ced9; font-size: 16px; padding-top: 14px; }
        .progress-label { color: #c4bdcb; font-size: 13px; font-weight: 700; }
        .chat-shell {
            margin-top: 12px; padding: 18px; border: 1px solid #353247;
            border-radius: 12px; background: rgba(8,11,22,.72);
        }
        div[data-testid="stChatMessage"] {
            max-width: 78%; padding: 8px 12px; margin-bottom: 10px;
            border: 1px solid #353247; border-radius: 9px; background: #111521;
        }
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            margin-left: auto; background: #15152d; border-color: #3f3d72;
        }
        /* AI 질문·사용자 답변·AI 결과 텍스트를 밝은 핑크로 고정합니다. */
        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] li,
        div[data-testid="stChatMessage"] strong,
        div[data-testid="stChatMessage"] code {
            color: #ffb3dc !important;
        }
        div[data-testid="stChatMessage"] code {
            background: #2b172b !important;
        }
        /* 사용자 답변은 AI 메시지와 구분되도록 흰색으로 표시합니다. */
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) li,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) strong,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) code {
            color: #ffffff !important;
        }
        div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] {
            background: #75329b;
        }
        div[data-testid="stChatInput"] {
            width: 100%; margin: 0; padding: 8px 0 0;
            background: #080b16 !important;
        }
        div[data-testid="stChatInput"] > div {
            min-height: 48px; background: #0d101b !important;
            border: 1px solid #363449;
            border-radius: 8px;
        }
        /* Streamlit이 chat_input 바깥에 자동으로 만드는 흰색 wrapper를 숨깁니다. */
        div[data-testid="stChatInput"] > div > div {
            background: #0d101b !important;
        }
        div[data-testid="stBottomBlockContainer"] {
            background: #080b16 !important;
        }
        div[data-testid="stChatInput"] textarea {
            color: #f4f0f7 !important; caret-color: #ff78c5;
        }
        div[data-testid="stChatInput"] textarea::placeholder {
            color: #777487 !important; opacity: 1;
        }
        div[data-testid="stChatInput"] button { color: #ff78c5; }
        div[data-testid="stChatInput"] > div:focus-within {
            border-color: #d84b9d; box-shadow: 0 0 0 1px #d84b9d;
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp p,
        .stApp label, .stApp [data-testid="stCaptionContainer"] { color: #eeeaf2; }
        .review-heading {
            margin-top: 16px; padding: 18px 20px;
            background: #10131f; border: 1px solid #50314f; border-radius: 11px;
        }
        .review-title { color: #ff9fd5; font-size: 22px; font-weight: 900; }
        .review-copy { color: #cfc7d3; margin-top: 5px; font-size: 14px; }
        .review-card {
            min-height: 112px; padding: 16px 17px; margin-bottom: 10px;
            background: #10131f; border: 1px solid #353247; border-radius: 10px;
        }
        .review-label { color: #ff9fd5; font-size: 13px; font-weight: 900; }
        .review-value { color: #ffffff; margin-top: 9px; line-height: 1.6; word-break: break-word; }
        .assessment-card {
            display: flex; justify-content: space-between; align-items: center;
            margin: 8px 0 18px; padding: 14px 17px;
            background: #211225; border: 1px solid #6f3159; border-radius: 9px;
        }
        .assessment-label { color: #f3b8da; font-size: 13px; font-weight: 800; }
        .assessment-value { color: #ffffff; font-size: 17px; font-weight: 900; }
        @media (max-width: 720px) {
            .assessment-card { align-items: flex-start; flex-direction: column; gap: 7px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_api_error(error: BackendAPIError, message_area) -> None:
    """온보딩에서 자주 발생하는 오류 코드를 사용자 문장으로 바꿉니다."""

    if error.code in {"UNAUTHORIZED", "ONBOARDING_SESSION_EXPIRED"}:
        clear_auth_state()
        message_area.error("인증 또는 세션이 만료되었습니다. 다시 로그인해 주세요.")
    elif error.code == "GEMINI_RATE_LIMITED":
        message_area.warning("AI 요청이 많습니다. 잠시 기다린 후 다시 시도해 주세요.")
    elif error.code in {"GEMINI_UNAVAILABLE", "ONBOARDING_REQUEST_IN_PROGRESS"}:
        message_area.warning("요청을 완료하지 못했습니다. 같은 요청을 다시 시도해 주세요.")
    elif error.code == "ONBOARDING_REVISION_CONFLICT":
        message_area.error("프로필 수정 상태가 변경되었습니다. 최신 검토 내용을 확인해 주세요.")
    else:
        message_area.error(error.message)


def start_session(message_area) -> None:
    """백엔드에 온보딩 세션을 생성하고 첫 AI 질문을 저장합니다."""

    try:
        st.session_state.onboarding_submitting = True
        response, pending = start_onboarding()
        save_response(response, pending)
    except BackendAPIError as error:
        show_api_error(error, message_area)
    finally:
        st.session_state.onboarding_submitting = False


def render_progress(latest: dict) -> None:
    """답변한 항목 수와 남은 항목 수로 0~100% 진행률을 계산합니다."""

    payload = latest["payload"]
    answered = len(payload.get("answered_fields", []))
    missing = len(payload.get("missing_fields", []))
    total = answered + missing
    label_column, count_column = st.columns([4, 1])
    label_column.markdown('<div class="progress-label">진단 진행률</div>', unsafe_allow_html=True)
    count_column.markdown(
        f'<div class="progress-label" style="text-align:right">{answered} / {total or 8}</div>',
        unsafe_allow_html=True,
    )
    st.progress(answered / total if total else 0.0)


def render_message_scroll() -> None:
    """저장된 AI 질문과 사용자 답변을 스크롤 가능한 영역에 표시합니다."""

    # 수업에서 사용한 Streamlit 기본 컨테이너와 chat_message로 대화를 표시합니다.
    with st.container(height=410, border=False):
        for message in st.session_state.onboarding_messages:
            role = message["role"]
            # 사용자는 Streamlit 기본 user 아바타를 사용해야 오른쪽 정렬 CSS가 정확히 적용됩니다.
            avatar = None if role == "user" else "🤖"
            with st.chat_message(role, avatar=avatar):
                # st.write를 사용해 사용자와 AI 문자열을 HTML로 실행하지 않습니다.
                st.write(message["content"])


def render_conversation(latest: dict, message_area) -> None:
    """대화 단계의 메시지와 답변 입력 폼을 표시합니다."""

    # 메시지와 입력창을 같은 테두리 안에 넣어 하나의 채팅 화면처럼 보이게 합니다.
    with st.container(border=True):
        render_message_scroll()

        choices = latest.get("choices") or []
        if choices:
            st.caption("선택 예시: " + " · ".join(choices))

        # 컨테이너 안에서 사용하면 입력창이 페이지 하단이 아닌 대화 바로 아래 표시됩니다.
        text = st.chat_input(
            "답변을 입력하세요...",
            max_chars=4000,
            disabled=st.session_state.onboarding_submitting,
        )

    if text:
        try:
            st.session_state.onboarding_submitting = True
            # session_id를 보내면 백엔드가 Redis의 현재 질문 단계를 찾습니다.
            response, pending = send_message(latest["session_id"], text)
            save_response(response, pending, user_text=text.strip())
            st.rerun()
        except BackendAPIError as error:
            show_api_error(error, message_area)
        finally:
            st.session_state.onboarding_submitting = False


def render_review(latest: dict, message_area) -> None:
    """8개 프로필 결과를 보여 주고 수정·확정·재시작을 처리합니다."""

    st.markdown(
        """
        <div class="review-heading">
            <div class="review-title">AI 진단 결과를 확인해 주세요</div>
            <div class="review-copy">저장하기 전에 작성된 프로필을 확인하고, 잘못된 내용은 AI에게 수정 요청할 수 있습니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    draft = latest["payload"].get("draft_profile", {})
    validation_errors = validate_draft_profile(draft)

    # 의심 값이 있으면 확정을 막고 AI에게 수정 요청을 보내도록 안내합니다.
    if validation_errors:
        with message_area.container():
            st.error("프로필에서 확인이 필요한 항목을 발견했습니다.")
            for error_message in validation_errors:
                st.warning(error_message)

    # 프로필 페이지와 같은 순서의 2열 카드로 결과를 보여 줍니다.
    profile_items = list(PROFILE_LABELS.items())
    for index in range(0, len(profile_items), 2):
        columns = st.columns(2)
        for column, (field, label) in zip(columns, profile_items[index:index + 2]):
            value = draft.get(field)
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if value is None and field == "target_company":
                value = "희망 기업 없음"
            display_value = str(value or "입력되지 않음")
            with column:
                st.markdown(
                    f"""
                    <div class="review-card">
                        <div class="review-label">{PROFILE_ICONS[field]} {escape(label)}</div>
                        <div class="review-value">{escape(display_value)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    assessment = latest["payload"].get("assessment")
    if assessment:
        score = escape(str(assessment.get("score", "-")))
        level = escape(str(assessment.get("level", "-")))
        st.markdown(
            f"""
            <div class="assessment-card">
                <div class="assessment-label">현재 취업 준비도</div>
                <div class="assessment-value">{score}점 · {level}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("일부 내용 수정하기"):
        with st.form("review_edit_form", clear_on_submit=True):
            selected_field = st.selectbox(
                "수정할 항목",
                options=list(PROFILE_LABELS.keys()),
                format_func=lambda field: (
                    f"{PROFILE_ICONS[field]} {PROFILE_LABELS[field]}"
                ),
            )
            selected_value = draft.get(selected_field)
            if isinstance(selected_value, list):
                selected_value = ", ".join(str(item) for item in selected_value)
            st.caption(f"현재 값: {selected_value or '입력되지 않음'}")
            edited_value = st.text_area(
                "새로운 내용",
                placeholder="선택한 항목에 적용할 내용을 입력해 주세요.",
                max_chars=4000,
            )
            edit_submitted = st.form_submit_button(
                "선택 항목 수정",
                use_container_width=True,
            )

    if edit_submitted:
        if not edited_value.strip():
            message_area.warning("새로운 내용을 입력해 주세요.")
        else:
            try:
                field_label = PROFILE_LABELS[selected_field]
                # 백엔드의 review 수정 계약은 자연어 입력이므로 필드 선택 결과를
                # 한 항목만 바꾸라는 명확한 문장으로 변환해 전송합니다.
                edit_request = (
                    f"{field_label} 항목만 '{edited_value.strip()}'으로 수정해 줘. "
                    "다른 프로필 항목은 변경하지 말고 그대로 유지해 줘."
                )
                response, pending = send_message(
                    latest["session_id"],
                    edit_request,
                )
                save_response(response, pending, user_text=edit_request)
                st.rerun()
            except BackendAPIError as error:
                show_api_error(error, message_area)

    confirm_column, restart_column = st.columns(2)
    if confirm_column.button(
        "프로필 확정",
        type="primary",
        use_container_width=True,
        disabled=bool(validation_errors),
        help=(
            "확인이 필요한 값을 먼저 수정해 주세요."
            if validation_errors
            else "검토한 프로필을 저장합니다."
        ),
    ):
        try:
            revision = latest["payload"]["draft_revision"]
            response, pending = confirm_onboarding(latest["session_id"], revision)
            save_response(response, pending)
            st.rerun()
        except BackendAPIError as error:
            show_api_error(error, message_area)

    if restart_column.button(
        "처음부터 다시 AI 진단",
        use_container_width=True,
    ):
        try:
            response, pending = restart_onboarding(latest["session_id"])
            if response.get("step") != "conversation":
                raise BackendAPIError(
                    "INVALID_RESPONSE",
                    "AI 진단을 처음 단계로 되돌리지 못했습니다.",
                )

            # 기존 검토 결과와 대화 내용을 지우고 백엔드가 반환한 첫 질문부터 다시 시작합니다.
            st.session_state.onboarding_messages = []
            save_response(response, pending)
            st.session_state.onboarding_flash = (
                "AI 진단을 처음부터 다시 시작합니다."
            )
            st.rerun()
        except BackendAPIError as error:
            show_api_error(error, message_area)


def render_completed(latest: dict, message_area) -> None:
    """온보딩 완료 후 DB에 저장된 최종 프로필을 다시 조회합니다."""

    st.success("취업 프로필 저장이 완료되었습니다.")
    try:
        st.session_state.profile = get_profile()
    except BackendAPIError as error:
        message_area.warning(
            "프로필 저장 결과를 불러오지 못했습니다. 확정 요청은 다시 보내지 마세요."
        )
        if st.button("프로필 조회 다시 시도"):
            st.rerun()
        return

    st.write("이제 사용자 홈에서 AI 취업 서비스를 이용할 수 있습니다.")
    # 사용자 대시보드 생성 후 아래 이동을 연결합니다.
    # st.switch_page("app_pages/user_dashboard.py")


def show_onboarding() -> None:
    """백엔드 step 값에 따라 대화·검토·완료 화면을 선택합니다."""

    initialize_state()
    apply_onboarding_style()
    message_area = st.empty()
    flash = st.session_state.pop("onboarding_flash", None)
    if flash:
        message_area.success(flash)

    st.markdown(
        """
        <div class="terminal-header">
            ❯ 02 AI 진단 대화
            <span class="terminal-controls">— □ ×</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.get("access_token"):
        message_area.error("로그인이 필요합니다.")
        if st.button("로그인으로 이동"):
            st.switch_page("app_pages/login.py")
        return

    if st.session_state.onboarding_latest is None:
        start_session(message_area)

    latest = st.session_state.onboarding_latest
    if latest is None:
        pending = st.session_state.onboarding_pending
        if pending and st.button("같은 요청 다시 시도"):
            try:
                save_response(retry_pending(pending), pending)
                st.rerun()
            except BackendAPIError as error:
                show_api_error(error, message_area)
        return

    if not st.session_state.onboarding_messages and latest.get("assistant_message"):
        st.session_state.onboarding_messages.append(
            {"role": "assistant", "content": latest["assistant_message"]}
        )

    copy_column, progress_column = st.columns([1.7, 1])
    with copy_column:
        st.markdown(
            '<div class="diagnosis-copy">AI 비서와 함께 당신을 분석하고 맞춤 플랜을 만들어요.</div>',
            unsafe_allow_html=True,
        )
    with progress_column:
        render_progress(latest)
    step = latest["step"]
    if step == "conversation":
        render_conversation(latest, message_area)
    elif step == "review":
        render_review(latest, message_area)
    elif step == "completed" and latest.get("completed") is True:
        render_completed(latest, message_area)
    else:
        message_area.error("백엔드에서 알 수 없는 온보딩 상태를 반환했습니다.")


show_onboarding()
