"""Supabase 연결을 만드는 공통 helper입니다.

이 폴더의 CRUD 예제는 모두 같은 방식으로 Supabase에 접속합니다.
연결 코드를 각 파일에 반복해서 쓰면 예제가 길어지므로 이 파일에 모아 둡니다.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


# 이 파일은 다음 위치에 있습니다.
# 02_supabase-ai-backend/03_supabase-db-and-auth/02_supabase-table-and-crud/supabase_client.py
# parents[2]는 02_supabase-ai-backend 폴더입니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


def get_required_env(name: str) -> str:
    """필수 환경 변수를 읽고, 비어 있거나 예시 값이면 오류를 냅니다.

    .env.example에는 `your-...`, `https://your-...` 같은 안내용 값이 들어 있습니다.
    이런 값은 실제 Supabase 접속 정보가 아니므로, Supabase 요청을 보내기 전에 막습니다.
    """

    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"{name} 값이 없습니다. C:\\aidev\\02_supabase-ai-backend\\.env 파일을 확인하세요.")

    if value.startswith(("your-", "https://your-")):
        raise RuntimeError(f"{name} 값이 예시 값입니다. Supabase Dashboard에서 실제 값을 복사해 넣어 주세요.")

    return value


def get_supabase() -> Client:
    """Supabase client를 생성합니다.

    이 예제는 백엔드 서버 코드 관점의 실습이므로 service role key를 사용합니다.
    service role key는 강한 권한을 가진 key이므로 화면 코드나 GitHub에 노출하면 안 됩니다.
    """

    load_dotenv(ENV_PATH)

    url = get_required_env("SUPABASE_URL")
    service_role_key = get_required_env("SUPABASE_SERVICE_ROLE_KEY")

    return create_client(url, service_role_key)
