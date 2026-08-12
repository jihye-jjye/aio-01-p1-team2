import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault(
    "streamlit",
    SimpleNamespace(cache_resource=lambda function: function, session_state={}),
)

from clients import assistant_client
from core.api_client import BackendAPIError

SESSION_ID = "d84d01dc-8ec4-4ab8-8863-b38b8ac62f62"


def test_chat_client_compatibility_exports_remain_importable():
    from clients.chat_client import build_chat_history, send_chat_message

    assert callable(build_chat_history)
    assert send_chat_message is assistant_client.send_chat_message


def test_send_chat_message_uses_assistant_session_contract(monkeypatch):
    captured: dict[str, object] = {}

    def fake_request(method, path, **kwargs):
        captured.update(method=method, path=path, **kwargs)
        return {
            "session_id": SESSION_ID,
            "revision": 4,
            "intent": "general",
            "assistant_message": "  다음 단계부터 함께 정리해 볼게요.  ",
            "tool_results": [],
        }

    monkeypatch.setattr(assistant_client, "request", fake_request)

    result = assistant_client.send_chat_message(
        session_id=SESSION_ID,
        expected_revision=3,
        text="  이력서부터 준비할까요?  ",
    )

    assert result["revision"] == 4
    assert result["assistant_message"] == "다음 단계부터 함께 정리해 볼게요."
    assert captured["method"] == "POST"
    assert captured["path"] == f"/assistant/sessions/{SESSION_ID}/messages"
    assert captured["auth_required"] is True
    assert captured["timeout"] == assistant_client.CHAT_TIMEOUT
    assert captured["json"]["expected_revision"] == 3
    assert captured["json"]["text"] == "이력서부터 준비할까요?"
    UUID(captured["json"]["request_id"])


@pytest.mark.parametrize(
    ("response", "expected_revision"),
    [
        (
            {
                "session_id": "6e489c07-1184-4c35-8f8b-c66759045eb4",
                "revision": 2,
                "assistant_message": "답변",
            },
            1,
        ),
        (
            {
                "session_id": SESSION_ID,
                "revision": 8,
                "assistant_message": "답변",
            },
            1,
        ),
        (
            {
                "session_id": SESSION_ID,
                "revision": 2,
                "assistant_message": "   ",
            },
            1,
        ),
        (None, 1),
    ],
)
def test_send_chat_message_rejects_invalid_backend_response(
    monkeypatch,
    response,
    expected_revision,
):
    monkeypatch.setattr(assistant_client, "request", lambda *args, **kwargs: response)

    with pytest.raises(BackendAPIError) as error:
        assistant_client.send_chat_message(
            session_id=SESSION_ID,
            expected_revision=expected_revision,
            text="질문",
        )

    assert error.value.code == "INVALID_RESPONSE"


@pytest.mark.parametrize(
    ("session_id", "expected_revision", "text"),
    [
        ("", 0, "질문"),
        (SESSION_ID, -1, "질문"),
        (SESSION_ID, 0, "   "),
    ],
)
def test_send_chat_message_rejects_invalid_client_state(
    monkeypatch,
    session_id,
    expected_revision,
    text,
):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("invalid input must not reach the backend")

    monkeypatch.setattr(assistant_client, "request", fail_if_called)

    with pytest.raises(ValueError):
        assistant_client.send_chat_message(
            session_id=session_id,
            expected_revision=expected_revision,
            text=text,
        )


def test_send_chat_message_rejects_non_uuid_request_id(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("invalid request ID must not reach the backend")

    monkeypatch.setattr(assistant_client, "request", fail_if_called)

    with pytest.raises(ValueError, match="request_id"):
        assistant_client.send_chat_message(
            session_id=SESSION_ID,
            expected_revision=0,
            text="질문",
            request_id="not-a-uuid",
        )
