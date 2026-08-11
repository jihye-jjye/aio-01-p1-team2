"""모든 메뉴 API에서 공통으로 사용하는 HTTP 요청 기능."""

import os
import httpx
from typing import Any
import streamlit as st

# BACKEND_URL = "http://127.0.0.1:8000"
BACKEND_USER_URL = "https://aio-01-p1-team2-1.onrender.com/api/v1" # 사용자 서버
BACKEND_AMDIN_URL = "https://aio-01-p1-team2.onrender.com/api/v1" # 관리자 서버
REQUEST_TIMEOUT = 60.0

class BackendAPIError(Exception):
    """백엔드 연결 또는 API 응답 처리 중 발생한 오류입니다."""

def request(method: str, 
            path: str, 
            json: dict[str, Any] | None = None,
            # data, files 는 multipart/form-data를 사용할 때 쓴다..
            data: dict[str, Any] | None = None, # ex. name, price, desc를 가지고 있는것이고            
            files: dict[str, Any] | None = None, # ex. image 파일,
            params: dict[str, Any] | None = None,
            role : str | None = None,
            auth_required: bool = True,  # 기본값: 인증 필요
             ):
    try:
        headers = {}

        if role =="ADMIN":
            BACKEND_URL = BACKEND_AMDIN_URL
        else :
            BACKEND_URL = BACKEND_USER_URL

        if auth_required:
            token = st.session_state.access_token
            headers["Authorization"] = f"Bearer {token}"

        response = httpx.request(
            method,
            f"{BACKEND_URL}{path}",
            json=json,
            data=data,
            files=files,        
            params=params,  
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TimeoutException as error:
        raise BackendAPIError("백엔드 응답 시간이 초과되었습니다.") from error
    except httpx.RequestError as error:
        raise BackendAPIError(
            "백엔드 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요."
        ) from error

    if response.status_code  == 401:
        raise BackendAPIError(
            "로그인 아이디 또는 패스워드 문제"
        )
    if response.status_code  == 404:
        raise BackendAPIError(
            "존재하지 않습니다."
        )
    if response.status_code  == 409:
        raise BackendAPIError(
            "ID가 사용 중 입니다."
        )
   
    try:
        payload = response.json()
    except ValueError as error:
        raise BackendAPIError("백엔드가 올바른 JSON을 반환하지 않았습니다.") from error
   
    return payload
