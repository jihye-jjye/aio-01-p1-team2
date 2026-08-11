"""관리자용 저장된 취업 공고 조회 API Schema."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SavedJobResponse(BaseModel):
    """saved_jobs 테이블의 취업 공고 한 건."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: Literal["url", "pasted_text"]
    source_url: str | None = None
    source_key: str
    company_name: str
    job_title: str
    deadline: date | None = None
    posting_text: str
    extracted_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SavedJobListResponse(BaseModel):
    """취업 공고 목록과 페이지 정보."""

    items: list[SavedJobResponse]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class SavedJobQueryParams(BaseModel):
    """취업 공고 목록 조회 조건."""

    model_config = ConfigDict(extra="forbid")

    source_type: Literal["url", "pasted_text"] | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
