from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    """Streamlit 화면에서 백엔드로 함께 보낼 수 있는 이전 대화 메시지 구조입니다."""

    role: str = Field(..., description="메시지 역할입니다. 예: user 또는 assistant")
    content: str = Field(..., min_length=1, description="메시지 내용입니다.")

class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, examples=["id01"])
    prompt: str = Field(min_length=1, examples=["안녕!"])
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="선택 사항입니다. 문맥 유지를 위해 함께 보낼 최근 대화 메시지 목록입니다.",
    )

class ChatResponse(BaseModel):
    answer: str = Field(min_length=1, examples=["안녕하세요!"])
