"""Streamlit 로그인 및 화면 상태 관리."""

import time
from threading import Lock

import streamlit as st


# 로그아웃할 때 한꺼번에 지워야 하는 상태 이름을 기능별로 모아 둡니다.
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
    "assistant_pending_question",
    "assistant_initializing",
    "assistant_init_attempted",
)

ROADMAP_STATE_KEYS = (
    "roadmap_plan",
    "roadmap_proposal",
    "roadmap_loaded",
    "roadmap_busy",
    "roadmap_request_id",
    "roadmap_start_on",
    "roadmap_flash",
    "roadmap_job_updates",
    "plan_update_preview",
)


@st.cache_resource
def _get_auth_store() -> tuple[dict[str, dict], Lock]:
    """새로고침 사이에 로그인 정보를 보관하는 서버 메모리 저장소입니다."""

    return {}, Lock()


def _get_browser_key() -> str | None:
    """Streamlit이 브라우저에 발급한 쿠키로 현재 브라우저를 구분합니다."""

    try:
        return st.context.cookies.get("_streamlit_xsrf")
    except Exception:
        # 테스트 환경처럼 브라우저 요청 정보가 없는 경우에는 저장하지 않습니다.
        return None


def persist_auth_state() -> None:
    """현재 인증 정보를 브라우저별 서버 메모리에 저장합니다."""

    browser_key = _get_browser_key()
    if not browser_key or not st.session_state.get("access_token"):
        return

    auth_data = {
        key: st.session_state.get(key)
        for key in AUTH_STATE_KEYS
        if key in st.session_state
    }
    store, lock = _get_auth_store()
    with lock:
        store[browser_key] = auth_data

def clear_persisted_auth() -> None:
    """현재 브라우저에 연결된 서버 측 로그인 정보를 삭제합니다."""

    browser_key = _get_browser_key()
    if not browser_key:
        return

    store, lock = _get_auth_store()
    with lock:
        store.pop(browser_key, None)


def save_auth_tokens(result: dict, remember: bool = False) -> None:
    """로그인 또는 회원가입 응답의 토큰을 현재 Streamlit 세션에 저장합니다."""

    # session_state는 Streamlit이 화면을 다시 실행해도 값을 유지하는 저장 공간입니다.
    st.session_state["access_token"] = result["access_token"]
    st.session_state["refresh_token"] = result["refresh_token"]
    expires_at = int(time.time()) + int(result["expires_in"])
    st.session_state["expires_at"] = expires_at
    st.session_state["logged_in"] = True
    st.session_state["remember_login"] = remember

    # 토큰을 URL이나 브라우저 저장소에 노출하지 않고 서버 메모리에만 보관합니다.
    persist_auth_state()

    # 로그인 상태는 현재 Streamlit 세션 안에서만 보관합니다.
    # 외부 브라우저 저장소는 페이지 전환 충돌 때문에 사용하지 않습니다.


def restore_auth_from_browser() -> None:
    """새로고침으로 새 세션이 만들어졌을 때 로그인 정보를 복원합니다."""

    if st.session_state.get("access_token"):
        return

    browser_key = _get_browser_key()
    if not browser_key:
        return

    store, lock = _get_auth_store()
    with lock:
        auth_data = store.get(browser_key)

    if not auth_data:
        return

    expires_at = auth_data.get("expires_at")
    if expires_at and int(expires_at) <= int(time.time()):
        clear_persisted_auth()
        return

    for key, value in auth_data.items():
        st.session_state[key] = value


def get_access_token() -> str | None:
    """저장된 access token이 없으면 None을 반환합니다."""

    return st.session_state.get("access_token")


def is_logged_in() -> bool:
    """로그인 표시와 access token이 모두 있을 때만 로그인 상태로 판단합니다."""

    return bool(st.session_state.get("logged_in") and get_access_token())


def clear_auth_state() -> None:
    """로그아웃 또는 401 발생 시 사용자 관련 상태를 모두 삭제합니다."""

    # pop의 두 번째 값으로 None을 주면 해당 상태가 없어도 오류가 발생하지 않습니다.
    for key in (
        AUTH_STATE_KEYS
        + ONBOARDING_STATE_KEYS
        + ASSISTANT_STATE_KEYS
        + ROADMAP_STATE_KEYS
    ):
        st.session_state.pop(key, None)
    clear_persisted_auth()
