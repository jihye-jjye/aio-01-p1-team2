"""관리자 사용자 목록·상세·상태 변경·삭제 Service."""

from math import ceil
from uuid import UUID

from app.repositories.user_admin_repository import (
    UserAdminRepository,
    UserAdminRepositoryError,
)
from app.schemas.user_admin_schema import (
    AdminPlanSummary,
    AdminQuestItem,
    AdminQuestOverviewResponse,
    AdminQuestProgress,
    AdminRoadmapHistoryItem,
    AdminRoadmapHistoryResponse,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserOverview,
    AdminUserQueryParams,
    AdminUserUpdate,
)
from app.services.exceptions import (
    UserAdminStorageError,
    UserDeleteForbiddenError,
    UserNotFoundError,
)


class UserAdminService:
    def __init__(
        self,
        repository: UserAdminRepository | None = None,
    ) -> None:
        self.repository = repository or UserAdminRepository()

    def get_user_overview(self, user_id: UUID) -> AdminUserOverview:
        account = self.get_user_detail(user_id)

        return self._build_user_overview(account)

    def get_user_overview_by_login_id(
        self,
        login_id: str,
    ) -> AdminUserOverview:
        account = self.get_user_detail_by_login_id(login_id)

        return self._build_user_overview(account)

    def get_user_roadmaps_by_login_id(
        self,
        login_id: str,
    ) -> AdminRoadmapHistoryResponse:
        overview = self.get_user_overview_by_login_id(login_id)

        return AdminRoadmapHistoryResponse(
            login_id=overview.account.login_id,
            items=overview.roadmap_history,
        )

    def get_user_quests_by_login_id(
        self,
        login_id: str,
    ) -> AdminQuestOverviewResponse:
        overview = self.get_user_overview_by_login_id(login_id)

        return AdminQuestOverviewResponse(
            login_id=overview.account.login_id,
            quests=overview.quests,
            active_plan_progress=overview.quest_progress,
        )

    def _build_user_overview(
        self,
        account: AdminUserDetail,
    ) -> AdminUserOverview:
        user_id = account.id

        try:
            plan_rows = self.repository.get_user_plans(user_id)
            quest_rows = self.repository.get_user_quests(user_id)
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
                "사용자 로드맵 이력을 조회할 수 없습니다."
            ) from exc

        plans = [
            AdminPlanSummary.model_validate(row)
            for row in plan_rows
        ]
        quests = [
            AdminQuestItem.model_validate(row)
            for row in quest_rows
        ]

        quests_by_plan: dict[UUID, list[AdminQuestItem]] = {}
        for quest in quests:
            if quest.plan_id is not None:
                quests_by_plan.setdefault(quest.plan_id, []).append(quest)

        roadmap_history: list[AdminRoadmapHistoryItem] = []
        for plan in plans:
            plan_quests = quests_by_plan.get(plan.id, [])
            progress = self._calculate_quest_progress(plan_quests)

            if (
                plan.status in {"completed", "expired", "superseded"}
                and plan.final_progress is not None
            ):
                progress = progress.model_copy(
                    update={
                        "progress_percent": plan.final_progress,
                        "is_final": True,
                    }
                )

            roadmap_history.append(
                AdminRoadmapHistoryItem(
                    plan=plan,
                    quests=plan_quests,
                    progress=progress,
                )
            )

        # 기존 평면 응답의 진행률은 활성 계획만 기준으로 계산한다.
        active_history = next(
            (
                history
                for history in roadmap_history
                if history.plan.status == "active"
            ),
            None,
        )
        quest_progress = (
            active_history.progress
            if active_history is not None
            else AdminQuestProgress(
                total=0,
                completed=0,
                in_progress=0,
                pending=0,
                progress_percent=0,
            )
        )

        return AdminUserOverview(
            account=account,
            plans=plans,
            quests=quests,
            quest_progress=quest_progress,
            roadmap_history=roadmap_history,
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

    def get_user_detail_by_login_id(
        self,
        login_id: str,
    ) -> AdminUserDetail:
        try:
            row = self.repository.get_user_by_login_id(login_id)
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
        """일반 사용자 계정과 모든 연관 데이터를 원자적으로 삭제한다."""

        account = self.get_user_detail(user_id)
        if account.role.value == "admin":
            raise UserDeleteForbiddenError(
                "관리자 계정은 영구 삭제할 수 없습니다."
            )

        try:
            row = self.repository.delete_user(user_id)
        except UserAdminRepositoryError as exc:
            raise UserAdminStorageError(
                "사용자를 삭제할 수 없습니다."
            ) from exc

        if row is None:
            raise UserNotFoundError("사용자를 찾을 수 없습니다.")

        deleted = dict(row)
        # 완전 삭제 후 profile은 존재하지 않으므로 삭제 전 조회값도 노출하지 않는다.
        deleted["profile"] = None
        return AdminUserDetail.model_validate(deleted)

    @staticmethod
    def _calculate_quest_progress(
        quests: list[AdminQuestItem],
    ) -> AdminQuestProgress:
        progress_quests = [
            quest
            for quest in quests
            if quest.kind == "task"
            and quest.counts_toward_progress
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

        return AdminQuestProgress(
            total=total,
            completed=completed,
            in_progress=in_progress,
            pending=pending,
            progress_percent=progress_percent,
        )
