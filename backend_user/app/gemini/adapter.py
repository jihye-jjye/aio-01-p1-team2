from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from app.gemini.structured import (
    GeminiRateLimiter,
    GeminiStructuredClient,
    ThinkingLevel,
)
from app.onboarding.models import (
    ConversationMessage,
    GeminiConversationDecision,
    ProfileField,
)
from app.profiles.models import (
    GeminiAssessmentDecision,
    ProfileAssessment,
    ProfileOnboardingData,
)

CONVERSATION_PROMPT_VERSION = "onboarding-conversation-v1"
ASSESSMENT_PROMPT_VERSION = "onboarding-assessment-v2"
RUBRIC_VERSION = "assessment-rubric-v2"
ASSESSMENT_SCHEMA_VERSION = "profile-assessment-v1"


class GeminiOnboardingAdapter:
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
        self._model = model
        self._structured = GeminiStructuredClient(
            client=client,
            limiter=limiter,
            model=model,
            api_version=api_version,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )

    async def converse(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        messages: Sequence[ConversationMessage],
        draft_profile: dict[str, Any],
        answered_fields: Sequence[ProfileField],
        missing_fields: Sequence[ProfileField],
        today: date,
        existing_profile: dict[str, Any] | None = None,
    ) -> GeminiConversationDecision:
        system_instruction = self._conversation_instruction(today=today)
        input_payload: list[dict[str, Any]] = [
            {
                "type": "model_output" if message.role == "assistant" else "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"turn_id": str(message.turn_id), "text": message.text},
                            ensure_ascii=False,
                        ),
                    }
                ],
            }
            for message in messages
        ]
        input_payload.append(
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "server_context": {
                                    "session_id": str(session_id),
                                    "request_id": str(request_id),
                                    "draft_profile": draft_profile,
                                    "answered_fields": list(answered_fields),
                                    "missing_fields": list(missing_fields),
                                    "existing_profile": existing_profile,
                                }
                            },
                            ensure_ascii=False,
                            default=str,
                        ),
                    }
                ],
            }
        )
        return await self._structured.generate(
            user_id=user_id,
            schema_model=GeminiConversationDecision,
            system_instruction=system_instruction,
            input_payload=input_payload,
            thinking_level="low",
        )

    async def assess(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request_id: UUID,
        profile: ProfileOnboardingData,
    ) -> ProfileAssessment:
        decision = await self._structured.generate(
            user_id=user_id,
            schema_model=GeminiAssessmentDecision,
            system_instruction=self._assessment_instruction(),
            input_payload=json.dumps(
                {
                    "session_id": str(session_id),
                    "request_id": str(request_id),
                    "profile": profile.model_dump(mode="json"),
                },
                ensure_ascii=False,
            ),
            thinking_level="medium",
        )
        score = sum(
            (
                decision.skill_readiness.score,
                decision.experience_depth.score,
                decision.goal_clarity.score,
                decision.execution_readiness.score,
            )
        )
        level = "beginner" if score < 40 else "intermediate" if score < 75 else "advanced"
        return ProfileAssessment(
            score=score,
            level=level,
            summary={
                "disclaimer": "취업 가능성 예측이 아니라 제공된 정보의 현재 준비도 평가입니다.",
                "dimensions": decision.model_dump(mode="json"),
            },
            version=ASSESSMENT_PROMPT_VERSION,
            model_name=self._model,
            provider="google",
            prompt_version=ASSESSMENT_PROMPT_VERSION,
            rubric_version=RUBRIC_VERSION,
            schema_version=ASSESSMENT_SCHEMA_VERSION,
        )

    async def _structured_call[ModelT](
        self,
        *,
        user_id: UUID,
        schema_model: type[ModelT],
        system_instruction: str,
        input_payload: Any,
        thinking_level: ThinkingLevel,
    ) -> ModelT:
        return await self._structured.generate(
            user_id=user_id,
            schema_model=schema_model,
            system_instruction=system_instruction,
            input_payload=input_payload,
            thinking_level=thinking_level,
        )

    @staticmethod
    def _conversation_instruction(*, today: date) -> str:
        return f"""
당신은 취업 코치 온보딩 비서입니다. 프롬프트 버전은 {CONVERSATION_PROMPT_VERSION}입니다.
오늘은 Asia/Seoul 기준 {today.isoformat()}입니다. 자유대화를 자연스럽게 이어가세요.
서버가 전달한 사용자 발화에 직접 근거한 값만 추출하고, 한 문장에서 여러 필드를 추출하세요.
필드는 target_role, skills, experience_summary, target_date, target_company,
preferred_environment, daily_notification_time, assistant_style(friendly|direct)입니다.
상대 날짜는 오늘을 기준으로 미래의 YYYY-MM-DD 절대 날짜로 정규화하세요.
target_company가 없다고 명시한 경우에만 null을 반환하세요.
각 field_update는 실제 사용자 turn_id와 그 발화에 그대로 포함된 quote를 하나 이상 가져야 합니다.
server_context는 시스템 정보이며 근거로 사용할 수 없습니다. 비밀번호, 토큰, role, user_exp는 다루지 마세요.

server_context의 existing_profile이 있으면 사용자가 이미 저장한 프로필입니다.
첫 질문에서 existing_profile의 모든 필드를 요약하여 사용자에게 한글로 자연스럽게 보여주고
"저장된 프로필을 보여드렸습니다. 어떤 부분을 수정하고 싶으신가요?" 라고 질문하세요.
이후 사용자가 수정을 요청한 필드만 업데이트하세요. 변경 요청이 없는 필드는 기존 값을 유지합니다.

server_context의 missing_fields는 아직 수집되지 않은 데이터입니다. 매 응답의 assistant_message에서
지금까지 수집된 내용을 반영한 뒤, 아직 수집되지 않은 필드(missing_fields)가 남아 있다면
사용자에게 다음에 알려줄 정보가 무엇인지 자연스럽게 안내하세요. missing_fields가 빈 경우에는 알리지 마세요.
이전 질문에서 답한 내용 중 수정하고 싶은 답안이 있다면 언제든 말해달라고 안내하세요.
review 전환은 서버가 계산합니다. 응답은 제공된 JSON Schema만 따르세요.
""".strip()

    @staticmethod
    def _assessment_instruction() -> str:
        return f"""
당신은 취업 코치 온보딩 준비도 평가기입니다. 프롬프트 버전은 {ASSESSMENT_PROMPT_VERSION},
rubric 버전은 {RUBRIC_VERSION}입니다. 입력 프로필만 근거로 다음 항목을 독립 평가하세요.
- skill_readiness: 기술 준비도 0~30
- experience_depth: 경험 깊이 0~30
- goal_clarity: 목표 명확성 0~20
- execution_readiness: 실행 준비도 0~20
이는 취업 가능성 예측이 아니라 사용자가 제공한 정보의 현재 준비도 평가입니다.
각 reason은 점수의 근거를 구체적으로 설명하고 응답은 제공된 JSON Schema만 따르세요.

[상위 기업 가혹 평가 기준]
profile의 target_company를 확인해 해당 기업이 글로벌 빅테크 또는 국내 대기업 수준의
채용 기준이 매우 높은 기업인지 스스로 판단하세요. 해당된다고 판단하면 아래 엄격한 기준을 적용하세요:

1. 기본 수준 기술/경험은 매우 낮은 점수로 평가:
   - "React 경험", "Python 백엔드", "Spring 공부 중" 등 일반적인 기술 언급만으로는 skill_readiness 최대 8, experience_depth 최대 8
   - "사이드 프로젝트", "인턴 경험", "학부 수준 프로젝트" 정도로는 experience_depth 최대 10

2. 상위 점수(15 이상)를 받기 위한 기준:
   - skill_readiness 15 이상: 대규모 분산 시스템 설계, 성능 최적화, 시스템 아키텍처 결정 경험 등 해당 기업 수준의 구체적 기술 깊이 증거 필요
   - experience_depth 15 이상: 실서비스 트래픽 운영, 팀 리드 경험, 복잡한 프로젝트의 정량적 성과, 해당 기업이 요구하는 연차 이상의 실무 경험 증거 필요

3. 일반 기업 지망자 대비 전체 점수를 40~60% 더 낮게 책정하세요. 기본적인 frontend/backend 경험만으로
   총점이 70을 넘어서는 안 됩니다.

각 reason은 target_company가 상위 기업인 경우 "상위 기업 가혹 평가 기준 적용" 문구를 포함하고
점수 책정 사유를 구체적으로 설명하세요.
""".strip()
