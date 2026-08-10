from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LogLevel(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class LogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True,)

    user_id: UUID | None = None
    session_id: UUID | None = None
    request_id: UUID

    level: LogLevel
    endpoint: str = Field(min_length=1, max_length=500)
    model_name: str | None = Field(default=None, min_length=1, max_length=100)

    status_code: int = Field(ge=100, le=599)
    latency_ms: int = Field(ge=0)

    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_error_fields(self):
        if self.level == LogLevel.ERROR and not self.error_code:
            raise ValueError(
                "ERROR 로그에는 error_code가 필요합니다."
            )
    
        if (self.level != LogLevel.ERROR and self.error_code is not None):
            raise ValueError(
                "INFO 또는 WARN 로그에는 "
                "error_code를 지정할 수 없습니다."
            )
    
        return self


class LogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    session_id: UUID | None
    request_id: UUID

    level: LogLevel
    endpoint: str
    model_name: str | None

    status_code: int
    latency_ms: int
    error_code: str | None
    message: str
    created_at: datetime


class LogListResponse(BaseModel):
    items: list[LogResponse]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class LogSummaryResponse(BaseModel):
    total_requests: int = Field(ge=0)
    error_count: int = Field(ge=0)
    error_rate: float = Field(ge=0, le=100)
    average_latency_ms: float = Field(ge=0)


class LogQueryParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    level: LogLevel | None = None
    endpoint: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    start_at: datetime | None = None
    end_at: datetime | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_date_range(self):
        if (
            self.start_at is not None
            and self.end_at is not None
            and self.start_at > self.end_at
        ):
            raise ValueError(
                "start_at은 end_at보다 늦을 수 없습니다."
            )

        return self

    