"""관리자 사용자 목록 화면."""

import streamlit as st

from clients.user_client import user_get_all_process
from core.api_client import BackendAPIError
from core.auth import is_logged_in
from core.datetime_format import format_created_at
from core.styles import page_header


def filtered_users(items: list[dict], keyword: str, role: str, status: str) -> list[dict]:
    """화면에서 입력한 검색어와 필터에 맞는 사용자만 반환합니다."""

    normalized_keyword = keyword.strip().casefold()
    result = []
    for item in items:
        searchable = f'{item.get("login_id", "")} {item.get("id", "")}'.casefold()
        if normalized_keyword and normalized_keyword not in searchable:
            continue
        if role != "전체" and str(item.get("role")) != role:
            continue
        is_active = bool(item.get("is_active"))
        if status == "활성" and not is_active:
            continue
        if status == "비활성" and is_active:
            continue
        result.append(item)
    return result


if not is_logged_in():
    st.warning("관리자 로그인이 필요한 페이지입니다.")
    if st.button("관리자 로그인으로 이동", type="primary"):
        st.switch_page("app_pages/start.py")
    st.stop()

page_header(
    "USER MANAGEMENT",
    "사용자 관리",
    "가입 사용자와 계정 상태, 활동 정보를 한곳에서 확인하세요.",
)

try:
    with st.spinner("사용자 정보를 불러오고 있어요..."):
        response = user_get_all_process() or {}
    items = response.get("items") or []
except BackendAPIError as error:
    st.error(f"사용자 정보를 불러오지 못했습니다. {error}")
    st.stop()

active_count = sum(1 for item in items if item.get("is_active"))
admin_count = sum(1 for item in items if item.get("role") == "admin")
metric_columns = st.columns(3)
metric_columns[0].metric("전체 사용자", f"{len(items)}명")
metric_columns[1].metric("활성 계정", f"{active_count}명")
metric_columns[2].metric("관리자", f"{admin_count}명")

st.divider()
search_column, role_column, status_column = st.columns([3, 1, 1])
with search_column:
    keyword = st.text_input(
        "사용자 검색",
        placeholder="아이디 또는 사용자 UUID 검색",
        label_visibility="collapsed",
    )
with role_column:
    selected_role = st.selectbox(
        "역할",
        ["전체", "user", "admin"],
        label_visibility="collapsed",
    )
with status_column:
    selected_status = st.selectbox(
        "상태",
        ["전체", "활성", "비활성"],
        label_visibility="collapsed",
    )

visible_items = filtered_users(items, keyword, selected_role, selected_status)
st.caption(f"조건에 맞는 사용자 {len(visible_items)}명")

if not visible_items:
    with st.container(border=True):
        st.subheader("표시할 사용자가 없습니다")
        st.caption("검색어나 필터 조건을 변경해 보세요.")
else:
    with st.container(border=True):
        header_columns = st.columns([2.2, 1, 1, 1, 1.4, 1.4, .8])
        headers = ["사용자", "역할", "EXP", "상태", "가입일", "최근 접속", "관리"]
        for column, header in zip(header_columns, headers):
            column.markdown(f'<div class="table-head">{header}</div>', unsafe_allow_html=True)
        st.divider()

        for item in visible_items:
            row_columns = st.columns([2.2, 1, 1, 1, 1.4, 1.4, .8])
            with row_columns[0]:
                st.write(f'**{item.get("login_id") or "아이디 없음"}**')
                st.caption(str(item.get("id") or "-"))
            row_columns[1].write("사용자" if item.get("role") == "user" else "관리자")
            row_columns[2].write(f'{int(item.get("user_exp") or 0)} EXP')
            row_columns[3].write("🟢 활성" if item.get("is_active") else "⚪ 비활성")
            row_columns[4].caption(format_created_at(item.get("created_at")))
            row_columns[5].caption(format_created_at(item.get("last_login_at")))

            with row_columns[6]:
                if st.button(
                    "상세",
                    key=f'user-detail-{item.get("id")}',
                    use_container_width=True,
                ):
                    st.session_state.selected_item_login_id = item.get("login_id")
                    st.switch_page("app_pages/user_management_detail.py")
            st.divider()
