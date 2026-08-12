"""관리자 화면에서 공통으로 사용하는 다크 테마 스타일."""

import streamlit as st


def apply_admin_style() -> None:
    """관리자 페이지 전체에 같은 색상과 카드 간격을 적용합니다."""

    # 어드민 페이지마다 CSS를 반복하지 않고 이 파일에서 공통으로 관리합니다.
    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }

        .stApp {
            background: #080b16;
            color: #f5f5f7;
        }
        .block-container {
            max-width: 1280px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }
        .stApp h1, .stApp h2, .stApp h3,
        .stApp p, .stApp label,
        .stApp [data-testid="stCaptionContainer"] {
            color: #f5f5f7;
        }

        /* 왼쪽 관리자 메뉴 */
        [data-testid="stSidebar"] {
            background: #0b0d18;
            border-right: 1px solid #38203b;
        }
        [data-testid="stSidebar"] hr { border-color: #4a2947; }
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #c4b6c7 !important;
        }
        .admin-brand {
            color: #ff78c5;
            font-size: 23px;
            font-weight: 900;
        }
        .admin-status {
            display: inline-block;
            padding: 5px 9px;
            border: 1px solid #71345e;
            border-radius: 999px;
            background: #251124;
            color: #ff9fd5;
            font-size: 12px;
            font-weight: 800;
        }

        /* 모든 관리자 페이지에서 같은 상단 제목을 사용합니다. */
        .admin-kicker {
            margin-bottom: 6px;
            color: #ff78c5;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .09em;
        }
        .admin-page-title {
            color: #ffffff;
            font-size: 32px;
            font-weight: 900;
        }
        .admin-page-copy {
            margin: 6px 0 24px;
            color: #9da2b3;
        }
        .table-head {
            color: #ff9fd5;
            font-size: 12px;
            font-weight: 900;
        }
        .muted { color: #9da2b3; font-size: 13px; }

        /* Streamlit 기본 카드와 지표 */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #101421;
            border-color: #343047 !important;
            border-radius: 13px;
            box-shadow: none;
        }
        div[data-testid="stMetric"] {
            padding: 14px 16px;
            border: 1px solid #343047;
            border-radius: 11px;
            background: #101421;
        }
        div[data-testid="stMetricLabel"] p { color: #9da2b3 !important; }
        div[data-testid="stMetricValue"] { color: #ffffff; }

        /* 입력창과 선택창 */
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stSelectbox"] > div > div {
            border-color: #3b3d52;
            background: #0d111d;
            color: #f5f5f7;
        }
        div[data-testid="stTextInput"] input::placeholder,
        div[data-testid="stTextArea"] textarea::placeholder {
            color: #777b8e;
        }

        /* 사용자 화면과 같은 버튼 톤 */
        .stButton button, .stFormSubmitButton button {
            border: 1px solid #a83276;
            background: #251124;
            color: #ff78c5;
            font-weight: 800;
        }
        .stButton button[kind="primary"],
        .stFormSubmitButton button[kind="primary"] {
            border-color: #db3d91;
            background: #c72478;
            color: #ffffff;
        }
        .stButton button:hover, .stFormSubmitButton button:hover {
            border-color: #ff78c5;
            background: #3b1738;
            color: #ffffff;
        }

        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
            min-height: 42px;
            margin-bottom: 7px;
            border: 1px solid #6f3159 !important;
            border-radius: 9px;
            background: #211225 !important;
            color: #ff8dce !important;
            font-weight: 800;
        }
        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p,
        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] span {
            color: #ff8dce !important;
        }
        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
            border-color: #d34b96 !important;
            background: #32152f !important;
        }
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
            border-color: #a83276 !important;
            background: #211225 !important;
            color: #ff8dce !important;
        }

        /* 표, 탭, 진행률, 상태 메시지 */
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            overflow: hidden;
            border: 1px solid #343047;
            border-radius: 12px;
            background: #101421;
        }
        button[data-baseweb="tab"] { color: #b9bbca; }
        button[data-baseweb="tab"][aria-selected="true"] { color: #ff78c5; }
        div[data-testid="stProgress"] > div > div > div > div {
            background: #e43b99;
        }
        div[data-testid="stAlert"] {
            border: 1px solid #4b3652;
            background: #151524;
            color: #f5f5f7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, description: str) -> None:
    """관리자 페이지의 공통 제목 영역을 표시합니다."""

    st.markdown(
        f"""
        <div class="admin-kicker">{kicker}</div>
        <div class="admin-page-title">{title}</div>
        <div class="admin-page-copy">{description}</div>
        """,
        unsafe_allow_html=True,
    )
