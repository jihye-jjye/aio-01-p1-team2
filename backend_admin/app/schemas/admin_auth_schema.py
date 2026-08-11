"""관리자 로그인과 현재 관리자 응답 Schema."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    login_id: str = Field(
        min_length=4,
        max_length=50,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )
    password: str = Field(min_length=1, max_length=256)


class AdminIdentity(BaseModel):
    id: UUID
    login_id: str
    role: Literal["admin"]


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0, description="Access Token 유효 시간(초)")
    admin: AdminIdentity
