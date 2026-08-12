from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings


def create_pool(settings: Settings) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        open=False,
        kwargs={"row_factory": dict_row},
    )
