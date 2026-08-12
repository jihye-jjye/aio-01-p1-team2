"""앱 전체에서 공통으로 사용하는 버튼 디자인."""

import streamlit as st


def apply_global_button_style() -> None:
    """모든 페이지의 버튼을 다크모드용 보라·분홍 색상으로 통일합니다."""

    st.markdown(
        """
        <style>
        /* 기본 버튼 */
        div[data-testid="stButton"] button,
        div[data-testid="stFormSubmitButton"] button {
            min-height: 44px;
            background: #211225 !important;
            color: #ff8dce !important;
            border: 1px solid #a63b79 !important;
            border-radius: 9px !important;
            font-weight: 800 !important;
            transition: background .15s ease, border-color .15s ease,
                        color .15s ease, box-shadow .15s ease;
        }

        /* 버튼 안의 글자와 아이콘도 같은 색상을 사용합니다. */
        div[data-testid="stButton"] button p,
        div[data-testid="stFormSubmitButton"] button p,
        div[data-testid="stButton"] button svg,
        div[data-testid="stFormSubmitButton"] button svg {
            color: inherit !important;
            fill: currentColor !important;
        }

        /* type="primary"로 만든 가장 중요한 버튼 */
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: #c02676 !important;
            color: #ffffff !important;
            border-color: #ec4899 !important;
        }

        /* 마우스를 올렸을 때 */
        div[data-testid="stButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
            background: #3b1738 !important;
            color: #ffffff !important;
            border-color: #ff78c5 !important;
            box-shadow: 0 0 0 2px rgba(255,120,197,.16) !important;
        }

        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
            background: #db2777 !important;
        }

        /* 사용할 수 없는 버튼 */
        div[data-testid="stButton"] button:disabled,
        div[data-testid="stFormSubmitButton"] button:disabled {
            background: #252433 !important;
            color: #777487 !important;
            border-color: #3a3849 !important;
            box-shadow: none !important;
            cursor: not-allowed !important;
        }

        /* 채팅 입력창 오른쪽의 전송 아이콘 버튼 */
        div[data-testid="stChatInput"] button {
            color: #ff8dce !important;
            background: #211225 !important;
            border-radius: 7px !important;
        }
        div[data-testid="stChatInput"] button:hover {
            color: #ffffff !important;
            background: #c02676 !important;
        }
        div[data-testid="stChatInput"] button:disabled {
            color: #777487 !important;
            background: #252433 !important;
        }

        /* 로그인 이후 사이드바 페이지 메뉴: 다크 배경과 핑크 글씨로 고정 */
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
            margin-bottom: 7px;
            background: #211225 !important;
            color: #ff8dce !important;
            border: 1px solid #6f3159 !important;
            border-radius: 8px !important;
        }
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p,
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] span,
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] svg {
            color: #ff8dce !important;
            fill: currentColor !important;
        }
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
            background: #2d172e !important;
            color: #ff8dce !important;
            border-color: #c34b8f !important;
        }
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
            background: #3b1738 !important;
            color: #ff9fd5 !important;
            border-color: #ec4899 !important;
            box-shadow: inset 3px 0 0 #ec4899 !important;
        }

        /* 사이드바 제목과 로그인 사용자 영역 */
        section[data-testid="stSidebar"] {
            background: #0c0e19 !important;
            border-right: 1px solid #3b203a !important;
        }
        section[data-testid="stSidebar"] h1 {
            color: #ff8dce !important;
            font-size: 23px !important;
            font-weight: 900 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stAlert"] {
            background: #211225 !important;
            color: #ff8dce !important;
            border: 1px solid #6f3159 !important;
            border-radius: 8px !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stAlert"] p,
        section[data-testid="stSidebar"] div[data-testid="stAlert"] svg {
            color: #ff8dce !important;
            fill: currentColor !important;
            font-weight: 800 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p {
            margin-top: 4px;
            color: #f3b8da !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] hr {
            border-color: #4a2947 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
