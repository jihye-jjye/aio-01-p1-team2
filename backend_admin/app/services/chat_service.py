# chat_service.py
import os
from app.schemas.chat_schema import ChatRequest, ChatResponse
from google import genai
from app.core.supabase_config import get_supabase

def call_gemini(chat_request:ChatRequest)->ChatResponse:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model = model,
        contents = chat_request.prompt,
    )    
    
    return ChatResponse(
        answer = response.text
    )

def save_gemini_db(chat_request:ChatRequest, answer : ChatResponse) :
    supabase = get_supabase()

    result = (
        supabase.table("chat_history")
        .insert(
            {
                "user_id" : chat_request.user_id,
                "prompt" : chat_request.prompt,
                "reply" : answer.answer
            }
        )
    )

    return

def process_gemini_chat(chat_request:ChatRequest) :

    answer = call_gemini(chat_request)
    save_gemini_db(chat_request, answer)
    return