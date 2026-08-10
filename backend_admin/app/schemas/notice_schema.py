"""공지사항 CRUD 및 목록 API Schema."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NoticeCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)


class NoticeUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=20_000,
    )

    @model_validator(mode="after")
    def require_change(self):
        if self.title is None and self.content is None:
            raise ValueError("수정할 제목 또는 내용을 입력해 주세요.")
        return self


class NoticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class NoticeListResponse(BaseModel):
    items: list[NoticeResponse]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class NoticeQueryParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    search: str | None = Field(default=None, min_length=1, max_length=200)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
