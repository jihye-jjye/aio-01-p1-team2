import asyncio
import json
import re
from collections.abc import Callable
from datetime import date
from typing import Protocol
from uuid import UUID

from app.gemini.errors import GeminiError, GeminiInvalidResponseError
from app.profiles.models import ProfileOnboardingData
from app.saved_jobs.models import (
    SavedJobRecommendationDecision,
    SavedJobRecommendationView,
    SavedJobView,
)

_TOKEN_PATTERN = re.compile(r"[0-9a-zA-Z가-힣]+")
_IGNORED_ENVIRONMENT_TERMS = {
    "가능",
    "근무",
    "없음",
    "업무",
    "원함",
    "이상",
    "환경",
    "회사",
    "희망",
}
_PARTICLE_SUFFIXES = ("에서", "으로", "와", "과", "이", "가", "을", "를", "은", "는")
_TERM_ALIASES = {
    "remote": "원격",
    "리모트": "원격",
    "재택": "원격",
}
_LLM_BATCH_SIZE = 40
_KEYWORD_FALLBACK_REASON = (
    "Gemini 판단을 사용할 수 없어 희망 환경 키워드 일치율로 추천했습니다."
)


class SavedJobRepositoryPort(Protocol):
    async def get_recommendation_profile(
        self,
        *,
        user_id: UUID,
    ) -> ProfileOnboardingData: ...

    async def list_all(self) -> list[SavedJobView]: ...


class SavedJobRecommendationPort(Protocol):
    async def choose(
        self,
        *,
        user_id: UUID,
        profile: ProfileOnboardingData,
        candidates: list[SavedJobView],
    ) -> SavedJobRecommendationDecision: ...


class SavedJobService:
    def __init__(
        self,
        repository: SavedJobRepositoryPort,
        *,
        recommender: SavedJobRecommendationPort,
        today_provider: Callable[[], date],
    ) -> None:
        self._repository = repository
        self._recommender = recommender
        self._today_provider = today_provider

    async def list_saved_jobs(self) -> list[SavedJobView]:
        return await self._repository.list_all()

    async def recommend_saved_job(
        self,
        *,
        user_id: UUID,
    ) -> SavedJobRecommendationView | None:
        profile = await self._repository.get_recommendation_profile(user_id=user_id)
        saved_jobs = await self._repository.list_all()
        today = self._today_provider()
        eligible_jobs = [
            job for job in saved_jobs if job.deadline is None or job.deadline >= today
        ]
        if not eligible_jobs:
            return None

        try:
            decision = await self._choose_with_batches(
                user_id=user_id,
                profile=profile,
                candidates=eligible_jobs,
            )
            selected_job = _job_for_decision(decision, eligible_jobs)
        except GeminiError:
            return recommend_saved_job(
                preferred_environment=profile.preferred_environment,
                saved_jobs=eligible_jobs,
            )

        return SavedJobRecommendationView(
            preferred_environment=profile.preferred_environment,
            match_score=decision.match_score,
            matched_terms=decision.matched_terms,
            recommendation_source="llm",
            reason=decision.reason,
            job=selected_job,
        )

    async def _choose_with_batches(
        self,
        *,
        user_id: UUID,
        profile: ProfileOnboardingData,
        candidates: list[SavedJobView],
    ) -> SavedJobRecommendationDecision:
        batches = [
            candidates[start : start + _LLM_BATCH_SIZE]
            for start in range(0, len(candidates), _LLM_BATCH_SIZE)
        ]
        if len(batches) == 1:
            return await self._recommender.choose(
                user_id=user_id,
                profile=profile,
                candidates=batches[0],
            )

        batch_tasks = [
            asyncio.create_task(
                self._recommender.choose(
                    user_id=user_id,
                    profile=profile,
                    candidates=batch,
                )
            )
            for batch in batches
        ]
        try:
            batch_results = await asyncio.gather(*batch_tasks)
        except BaseException:
            for task in batch_tasks:
                task.cancel()
            await asyncio.gather(*batch_tasks, return_exceptions=True)
            raise
        finalists = [
            _job_for_decision(decision, batch)
            for decision, batch in zip(batch_results, batches, strict=True)
        ]
        return await self._recommender.choose(
            user_id=user_id,
            profile=profile,
            candidates=finalists,
        )


def recommend_saved_job(
    *,
    preferred_environment: str,
    saved_jobs: list[SavedJobView],
) -> SavedJobRecommendationView | None:
    if not saved_jobs:
        return None

    environment_terms = _environment_terms(preferred_environment)
    ranked: list[tuple[int, list[str], int, SavedJobView]] = []
    for position, saved_job in enumerate(saved_jobs):
        document = _job_document(saved_job)
        matched_terms = [term for term in environment_terms if term in document]
        score = (
            round(len(matched_terms) * 100 / len(environment_terms))
            if environment_terms
            else 0
        )
        ranked.append((score, matched_terms, -position, saved_job))

    score, matched_terms, _position, job = max(ranked, key=lambda item: (item[0], item[2]))
    return SavedJobRecommendationView(
        preferred_environment=preferred_environment,
        match_score=score,
        matched_terms=matched_terms,
        recommendation_source="keyword_fallback",
        reason=_KEYWORD_FALLBACK_REASON,
        job=job,
    )


def _job_for_decision(
    decision: SavedJobRecommendationDecision,
    candidates: list[SavedJobView],
) -> SavedJobView:
    for candidate in candidates:
        if candidate.id == decision.selected_job_id:
            return candidate
    raise GeminiInvalidResponseError("Gemini가 허용되지 않은 공고를 선택했습니다.")


def _environment_terms(value: str) -> list[str]:
    terms: list[str] = []
    for raw_term in _TOKEN_PATTERN.findall(value.casefold()):
        term = _strip_particle(raw_term)
        term = _TERM_ALIASES.get(term, term)
        if len(term) < 2 or term in _IGNORED_ENVIRONMENT_TERMS or term in terms:
            continue
        terms.append(term)
    return terms


def _strip_particle(term: str) -> str:
    for suffix in _PARTICLE_SUFFIXES:
        if term.endswith(suffix) and len(term) >= len(suffix) + 2:
            return term[: -len(suffix)]
    return term


def _job_document(saved_job: SavedJobView) -> str:
    extracted_data = json.dumps(
        saved_job.extracted_data,
        ensure_ascii=False,
        sort_keys=True,
    )
    document = (
        f"{saved_job.company_name} {saved_job.job_title} "
        f"{saved_job.posting_text} {extracted_data}"
    ).casefold()
    for alias, canonical in _TERM_ALIASES.items():
        document = document.replace(alias, canonical)
    return document
