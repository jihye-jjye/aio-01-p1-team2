"""일반 사용자 JWT의 발급 및 검증."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from dotenv import load_dotenv

from app.core.supabase_config import ENV_PATH


SUPPORTED_JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60


class TokenValidationError(ValueError):
    """JWT가 잘못됐거나 만료됐을 때 발생한다."""


def _get_jwt_settings() -> tuple[str, str | None, str | None, int]:
    load_dotenv(ENV_PATH)
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    algorithm = os.getenv(
        "JWT_ALGORITHM",
        SUPPORTED_JWT_ALGORITHM,
    ).strip()
    issuer = os.getenv("JWT_ISSUER", "").strip() or None
    audience = os.getenv("JWT_AUDIENCE", "").strip() or None

    try:
        expires_minutes = int(
            os.getenv(
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
                str(DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES),
            )
        )
    except ValueError as exc:
        raise RuntimeError(
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES는 정수여야 합니다."
        ) from exc

    if not secret or secret.startswith("your-"):
        raise RuntimeError("JWT_SECRET_KEY 환경 변수를 설정해 주세요.")
    if algorithm != SUPPORTED_JWT_ALGORITHM:
        raise RuntimeError("JWT_ALGORITHM은 HS256만 지원합니다.")
    if expires_minutes <= 0:
        raise RuntimeError(
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES는 1 이상이어야 합니다."
        )
    return secret, issuer, audience, expires_minutes


def _create_access_token(
    *,
    subject: str,
    scope: str,
) -> tuple[str, int]:
    secret, issuer, audience, expires_minutes = _get_jwt_settings()
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=expires_minutes)
    payload: dict[str, object] = {
        "sub": subject,
        "scope": scope,
        "iat": now,
        "exp": now + expires_delta,
    }
    if issuer is not None:
        payload["iss"] = issuer
    if audience is not None:
        payload["aud"] = audience

    token = jwt.encode(
        payload,
        secret,
        algorithm=SUPPORTED_JWT_ALGORITHM,
    )
    return token, int(expires_delta.total_seconds())


def create_access_token(subject: UUID) -> tuple[str, int]:
    """일반 사용자 UUID를 갖는 JWT를 발급한다."""

    return _create_access_token(subject=str(subject), scope="user")


def create_admin_access_token(subject: UUID) -> tuple[str, int]:
    """관리자 UUID를 갖는 관리자 전용 JWT를 발급한다."""

    return _create_access_token(subject=str(subject), scope="admin")


def _decode_token(token: str) -> dict:
    try:
        secret, issuer, audience, _ = _get_jwt_settings()
        return jwt.decode(
            token,
            secret,
            algorithms=[SUPPORTED_JWT_ALGORITHM],
            issuer=issuer,
            audience=audience,
            options={
                "require": ["sub", "scope", "exp"],
                "verify_iss": issuer is not None,
                "verify_aud": audience is not None,
            },
        )
    except RuntimeError:
        raise
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError(
            "유효하지 않거나 만료된 토큰입니다."
        ) from exc


def decode_access_token(token: str) -> UUID:
    """일반 사용자 JWT를 검증하고 사용자 UUID를 반환한다."""

    payload = _decode_token(token)
    if payload.get("scope") != "user":
        raise TokenValidationError("일반 사용자 토큰이 아닙니다.")
    try:
        return UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("사용자 식별자가 올바르지 않습니다.") from exc


def decode_admin_access_token(token: str) -> UUID:
    """관리자 JWT를 검증하고 관리자 UUID를 반환한다."""

    payload = _decode_token(token)
    if payload.get("scope") != "admin":
        raise TokenValidationError("관리자 토큰이 아닙니다.")
    try:
        return UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("관리자 식별자가 올바르지 않습니다.") from exc
