from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.auth.errors import AccountNotFoundError
from app.auth.models import (
    AccountAuthRecord,
    AccountSummary,
    CreatedUserIdentity,
    LoginResult,
    Role,
    SignupResult,
)
from app.auth.passwords import PasswordService
from app.auth.tokens import TokenService


class InvalidCredentialsError(ValueError):
    def __init__(self) -> None:
        super().__init__("아이디 또는 비밀번호가 올바르지 않습니다.")


class AccountRepository(Protocol):
    async def create_user(
        self,
        normalized_login_id: str,
        password_hash: str,
        user_name: str,
    ) -> CreatedUserIdentity: ...

    async def get_for_login(self, normalized_login_id: str) -> AccountAuthRecord | None: ...

    async def record_failed_login(self, account_id: UUID, *, now: datetime) -> None: ...

    async def record_successful_login(self, account_id: UUID, *, now: datetime) -> bool: ...

    async def update_account(
        self,
        account_id: UUID,
        *,
        login_id: str | None,
        user_name: str | None,
    ) -> AccountSummary | None: ...

    async def delete_account(self, account_id: UUID) -> bool: ...


class RefreshTokenStore(Protocol):
    async def save(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        token_hash: str,
        ttl_seconds: int,
    ) -> None: ...

    async def revoke(self, *, session_id: UUID) -> None: ...


class AuthService:
    def __init__(
        self,
        *,
        accounts: AccountRepository,
        passwords: PasswordService,
        tokens: TokenService,
        refresh_tokens: RefreshTokenStore,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._accounts = accounts
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_tokens = refresh_tokens
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def login(self, *, login_id: str, login_pw: str) -> LoginResult:
        normalized_login_id = login_id.strip().casefold()
        now = self._now_provider()
        account = await self._accounts.get_for_login(normalized_login_id)

        if account is None:
            self._passwords.verify_dummy(login_pw)
            raise InvalidCredentialsError

        password_matches = self._passwords.verify(login_pw, account.password_hash)
        if not password_matches:
            await self._accounts.record_failed_login(account.id, now=now)
            raise InvalidCredentialsError

        if not account.is_active or (
            account.locked_until is not None and account.locked_until > now
        ):
            raise InvalidCredentialsError

        if not await self._accounts.record_successful_login(account.id, now=now):
            raise InvalidCredentialsError

        return await self._issue_session(user_id=account.id, role=account.role, now=now)

    async def signup(self, *, login_id: str, login_pw: str, user_name: str) -> SignupResult:
        normalized_login_id = login_id.strip().casefold()
        password_hash = self._passwords.hash(login_pw)
        identity = await self._accounts.create_user(
            normalized_login_id,
            password_hash,
            user_name.strip(),
        )
        session = await self._issue_session(
            user_id=identity.id,
            role=identity.role,
            now=self._now_provider(),
        )
        return SignupResult(
            user_id=identity.id,
            login_id=identity.login_id,
            **session.model_dump(),
        )

    async def update_account(
        self,
        *,
        user_id: UUID,
        login_id: str | None,
        user_name: str | None,
    ) -> AccountSummary:
        account = await self._accounts.update_account(
            user_id,
            login_id=login_id.strip().casefold() if login_id is not None else None,
            user_name=user_name.strip() if user_name is not None else None,
        )
        if account is None:
            raise AccountNotFoundError
        return account

    async def delete_account(self, *, user_id: UUID, session_id: UUID) -> None:
        await self._refresh_tokens.revoke(session_id=session_id)
        if not await self._accounts.delete_account(user_id):
            raise AccountNotFoundError

    async def _issue_session(
        self,
        *,
        user_id: UUID,
        role: Role,
        now: datetime,
    ) -> LoginResult:
        issued = self._tokens.issue(user_id=user_id, role=role, now=now)
        await self._refresh_tokens.save(
            session_id=issued.session_id,
            user_id=user_id,
            token_hash=issued.refresh_token_hash,
            ttl_seconds=issued.refresh_ttl_seconds,
        )
        return LoginResult(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            expires_in=issued.access_ttl_seconds,
        )
