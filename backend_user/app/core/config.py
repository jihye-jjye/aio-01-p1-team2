from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str
    upstash_redis_url: str = Field(
        validation_alias=AliasChoices("UPSTASH_REDIS_URL", "REDIS_URL", "upstash_redis_url")
    )
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    onboarding_session_ttl_seconds: int = Field(default=1800, ge=300, le=86400)
    gemini_api_key: str = Field(min_length=1)
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_version: str = "v1"
    gemini_timeout_seconds: int = Field(default=15, ge=1, le=300)
    gemini_max_attempts: int = Field(default=2, ge=1, le=2)
    db_pool_min_size: int = Field(default=1, ge=1, le=20)
    db_pool_max_size: int = Field(default=5, ge=1, le=50)

    @field_validator("jwt_algorithm")
    @classmethod
    def only_hs256(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM은 HS256이어야 합니다.")
        return value

    @field_validator("gemini_model")
    @classmethod
    def only_configured_gemini_model(cls, value: str) -> str:
        if value != "gemini-3.6-flash":
            raise ValueError("GEMINI_MODEL은 gemini-3.6-flash여야 합니다.")
        return value

    @field_validator("gemini_api_version")
    @classmethod
    def only_stable_gemini_api(cls, value: str) -> str:
        if value != "v1":
            raise ValueError("GEMINI_API_VERSION은 v1이어야 합니다.")
        return value

    @model_validator(mode="after")
    def validate_pool_range(self) -> "Settings":
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("DB_POOL_MIN_SIZE는 DB_POOL_MAX_SIZE보다 클 수 없습니다.")
        return self
