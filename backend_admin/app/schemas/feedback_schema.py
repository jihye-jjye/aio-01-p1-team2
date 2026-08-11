from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=1, le=5)
    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("comment")
    @classmethod
    def normalize_comment(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    log_id: UUID
    user_id: UUID
    score: int = Field(ge=1, le=5)
    comment: str | None
    created_at: datetime
    updated_at: datetime