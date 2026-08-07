from core.api_client import request

def call_gemini(user_id: str, prompt: str, history=None):

    payload = {"user_id" : user_id, "prompt": prompt, "message" : history}

    return ""
    return request("POST", "/chat/gemini", json=payload)