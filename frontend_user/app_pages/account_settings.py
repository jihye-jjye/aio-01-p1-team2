"""로그인 아이디와 사용자 이름을 수정하는 계정 설정 페이지입니다."""

import re

import streamlit as st

from clients.auth_client import delete_me, update_me
from core.api_client import BackendAPIError
from core.session import clear_auth_state, is_logged_in, persist_auth_state
from core.styles import apply_user_page_background, render_page_header


LOGIN_ID_PATTERN = re.compile(r"^[a-z0-9._-]{4,50}$")


def show_error(error: BackendAPIError) -> None:
    """백엔드 오류를 사용자가 이해하기 쉬운 문장으로 보여줍니다."""

    messages = {
        "LOGIN_ID_ALREADY_EXISTS": "이미 사용 중인 아이디입니다.",
        "ACCOUNT_NOT_FOUND": "수정할 계정을 찾을 수 없습니다.",
        "VALIDATION_ERROR": "입력한 내용을 다시 확인해 주세요.",
    }
    st.error(messages.get(error.code, error.message))


def validate_values(
    login_id: str,
    user_name: str,
    original_login_id: str,
    original_user_name: str,
) -> list[str]:
    """아이디와 이름이 입력 규칙에 맞는지 확인합니다."""

    errors = []
    normalized_login_id = login_id.strip().casefold()
    normalized_user_name = user_name.strip()

    # 백엔드는 아이디와 이름 중 한 항목만 보내는 부분 수정을 허용합니다.
    # 따라서 입력한 항목만 형식을 검사하고, 두 항목이 모두 비었을 때만 막습니다.
    if normalized_login_id and not LOGIN_ID_PATTERN.fullmatch(normalized_login_id):
        errors.append("아이디는 영문 소문자, 숫자, 점, 밑줄, 하이픈으로 4~50자여야 합니다.")

    if normalized_user_name and len(normalized_user_name) > 50:
        errors.append("이름은 50자 이하로 입력해 주세요.")

    if not normalized_login_id and not normalized_user_name:
        errors.append("수정할 아이디 또는 이름을 입력해 주세요.")

    login_id_changed = bool(
        normalized_login_id and normalized_login_id != original_login_id
    )
    user_name_changed = bool(
        normalized_user_name and normalized_user_name != original_user_name
    )
    if (normalized_login_id or normalized_user_name) and not (
        login_id_changed or user_name_changed
    ):
        errors.append("변경된 내용이 없습니다.")

    return errors


def submit_update(
    login_id: str,
    user_name: str,
    original_login_id: str,
    original_user_name: str,
) -> None:
    """변경된 항목만 백엔드로 보내고 화면의 로그인 정보도 갱신합니다."""

    normalized_login_id = login_id.strip().casefold()
    normalized_user_name = user_name.strip()

    result = update_me(
        login_id=(
            normalized_login_id
            if normalized_login_id
            and normalized_login_id != original_login_id
            else None
        ),
        user_name=(
            normalized_user_name
            if normalized_user_name
            and normalized_user_name != original_user_name
            else None
        ),
    )

    current_user = st.session_state.get("user") or {}
    st.session_state.user = {**current_user, **(result or {})}
    persist_auth_state()
    st.session_state.account_settings_flash = "사용자 정보가 수정되었습니다."


def render_delete_account() -> None:
    """오입력을 막기 위한 확인 절차와 회원 탈퇴 버튼을 표시합니다."""

    st.divider()
    st.subheader("회원 탈퇴")
    st.caption("탈퇴하면 프로필, 로드맵, 퀘스트 기록이 영구 삭제되며 복구할 수 없어요.")

    with st.expander("회원 탈퇴 진행하기"):
        st.warning("계속하려면 아래 입력창에 회원탈퇴를 입력해 주세요.")

        with st.form("delete_account_form"):
            confirmation = st.text_input(
                "탈퇴 확인",
                placeholder="회원탈퇴",
            )
            delete_submitted = st.form_submit_button(
                "계정 영구 삭제",
                use_container_width=True,
            )

        if delete_submitted:
            if confirmation.strip() != "회원탈퇴":
                st.warning("탈퇴를 진행하려면 회원탈퇴를 정확히 입력해 주세요.")
            else:
                try:
                    with st.spinner("계정 정보를 삭제하고 있어요..."):
                        delete_me()
                    clear_auth_state()
                    st.switch_page("app_pages/home.py")
                except BackendAPIError as error:
                    show_error(error)


def main() -> None:
    """사용자 정보 수정 화면을 표시합니다."""

    # 로그인 이후 다른 사용자 페이지와 같은 배경과 상단 간격을 사용합니다.
    apply_user_page_background()

    if not is_logged_in():
        st.warning("로그인이 필요한 페이지입니다.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    render_page_header(
        "ACCOUNT SETTINGS",
        "사용자 정보 수정",
        "로그인 아이디와 서비스에서 사용할 이름을 변경할 수 있어요.",
    )

    flash_message = st.session_state.pop("account_settings_flash", None)
    if flash_message:
        st.success(flash_message)

    user = st.session_state.get("user") or {}
    original_login_id = str(user.get("login_id") or "")
    original_user_name = str(user.get("user_name") or "")

    with st.container(border=True):
        with st.form("account_settings_form"):
            login_id = st.text_input(
                "아이디",
                value=original_login_id,
                placeholder="4자 이상",
                max_chars=50,
            )
            user_name = st.text_input(
                "이름",
                value=original_user_name,
                placeholder="서비스에서 사용할 이름",
                max_chars=50,
            )
            submitted = st.form_submit_button(
                "변경 내용 저장",
                type="primary",
                use_container_width=True,
            )

    if submitted:
        errors = validate_values(
            login_id,
            user_name,
            original_login_id,
            original_user_name,
        )
        if errors:
            for message in errors:
                st.warning(message)
        else:
            try:
                with st.spinner("사용자 정보를 수정하고 있어요..."):
                    submit_update(
                        login_id,
                        user_name,
                        original_login_id,
                        original_user_name,
                    )
                st.rerun()
            except BackendAPIError as error:
                show_error(error)

    render_delete_account()


main()
