from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoticeView(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: UUID
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)
    is_pinned: bool
    published_at: datetime
    expires_at: datetime | None
