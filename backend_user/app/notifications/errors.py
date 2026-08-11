from __future__ import annotations


class NotificationDomainError(RuntimeError):
    status_code = 500
    code = "NOTIFICATION_DATA_INTEGRITY_ERROR"
    retryable = False
    default_message = "알림 데이터를 안전하게 처리할 수 없습니다."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)

    @property
    def safe_details(self) -> dict[str, object]:
        return {}


class NotificationNotFoundError(NotificationDomainError):
    status_code = 404
    code = "NOTIFICATION_NOT_FOUND"
    default_message = "알림을 찾을 수 없습니다."


class NotificationDataIntegrityError(NotificationDomainError):
    pass
