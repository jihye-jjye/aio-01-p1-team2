import streamlit as st  # Python 코드로 웹 화면을 만들기 위해 Streamlit을 st라는 별칭으로 가져옵니다.
from clients.chat_client import call_gemini
from frontend_user.core.auth_sample import is_logged_in
from core.api_client import BackendAPIError

def create_reply(prompt):  # 요청 본문으로 받은 데이터를 새 항목으로 저장합니다.
    return f"질문을 확인했습니다: {prompt}"  # 함수 실행 결과를 호출한 위치로 돌려줍니다.

if not is_logged_in():
    st.switch_page("app_pages/01_start.py") # 로그인 상태가 아니면 특정 페이지로 이동하게 하는 코드
else:
    st.title("대화 이력 추가")  # Streamlit 화면의 가장 큰 제목을 표시합니다.

    if "messages" not in st.session_state:  # session_state에 값이 없을 때만 초기값을 만들어 화면 재실행에도 상태를 유지합니다.
        st.session_state.messages = []  # Streamlit이 재실행되어도 유지해야 하는 화면 상태를 session_state에 저장하거나 읽습니다.

    for message in st.session_state.messages:  # Streamlit이 재실행되어도 유지해야 하는 화면 상태를 session_state에 저장하거나 읽습니다.
        with st.chat_message(message["role"]):  # 파일, 화면 영역, 로딩 상태처럼 시작과 종료가 있는 작업 범위를 만듭니다.
            st.write(message["content"])  # 문자열, 숫자, 객체를 Streamlit 화면에 출력합니다.

    prompt = st.chat_input("질문을 입력하세요")  # 채팅 입력창에서 사용자가 보낸 질문 문자열을 변수에 저장합니다.

    if prompt:  # 사용자가 채팅 입력창에 질문을 입력했을 때만 메시지 처리 로직을 실행합니다.
        with st.chat_message("user"):
            st.write(prompt)

        st.session_state.messages.append({"role": "user", "content": prompt})  # Streamlit이 재실행되어도 유지해야 하는 화면 상태를 session_state에 저장하거나 읽습니다.
        try:
            with st.spinner("AI 가 답변을 작성 중입니다...") :
                reply = call_gemini(st.session_state.user_id, prompt, st.session_state.messages)  # 백엔드 또는 AI 서비스가 만든 응답 문자열을 화면 출력용 변수에 저장합니다.
                reply = reply["data"].get("answer", "답변을 받지 못했습니다.")
            st.session_state.messages.append({"role": "assistant", "content": reply})  # Streamlit이 재실행되어도 유지해야 하는 화면 상태를 session_state에 저장하거나 읽습니다.
            st.rerun()  # session_state 변경 사항을 즉시 반영하기 위해 Streamlit 스크립트를 다시 실행합니다.
        except BackendAPIError as error:
            st.error(f"오류가 발생했습니다 : {error}")


