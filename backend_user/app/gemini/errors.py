from __future__ import annotations


class GeminiError(RuntimeError):
    status_code = 502
    code = "GEMINI_UNAVAILABLE"
    retryable = True


class GeminiRateLimitedError(GeminiError):
    status_code = 429
    code = "GEMINI_RATE_LIMITED"


class GeminiUnavailableError(GeminiError):
    pass


class GeminiConfigurationError(GeminiError):
    code = "GEMINI_CONFIGURATION_ERROR"
    retryable = False


class GeminiInvalidResponseError(GeminiError):
    code = "GEMINI_INVALID_RESPONSE"
    retryable = False


class GeminiContentBlockedError(GeminiError):
    status_code = 422
    code = "GEMINI_CONTENT_BLOCKED"
    retryable = False
