from __future__ import annotations

import argparse
import asyncio
import getpass
from typing import Any, Protocol
from uuid import UUID

from app.auth.passwords import PasswordService
from app.core.config import Settings
from app.db.pool import create_pool


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


async def upsert_demo_user(
    *,
    pool: Any,
    passwords: PasswordHasher,
    login_id: str,
    password: str,
) -> UUID:
    normalized_login = login_id.strip().casefold()
    if not normalized_login or len(normalized_login) > 50:
        raise ValueError("로그인 아이디는 1~50자여야 합니다.")
    if len(password) < 8 or len(password) > 128:
        raise ValueError("비밀번호는 8자 이상 128자 이하여야 합니다.")
    password_hash = passwords.hash(password)
    async with pool.connection() as connection:
        cursor = await connection.execute(
            """
            insert into app.user_accounts (login_id, password_hash)
            values (%(login_id)s, %(password_hash)s)
            on conflict (lower(login_id)) do update set
              password_hash = excluded.password_hash,
              is_active = true,
              failed_login_count = 0,
              locked_until = null
            returning id
            """,
            {"login_id": normalized_login, "password_hash": password_hash},
        )
        row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("데모 사용자를 생성하지 못했습니다.")
    return UUID(str(row["id"]))


async def _run(login_id: str, password: str) -> UUID:
    settings = Settings()  # type: ignore[call-arg]
    pool = create_pool(settings)
    await pool.open(wait=True)
    try:
        return await upsert_demo_user(
            pool=pool,
            passwords=PasswordService(),
            login_id=login_id,
            password=password,
        )
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬 CLI 시연용 사용자를 생성하거나 갱신합니다.")
    parser.add_argument("--login-id", default="demo.user")
    args = parser.parse_args()
    password = getpass.getpass("데모 사용자 비밀번호: ")
    confirmation = getpass.getpass("비밀번호 확인: ")
    if password != confirmation:
        raise SystemExit("비밀번호 확인이 일치하지 않습니다.")
    try:
        user_id = asyncio.run(_run(args.login_id, password))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"데모 사용자 준비 완료: {user_id}")
