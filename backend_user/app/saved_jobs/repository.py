from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app.api.errors import ProfileNotFoundError
from app.saved_jobs.models import SavedJobView


class PsycopgSavedJobRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_preferred_environment(self, *, user_id: UUID) -> str:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select preferred_environment
                from app.profiles
                where user_id = %(user_id)s
                  and onboarding_completed_at is not null
                """,
                {"user_id": user_id},
            )
            row = await cursor.fetchone()
        if row is None:
            raise ProfileNotFoundError
        return str(row["preferred_environment"])

    async def list_all(self) -> list[SavedJobView]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select
                  id, source_type, source_url, source_key, company_name,
                  job_title, deadline, posting_text, extracted_data,
                  created_at, updated_at
                from app.saved_jobs
                order by created_at desc, id desc
                """,
                {},
            )
            rows = await cursor.fetchall()
        return [SavedJobView.model_validate(row) for row in rows]
