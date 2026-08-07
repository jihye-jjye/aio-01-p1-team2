import streamlit as st


def show_home() -> None:
    st.title("홈")
    st.write("좌측 메뉴를 선택하면 관련 탭이 화면에 나타납니다.")

    col1, col2, col3 = st.columns(3)
    col1.metric("접속자", "24명")
    col2.metric("로그", "128건")
    col3.metric("완료율", "76%")
