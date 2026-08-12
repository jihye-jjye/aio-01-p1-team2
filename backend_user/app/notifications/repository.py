from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool
from pydantic import ValidationError

from app.notifications.errors import NotificationDataIntegrityError
from app.notifications.models import (
    NotificationFeedSnapshot,
    StoredNotification,
    parse_notification_payload,
)

NOTIFICATION_COLUMNS = """
  id, type, plan_id, schedule_item_id, available_at,
  is_read, read_at, payload, created_at
"""


class PsycopgNotificationRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def sync_login_feed(self, *, user_id: UUID) -> NotificationFeedSnapshot:
        parameters = {"user_id": user_id}
        async with self._pool.connection() as connection, connection.transaction():
            sync_cursor = await connection.execute(
                """
                select upserted_count, invalidated_count
                from app.sync_daily_task_notifications(%(user_id)s)
                """,
                parameters,
            )
            await sync_cursor.fetchone()

            summary_cursor = await connection.execute(
                """
                select
                  pg_catalog.timezone('Asia/Seoul', now())::date as window_start,
                  (
                    pg_catalog.timezone('Asia/Seoul', now())::date
                    + 6
                  ) as window_end,
                  pg_catalog.count(*) filter (
                    where is_read = false
                      and invalidated_at is null
                      and available_at <= now()
                  ) as unread_count
                from app.notifications
                where user_id = %(user_id)s
                """,
                parameters,
            )
            summary = await summary_cursor.fetchone()

            upcoming_cursor = await connection.execute(
                f"""
                select {NOTIFICATION_COLUMNS}
                from app.notifications
                where user_id = %(user_id)s
                  and type = 'daily_tasks'
                  and is_read = false
                  and invalidated_at is null
                  and available_at <= now()
                order by
                  payload ->> 'date' asc nulls last,
                  available_at asc,
                  id asc
                limit 7
                """,
                parameters,
            )
            upcoming_rows = await upcoming_cursor.fetchall()

            changes_cursor = await connection.execute(
                f"""
                select {NOTIFICATION_COLUMNS}
                from app.notifications
                where user_id = %(user_id)s
                  and type <> 'daily_tasks'
                  and is_read = false
                  and invalidated_at is null
                  and available_at <= now()
                order by available_at desc, id desc
                limit 50
                """,
                parameters,
            )
            change_rows = await changes_cursor.fetchall()

            try:
                if summary is None:
                    raise ValueError("missing notification feed summary")
                return NotificationFeedSnapshot(
                    window_start=summary["window_start"],
                    window_end=summary["window_end"],
                    upcoming=[self._stored(row) for row in upcoming_rows],
                    changes=[self._stored(row) for row in change_rows],
                    unread_count=summary["unread_count"],
                )
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                raise NotificationDataIntegrityError() from exc

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> StoredNotification | None:
        parameters = {
            "user_id": user_id,
            "notification_id": notification_id,
        }
        async with self._pool.connection() as connection, connection.transaction():
            cursor = await connection.execute(
                f"""
                update app.notifications
                set
                  is_read = true,
                  read_at = coalesce(read_at, now())
                where user_id = %(user_id)s
                  and id = %(notification_id)s
                returning {NOTIFICATION_COLUMNS}
                """,
                parameters,
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            notification = self._stored(row)
            parse_notification_payload(notification)
            return notification

    @staticmethod
    def _stored(row: Mapping[str, Any]) -> StoredNotification:
        try:
            return StoredNotification.model_validate(row)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise NotificationDataIntegrityError() from exc
