"""Streamlit 로그인과 화면 상태를 관리합니다."""

import json
import time

import streamlit as st
from streamlit_session_browser_storage import SessionStorage


AUTH_STATE_KEYS = (
    "access_token",
    "refresh_token",
    "expires_at",
    "logged_in",
    "user",
    "profile",
    "remember_login",
    "next_screen",
    "auth_flash",
    "onboarding_flash",
    "assistant_flash",
)

ONBOARDING_STATE_KEYS = (
    "onboarding_latest",
    "onboarding_pending",
    "onboarding_submitting",
    "onboarding_messages",
)

ASSISTANT_STATE_KEYS = (
    "assistant_messages",
    "assistant_submitting",
    "assistant_session_id",
    "assistant_revision",
    "assistant_expires_at",
    "assistant_initial_message",
    "assistant_pending_question",
    "assistant_pending_request",
    "assistant_initializing",
    "assistant_init_attempted",
    "assistant_error",
)

ROADMAP_STATE_KEYS = (
    "roadmap_plan",
    "roadmap_proposal",
    "roadmap_loaded",
    "roadmap_busy",
    "roadmap_request_id",
    "roadmap_start_on",
    "roadmap_flash",
)

JOB_STATE_KEYS = (
    "jobs_loaded",
    "recommended_job",
    "jobs_error",
)

TODAY_QUEST_STATE_KEYS = (
    "today_quests_data",
    "today_quests_loaded",
    "today_quests_busy",
    "today_quests_flash",
    "today_quests_user_id",
    "today_quests_completion_popup",
)

NOTIFICATION_STATE_KEYS = (
    "notification_feed",
    "notification_popup_pending",
    "notification_login_toast_pending",
    "notification_busy",
    "notification_error",
)

# sessionStorage는 같은 브라우저 탭에서 새로고침해도 유지되고 탭을 닫으면 제거됩니다.
BROWSER_AUTH_ITEM = "job_quest_auth"
BROWSER_STORAGE_STATE_KEY = "job_quest_browser_storage"
BROWSER_AUTH_KEYS = (
    "access_token",
    "expires_at",
    "logged_in",
    "user",
    "profile",
    "remember_login",
    "next_screen",
)


def _browser_storage() -> SessionStorage:
    """현재 브라우저 탭의 sessionStorage를 엽니다."""

    return SessionStorage(key=BROWSER_STORAGE_STATE_KEY)


def persist_auth_state() -> None:
    """새로고침 복원을 위해 현재 인증 상태를 브라우저에 저장합니다."""

    if not st.session_state.get("access_token"):
        return

    auth_data = {
        key: st.session_state.get(key)
        for key in BROWSER_AUTH_KEYS
        if key in st.session_state
    }
    try:
        _browser_storage().setItem(
            BROWSER_AUTH_ITEM,
            json.dumps(auth_data, ensure_ascii=False),
            key="save_auth_to_browser",
        )
    except Exception:
        # 브라우저 저장소가 차단돼도 현재 Streamlit 세션의 로그인은 유지합니다.
        return


def sync_auth_to_browser() -> None:
    """로그인 페이지 이동이 끝난 뒤 인증 상태를 브라우저에 한 번만 저장합니다."""

    if not is_logged_in() or st.session_state.get("browser_auth_saved"):
        return

    persist_auth_state()
    st.session_state.browser_auth_saved = True


def clear_persisted_auth() -> None:
    """로그아웃할 때 브라우저에 저장한 인증 상태를 제거합니다."""

    try:
        _browser_storage().eraseItem(
            BROWSER_AUTH_ITEM,
            key="clear_auth_from_browser",
        )
    except Exception:
        return


def save_auth_tokens(result: dict, remember: bool = False) -> None:
    """로그인·회원가입 응답의 토큰을 현재 세션과 브라우저에 저장합니다."""

    st.session_state["access_token"] = result["access_token"]
    st.session_state["refresh_token"] = result["refresh_token"]
    st.session_state["expires_at"] = int(time.time()) + int(result["expires_in"])
    st.session_state["logged_in"] = True
    st.session_state["remember_login"] = remember
    # 로그인 페이지에서는 화면 이동을 먼저 하고,
    # 다음 실행에서 브라우저 저장소와 동기화합니다.
    st.session_state["browser_auth_saved"] = False


def restore_auth_from_browser() -> None:
    """새로고침 후 브라우저 sessionStorage에서 인증 상태를 복원합니다."""

    if st.session_state.get("access_token"):
        return

    try:
        saved_value = _browser_storage().getItem(BROWSER_AUTH_ITEM)
    except Exception:
        return
    if not saved_value:
        return

    try:
        auth_data = json.loads(saved_value) if isinstance(saved_value, str) else saved_value
    except (TypeError, ValueError):
        clear_persisted_auth()
        return
    if not isinstance(auth_data, dict):
        clear_persisted_auth()
        return

    expires_at = auth_data.get("expires_at")
    if expires_at and int(expires_at) <= int(time.time()):
        clear_persisted_auth()
        return

    for key in BROWSER_AUTH_KEYS:
        if key in auth_data:
            st.session_state[key] = auth_data[key]
    st.session_state.browser_auth_saved = True


def get_access_token() -> str | None:
    """현재 access token을 반환합니다."""

    return st.session_state.get("access_token")


def is_logged_in() -> bool:
    """로그인 표시와 access token이 모두 있을 때 로그인으로 판단합니다."""

    return bool(st.session_state.get("logged_in") and get_access_token())


def clear_auth_state() -> None:
    """로그아웃 또는 401 응답 시 사용자 범위 상태를 모두 제거합니다."""

    for key in (
        AUTH_STATE_KEYS
        + ONBOARDING_STATE_KEYS
        + ASSISTANT_STATE_KEYS
        + ROADMAP_STATE_KEYS
        + JOB_STATE_KEYS
        + TODAY_QUEST_STATE_KEYS
        + NOTIFICATION_STATE_KEYS
    ):
        st.session_state.pop(key, None)
    st.session_state.pop("browser_auth_saved", None)
    clear_persisted_auth()
