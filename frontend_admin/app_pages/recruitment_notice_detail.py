from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import streamlit as st


def _text(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


def _deadline_value(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _detail_info() -> Mapping[str, Any] | None:
    detail = st.session_state.get("recruitment_notice_detail")
    return detail if isinstance(detail, Mapping) else None


st.header("채용공고 상세 보기")

top_left, top_right = st.columns([5, 1])
with top_left:
    if st.button("← 뒤로가기", use_container_width=False):
        st.switch_page("app_pages/recruitment_notice.py")

detail_info = _detail_info()
if not detail_info:
    st.info("선택된 채용공고가 없습니다. 목록에서 공고를 선택해 주세요.")
    if st.button("채용공고 목록으로 이동"):
        st.switch_page("app_pages/recruitment_notice.py")
    st.stop()

extracted_data = detail_info.get("extracted_data") or {}
if not isinstance(extracted_data, Mapping):
    extracted_data = {}

with st.container(border=True):
    st.subheader("공고 기본 정보")
    with st.form("recruitment_notice_detail_form"):
        company_name = st.text_input(
            "회사명", value=_text(detail_info.get("company_name")), placeholder="회사명을 입력하세요", disabled=True
        )
        job_title = st.text_input(
            "직무", value=_text(detail_info.get("job_title")), placeholder="채용 직무를 입력하세요", disabled=True
        )

        career_options = ["신입", "경력", "신입·경력", "무관"]
        career = _text(extracted_data.get("career"), "무관")
        career_index = career_options.index(career) if career in career_options else 3
        career = st.selectbox("경력", career_options, index=career_index, disabled=True)

        deadline = _deadline_value(detail_info.get("deadline"))
        deadline_enabled = st.checkbox("마감일 지정", value=deadline is not None)
        # deadline = st.date_input("마감일", value=deadline, disabled=not deadline_enabled)
        deadline = st.date_input("마감일", value=deadline, disabled=True)

        posting_text = st.text_area(
            "설명",
            value=_text(detail_info.get("posting_text")),
            placeholder="공고 내용을 입력하세요",
            height=180,
            disabled=True
        )

        source_col, status_col = st.columns(2)
        source_col.text_input("출처", value=_text(extracted_data.get("platform") or extracted_data.get("source")), disabled=True)
        status_col.selectbox("상태", ["게시중", "마감", "비공개"], index=0, disabled=True)

        st.caption(f"공고 ID: {_text(detail_info.get('id'), '-')}")
        st.caption(f"원문 링크: {_text(detail_info.get('source_url'), '-')}")

        submitted = st.form_submit_button("수정하기", type="primary", use_container_width=True,disabled=True)

if submitted:
    st.warning("현재 관리자 API는 채용공고 조회만 지원합니다. 저장 API가 추가되면 수정 내용을 연결할 수 있습니다.")
