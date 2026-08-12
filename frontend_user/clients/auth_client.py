"""회원가입, 로그인, 사용자·프로필 조회 API."""

from core.api_client import request


def login(login_id: str, login_pw: str) -> dict:
    """아이디와 비밀번호를 백엔드에 보내고 토큰 응답을 반환합니다."""

    return request(
        "POST",
        "/auth/login",
        json={"login_id": login_id, "login_pw": login_pw},
        auth_required=False,
    )


def signup(login_id: str, login_pw: str, user_name: str) -> dict:
    """계정을 생성합니다. 실제 토큰 저장은 회원가입 페이지에서 처리합니다."""

    return request(
        "POST",
        "/auth/signup",
        json={
            "login_id": login_id.strip().casefold(),
            # 백엔드 계약상 비밀번호 공백은 제거하지 않습니다.
            "login_pw": login_pw,
            "user_name": user_name.strip(),
        },
        auth_required=False,
    )


def get_me() -> dict:
    """현재 access token의 사용자 정보를 조회합니다."""

    return request("GET", "/auth/me")


def update_me(login_id: str | None = None, user_name: str | None = None) -> dict:
    """현재 사용자의 로그인 ID 또는 사용자 이름을 수정합니다."""

    body = {}
    if login_id is not None:
        body["login_id"] = login_id.strip().casefold()
    if user_name is not None:
        body["user_name"] = user_name.strip()

    return request("PATCH", "/auth/me", json=body)


def delete_me() -> None:
    """현재 로그인한 계정과 사용자 소유 데이터를 영구 삭제합니다."""

    request("DELETE", "/auth/me")


def get_profile() -> dict:
    """현재 사용자의 취업 프로필을 조회합니다."""

    return request("GET", "/profile")
