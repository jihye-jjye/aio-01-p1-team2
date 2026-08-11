"""관리자 사용자 목록·상세·상태 변경·삭제 Service."""

from math import ceil
from uuid import UUID

from app.repositories.user_admin_repository import (
    UserAdminRepository,
    UserAdminRepositoryError,
)
from app.schemas.user_admin_schema import (
    AdminUserDetail,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserQueryParams,
    AdminUserUpdate,
)
from app.services.exceptions import (
    UserAdminStorageError,
    UserNotFoundError,
)
from app.schemas.user_admin_schema import (
    AdminPlanSummary,
    AdminQuestItem,
    AdminQuestProgress,
    AdminUserOverview,
)

class UserAdminService:
    def __init__(
        self,
        repository: UserAdminRepository | None = None,
    ) -> None:
        self.repository = repository or UserAdminRepository()
    def get_user_overview(self, user_id: UUID) -> AdminUserOverview:
        account = self.get_user_detail(user_id)

        try:
            plan_rows = self.repository.get_user_plans(user_id)
            quest_rows = self.repository.get_user_quests(user_id)
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
            "사용자 상세 정보를 조회할 수 없습니다."
        ) from exc

        plans = [
            AdminPlanSummary.model_validate(row)
            for row in plan_rows
                ]

        quests = [
        AdminQuestItem.model_validate(row)
        for row in quest_rows
    ]

        progress_quests = [
        quest
        for quest in quests
        if quest.counts_toward_progress
        and quest.status != "cancelled"
    ]

        total = len(progress_quests)
        completed = sum(
        quest.status == "completed"
        for quest in progress_quests
    )
        in_progress = sum(
        quest.status == "in_progress"
        for quest in progress_quests
    )
        pending = sum(
        quest.status == "pending"
        for quest in progress_quests
    )

        progress_percent = (
        round(completed / total * 100)
        if total
        else 0
    )

        return AdminUserOverview(
        account=account,
        plans=plans,
        quests=quests,
        quest_progress=AdminQuestProgress(
            total=total,
            completed=completed,
            in_progress=in_progress,
            pending=pending,
            progress_percent=progress_percent,
        ),
        last_login_at=account.last_login_at,
    )


    def get_users(
        self,
        params: AdminUserQueryParams,
    ) -> AdminUserListResponse:
        try:
            rows, total = self.repository.get_users(params)
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
                "사용자 목록을 조회할 수 없습니다."
            ) from exc

        return AdminUserListResponse(
            items=[AdminUserListItem.model_validate(row) for row in rows],
            page=params.page,
            size=params.size,
            total=total,
            total_pages=ceil(total / params.size) if total else 0,
        )

    def get_user_detail(self, user_id: UUID) -> AdminUserDetail:
        try:
            row = self.repository.get_user_by_id(user_id)
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
                "사용자 상세 정보를 조회할 수 없습니다."
            ) from exc

        if row is None:
            raise UserNotFoundError("사용자를 찾을 수 없습니다.")
        return AdminUserDetail.model_validate(row)

    def update_user(
        self,
        user_id: UUID,
        payload: AdminUserUpdate,
    ) -> AdminUserDetail:
        try:
            updated = self.repository.update_user_active(
                user_id,
                is_active=payload.is_active,
            )
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
                "사용자 상태를 수정할 수 없습니다."
            ) from exc

        if updated is None:
            raise UserNotFoundError("사용자를 찾을 수 없습니다.")
        return self.get_user_detail(user_id)

    def delete_user(self, user_id: UUID) -> AdminUserDetail:
        """사용자 계정 행을 실제로 삭제한다."""

        try:
            row = self.repository.delete_user(user_id)
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
                "사용자를 삭제할 수 없습니다."
            ) from exc

        if row is None:
            raise UserNotFoundError("사용자를 찾을 수 없습니다.")

        row = dict(row)
        row["profile"] = None
        return AdminUserDetail.model_validate(row)
