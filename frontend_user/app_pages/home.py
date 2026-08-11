#home.py 사용자 모드와 관리자 모드를 선택하는 첫 화면입니다.

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
ADMIN_FRONTEND_URL = os.getenv("ADMIN_FRONTEND_URL", "").strip().rstrip("/")


def apply_home_style() -> None:
    """첫 화면의 카드와 버튼에 사용할 CSS를 적용합니다."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp {
            background: #f6f8fc;
            color: #111827;
        }
        .block-container { max-width: 1080px; padding-top: 4rem; }
        .home-eyebrow {
            color: #7c3aed; text-align: center; font-size: 14px;
            font-weight: 800; letter-spacing: .12em;
        }
        .home-title {
            color: #111827; text-align: center; font-size: 42px;
            font-weight: 900; margin: 8px 0 10px;
        }
        .home-description {
            color: #6b7280; text-align: center; font-size: 17px;
            margin-bottom: 38px;
        }
        .mode-card {
            min-height: 285px; padding: 32px; background: #ffffff;
            border: 1px solid #e5e7eb; border-radius: 18px;
            box-shadow: 0 14px 38px rgba(15,23,42,.08);
        }
        .mode-icon { font-size: 44px; margin-bottom: 10px; }
        .mode-card h2 { color: #111827; margin: 0 0 12px; }
        .mode-card p { color: #4b5563; line-height: 1.8; }
        .mode-card ul { color: #374151; line-height: 2; padding-left: 20px; }
        div[data-testid="stButton"] button {
            height: 52px; border-radius: 10px; font-weight: 800;
        }
        .user-status {
            margin-top: 32px; padding: 15px 20px; border-radius: 10px;
            color: #4b5563; background: #ffffff; border: 1px solid #e5e7eb;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_home() -> None:
    """사용자 모드와 관리자 모드를 선택하는 첫 화면입니다."""

    apply_home_style()
    st.markdown(
        """
        <div class="home-eyebrow">AI CAREER COACH</div>
        <div class="home-title">취업 여정의 시작</div>
        <div class="home-description">
            이용하려는 모드를 선택해 주세요.
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, user_column, admin_column, _ = st.columns([0.15, 1, 1, 0.15], gap="large")

    with user_column:
        st.markdown(
            """
            <div class="mode-card">
                <div class="mode-icon">👤</div>
                <h2>사용자 모드</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("사용자로 시작하기", type="primary", use_container_width=True):
            st.switch_page("app_pages/login.py")

    with admin_column:
        st.markdown(
            """
            <div class="mode-card">
                <div class="mode-icon">🛡️</div>
                <h2>관리자 모드</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if ADMIN_FRONTEND_URL:
            st.link_button(
                "관리자로 시작하기",
                ADMIN_FRONTEND_URL,
                use_container_width=True,
            )
        else:
            st.button(
                "관리자로 시작하기",
                use_container_width=True,
                disabled=True,
            )
            st.caption("ADMIN_FRONTEND_URL 설정이 필요합니다.")

    st.markdown(
        '<div class="user-status">CONNECTED TO AI CAREER SERVICE · READY</div>',
        unsafe_allow_html=True,
    )


show_home()
