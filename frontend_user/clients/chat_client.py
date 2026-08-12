"""이전 import 경로 호환용 모듈.

새 코드는 ``frontend_user.clients.assistant_client``를 사용합니다.
"""

from clients.assistant_client import (
    build_chat_history,
    send_chat_message,
    start_assistant_session,
)

__all__ = ["build_chat_history", "send_chat_message", "start_assistant_session"]
