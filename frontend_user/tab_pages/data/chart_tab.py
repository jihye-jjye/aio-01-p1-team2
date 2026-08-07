import pandas as pd
import streamlit as st

from frontend_user.core.auth_sample import is_logged_in


def show_chart() -> None:
    st.subheader("차트")

    if not is_logged_in():
        st.warning("로그인이 필요한 화면입니다.")
        return

    data = {
        "주차": [1, 2, 3, 4],
        "학습 시간": [3, 5, 4, 7],
    }
    dataframe = pd.DataFrame(data).set_index("주차")

    st.dataframe(dataframe, use_container_width=True)
    st.line_chart(dataframe)
