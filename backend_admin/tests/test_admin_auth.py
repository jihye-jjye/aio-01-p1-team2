from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.password import hash_password
from app.main import app
from app.repositories.admin_auth_repository import AdminAuthRepositoryError
from app.routers import admin_auth_router
from app.schemas.admin_auth_schema import AdminLoginRequest
from app.services.admin_auth_service import AdminAuthService
from app.services.exceptions import (
    AdminAccountDisabledError,
    AdminAuthenticationError,
    AdminAuthStorageError,
)


ADMIN_ID = UUID("00000000-0000-0000-0000-000000000002")


def make_account(**updates: Any) -> dict[str, Any]:
    account = {
        "id": str(ADMIN_ID),
        "login_id": "admin001",
        "password_hash": hash_password("Admin1234!"),
        "role": "admin",
        "is_active": True,
        "failed_login_count": 0,
        "locked_until": None,
    }
    account.update(updates)
    return account


class FakeAdminAuthRepository:
    def __init__(
        self,
        account: dict[str, Any] | None,
        *,
        error: bool = False,
    ) -> None:
        self.account = account
        self.error = error
        self.login_id: str | None = None
        self.success_id: UUID | None = None

    def get_account_by_login_id(self, login_id: str) -> dict[str, Any] | None:
        if self.error:
            raise AdminAuthRepositoryError("DB failure")
        self.login_id = login_id
        return self.account

    def record_login_success(self, admin_id: UUID) -> None:
        self.success_id = admin_id


def test_admin_login_succeeds_for_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeAdminAuthRepository(make_account())
    service = AdminAuthService(repository=repository)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "app.services.admin_auth_service.create_admin_access_token",
        lambda admin_id: (f"token-for-{admin_id}", 3600),
    )

    result = service.login(
        AdminLoginRequest(login_id="ADMIN001", password="Admin1234!")
    )

    assert repository.login_id == "admin001"
    assert repository.success_id == ADMIN_ID
    assert result.admin.role == "admin"
    assert result.access_token == f"token-for-{ADMIN_ID}"


@pytest.mark.parametrize(
    ("account", "password"),
    [
        (None, "Admin1234!"),
        (make_account(role="user"), "Admin1234!"),
        (make_account(), "wrong-password"),
    ],
)
def test_admin_login_rejects_invalid_credentials(
    account: dict[str, Any] | None,
    password: str,
) -> None:
    service = AdminAuthService(  # type: ignore[arg-type]
        repository=FakeAdminAuthRepository(account)
    )

    with pytest.raises(AdminAuthenticationError):
        service.login(AdminLoginRequest(login_id="admin001", password=password))


@pytest.mark.parametrize(
    "account",
    [
        make_account(is_active=False),
        make_account(locked_until=(datetime.now(UTC) + timedelta(hours=1)).isoformat()),
    ],
)
def test_admin_login_rejects_unavailable_account(
    account: dict[str, Any],
) -> None:
    service = AdminAuthService(  # type: ignore[arg-type]
        repository=FakeAdminAuthRepository(account)
    )

    with pytest.raises(AdminAccountDisabledError):
        service.login(
            AdminLoginRequest(login_id="admin001", password="Admin1234!")
        )


def test_admin_login_converts_storage_error() -> None:
    service = AdminAuthService(  # type: ignore[arg-type]
        repository=FakeAdminAuthRepository(None, error=True)
    )

    with pytest.raises(AdminAuthStorageError):
        service.login(
            AdminLoginRequest(login_id="admin001", password="Admin1234!")
        )


def test_admin_login_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAdminAuthService:
        def login(self, payload: AdminLoginRequest) -> dict[str, Any]:
            return {
                "access_token": "admin-token",
                "token_type": "bearer",
                "expires_in": 3600,
                "admin": {
                    "id": str(ADMIN_ID),
                    "login_id": payload.login_id,
                    "role": "admin",
                },
            }

    monkeypatch.setattr(
        admin_auth_router,
        "admin_auth_service",
        FakeAdminAuthService(),
    )

    response = TestClient(app).post(
        "/api/v1/admin/auth/login",
        json={"login_id": "admin001", "password": "Admin1234!"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "admin-token"


def test_admin_me_endpoint_uses_authenticated_admin() -> None:
    response = TestClient(app).get("/api/v1/admin/auth/me")

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
