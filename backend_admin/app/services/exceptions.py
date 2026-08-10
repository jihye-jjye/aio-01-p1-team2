"""관리자 백엔드 Service 계층에서 사용하는 도메인 예외."""


class ServiceError(Exception):
    """Service 계층 예외의 기반 클래스."""


class LogNotFoundError(ServiceError):
    """요청한 AI 로그가 존재하지 않는다."""


class LogAccessDeniedError(ServiceError):
    """현재 사용자가 해당 AI 로그에 접근할 수 없다."""


class LogStorageError(ServiceError):
    """AI 로그 저장소 작업이 실패했다."""


class FeedbackStorageError(ServiceError):
    """피드백 저장소 작업이 실패했다."""


class UserNotFoundError(ServiceError):
    """관리 대상 사용자가 존재하지 않는다."""


class UserAdminStorageError(ServiceError):
    """사용자 관리 저장소 작업이 실패했다."""


class NoticeNotFoundError(ServiceError):
    """공지사항이 존재하지 않는다."""


class NoticeStorageError(ServiceError):
    """공지사항 저장소 작업에 실패했다."""


class AdminAuthenticationError(ServiceError):
    """관리자 자격 증명이 올바르지 않다."""


class AdminAuthStorageError(ServiceError):
    """관리자 인증 설정 또는 토큰 발급을 사용할 수 없다."""
    """공지사항 저장소 작업이 실패했다."""
