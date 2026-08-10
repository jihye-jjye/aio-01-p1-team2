import streamlit as st
import pandas as pd

from core.api_client import BackendAPIError

st.markdown(
    '<div class="breadcrumb">대시보드 〉 사용자 관리</div>',
    unsafe_allow_html=True
)

st.subheader("사용자 관리", divider="rainbow")

# ---------------------------------------------------------
# Search / Filter Area
# ---------------------------------------------------------
search_col, role_col, status_col, button_col = st.columns(
    [4, 1.5, 1.5, 1.3]
)

with search_col:
    keyword = st.text_input(
        "사용자 검색",
        placeholder="사용자 검색 (이름, ID)",
        label_visibility="collapsed"
    )

with role_col:
    selected_role = st.selectbox(
        "역할",
        ["전체 역할", "일반", "관리자"],
        label_visibility="collapsed"
    )

with status_col:
    selected_status = st.selectbox(
        "상태",
        ["전체 상태", "활성", "비활성"],
        label_visibility="collapsed"
    )

with button_col:
    add_user = st.button(
        "＋ 사용자 추가",
        type="primary",
        use_container_width=True
    )

user_infos = [
    {
        "ID": "1001",
        "이름": "김혜준",
        "아이디": "kim@example.com",
        "역할": "일반",
        "레벨": "Lv.5",
        "상태": "활성",
        "가입일": "2024-06-16"
    },
    {
        "ID": "1002",
        "이름": "이준",
        "아이디": "lee@example.com",
        "역할": "일반",
        "레벨": "Lv.3",
        "상태": "활성",
        "가입일": "2024-06-17"
    },
    {
        "ID": "1003",
        "이름": "박민규",
        "아이디": "park@example.com",
        "역할": "일반",
        "레벨": "Lv.7",
        "상태": "활성",
        "가입일": "2024-06-15"
    },
    {
        "ID": "1004",
        "이름": "최태영",
        "아이디": "choi@example.com",
        "역할": "일반",
        "레벨": "Lv.2",
        "상태": "비활성",
        "가입일": "2024-06-15"
    },
    {
        "ID": "1005",
        "이름": "정하늘",
        "아이디": "jung@example.com",
        "역할": "일반",
        "레벨": "Lv.6",
        "상태": "활성",
        "가입일": "2024-06-14"
    }
]

items = user_infos or []
with st.container(border=True):
    # ID / 이름 / 아이디 / 역할 / 레벨 / 상태 / 가입일 / 관리
    column_widths = [0.8, 1.0, 2.0, 0.8, 0.8, 0.9, 1.2, 1.8]

    # 헤더
    header_cols = st.columns(column_widths)
    headers = ["ID", "이름", "아이디", "역할", "레벨", "상태", "가입일", "관리"]

    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    st.divider()

    # 행
    for item in user_infos:
        row_cols = st.columns(column_widths)

        row_cols[0].write(item["ID"])
        row_cols[1].write(item["이름"])
        row_cols[2].write(item["아이디"])
        row_cols[3].write(item["역할"])
        row_cols[4].write(item["레벨"])
        row_cols[5].write(item["상태"])
        row_cols[6].write(item["가입일"])

        # 마지막 '관리' 컬럼
        with row_cols[7]:
            edit_col, delete_col = st.columns(2)

            with edit_col:
                if st.button(
                    "수정",
                    key=f"user-edit-{item['ID']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_item_id = item["ID"]
                    # 여기서 수정 페이지 또는 수정 폼을 열기

            with delete_col:
                if st.button(
                    "삭제",
                    key=f"user-delete-{item['ID']}",
                    use_container_width=True,
                ):
                    st.session_state.delete_item_id = item["ID"]
                    # 여기서 삭제 확인창 또는 삭제 API 호출

        st.divider()


# with st.container(border=True) : 
#     # st.subheader("", divider="rainbow")
#     with st.spinner("사용자 정보 조회 중") :
#         # response = httpx.get(f"{server_URL}/product/getall", timeout=5.0)
#         response = user_infos
#         if response is not None :
#             # result_data = response.json()
#             # data = result_data["data"]
#             df = pd.DataFrame(response)
#             select_event = st.dataframe(response, use_container_width=True, selection_mode="single-row", on_select="rerun")
#             if select_event.selection.rows :
#                 row_index = select_event.selection.rows[0]
#                 selected_row = df.iloc[row_index].to_dict()
#                 edit_col, delete_col, _ = st.columns([1, 1, 5])

#                 with edit_col:
#                     if st.button("수정", key="selected-user-edit", use_container_width=True):
#                         st.session_state.selected_item_id = selected_row["ID"]
#                         # 수정 화면으로 이동 또는 수정 폼 표시

#                 with delete_col:
#                     if st.button("삭제", key="selected-user-delete", use_container_width=True):
#                         st.session_state.delete_item_id = selected_row["ID"]
#                         # 삭제 확인 후 API 호출


# try:
#     selected_item_id = st.session_state.get("selected_item_id")
#     if selected_item_id is None:
#         show_item_list()
#     else:
#         show_item_detail(selected_item_id)
# except BackendAPIError as error:
#     st.error(str(error))