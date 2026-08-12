import streamlit as st
from core.api_client import BackendAPIError, request
from clients.recruitment_notice_client import get_recruitment_notice_process

try:
    response = get_recruitment_notice_process()

    if response is not None:
        with st.container(border=True):
           
            column_widths = [2.0, 1.8, 1.8, 1.0, 1.0, 1.0, 0.8]

            # 헤더
            header_cols = st.columns(column_widths)
            headers = ["ID", "회사명", "직무", "경력", "마감일", "플랫폼", "관리"]

            for col, header in zip(header_cols, headers):
                col.markdown(f"**{header}**")

            st.divider()

            # 행
            for item in response["items"]:
                row_cols = st.columns(column_widths)
                row_cols[0].write(item["id"])
                row_cols[1].write(item["company_name"])
                row_cols[2].write(item["job_title"])
                row_cols[3].write(item["extracted_data"]["career"])
                row_cols[4].write(item["deadline"] if item["deadline"] is not None else "상시모집")
                row_cols[5].write(item["extracted_data"]["platform"])

                # 마지막 '관리' 컬럼
                with row_cols[6]:
                    # edit_col, delete_col = st.columns(2)

                    # with edit_col:
                    if st.button(
                        "수정",
                        key=f"user-edit-{item['id']}",
                        use_container_width=True):                    
                        st.session_state.selected_item_notice_id = item["id"]
                        st.session_state["recruitment_notice_detail"] = item
                        # 여기서 수정 페이지 또는 수정 폼을 열기
                        st.switch_page("app_pages/recruitment_notice_detail.py")

                    # with delete_col:
                    #     if st.button(
                    #         "삭제",
                    #         key=f"user-delete-{item['id']}",
                    #         use_container_width=True,
                    #     ):
                    #         st.session_state.delete_notice_id = item["id"]
                    #         # 여기서 삭제 확인창 또는 삭제 API 호출

                st.divider()

except BackendAPIError as error :
    st.warning(str(error))