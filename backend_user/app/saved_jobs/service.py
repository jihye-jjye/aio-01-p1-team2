import json
import re
from typing import Protocol
from uuid import UUID

from app.saved_jobs.models import SavedJobRecommendationView, SavedJobView

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


class SavedJobRepositoryPort(Protocol):
    async def get_preferred_environment(self, *, user_id: UUID) -> str: ...
    async def list_all(self) -> list[SavedJobView]: ...


class SavedJobService:
    def __init__(self, repository: SavedJobRepositoryPort) -> None:
        self._repository = repository

    async def list_saved_jobs(self) -> list[SavedJobView]:
        return await self._repository.list_all()

    async def recommend_saved_job(
        self,
        *,
        user_id: UUID,
    ) -> SavedJobRecommendationView | None:
        preferred_environment = await self._repository.get_preferred_environment(
            user_id=user_id
        )
        saved_jobs = await self._repository.list_all()
        return recommend_saved_job(
            preferred_environment=preferred_environment,
            saved_jobs=saved_jobs,
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
        job=job,
    )


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
