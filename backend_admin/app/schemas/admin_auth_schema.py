from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    login_id: str = Field(
        min_length=8,
        max_length=8,
        pattern=r"^[a-z0-9._-]+$",
    )
    password: str = Field(
        min_length=12,
        max_length=128,
    )


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(gt=0)
