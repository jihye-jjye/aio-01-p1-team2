from fastapi import APIRouter
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat_service import call_gemini
from app.core.api_response import ApiResponse

chat_router = APIRouter(tags=["Chat"])

@chat_router.post("/chat/gemini")
def chat_gemini(chat_request:ChatRequest) -> ApiResponse:
    # print(chat_request.user_id)
    # print(chat_request.prompt)
    response = ApiResponse(
        success = True,
        message = f"정상 !",
        data = call_gemini(chat_request)
    )
    return response
