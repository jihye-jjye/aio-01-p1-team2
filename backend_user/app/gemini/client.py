from google import genai
from google.genai import types

from app.core.config import Settings


def create_genai_client(settings: Settings) -> genai.Client:
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            api_version=settings.gemini_api_version,
            timeout=settings.gemini_timeout_seconds * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
