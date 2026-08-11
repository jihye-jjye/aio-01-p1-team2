import streamlit as st
import streamlit.components.v1 as components

from clients.assistant_client import start_assistant_session
from core.api_client import BackendAPIError


SUGGESTED_PROMPTS = [
    "내 프로필에 맞는 채용공고를 추천해 줘",
    "오늘 공부할 내용을 알려줘",
    "현재 취업 로드맵을 점검해 줘",
]


def initialize_chat_state() -> None:
    """AI 상담 화면에서 사용할 메시지와 요청 상태를 준비합니다."""

    if "assistant_messages" not in st.session_state:
        # 시작 메시지는 백엔드 응답을 받은 뒤 추가합니다.
        st.session_state.assistant_messages = []
    if "assistant_submitting" not in st.session_state:
        st.session_state.assistant_submitting = False
    if "assistant_pending_question" not in st.session_state:
        st.session_state.assistant_pending_question = None
    if "assistant_initializing" not in st.session_state:
        st.session_state.assistant_initializing = False
    if "assistant_init_attempted" not in st.session_state:
        st.session_state.assistant_init_attempted = False


def initialize_assistant_session(message_area) -> None:
    """페이지 최초 진입 시 백엔드 상담 세션을 한 번 생성합니다."""

    # 이미 만든 세션이 있으면 새 세션을 중복 생성하지 않습니다.
    if st.session_state.get("assistant_session_id"):
        return
    if st.session_state.assistant_init_attempted:
        return

    st.session_state.assistant_init_attempted = True
    st.session_state.assistant_initializing = True
    try:
        # spinner는 백엔드 응답을 기다리는 동안 사용자에게 진행 상태를 보여 줍니다.
        with st.spinner("AI 상담을 준비하고 있습니다..."):
            result = start_assistant_session()
        st.session_state.assistant_session_id = result["session_id"]
        st.session_state.assistant_messages = [
            {
                "role": "assistant",
                "content": result["assistant_message"],
            }
        ]
    except BackendAPIError as error:
        message_area.error(error.message)
    finally:
        st.session_state.assistant_initializing = False


def apply_chat_style() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #f5f7fb; color: #111827; }
        .block-container { max-width: 1100px; padding-top: 2.3rem; }
        .chat-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 24px; background: #ffffff; border: 1px solid #e5e7eb;
            border-radius: 16px; box-shadow: 0 8px 24px rgba(15,23,42,.06);
            margin-bottom: 20px;
        }
        .chat-title { color: #111827; font-size: 25px; font-weight: 900; }
        .chat-subtitle { color: #6b7280; font-size: 14px; margin-top: 4px; }
        .online-badge {
            padding: 7px 11px; border-radius: 999px; color: #15803d;
            background: #dcfce7; font-size: 12px; font-weight: 800;
        }
        .suggestion-title { color: #6b7280; font-size: 13px; font-weight: 700; }
        div[data-testid="stChatMessage"] {
            background: #ffffff; border: 1px solid #e5e7eb;
            border-radius: 14px; padding: 8px 12px; margin-bottom: 10px;
        }
        /* 밝은 배경에서도 잘 보이는 진한 핑크로 모든 대화 텍스트를 고정합니다. */
        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] li,
        div[data-testid="stChatMessage"] strong,
        div[data-testid="stChatMessage"] code {
            color: #be185d !important;
        }
        div[data-testid="stChatMessage"] code {
            background: #fce7f3 !important;
        }
        /* 사용자 답변은 AI 메시지와 구분되도록 흰색으로 표시합니다. */
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            background: #4a1d3d;
            border-color: #be185d;
        }
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) li,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) strong,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) code {
            color: #ffffff !important;
        }
        div[data-testid="stChatInput"] {
            width: 100%; margin: 0; padding: 8px 0 0;
        }
        div[data-testid="stChatInput"] > div {
            background: #ffffff; border: 1px solid #d1d5db;
        }
        div[data-testid="stChatInput"] textarea { color: #111827 !important; }
        div[data-testid="stChatInput"] textarea::placeholder {
            color: #6b7280 !important; opacity: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def submit_message(text: str) -> None:
    """질문을 화면 상태에 저장합니다. API 호출은 client 연결 단계에서 추가합니다."""

    normalized_text = text.strip()
    if not normalized_text:
        return

    # 아직 실제 전송 전이므로 사용자 질문과 미처리 질문 상태만 저장합니다.
    st.session_state.assistant_messages.append(
        {"role": "user", "content": normalized_text}
    )
    st.session_state.assistant_pending_question = normalized_text


def scroll_to_latest_message() -> None:
    """고정 높이 상담 영역을 가장 최근 메시지 위치로 이동합니다."""

    # st.container(height=...)는 스크롤바만 만들고 자동 이동은 하지 않습니다.
    components.html(
        """
        <script>
        setTimeout(() => {
            const parentDocument = window.parent.document;
            const wrappers = parentDocument.querySelectorAll(
                '[data-testid="stVerticalBlockBorderWrapper"]'
            );

            for (let index = wrappers.length - 1; index >= 0; index -= 1) {
                const elements = wrappers[index].querySelectorAll('div');
                for (const element of elements) {
                    const style = window.parent.getComputedStyle(element);
                    const scrollable = ['auto', 'scroll'].includes(style.overflowY);
                    if (scrollable && element.scrollHeight > element.clientHeight) {
                        element.scrollTop = element.scrollHeight;
                        return;
                    }
                }
            }
        }, 100);
        </script>
        """,
        height=0,
        scrolling=False,
    )


def show_assistant() -> None:
    """AI 상담 헤더, 추천 질문, 대화 목록, 입력 폼을 순서대로 표시합니다."""

    initialize_chat_state()
    apply_chat_style()

    message_area = st.empty()

    flash_message = st.session_state.pop("assistant_flash", None)
    if flash_message:
        message_area.success(flash_message)

    initialize_assistant_session(message_area)

    st.markdown(
        """
        <div class="chat-header">
            <div>
                <div class="chat-title">AI 커리어 코치</div>
                <div class="chat-subtitle">취업 준비에 필요한 내용을 편하게 질문해 주세요.</div>
            </div>
            <div class="online-badge">● UI READY</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_left, top_right = st.columns([4, 1])
    with top_right:
        if st.button("새 대화", use_container_width=True):
            st.session_state.assistant_messages = []
            st.session_state.assistant_pending_question = None
            st.session_state.pop("assistant_session_id", None)
            st.session_state.assistant_init_attempted = False
            st.rerun()

    st.markdown('<div class="suggestion-title">추천 질문</div>', unsafe_allow_html=True)
    prompt_columns = st.columns(3)
    for column, prompt in zip(prompt_columns, SUGGESTED_PROMPTS):
        with column:
            if st.button(prompt, use_container_width=True, key=f"prompt_{prompt}"):
                submit_message(prompt)
                st.rerun()

    st.divider()

    if not st.session_state.assistant_messages:
        if st.session_state.assistant_init_attempted:
            if st.button("AI 상담 초기화 다시 시도", use_container_width=True):
                st.session_state.assistant_init_attempted = False
                st.rerun()

    # 대화 내용과 입력창을 한 컨테이너에 넣어 하나의 AI 상담 화면으로 구성합니다.
    with st.container(border=True):
        with st.container(height=410, border=False):
            for message in st.session_state.assistant_messages:
                with st.chat_message(message["role"]):
                    # AI 응답과 사용자 입력은 HTML이 아닌 일반 text로 렌더링합니다.
                    st.write(message["content"])

            if not st.session_state.assistant_messages:
                st.info("AI 상담을 시작하려면 아래에 질문을 입력해 주세요.")

            if st.session_state.assistant_pending_question:
                st.info("질문이 화면 상태에 저장되었습니다. AI API 연결 후 응답을 표시합니다.")

        scroll_to_latest_message()

        # 컨테이너 안에서 사용하면 입력창이 대화 영역 바로 아래에 표시됩니다.
        user_text = st.chat_input(
            "예: 내게 맞는 백엔드 개발자 공고를 추천해 줘",
            max_chars=4000,
            disabled=st.session_state.assistant_submitting,
        )

    if user_text:
        submit_message(user_text)
        st.rerun()


show_assistant()
