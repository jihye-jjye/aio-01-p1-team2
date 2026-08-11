from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pydantic import ValidationError

from app.auth.models import CurrentUser, Role


class InvalidAccessTokenError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    session_id: UUID
    refresh_token_hash: str
    access_ttl_seconds: int
    refresh_ttl_seconds: int


class TokenService:
    def __init__(
        self,
        *,
        secret_key: str,
        access_ttl: timedelta,
        refresh_ttl: timedelta,
        algorithm: str = "HS256",
    ) -> None:
        if len(secret_key.encode("utf-8")) < 32:
            raise ValueError("JWT secret key must be at least 32 bytes")
        self._secret_key = secret_key
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._algorithm = algorithm

    def issue(self, *, user_id: UUID, role: Role, now: datetime) -> IssuedTokens:
        session_id = uuid4()
        access_expires_at = now + self._access_ttl
        claims = {
            "sub": str(user_id),
            "sid": str(session_id),
            "role": role,
            "type": "access",
            "iat": now,
            "exp": access_expires_at,
        }
        access_token = jwt.encode(claims, self._secret_key, algorithm=self._algorithm)

        refresh_secret = secrets.token_urlsafe(32)
        refresh_token = f"{session_id}.{refresh_secret}"
        refresh_token_hash = hashlib.sha256(refresh_secret.encode("utf-8")).hexdigest()

        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session_id,
            refresh_token_hash=refresh_token_hash,
            access_ttl_seconds=int(self._access_ttl.total_seconds()),
            refresh_ttl_seconds=int(self._refresh_ttl.total_seconds()),
        )

    def decode_access(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> CurrentUser:
        current_time = now or datetime.now(UTC)
        try:
            claims = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={
                    "require": ["sub", "sid", "role", "type", "iat", "exp"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            if claims["type"] != "access":
                raise InvalidAccessTokenError

            expires_at = self._numeric_date(claims["exp"])
            issued_at = self._numeric_date(claims["iat"])
            if expires_at <= current_time or issued_at > current_time + timedelta(minutes=1):
                raise InvalidAccessTokenError

            return CurrentUser(
                id=UUID(str(claims["sub"])),
                role=claims["role"],
                session_id=UUID(str(claims["sid"])),
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise InvalidAccessTokenError("유효하지 않은 access token입니다.") from exc

    @staticmethod
    def _numeric_date(value: object) -> datetime:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidAccessTokenError
        return datetime.fromtimestamp(value, tz=UTC)
