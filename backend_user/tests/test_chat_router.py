from fastapi.testclient import TestClient

from app.main import app
from app.routers import chat_router
from app.schemas.chat_schema import ChatResponse


client = TestClient(app)


def test_chat_gemini_returns_chat_response(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "call_gemini",
        lambda chat_request: ChatResponse(answer=f"응답: {chat_request.prompt}"),
    )

    response = client.post(
        "/chat/gemini",
        json={"user_id": "user-1", "prompt": "안녕"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["answer"] == "응답: 안녕"


def test_chat_gemini_rejects_empty_prompt():
    response = client.post(
        "/chat/gemini",
        json={"user_id": "user-1", "prompt": ""},
    )

    assert response.status_code == 422
