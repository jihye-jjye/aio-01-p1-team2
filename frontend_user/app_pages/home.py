#home.py 사용자 모드와 관리자 모드를 선택하는 첫 화면입니다.

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
ADMIN_FRONTEND_URL = os.getenv(
    "ADMIN_FRONTEND_URL",
    "https://aio-01-p1-team2-rzimyu6vqsrngdodufwbe2.streamlit.app"
)


def apply_home_style() -> None:
    """첫 화면의 카드와 버튼에 사용할 CSS를 적용합니다."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        section[data-testid="stSidebar"],
        button[data-testid="stBaseButton-headerNoPadding"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        .stApp {
            background-color: #080b16;
            background-image:
                linear-gradient(rgba(255,120,197,.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,120,197,.025) 1px, transparent 1px);
            background-size: 32px 32px;
            color: #f4f0f7;
        }
        .block-container { max-width: 1080px; padding-top: 4rem; }
        .home-title {
            color: #ffffff; text-align: center; font-size: 42px;
            font-weight: 900; letter-spacing: .04em; margin: 8px 0 10px;
        }
        .home-description {
            color: #aaa3b2; text-align: center; font-size: 17px;
            margin-bottom: 38px;
        }
        .mode-card {
            min-height: 230px; padding: 32px; background: #ffffff;
            border: 1px solid #ead5e3; border-radius: 14px;
            box-shadow: 0 14px 38px rgba(0,0,0,.22);
            text-align: center;
        }
        .mode-icon { font-size: 44px; margin-bottom: 10px; }
        .mode-card h2 { color: #c9257d; margin: 0 0 12px; }
        .mode-card p { color: #4b4350; line-height: 1.8; }
        .mode-card ul { color: #4b4350; line-height: 2; padding-left: 20px; }
        div[data-testid="stButton"] button {
            height: 52px; border-radius: 10px; font-weight: 800;
            color: #ff8dce !important; background: #251124 !important;
            border: 1px solid #b4387f !important;
        }
        div[data-testid="stLinkButton"] a {
            min-height: 52px; border-radius: 10px; font-weight: 800;
            color: #ff8dce !important; background: #251124 !important;
            border: 1px solid #b4387f !important;
        }
        div[data-testid="stButton"] button:hover,
        div[data-testid="stLinkButton"] a:hover {
            color: #ffffff !important; background: #3b1738 !important;
            border-color: #ff78c5 !important;
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
        <div class="home-title">AI CAREER COACH</div>
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
        st.link_button(
            "관리자로 시작하기",
            ADMIN_FRONTEND_URL,
            use_container_width=True,
        )

show_home()
