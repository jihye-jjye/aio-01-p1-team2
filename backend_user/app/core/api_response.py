from typing import Any

from pydantic import BaseModel, Field

class ApiResponse(BaseModel):
    """수업용 표준 응답 모델입니다."""

    # success는 요청 처리 성공 여부를 나타냅니다.
    success: bool
    # message는 사용자가 보거나 프론트엔드가 표시할 수 있는 짧은 설명입니다.
    message: str
    # data는 실제 데이터입니다. 목록, 객체, None 등 여러 모양이 올 수 있어 Any를 사용합니다.
    data: Any | None = None