from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SavedJobView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_type: Literal["url", "pasted_text"]
    source_url: str | None
    source_key: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    job_title: str = Field(min_length=1)
    deadline: date | None
    posting_text: str = Field(min_length=1)
    extracted_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime
