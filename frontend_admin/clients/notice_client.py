from core.api_client import request
import streamlit as st

def notice_all_process():
    return request("GET", "/admin/notices", role="ADMIN")

def notice_get_process(notice_id :str):
    return request("GET", f"/admin/notices/{notice_id}", role="ADMIN")