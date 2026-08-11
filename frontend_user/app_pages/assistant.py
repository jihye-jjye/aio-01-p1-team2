import streamlit as st
import streamlit.components.v1 as components
from uuid import uuid4

from clients.assistant_client import send_assistant_message, start_assistant_session
from core.api_client import BackendAPIError
from core.styles import apply_user_page_background, render_page_header


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
    if "assistant_revision" not in st.session_state:
        st.session_state.assistant_revision = 0
    if "assistant_expires_at" not in st.session_state:
        st.session_state.assistant_expires_at = None
    if "assistant_error" not in st.session_state:
        st.session_state.assistant_error = None


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
        st.session_state.assistant_revision = int(result["revision"])
        st.session_state.assistant_expires_at = result["expires_at"]
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
        #MainMenu, footer { visibility: hidden; }
        .st-key-assistant_new_chat button {
            color: #ff78c5 !important;
            background: #251124 !important;
            border: 1px solid #b4387f !important;
        }
        .st-key-assistant_new_chat button:hover {
            color: #ffffff !important;
            background: #3b1738 !important;
            border-color: #ff78c5 !important;
        }
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


def submit_message(text: str) -> bool:
    """사용자 질문을 백엔드 상담 API로 보내고 AI 답변을 저장합니다."""

    normalized_text = text.strip()
    if not normalized_text:
        return False

    session_id = st.session_state.get("assistant_session_id")
    if not session_id:
        st.session_state.assistant_error = "상담을 준비하지 못했어요. 다시 시도해 주세요."
        return False

    st.session_state.assistant_messages.append(
        {"role": "user", "content": normalized_text}
    )
    st.session_state.assistant_pending_question = normalized_text

    try:
        st.session_state.assistant_submitting = True
        with st.spinner("AI 코치가 답변을 준비하고 있어요..."):
            result = send_assistant_message(
                str(session_id),
                int(st.session_state.assistant_revision),
                normalized_text,
                request_id=str(uuid4()),
            )

        st.session_state.assistant_revision = int(result["revision"])
        st.session_state.assistant_expires_at = result["expires_at"]
        st.session_state.assistant_messages.append(
            {"role": "assistant", "content": result["assistant_message"]}
        )
        st.session_state.assistant_pending_question = None
        return True
    except BackendAPIError as error:
        st.session_state.assistant_error = error.message
        if error.code == "ASSISTANT_SESSION_EXPIRED":
            st.session_state.pop("assistant_session_id", None)
            st.session_state.assistant_revision = 0
            st.session_state.assistant_expires_at = None
            st.session_state.assistant_init_attempted = False
        return False
    finally:
        st.session_state.assistant_submitting = False


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
    apply_user_page_background()
    apply_chat_style()

    render_page_header(
        "AI CAREER CHAT",
        "AI 커리어 상담",
        "막히는 순간, AI 코치에게 바로 물어보세요.",
    )

    # 상태 알림은 페이지 제목을 가리지 않도록 공통 헤더 바로 아래에 표시합니다.
    message_area = st.empty()
    flash_message = st.session_state.pop("assistant_flash", None)
    if flash_message:
        message_area.success(flash_message)
    error_message = st.session_state.pop("assistant_error", None)
    if error_message:
        message_area.error(error_message)

    initialize_assistant_session(message_area)

    if not st.session_state.assistant_messages:
        if st.session_state.assistant_init_attempted:
            if st.button("AI 상담 초기화 다시 시도", use_container_width=True):
                st.session_state.assistant_init_attempted = False
                st.rerun()

    # 대화 내용과 입력창을 한 컨테이너에 넣어 하나의 AI 상담 화면으로 구성합니다.
    with st.container(border=True):
        with st.container(height=360, border=False):
            for message in st.session_state.assistant_messages:
                with st.chat_message(message["role"]):
                    # AI 응답과 사용자 입력은 HTML이 아닌 일반 text로 렌더링합니다.
                    st.write(message["content"])

            if not st.session_state.assistant_messages:
                st.info("AI 상담을 시작하려면 아래에 질문을 입력해 주세요.")

        scroll_to_latest_message()

        # 대화를 읽은 뒤 바로 찾을 수 있도록 입력 영역 위에 새 대화 버튼을 둡니다.
        _, new_chat_column = st.columns([4, 1.2], vertical_alignment="center")
        with new_chat_column:
            if st.button(
                "＋ 새 대화",
                use_container_width=True,
                key="assistant_new_chat",
                disabled=st.session_state.assistant_submitting,
                help="현재 화면의 대화를 비우고 새 상담을 시작합니다.",
            ):
                st.session_state.assistant_messages = []
                st.session_state.assistant_pending_question = None
                st.session_state.pop("assistant_session_id", None)
                st.session_state.assistant_revision = 0
                st.session_state.assistant_expires_at = None
                st.session_state.assistant_init_attempted = False
                st.rerun()

        # 추천 질문은 실제 입력창 바로 위에 배치합니다.
        st.caption("이런 질문은 어때요?")
        prompt_columns = st.columns(3)
        for column, prompt in zip(prompt_columns, SUGGESTED_PROMPTS):
            with column:
                if st.button(
                    prompt,
                    use_container_width=True,
                    key=f"prompt_{prompt}",
                    disabled=st.session_state.assistant_submitting,
                ):
                    submit_message(prompt)
                    st.rerun()

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
