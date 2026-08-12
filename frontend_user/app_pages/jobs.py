"""사용자 추천 공고 """

from datetime import date
from pathlib import Path
import re

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import streamlit as st

from clients.job_client import get_recommended_job
from core.api_client import BackendAPIError
from core.session import is_logged_in
from core.styles import apply_user_page_background, render_page_header


JOB_HIRING_IMAGE = (
    Path(__file__).resolve().parents[1] / "assets" / "job_hiring_board.png"
)


def initialize_state() -> None:
    """페이지가 다시 실행돼도 추천 결과를 유지합니다."""

    defaults = {
        "jobs_loaded": False,
        "recommended_job": None,
        "jobs_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_header() -> None:
    """로드맵 페이지와 같은 구조로 추천 공고 페이지 제목을 표시합니다."""

    render_page_header(
        "AI JOB MATCH",
        "AI 추천 공고",
        "내 프로필을 읽고, 지금 지원해 볼 만한 포지션만 골랐어요.",
    )


def load_recommendation() -> None:
    """희망 근무 환경 기반 추천 공고 한 건을 백엔드에서 조회합니다."""

    if st.session_state.jobs_loaded:
        return

    st.session_state.jobs_error = None
    try:
        st.session_state.recommended_job = get_recommended_job()
        st.session_state.jobs_loaded = True
    except BackendAPIError as error:
        st.session_state.recommended_job = None
        st.session_state.jobs_error = error


def extracted_text(job: dict, keys: tuple[str, ...], default: str) -> str:
    """공고의 구조화 데이터에서 여러 후보 필드 중 실제 값을 찾습니다."""

    extracted = job.get("extracted_data") or {}
    for key in keys:
        value = extracted.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            return ", ".join(map(str, value))
        return str(value)
    return default


def deadline_label(deadline: str | None) -> str:
    """마감일을 D-day 형태로 표시합니다."""

    if not deadline:
        return "상시"
    try:
        remaining = (date.fromisoformat(deadline) - date.today()).days
    except ValueError:
        return str(deadline)
    if remaining < 0:
        return "마감"
    if remaining == 0:
        return "D-DAY"
    return f"D-{remaining}"


def normalize_skills(value: object) -> list[str]:
    """API의 역량 값을 화면에서 사용할 문자열 목록으로 정리합니다."""

    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_gap_reason(reason: str) -> dict[str, str]:
    """AI 추천 이유 문장을 추천·준비·부족 구간으로 나눕니다."""

    labels = {
        "추천 이유": "matched_summary",
        "지원 준비": "preparation",
        "부족한 부분": "missing_summary",
    }
    sections = {
        "matched_summary": "",
        "preparation": "",
        "missing_summary": "",
    }
    pattern = r"(추천 이유|지원 준비|부족한 부분)\s*:\s*"
    parts = re.split(pattern, reason)
    for index in range(1, len(parts), 2):
        label = parts[index]
        content = parts[index + 1].strip() if index + 1 < len(parts) else ""
        sections[labels[label]] = content
    return sections


def gap_analysis(recommendation: dict, job: dict) -> dict:
    """백엔드가 GAP 분석 필드를 제공한 경우에만 해당 값을 반환합니다."""

    extracted = job.get("extracted_data") or {}
    matched = normalize_skills(
        recommendation.get("matched_skills")
        or extracted.get("matched_skills")
    )
    missing = normalize_skills(
        recommendation.get("missing_skills")
        or extracted.get("missing_skills")
    )
    comment = str(
        recommendation.get("reason")
        or recommendation.get("recommendation")
        or extracted.get("recommendation")
        or ""
    ).strip()
    reason_sections = parse_gap_reason(comment)
    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "matched_summary": reason_sections["matched_summary"],
        "missing_summary": reason_sections["missing_summary"],
        "recommendation": reason_sections["preparation"] or comment,
        "available": bool(
            matched
            or missing
            or reason_sections["matched_summary"]
            or reason_sections["missing_summary"]
            or reason_sections["preparation"]
        ),
    }


def render_match_chart(score: int) -> None:
    """추천 점수를 도넛형 적합도 그래프로 표시합니다."""

    score = max(0, min(int(score), 100))
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    korean_font = (
        FontProperties(fname=str(font_path))
        if font_path.exists()
        else FontProperties()
    )

    figure, axis = plt.subplots(figsize=(2, 2))
    axis.pie(
        [score, 100 - score],
        startangle=90,
        counterclock=False,
        colors=["#ec4899", "#292738"],
        wedgeprops={"width": 0.18, "edgecolor": "none"},
    )
    axis.text(
        0, 0.12, f"{score}%",
        ha="center", va="center",
        fontsize=18, fontweight="bold", color="#ec4899",
    )
    axis.text(
        0, -0.18, "적합도",
        ha="center", va="center",
        fontsize=9, color="#b8b4c2",
        fontproperties=korean_font,
    )
    axis.axis("equal")
    axis.axis("off")
    figure.patch.set_alpha(0)
    axis.set_facecolor("none")
    figure.subplots_adjust(left=0, right=1, top=1, bottom=0)
    st.pyplot(figure, use_container_width=True)
    plt.close(figure)


def show_api_error(error: BackendAPIError) -> None:
    """추천 API 오류를 사용자용 문장으로 표시합니다."""

    if error.status_code == 401:
        st.error("로그인이 만료됐어요. 다시 로그인해 주세요.")
    elif error.code == "PROFILE_NOT_FOUND":
        st.warning("AI가 분석할 취업 프로필을 먼저 완성해 주세요.")
        if st.button("프로필 완성하러가기", type="primary"):
            st.switch_page("app_pages/onboarding.py")
    else:
        st.error(f"추천 공고를 불러오지 못했어요. {error.message}")


def render_recommendation(recommendation: dict) -> None:
    """추천 공고와 백엔드 GAP 분석 결과를 카드로 표시합니다."""

    job = recommendation.get("job") or {}
    score = int(recommendation.get("match_score") or 0)
    analysis = gap_analysis(recommendation, job)
    recommendation_source = str(
        recommendation.get("recommendation_source") or "rule"
    ).lower()
    preferred_environment = str(
        recommendation.get("preferred_environment") or ""
    ).strip()
    company_name = str(job.get("company_name") or "회사명 미정")
    experience = extracted_text(
        job,
        ("experience", "experience_level", "career", "career_level"),
        "경력 협의",
    )
    location = extracted_text(
        job,
        ("location", "work_location", "region", "workplace"),
        "근무지역 미정",
    )

    with st.container(border=True):
        logo_column, job_column, deadline_column, source_column = st.columns(
            [0.9, 3.5, 0.8, 1.3],
            vertical_alignment="center",
        )
        with logo_column:
            if JOB_HIRING_IMAGE.exists():
                st.image(str(JOB_HIRING_IMAGE), use_container_width=True)
            else:
                st.write("💼")
        with job_column:
            st.caption("AI PICK")
            st.subheader(job.get("job_title") or "직무명 미정")
            st.caption(f"{company_name} · {experience} · {location}")
        with deadline_column:
            st.caption("마감")
            st.subheader(deadline_label(job.get("deadline")))
        with source_column:
            if job.get("source_url"):
                st.link_button(
                    "공고 보러가기",
                    job["source_url"],
                    use_container_width=True,
                )
            else:
                st.button("원문 링크 없음", disabled=True, use_container_width=True)

        st.divider()
        score_column, analysis_column = st.columns([1.1, 3.9], vertical_alignment="center")
        with score_column:
            render_match_chart(score)
        with analysis_column:
            st.write(f"**AI 적합도 {score}점**")
            if score > 0:
                st.markdown("#### 지금 나에게 적절한 포지션이에요")
            else:
                st.markdown("#### 최신 공고를 먼저 보여드렸어요")
            if preferred_environment:
                st.caption(f"내 희망 환경 · {preferred_environment}")
            matched_terms = recommendation.get("matched_terms") or []
            if matched_terms:
                st.caption("환경 매칭 · " + " · ".join(map(str, matched_terms)))

            if analysis["available"]:
                matched_column, missing_column = st.columns(2)
                with matched_column:
                    st.markdown("**현재 충족**")
                    if analysis["matched_skills"]:
                        for skill in analysis["matched_skills"]:
                            st.write(f"✅ {skill}")
                    else:
                        st.write(analysis["matched_summary"] or "분석 결과 없음")
                with missing_column:
                    st.markdown("**보완 필요**")
                    if analysis["missing_skills"]:
                        for skill in analysis["missing_skills"]:
                            st.write(f"△ {skill}")
                    else:
                        st.write(analysis["missing_summary"] or "추가 보완사항 없음")
            else:
                st.info("역량 GAP 분석 API 연결 후 충족·보완 역량이 표시됩니다.")

        if analysis["recommendation"]:
            with st.container(border=True):
                source_label = (
                    "AI RECOMMENDATION"
                    if recommendation_source == "llm"
                    else "MATCH REASON"
                )
                st.caption(source_label)
                st.write(analysis["recommendation"])

        st.divider()
        roadmap_column, today_column = st.columns(2)
        with roadmap_column:
            if st.button(
                "내 로드맵 확인하기",
                type="primary",
                use_container_width=True,
            ):
                st.switch_page("app_pages/roadmap.py")
        with today_column:
            if st.button("오늘의 할 일 보기", use_container_width=True):
                st.switch_page("app_pages/today_quests.py")


def main() -> None:
    """로그인 상태에 따라 실제 추천 공고 화면을 실행합니다."""

    initialize_state()
    apply_user_page_background()
    if not is_logged_in():
        st.warning("로그인하면 내 프로필에 맞는 공고를 추천받을 수 있어요.")
        if st.button("로그인으로 이동", type="primary"):
            st.switch_page("app_pages/login.py")
        return

    render_header()

    if not st.session_state.jobs_loaded:
        with st.spinner("AI가 내 프로필과 공고를 비교하고 있어요..."):
            load_recommendation()

    error = st.session_state.jobs_error
    if error:
        show_api_error(error)
        return

    recommendation = st.session_state.recommended_job
    if not recommendation:
        st.info("현재 추천할 수 있는 저장 공고가 없어요.")
        return

    render_recommendation(recommendation)


main()
