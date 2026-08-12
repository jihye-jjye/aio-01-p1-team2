from datetime import date
from typing import Any
from core.api_client import request

import streamlit as st

def login_process(auth : dict):
    
    return request("POST", "/admin/auth/login", json=auth, role="ADMIN", auth_required=False)

def user_get_all_process():
    """사용자 관리 페이지 사용자 정보 가져오기"""
    
    return request("GET", "/admin/users", role="ADMIN")

def user_get_detail_process(user_id : str):
    return request("GET",f"/admin/users/by-login-id/{user_id}", role="ADMIN")

def user_get_overview_process(user_id : str):
    return request("GET",f"/admin/users/by-login-id/{user_id}/overview", role="ADMIN")