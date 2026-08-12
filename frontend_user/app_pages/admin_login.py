import streamlit as st


def apply_admin_style() -> None:
    """관리자 로그인 화면 전용 CSS입니다."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #111827; color: #f9fafb; }
        .block-container { max-width: 560px; padding-top: 4rem; }
        .admin-badge {
            display: inline-block; padding: 7px 12px; border-radius: 999px;
            color: #c4b5fd; background: #312e81; font-size: 13px;
            font-weight: 800;
        }
        .admin-title { color: #ffffff; font-size: 34px; font-weight: 900; margin: 18px 0 8px; }
        .admin-description { color: #9ca3af; margin-bottom: 28px; }
        .stApp label, .stApp label p { color: #f9fafb !important; }
        div[data-testid="stTextInput"] input {
            background: #1f2937; color: #ffffff; border: 1px solid #4b5563;
        }
        div[data-testid="stTextInput"] input::placeholder { color: #9ca3af; opacity: 1; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_admin_login() -> None:
    """현재는 화면만 제공하며 관리자 API는 추후 연결합니다."""

    apply_admin_style()
    st.markdown(
        """
        <span class="admin-badge">ADMIN MODE</span>
        <div class="admin-title">관리자 로그인</div>
        <div class="admin-description">
            관리자 계정으로 서비스 운영 화면에 접속합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("admin_login_form"):
        st.text_input("관리자 아이디", placeholder="admin")
        st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
        submitted = st.form_submit_button("관리자 로그인", use_container_width=True)

    if submitted:
        st.info("관리자 인증 API가 준비되면 이 버튼에 연결합니다.")

    if st.button("처음 화면으로 돌아가기", use_container_width=True):
        st.switch_page("app_pages/home.py")


show_admin_login()
