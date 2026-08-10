from typing import Any

from pydantic import BaseModel


class APIErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any]


class APIErrorEnvelope(BaseModel):
    error: APIErrorBody


class UnauthorizedError(ValueError):
    pass


class ProfileNotFoundError(LookupError):
    pass
