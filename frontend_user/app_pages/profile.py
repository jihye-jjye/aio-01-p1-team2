from html import escape
import json

import streamlit as st

from clients.auth_client import get_profile
from clients.onboarding_client import send_message, start_onboarding
from core.api_client import BackendAPIError
from core.session import is_logged_in


# 온보딩에서 저장하는 8개 항목과 같은 순서로 보여 줍니다.
PROFILE_FIELDS = {
    "target_role": ("🎯", "목표 직무"),
    "skills": ("🛠️", "보유 기술"),
    "experience_summary": ("📁", "경험 요약"),
    "target_date": ("📅", "목표 취업일"),
    "target_company": ("🏢", "희망 기업"),
    "preferred_environment": ("🌿", "선호 근무 환경"),
    "daily_notification_time": ("⏰", "알림 시간"),
    "assistant_style": ("🤖", "AI 답변 스타일"),
}


def apply_profile_style() -> None:
    """프로필 페이지에 사용하는 다크 테마를 적용합니다."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #080b16; color: #f4f0f7; }
        .block-container { max-width: 1050px; padding-top: 2rem; }
        .profile-header {
            padding: 20px 22px; margin-bottom: 18px;
            background: #10131f; border: 1px solid #50314f;
            border-radius: 12px;
        }
        .profile-title { color: #ff9fd5; font-size: 25px; font-weight: 900; }
        .profile-copy { color: #cfc7d3; margin-top: 5px; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #10131f;
            border-color: #353247 !important;
            border-radius: 11px;
        }
        .field-label { color: #ff9fd5; font-size: 13px; font-weight: 800; }
        .field-value { color: #ffffff; font-size: 16px; margin-top: 7px; }
        .character-slot {
            min-height: 300px; display: flex; align-items: center;
            justify-content: center; flex-direction: column; gap: 12px;
            background: linear-gradient(180deg, #151222 0%, #0d101b 100%);
            border: 1px dashed #a63b79; border-radius: 14px;
        }
        .character-placeholder { font-size: 88px; line-height: 1; }
        .character-caption { color: #8d8794; font-size: 13px; }
        .character-level {
            margin-top: 12px; padding: 9px 12px; text-align: center;
            color: #ff9fd5; background: #211225;
            border: 1px solid #6f3159; border-radius: 8px; font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def display_value(value) -> str:
    """목록과 빈 값을 사용자가 읽기 쉬운 문자열로 바꿉니다."""

    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "아직 입력되지 않았습니다."
    if value in (None, ""):
        return "아직 입력되지 않았습니다."
    return str(value)


def load_profile() -> dict | None:
    """저장된 값이 없을 때만 백엔드에서 프로필을 조회합니다."""

    if st.session_state.get("profile"):
        return st.session_state.profile

    try:
        st.session_state.profile = get_profile()
        return st.session_state.profile
    except BackendAPIError as error:
        if error.code == "PROFILE_NOT_FOUND":
            return None
        st.error(f"프로필을 불러오지 못했습니다. {error.message}")
        return None


def render_profile_cards(profile: dict) -> None:
    """프로필 8개 항목을 두 열의 카드 형태로 표시합니다."""

    items = list(PROFILE_FIELDS.items())
    for index in range(0, len(items), 2):
        columns = st.columns(2)
        for column, (field, (icon, label)) in zip(columns, items[index:index + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(
                        f'<div class="field-label">{icon} {label}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="field-value">{escape(display_value(profile.get(field)))}</div>',
                        unsafe_allow_html=True,
                    )


def render_character_slot(profile: dict) -> None:
    """추후 4단계 캐릭터 이미지를 넣을 왼쪽 영역을 표시합니다."""

    # 백엔드의 100점 만점 진단 점수를 임시 기준으로 4개 구간에 나눕니다.
    # 팀에서 점수 구간을 확정하면 아래 숫자만 변경하면 됩니다.
    score = profile.get("assessment_score")
    try:
        numeric_score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        numeric_score = 0

    if numeric_score <= 25:
        level_label = "1단계 · 새싹"
    elif numeric_score <= 50:
        level_label = "2단계 · 성장"
    elif numeric_score <= 75:
        level_label = "3단계 · 도전"
    else:
        level_label = "4단계 · 전문가"

    st.markdown(
        """
        <div class="character-slot">
            <div class="character-placeholder">🧑‍💻</div>
            <div class="character-caption">캐릭터 이미지 영역</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="character-level">{escape(level_label)}</div>',
        unsafe_allow_html=True,
    )


def start_profile_edit(profile: dict, field: str, new_value: str) -> None:
    """기존 프로필과 한 항목의 변경값을 새 AI 검토 세션으로 전달합니다."""

    # 내부 ID와 평가 결과는 제외하고 사용자가 작성한 8개 필드만 전달합니다.
    current_profile = {
        key: profile.get(key)
        for key in PROFILE_FIELDS
    }
    field_label = PROFILE_FIELDS[field][1]
    edit_request = (
        "아래는 이미 저장된 내 취업 프로필이야. 기존 내용을 초안으로 사용해 줘.\n"
        f"{json.dumps(current_profile, ensure_ascii=False)}\n"
        f"이 중 {field_label} 항목만 '{new_value.strip()}'으로 수정하고 "
        "나머지 항목은 그대로 유지해 줘. 수정된 전체 프로필을 검토할 수 있게 해 줘."
    )
    if len(edit_request) > 4000:
        raise BackendAPIError(
            "VALIDATION_ERROR",
            "기존 프로필과 수정 내용이 너무 깁니다. 수정 내용을 더 짧게 입력해 주세요.",
        )

    # 새 온보딩 세션을 만든 뒤 기존 프로필과 부분 수정 요청을 첫 답변으로 보냅니다.
    start_response, _ = start_onboarding()
    response, pending = send_message(start_response["session_id"], edit_request)
    messages = []
    if start_response.get("assistant_message"):
        messages.append(
            {"role": "assistant", "content": start_response["assistant_message"]}
        )
    messages.append({"role": "user", "content": edit_request})
    if response.get("assistant_message"):
        messages.append(
            {"role": "assistant", "content": response["assistant_message"]}
        )

    st.session_state.onboarding_latest = response
    st.session_state.onboarding_pending = pending
    st.session_state.onboarding_messages = messages
    st.session_state.onboarding_submitting = False
    st.session_state.onboarding_flash = "기존 프로필을 불러왔습니다. 수정 결과를 확인해 주세요."


def main() -> None:
    apply_profile_style()

    if not is_logged_in():
        st.warning("로그인이 필요한 페이지입니다.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    st.markdown(
        """
        <div class="profile-header">
            <div class="profile-title">내 취업 프로필</div>
            <div class="profile-copy">온보딩에서 작성한 취업 목표와 선호 정보를 확인합니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    profile = load_profile()
    if profile is None:
        st.info("아직 작성된 취업 프로필이 없습니다.")
        if st.button("프로필 작성 시작", type="primary"):
            st.switch_page("app_pages/onboarding.py")
        return

    # 왼쪽에는 점수별 성장 캐릭터, 오른쪽에는 프로필 정보를 배치합니다.
    character_column, profile_column = st.columns([1, 2.8], gap="large")
    with character_column:
        render_character_slot(profile)
    with profile_column:
        render_profile_cards(profile)

    with st.expander("AI 채팅으로 프로필 일부 수정"):
        with st.form("profile_ai_edit_form"):
            selected_field = st.selectbox(
                "수정할 항목",
                options=list(PROFILE_FIELDS.keys()),
                format_func=lambda field: (
                    f"{PROFILE_FIELDS[field][0]} {PROFILE_FIELDS[field][1]}"
                ),
            )
            current_value = display_value(profile.get(selected_field))
            st.caption(f"현재 값: {current_value}")
            new_value = st.text_area(
                "새로운 내용",
                placeholder="선택한 항목에 적용할 내용을 입력해 주세요.",
                max_chars=1000,
            )
            edit_submitted = st.form_submit_button(
                "AI에게 수정 요청",
                use_container_width=True,
            )

        if edit_submitted:
            if not new_value.strip():
                st.warning("새로운 내용을 입력해 주세요.")
            else:
                try:
                    with st.spinner("AI가 기존 프로필을 불러오고 있습니다..."):
                        start_profile_edit(
                            profile,
                            selected_field,
                            new_value,
                        )
                    st.switch_page("app_pages/onboarding.py")
                except BackendAPIError as error:
                    st.error(error.message)

    if st.button(
        "취업 로드맵으로 이동",
        use_container_width=True,
        type="primary",
    ):
        st.switch_page("app_pages/roadmap.py")


main()
