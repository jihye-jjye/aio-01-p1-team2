from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.gemini.errors import (
    GeminiConfigurationError,
    GeminiContentBlockedError,
    GeminiError,
    GeminiInvalidResponseError,
    GeminiRateLimitedError,
    GeminiUnavailableError,
)
from app.structured import StructuredOutputValidationError

type ThinkingLevel = Literal["minimal", "low", "medium", "high"]
type OutputValidator[ModelT: BaseModel] = Callable[[ModelT], None]


class GeminiRateLimiter(Protocol):
    async def acquire(self, user_id: UUID) -> None: ...


class _Interactions(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class NoopGeminiRateLimiter:
    async def acquire(self, user_id: UUID) -> None:
        return None


@dataclass(frozen=True, slots=True)
class GeminiStructuredConfiguration:
    model: str
    api_version: str
    store: bool = False


class StructuredOutputClient(Protocol):
    @property
    def configuration(self) -> GeminiStructuredConfiguration: ...

    async def generate[ModelT: BaseModel](
        self,
        *,
        user_id: UUID,
        schema_model: type[ModelT],
        system_instruction: str,
        input_payload: Any,
        thinking_level: ThinkingLevel,
        validator: OutputValidator[ModelT] | None = None,
        omit_array_upper_bounds: bool = False,
    ) -> ModelT: ...


class GeminiStructuredClient:
    def __init__(
        self,
        *,
        client: Any,
        limiter: GeminiRateLimiter | None = None,
        model: str = "gemini-3.6-flash",
        api_version: str = "v1",
        timeout_seconds: float = 15,
        max_attempts: int = 2,
    ) -> None:
        self._interactions: _Interactions = client.interactions
        self._limiter = limiter or NoopGeminiRateLimiter()
        self._model = model
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, min(max_attempts, 2))
        self._configuration = GeminiStructuredConfiguration(
            model=model,
            api_version=api_version,
        )

    @property
    def configuration(self) -> GeminiStructuredConfiguration:
        return self._configuration

    async def generate[ModelT: BaseModel](
        self,
        *,
        user_id: UUID,
        schema_model: type[ModelT],
        system_instruction: str,
        input_payload: Any,
        thinking_level: ThinkingLevel,
        validator: OutputValidator[ModelT] | None = None,
        omit_array_upper_bounds: bool = False,
    ) -> ModelT:
        validation_error: str | None = None
        last_provider_error: GeminiError | None = None
        for attempt in range(self._max_attempts):
            instruction = system_instruction
            if validation_error is not None:
                instruction += (
                    "\n\n이전 JSON의 검증 오류를 수정해 전체 JSON을 다시 반환하세요. "
                    f"검증 오류: {validation_error}"
                )
            await self._limiter.acquire(user_id)
            try:
                async with asyncio.timeout(self._timeout_seconds):
                    interaction = await self._interactions.create(
                        api_version=self._api_version,
                        model=self._model,
                        store=False,
                        system_instruction=instruction,
                        response_format={
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": self._provider_json_schema(
                                schema_model,
                                omit_array_upper_bounds=omit_array_upper_bounds,
                            ),
                        },
                        generation_config={"thinking_level": thinking_level},
                        input=input_payload,
                        timeout=self._timeout_seconds,
                    )
            except Exception as exc:  # noqa: BLE001 - external SDK boundary
                mapped = self.map_error(exc)
                last_provider_error = mapped
                if not mapped.retryable or attempt + 1 >= self._max_attempts:
                    break
                continue

            output_text = interaction.output_text
            if not isinstance(output_text, str) or not output_text.strip():
                validation_error = (
                    "location=output_text; type=missing; message=non-empty text required"
                )
            else:
                try:
                    result = schema_model.model_validate_json(output_text)
                    if validator is not None:
                        validator(result)
                    return result
                except ValidationError as exc:
                    validation_error = self._safe_pydantic_summary(exc, schema_model)
                except StructuredOutputValidationError as exc:
                    validation_error = exc.safe_summary

            if attempt + 1 >= self._max_attempts:
                raise GeminiInvalidResponseError(
                    "Gemini 구조화 응답이 스키마 검증에 실패했습니다."
                ) from None

        if last_provider_error is not None:
            raise last_provider_error from None
        raise GeminiInvalidResponseError("Gemini 응답을 검증할 수 없습니다.")

    @staticmethod
    def _provider_json_schema(
        schema_model: type[BaseModel],
        *,
        omit_array_upper_bounds: bool,
    ) -> dict[str, Any]:
        schema = schema_model.model_json_schema()
        if not omit_array_upper_bounds:
            return schema

        def remove_array_upper_bounds(value: object) -> None:
            if isinstance(value, dict):
                for key, child in list(value.items()):
                    if key == "maxItems":
                        del value[key]
                        continue
                    remove_array_upper_bounds(child)
            elif isinstance(value, list):
                for child in value:
                    remove_array_upper_bounds(child)

        remove_array_upper_bounds(schema)
        return schema

    @staticmethod
    def _safe_pydantic_summary(exc: ValidationError, schema_model: type[BaseModel]) -> str:
        allowed_paths = GeminiStructuredClient._schema_field_names(schema_model)
        allowed_codes = {
            "date_from_datetime_parsing",
            "date_parsing",
            "dict_type",
            "extra_forbidden",
            "greater_than",
            "greater_than_equal",
            "int_parsing",
            "less_than",
            "less_than_equal",
            "list_type",
            "literal_error",
            "missing",
            "string_too_long",
            "string_too_short",
            "time_parsing",
            "too_long",
            "too_short",
            "uuid_parsing",
        }
        summaries = []
        for error in exc.errors(include_input=False, include_url=False)[:20]:
            location_parts = error.get("loc", ())
            if all(
                (isinstance(part, int) and 0 <= part <= 1095)
                or (isinstance(part, str) and part in allowed_paths)
                for part in location_parts
            ):
                location = ".".join(str(part) for part in location_parts) or "root"
            else:
                location = "root"
            error_type = error.get("type")
            code = error_type if error_type in allowed_codes else "validation_error"
            summaries.append(f"path={location}; code={code}")
        return " | ".join(summaries)

    @staticmethod
    def _schema_field_names(schema_model: type[BaseModel]) -> frozenset[str]:
        field_names: set[str] = set()

        def visit(value: object) -> None:
            if isinstance(value, dict):
                properties = value.get("properties")
                if isinstance(properties, dict):
                    field_names.update(
                        key
                        for key in properties
                        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", key)
                    )
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(schema_model.model_json_schema())
        return frozenset(field_names)

    @staticmethod
    def map_error(exc: Exception) -> GeminiError:
        if isinstance(exc, GeminiRateLimitedError):
            return GeminiRateLimitedError("Gemini 호출 한도를 초과했습니다.")
        if isinstance(exc, GeminiContentBlockedError):
            return GeminiContentBlockedError("Gemini 안전 정책으로 응답할 수 없습니다.")
        if isinstance(exc, GeminiConfigurationError):
            return GeminiConfigurationError("Gemini 인증 또는 설정이 올바르지 않습니다.")
        if isinstance(exc, GeminiInvalidResponseError):
            return GeminiInvalidResponseError("Gemini 구조화 응답이 올바르지 않습니다.")
        if isinstance(exc, GeminiError):
            return GeminiUnavailableError("Gemini 서비스를 일시적으로 사용할 수 없습니다.")
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return GeminiUnavailableError("Gemini 요청 시간이 초과되었습니다.")
        status_code = getattr(exc, "status_code", None)
        if not isinstance(status_code, int) or isinstance(status_code, bool):
            provider_code = getattr(exc, "code", None)
            status_code = (
                provider_code
                if isinstance(provider_code, int) and not isinstance(provider_code, bool)
                else None
            )
        if status_code == 429:
            return GeminiRateLimitedError("Gemini 호출 한도를 초과했습니다.")
        if status_code == 422 or getattr(exc, "blocked", False):
            return GeminiContentBlockedError("Gemini 안전 정책으로 응답할 수 없습니다.")
        if status_code in {400, 401, 403}:
            return GeminiConfigurationError("Gemini 인증 또는 설정이 올바르지 않습니다.")
        return GeminiUnavailableError("Gemini 서비스를 일시적으로 사용할 수 없습니다.")
