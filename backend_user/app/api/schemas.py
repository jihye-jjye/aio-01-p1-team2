from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=50)
    login_pw: str = Field(min_length=1, max_length=128)


class SignupRequest(BaseModel):
    login_id: str = Field(min_length=4, max_length=50, pattern=r"^[a-z0-9._-]+$")
    login_pw: str = Field(min_length=8, max_length=128)
    user_name: str = Field(min_length=1, max_length=50)

    @field_validator("login_id", mode="before")
    @classmethod
    def normalize_login_id(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value

    @field_validator("user_name", mode="before")
    @classmethod
    def normalize_user_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AccountUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_id: (
        Annotated[
            str,
            Field(min_length=4, max_length=50, pattern=r"^[a-z0-9._-]+$"),
        ]
        | SkipJsonSchema[None]
    ) = None
    user_name: Annotated[str, Field(min_length=1, max_length=50)] | SkipJsonSchema[None] = None

    @field_validator("login_id", mode="before")
    @classmethod
    def normalize_login_id(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value

    @field_validator("user_name", mode="before")
    @classmethod
    def normalize_user_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_non_null_update(self) -> "AccountUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("login_id와 user_name 중 하나 이상이 필요합니다.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("수정할 필드는 null일 수 없습니다.")
        return self


class OnboardingStartRequest(BaseModel):
    request_id: UUID


class OnboardingConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    expected_revision: int = Field(ge=0)


class PlanProposalCreateRequest(BaseModel):
    request_id: UUID
    saved_job_id: UUID | None = None


class PlanTaskStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "completed"]


class PlanProposalReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    feedback: str = Field(min_length=1, max_length=4000)


class OnboardingMessageRequest(BaseModel):
    request_id: UUID
    text: str | None = Field(default=None, max_length=4000)
    action: str | None = Field(default=None, max_length=100)
    expected_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "OnboardingMessageRequest":
        if (self.text is None) == (self.action is None):
            raise ValueError("text와 action 중 정확히 하나만 필요합니다.")
        if self.action == "onboarding.confirm" and self.expected_revision is None:
            raise ValueError("onboarding.confirm에는 expected_revision이 필요합니다.")
        if self.action != "onboarding.confirm" and self.expected_revision is not None:
            raise ValueError("expected_revision은 onboarding.confirm에만 사용할 수 있습니다.")
        return self
