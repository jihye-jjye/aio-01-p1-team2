"""로그인 아이디로 사용자의 로드맵 이력을 조회하는 관리자 화면."""

from __future__ import annotations

from typing import Any

import streamlit as st

from clients.loadmap_client import loadmap_from_user
from core.api_client import BackendAPIError

RESULT_STATE_KEY = "admin_roadmap_lookup_result"


def _validate_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BackendAPIError("로드맵 응답 형식이 올바르지 않습니다.")
    if not isinstance(payload.get("login_id"), str):
        raise BackendAPIError("로드맵 응답에 사용자 아이디가 없습니다.")
    if not isinstance(payload.get("items"), list):
        raise BackendAPIError("로드맵 응답에 이력 목록이 없습니다.")
    return payload


def _render_roadmap(payload: dict[str, Any]) -> None:
    items = payload["items"]
    st.success(f"{payload['login_id']} 사용자의 로드맵 {len(items)}건을 조회했습니다.")

    if not items:
        st.info("생성된 로드맵 이력이 없습니다.")
        return

    for index, item in enumerate(items):
        plan = item.get("plan") if isinstance(item, dict) else {}
        progress = item.get("progress") if isinstance(item, dict) else {}
        quests = item.get("quests") if isinstance(item, dict) else []
        plan = plan if isinstance(plan, dict) else {}
        progress = progress if isinstance(progress, dict) else {}
        quests = quests if isinstance(quests, list) else []

        title = plan.get("title") or f"로드맵 {index + 1}"
        status = plan.get("status") or "상태 미상"
        with st.expander(f"{title} · {status}", expanded=index == 0):
            period_col, task_col, progress_col = st.columns(3)
            period_col.metric(
                "기간",
                f"{plan.get('starts_on', '-')} ~ {plan.get('ends_on', '-')}",
            )
            task_col.metric("퀘스트", len(quests))

            progress_percent = progress.get("progress_percent", 0)
            if not isinstance(progress_percent, (int, float)):
                progress_percent = 0
            progress_percent = max(0, min(100, int(progress_percent)))
            progress_col.metric("진행률", f"{progress_percent}%")
            st.progress(progress_percent / 100)

            if plan.get("summary"):
                st.write(plan["summary"])

            if quests:
                quest_rows = [
                    {
                        "제목": quest.get("title", ""),
                        "종류": quest.get("kind", ""),
                        "상태": quest.get("status", ""),
                        "예정일": quest.get("scheduled_at") or "",
                    }
                    for quest in quests
                    if isinstance(quest, dict)
                ]
                st.dataframe(
                    quest_rows,
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("이 로드맵에 등록된 퀘스트가 없습니다.")


st.markdown(
    '<div class="breadcrumb">대시보드 〉 로드맵 관리</div>',
    unsafe_allow_html=True,
)
st.subheader("로드맵 관리", divider="rainbow")
st.caption("회원가입 시 사용한 로그인 아이디로 로드맵 이력을 조회합니다.")

default_login_id = st.session_state.get("selected_item_login_id", "")
with st.form("admin-roadmap-search"):
    login_id = st.text_input(
        "대상 사용자 로그인 아이디",
        value=default_login_id,
        placeholder="예: roadmap_user",
    )
    submitted = st.form_submit_button("로드맵 조회", type="primary")

if submitted:
    normalized_login_id = login_id.strip()
    if not normalized_login_id:
        st.warning("조회할 사용자 로그인 아이디를 입력해 주세요.")
        st.session_state.pop(RESULT_STATE_KEY, None)
    else:
        try:
            with st.spinner("로드맵을 조회하고 있습니다..."):
                response = loadmap_from_user(normalized_login_id)
            st.session_state[RESULT_STATE_KEY] = _validate_response(response)
        except BackendAPIError as error:
            st.session_state.pop(RESULT_STATE_KEY, None)
            st.error(str(error))

result = st.session_state.get(RESULT_STATE_KEY)
if isinstance(result, dict):
    _render_roadmap(result)
