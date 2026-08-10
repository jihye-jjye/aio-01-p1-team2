from datetime import date
from typing import Any

from core.api_client import request

def login_process(auth : dict):
    
    return request("POST", "/auth/login", json=auth)

def user_get_all_process():
    """사용자 관리 페이지 사용자 정보 가져오기"""
    return request("", "")