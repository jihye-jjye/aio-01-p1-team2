"""로그인 후 미확인 퀘스트 알림을 화면 중앙 팝업으로 표시합니다."""

import streamlit as st

from clients.notification_client import mark_notification_read
from core.api_client import BackendAPIError


def _notifications(feed: dict) -> list[dict]:
    """다가오는 일정과 변경 알림을 화면 표시 순서로 합칩니다."""

    upcoming = feed.get("upcoming") or []
    changes = feed.get("changes") or []
    return [item for item in [*upcoming, *changes] if isinstance(item, dict)]


def _remove_notification(notification_id: str) -> None:
    """읽은 알림을 현재 화면 feed에서 제거합니다."""

    feed = st.session_state.get("notification_feed") or {}
    for key in ("upcoming", "changes"):
        feed[key] = [
            item
            for item in feed.get(key) or []
            if str(item.get("id")) != notification_id
        ]
    feed["unread_count"] = max(0, int(feed.get("unread_count") or 0) - 1)
    st.session_state.notification_feed = feed
    st.session_state.notification_popup_pending = bool(_notifications(feed))


def _confirm_notification(notification: dict) -> bool:
    """사용자가 확인한 알림을 명세에 따라 서버에서 읽음 처리합니다."""

    notification_id = str(notification.get("id") or "")
    if not notification_id:
        st.error("알림 ID를 확인할 수 없습니다.")
        return False

    try:
        st.session_state.notification_busy = True
        with st.spinner("알림을 확인하고 있어요..."):
            mark_notification_read(notification_id)
        _remove_notification(notification_id)
        return True
    except BackendAPIError as error:
        st.error(error.message)
        return False
    finally:
        st.session_state.notification_busy = False


@st.dialog("🔔 오늘의 퀘스트", width="small")
def _show_notification_content(notification: dict) -> None:
    """알림 요약과 행동 버튼을 화면 중앙 다이얼로그에 표시합니다."""

    title = str(notification.get("title") or "오늘의 퀘스트가 도착했어요")
    message = str(
        notification.get("message") or "오늘 진행할 할 일을 확인해 보세요."
    )
    st.subheader(title)
    st.write(message)

    payload = notification.get("payload") or {}
    schedules = payload.get("schedules") or []
    for schedule in schedules[:3]:
        st.write(f'• {schedule.get("title") or "할 일"}')

    remaining = len(_notifications(st.session_state.get("notification_feed") or {}))
    st.caption(f"미확인 알림 {remaining}개")

    move_column, confirm_column = st.columns(2)
    with move_column:
        if st.button(
            "오늘 할 일 보기",
            type="primary",
            use_container_width=True,
            key="notification_go_to_today",
            disabled=st.session_state.get("notification_busy", False),
        ):
            if _confirm_notification(notification):
                st.session_state.notification_popup_pending = False
                st.switch_page("app_pages/today_quests.py")

    with confirm_column:
        if st.button(
            "확인",
            use_container_width=True,
            key="notification_confirm",
            disabled=st.session_state.get("notification_busy", False),
        ):
            if _confirm_notification(notification):
                st.rerun()


def render_notification_popup() -> None:
    """미확인 알림이 있을 때 화면 중앙에 팝업을 표시합니다."""

    # 예전 토스트 표시 상태는 소비만 하고 별도의 팝업을 띄우지 않습니다.
    st.session_state.pop("notification_login_toast_pending", False)

    error_message = st.session_state.pop("notification_error", None)
    if error_message:
        st.toast(error_message, icon="⚠️")

    items = _notifications(st.session_state.get("notification_feed") or {})
    if not items:
        st.session_state.notification_popup_pending = False
        return

    if "notification_busy" not in st.session_state:
        st.session_state.notification_busy = False

    _show_notification_content(items[0])
