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


class UserDeleteForbiddenError(ServiceError):
    """보호 대상 관리자 계정은 영구 삭제할 수 없다."""


class NoticeNotFoundError(ServiceError):
    """공지사항이 존재하지 않는다."""


class NoticeStorageError(ServiceError):
    """공지사항 저장소 작업에 실패했다."""


class DashboardStorageError(ServiceError):
    """관리자 대시보드 집계 작업이 실패했다."""


class SavedJobStorageError(ServiceError):
    """저장된 취업 공고 조회 작업이 실패했다."""


class AdminAuthenticationError(ServiceError):
    """관리자 아이디, 비밀번호 또는 역할 검증 실패."""


class AdminAccountDisabledError(ServiceError):
    """관리자 계정이 비활성화됐거나 잠겨 있다."""


class AdminAuthStorageError(ServiceError):
    """관리자 인증 저장소 또는 토큰 처리 실패."""
