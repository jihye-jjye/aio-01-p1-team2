from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app.notices.models import NoticeView


class PsycopgNoticeRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_published(self, *, user_id: UUID) -> list[NoticeView]:
        del user_id
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                select id, title, content, is_pinned, published_at, expires_at
                from app.notices
                where published_at <= now()
                  and (expires_at is null or expires_at > now())
                order by is_pinned desc, published_at desc, id desc
                """,
                {},
            )
            rows = await cursor.fetchall()
        return [NoticeView.model_validate(row) for row in rows]
