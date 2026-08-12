from html import escape
import json
from pathlib import Path

import streamlit as st

from clients.auth_client import get_profile
from clients.onboarding_client import send_message, start_onboarding
from core.api_client import BackendAPIError
from core.session import is_logged_in


# AI와 함께 작성해 저장하는 8개 항목과 같은 순서로 보여 줍니다.
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

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
LEVEL_1_CHARACTER_IMAGE = ASSETS_DIR / "character_level_1.png"
LEVEL_2_CHARACTER_IMAGE = ASSETS_DIR / "character_level_2.png"
LEVEL_3_CHARACTER_IMAGE = ASSETS_DIR / "character_level_3.png"
LEVEL_4_CHARACTER_IMAGE = ASSETS_DIR / "character_level_4.png"


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


def display_value(value, field: str | None = None) -> str:
    """목록과 빈 값을 사용자가 읽기 쉬운 문자열로 바꿉니다."""

    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "아직 입력되지 않았습니다."
    if value in (None, ""):
        return "아직 입력되지 않았습니다."

    # 백엔드는 10:00:00+09:00처럼 타임존이 포함된 시간을 반환합니다.
    # 프로필 화면에서는 사용자가 읽기 쉬운 HH:MM까지만 표시합니다.
    if field == "daily_notification_time":
        time_parts = str(value).split(":")
        if len(time_parts) >= 2:
            return f"{time_parts[0]}:{time_parts[1]}"

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
                        f'<div class="field-value">{escape(display_value(profile.get(field), field))}</div>',
                        unsafe_allow_html=True,
                    )


def render_character_slot(profile: dict) -> None:
    """진단 점수에 맞는 성장 단계 캐릭터를 표시합니다."""

    # 백엔드의 100점 만점 진단 점수를 임시 기준으로 4개 구간에 나눕니다.
    # 팀에서 점수 구간을 확정하면 아래 숫자만 변경하면 됩니다.
    score = profile.get("assessment_score")
    try:
        numeric_score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        numeric_score = 0

    if numeric_score <= 25:
        level_label = "1단계 · 새싹"
        character_image = LEVEL_1_CHARACTER_IMAGE
        character_background = "#dce1e7"
    elif numeric_score <= 50:
        level_label = "2단계 · 성장"
        character_image = LEVEL_2_CHARACTER_IMAGE
        character_background = "#d9dce3"
    elif numeric_score <= 75:
        level_label = "3단계 · 도전"
        character_image = LEVEL_3_CHARACTER_IMAGE
        character_background = "#d9dce3"
    else:
        level_label = "4단계 · 전문가"
        character_image = LEVEL_4_CHARACTER_IMAGE
        character_background = "#d9dce3"

    # 준비된 단계 이미지는 Streamlit 기본 이미지 요소로 보여 줍니다.
    # 파일을 찾지 못한 경우에만 기존 자리 표시를 사용합니다.
    if character_image and character_image.exists():
        # 이미지 가장자리와 카드 사이가 끊겨 보이지 않도록
        # 원본 이미지에서 확인한 배경색을 캐릭터 카드에도 사용합니다.
        st.markdown(
            f"""
            <style>
            .st-key-profile_character_card {{
                background: {character_background} !important;
                padding: 8px !important;
                border-radius: 10px;
                overflow: hidden;
            }}
            .st-key-profile_character_card div[data-testid="stImage"] {{
                margin: 0 !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True, key="profile_character_card"):
            st.image(str(character_image), use_container_width=True)
    else:
        st.markdown(
            """
            <div class="character-slot">
                <div class="character-placeholder">🧑‍💻</div>
                <div class="character-caption">캐릭터 이미지 준비 중</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="character-level">{escape(level_label)}</div>',
        unsafe_allow_html=True,
    )


def start_full_profile_edit(profile: dict) -> None:
    """현재 프로필 전체를 AI 채팅에 전달해 모든 항목을 다시 검토합니다."""

    current_profile = {
        key: profile.get(key)
        for key in PROFILE_FIELDS
    }
    edit_request = (
        "아래는 현재 저장된 내 취업 프로필이야. 기존 내용을 초안으로 사용해 줘.\n"
        f"{json.dumps(current_profile, ensure_ascii=False)}\n"
        "목표 직무, 보유 기술, 경험, 목표 취업일, 희망 기업, 근무 환경, "
        "알림 시간, AI 답변 스타일을 전체적으로 다시 수정하고 싶어. "
        "한 번에 하나씩 필요한 내용을 질문하고 마지막에 수정된 전체 프로필을 검토하게 해 줘."
    )

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
    st.session_state.onboarding_flash = (
        "현재 프로필을 불러왔어요. AI와 대화하며 전체 내용을 다시 정리해 보세요."
    )


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
            <div class="profile-copy">AI와 함께 완성한 취업 목표와 선호 정보를 확인해 보세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    profile = load_profile()
    if profile is None:
        st.info("아직 작성된 취업 프로필이 없습니다.")
        if st.button("프로필 완성하러가기", type="primary"):
            st.switch_page("app_pages/onboarding.py")
        return

    # 왼쪽에는 점수별 성장 캐릭터, 오른쪽에는 프로필 정보를 배치합니다.
    character_column, profile_column = st.columns([1, 2.8], gap="large")
    with character_column:
        render_character_slot(profile)
    with profile_column:
        render_profile_cards(profile)

    st.divider()
    full_edit_column, roadmap_column = st.columns(2)
    with full_edit_column:
        if st.button(
            "AI와 전체 프로필 다시 작성하기",
            use_container_width=True,
        ):
            try:
                with st.spinner("AI가 현재 프로필을 불러오고 있어요..."):
                    start_full_profile_edit(profile)
                st.switch_page("app_pages/onboarding.py")
            except BackendAPIError as error:
                st.error(error.message)

    with roadmap_column:
        if st.button(
            "취업 로드맵으로 이동",
            use_container_width=True,
            type="primary",
        ):
            st.switch_page("app_pages/roadmap.py")


main()
