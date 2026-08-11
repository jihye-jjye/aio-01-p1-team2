from collections.abc import Mapping

import altair as alt
import pandas as pd
import streamlit as st


def _as_count(value: object) -> int:
    """API 응답의 누락값이나 문자열 값을 안전한 정수로 바꾼다."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def show_quest(quests: Mapping[str, object] | None) -> None:
    """활성 로드맵의 퀘스트 진행 현황을 요약 카드와 그래프로 보여준다."""
    st.subheader("퀘스트 진행 현황")

    if not quests:
        st.info("표시할 퀘스트 진행 정보가 없습니다.")
        return

    total = _as_count(quests.get("total"))
    completed = _as_count(quests.get("completed"))
    in_progress = _as_count(quests.get("in_progress"))
    pending = _as_count(quests.get("pending"))
    percent = min(100, _as_count(quests.get("progress_percent")))
    is_final = bool(quests.get("is_final"))

    completed_col, progress_col, pending_col = st.columns(3)
    completed_col.metric("완료", f"{completed}개")
    progress_col.metric("진행 중", f"{in_progress}개")
    pending_col.metric("대기", f"{pending}개")

    st.caption(f"전체 {total}개 중 {completed}개 완료 ({percent}%)")
    st.progress(percent, text=f"퀘스트 완료율 {percent}%")

    chart_data = pd.DataFrame(
        {
            "상태": ["완료", "진행 중", "대기"],
            "퀘스트 수": [completed, in_progress, pending],
        }
    )
    color_scale = alt.Scale(
        domain=["완료", "진행 중", "대기"],
        range=["#22c55e", "#3b82f6", "#cbd5e1"],
    )
    donut_chart = (
        alt.Chart(chart_data)
        .mark_arc(innerRadius=75)
        .encode(
            theta=alt.Theta("퀘스트 수:Q"),
            color=alt.Color("상태:N", scale=color_scale, legend=alt.Legend(title=None)),
            tooltip=["상태:N", "퀘스트 수:Q"],
        )
        .properties(height=300)
    )
    completion_label = (
        alt.Chart(pd.DataFrame({"label": [f"{percent}%"], "sub": ["완료율"]}))
        .mark_text(fontSize=28, fontWeight="bold", dy=-10)
        .encode(text="label:N")
        + alt.Chart(pd.DataFrame({"label": [f"{percent}%"], "sub": ["완료율"]}))
        .mark_text(fontSize=13, color="#64748b", dy=18)
        .encode(text="sub:N")
    )
    st.altair_chart(donut_chart + completion_label, use_container_width=True)

    if total == 0:
        st.info("활성 로드맵에 진행률로 집계되는 퀘스트가 없습니다.")
    elif is_final:
        st.caption("종료된 로드맵의 최종 진행률입니다.")
