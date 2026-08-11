from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime
from types import TracebackType
from uuid import UUID

import pytest

from app.notifications.errors import NotificationDataIntegrityError
from app.notifications.models import StoredNotification
from app.notifications.repository import PsycopgNotificationRepository

USER_ID = UUID(int=911)
OTHER_USER_ID = UUID(int=912)
PLAN_ID = UUID(int=913)
NOTIFICATION_ID = UUID(int=914)
NOW = datetime(2026, 8, 11, 1, tzinfo=UTC)


class FakeCursor:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def fetchone(self) -> object | None:
        if isinstance(self.value, list):
            return self.value[0] if self.value else None
        return self.value

    async def fetchall(self) -> list[object]:
        if self.value is None:
            return []
        return self.value if isinstance(self.value, list) else [self.value]


class FakeTransaction(AbstractAsyncContextManager[None]):
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    async def __aenter__(self) -> None:
        self.connection.transactions += 1

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.connection.exited_with = exc_type


class FakeConnection:
    def __init__(self, rows: list[object | None]) -> None:
        self.rows = rows
        self.statements: list[tuple[str, dict[str, object]]] = []
        self.transactions = 0
        self.exited_with: type[BaseException] | None = None

    async def execute(self, sql: str, parameters: dict[str, object]) -> FakeCursor:
        normalized = " ".join(sql.split()).lower()
        self.statements.append((normalized, parameters))
        return FakeCursor(self.rows.pop(0) if self.rows else None)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)


class FakeConnectionContext(AbstractAsyncContextManager[FakeConnection]):
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakePool:
    def __init__(self, rows: list[object | None]) -> None:
        self.value = FakeConnection(rows)

    def connection(self) -> FakeConnectionContext:
        return FakeConnectionContext(self.value)


def row(
    *,
    notification_id: UUID = NOTIFICATION_ID,
    notification_type: str = "check_in",
    payload: dict[str, object] | None = None,
    read_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": notification_id,
        "type": notification_type,
        "plan_id": PLAN_ID,
        "schedule_item_id": None,
        "available_at": NOW,
        "is_read": read_at is not None,
        "read_at": read_at,
        "payload": payload or {"message": "확인"},
        "created_at": NOW,
    }


@pytest.mark.asyncio
async def test_login_feed_syncs_and_reads_owned_due_rows_in_one_transaction() -> None:
    upcoming = row(
        notification_type="daily_tasks",
        payload={
            "version": "daily_tasks.v1",
            "date": "2026-08-11",
            "plan_title": "로드맵",
            "count": 0,
            "schedules": [],
        },
    )
    changes = row(notification_id=UUID(int=915), notification_type="roadmap_changed")
    pool = FakePool(
        [
            {"upserted_count": 1, "invalidated_count": 0},
            {
                "window_start": date(2026, 8, 11),
                "window_end": date(2026, 8, 17),
                "unread_count": 58,
            },
            [upcoming],
            [changes],
        ]
    )
    repository = PsycopgNotificationRepository(pool)  # type: ignore[arg-type]

    snapshot = await repository.sync_login_feed(user_id=USER_ID)

    assert pool.value.transactions == 1
    assert snapshot.window_start == date(2026, 8, 11)
    assert snapshot.window_end == date(2026, 8, 17)
    assert snapshot.unread_count == 58
    assert snapshot.upcoming == [StoredNotification.model_validate(upcoming)]
    assert snapshot.changes == [StoredNotification.model_validate(changes)]

    statements = pool.value.statements
    assert len(statements) == 4
    assert "app.sync_daily_task_notifications(%(user_id)s)" in statements[0][0]
    assert "timezone('asia/seoul', now())::date" in statements[1][0]
    assert "is_read = false" in statements[1][0]
    assert "invalidated_at is null" in statements[1][0]
    assert "available_at <= now()" in statements[1][0]
    assert "type = 'daily_tasks'" in statements[2][0]
    assert "payload ->> 'date' asc nulls last" in statements[2][0]
    assert "::date" not in statements[2][0]
    assert "order by" in statements[2][0] and "limit 7" in statements[2][0]
    assert "type <> 'daily_tasks'" in statements[3][0]
    assert "order by available_at desc, id desc" in statements[3][0]
    assert "limit 50" in statements[3][0]
    assert all(parameters == {"user_id": USER_ID} for _, parameters in statements)


@pytest.mark.asyncio
async def test_mark_read_is_owned_idempotent_and_does_not_touch_claim_state() -> None:
    first_read_at = NOW.replace(minute=5)
    stored_row = row(read_at=first_read_at)
    pool = FakePool([stored_row, stored_row])
    repository = PsycopgNotificationRepository(pool)  # type: ignore[arg-type]

    result = await repository.mark_read(
        user_id=USER_ID,
        notification_id=NOTIFICATION_ID,
    )
    repeated = await repository.mark_read(
        user_id=USER_ID,
        notification_id=NOTIFICATION_ID,
    )

    assert result == StoredNotification.model_validate(stored_row)
    assert repeated is not None and repeated.read_at == result.read_at == first_read_at
    sql, parameters = pool.value.statements[0]
    assert "where user_id = %(user_id)s" in sql
    assert "and id = %(notification_id)s" in sql
    assert "is_read = true" in sql
    assert "read_at = coalesce(read_at, now())" in sql
    assert "claim_token" not in sql and "claimed_until" not in sql
    assert parameters == {
        "user_id": USER_ID,
        "notification_id": NOTIFICATION_ID,
    }
    assert pool.value.statements[1][1] == parameters


@pytest.mark.asyncio
async def test_mark_read_rolls_back_when_returned_known_payload_is_malformed() -> None:
    malformed = row(
        notification_type="daily_tasks",
        read_at=NOW.replace(minute=5),
        payload={
            "version": "daily_tasks.v1",
            "date": "not-a-date",
            "plan_title": "로드맵",
            "count": 1,
            "schedules": [],
        },
    )
    pool = FakePool([malformed])
    repository = PsycopgNotificationRepository(pool)  # type: ignore[arg-type]

    with pytest.raises(NotificationDataIntegrityError):
        await repository.mark_read(
            user_id=USER_ID,
            notification_id=NOTIFICATION_ID,
        )

    # The validation exception must leave the explicit transaction, which makes
    # psycopg roll back the UPDATE instead of committing a read state the API rejected.
    assert pool.value.transactions == 1
    assert pool.value.exited_with is NotificationDataIntegrityError


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [USER_ID, OTHER_USER_ID])
async def test_missing_and_foreign_mark_read_have_the_same_none_result(user_id: UUID) -> None:
    pool = FakePool([None])
    repository = PsycopgNotificationRepository(pool)  # type: ignore[arg-type]

    result = await repository.mark_read(
        user_id=user_id,
        notification_id=NOTIFICATION_ID,
    )

    assert result is None
    assert pool.value.statements[0][1] == {
        "user_id": user_id,
        "notification_id": NOTIFICATION_ID,
    }
