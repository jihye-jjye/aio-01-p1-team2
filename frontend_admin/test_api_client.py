"""관리자 프론트엔드의 백엔드 URL/경로 계약 회귀 테스트."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest

FRONTEND_ADMIN_ROOT = Path(__file__).resolve().parent
if str(FRONTEND_ADMIN_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ADMIN_ROOT))

try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    streamlit_stub = ModuleType("streamlit")
    streamlit_stub.session_state = SimpleNamespace(access_token="")
    sys.modules["streamlit"] = streamlit_stub

from clients import loadmap_client
from core import api_client


def _set_authenticated_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_client.st,
        "session_state",
        SimpleNamespace(access_token="admin-token"),
    )


def test_backend_urls_prefer_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as scoped:
        scoped.setenv("BACKEND_USER_URL", "https://user.example.com/api/v1/")
        scoped.setenv("BACKEND_ADMIN_URL", "https://admin.example.com/api/v1/")

        reloaded = importlib.reload(api_client)

        assert reloaded.BACKEND_USER_URL == "https://user.example.com/api/v1"
        assert reloaded.BACKEND_ADMIN_URL == "https://admin.example.com/api/v1"

    importlib.reload(api_client)


@pytest.mark.parametrize(
    ("role", "base_url"),
    [
        (None, "https://user.example.com/api/v1"),
        ("USER", "https://user.example.com/api/v1"),
        ("ADMIN", "https://admin.example.com/api/v1"),
    ],
)
def test_request_joins_base_url_and_path_with_one_slash(
    monkeypatch: pytest.MonkeyPatch,
    role: str | None,
    base_url: str,
) -> None:
    _set_authenticated_session(monkeypatch)
    monkeypatch.setattr(api_client, "BACKEND_USER_URL", "https://user.example.com/api/v1/")
    monkeypatch.setattr(api_client, "BACKEND_ADMIN_URL", "https://admin.example.com/api/v1/")
    captured: dict[str, object] = {}

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        captured.update(method=method, url=url, kwargs=kwargs)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(api_client.httpx, "request", fake_request)

    payload = api_client.request("GET", "admin/users", role=role)

    assert payload == {"ok": True}
    assert captured["url"] == f"{base_url}/admin/users"
    request_kwargs = captured["kwargs"]
    assert isinstance(request_kwargs, dict)
    assert request_kwargs["headers"] == {
        "Authorization": "Bearer admin-token",
    }


def test_request_rejects_unsupported_role_before_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network_called = False

    def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        nonlocal network_called
        network_called = True
        return httpx.Response(200, json={})

    monkeypatch.setattr(api_client.httpx, "request", fake_request)

    with pytest.raises(api_client.BackendAPIError, match="지원하지 않는 백엔드 역할"):
        api_client.request("GET", "/admin/users", role="MANAGER")

    assert network_called is False


@pytest.mark.parametrize("status_code", [300, 400, 401, 404, 409, 500])
def test_request_raises_consistent_error_for_every_non_2xx_response(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    _set_authenticated_session(monkeypatch)

    def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "backend detail"})

    monkeypatch.setattr(api_client.httpx, "request", fake_request)

    with pytest.raises(
        api_client.BackendAPIError,
        match=rf"HTTP {status_code}.*backend detail",
    ):
        api_client.request("GET", "/admin/users", role="ADMIN")


def test_loadmap_client_uses_admin_roadmap_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"login_id": "roadmap_user", "items": []}

    monkeypatch.setattr(loadmap_client, "request", fake_request)

    payload = loadmap_client.loadmap_from_user("roadmap_user")

    assert payload == {"login_id": "roadmap_user", "items": []}
    assert captured == {
        "method": "GET",
        "path": "/admin/users/by-login-id/roadmap_user/roadmaps",
        "kwargs": {"role": "ADMIN"},
    }
