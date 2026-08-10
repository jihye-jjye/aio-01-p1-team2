from psycopg_pool import AsyncConnectionPool

from app.saved_jobs.models import SavedJobView


class PsycopgSavedJobRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

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
