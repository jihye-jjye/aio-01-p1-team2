from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal["user", "admin"]


class AccountAuthRecord(BaseModel):
    id: UUID
    role: Role
    login_id: str
    password_hash: str
    is_active: bool
    failed_login_count: int
    locked_until: datetime | None


class CreatedUserIdentity(BaseModel):
    id: UUID
    role: Role
    login_id: str


class LoginResult(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignupResult(BaseModel):
    user_id: UUID
    login_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUser(BaseModel):
    id: UUID
    role: Role
    session_id: UUID
