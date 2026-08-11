from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.notifications.errors import NotificationNotFoundError
from app.notifications.models import (
    NotificationFeed,
    NotificationFeedSnapshot,
    NotificationView,
    StoredNotification,
)
from app.notifications.presentation import build_notification_view


class NotificationRepositoryPort(Protocol):
    async def sync_login_feed(self, *, user_id: UUID) -> NotificationFeedSnapshot: ...

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> StoredNotification | None: ...


class NotificationService:
    def __init__(self, repository: NotificationRepositoryPort) -> None:
        self._repository = repository

    async def login_feed(self, *, user_id: UUID) -> NotificationFeed:
        snapshot = await self._repository.sync_login_feed(user_id=user_id)
        return NotificationFeed(
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
            upcoming=[build_notification_view(item) for item in snapshot.upcoming],
            changes=[build_notification_view(item) for item in snapshot.changes],
            unread_count=snapshot.unread_count,
        )

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> NotificationView:
        notification = await self._repository.mark_read(
            user_id=user_id,
            notification_id=notification_id,
        )
        if notification is None:
            raise NotificationNotFoundError()
        return build_notification_view(notification)
