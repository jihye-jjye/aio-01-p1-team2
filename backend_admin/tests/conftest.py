from __future__ import annotations

from uuid import UUID

import pytest

from app.core.dependencies import CurrentAdmin, get_current_admin
from app.main import app


TEST_ADMIN = CurrentAdmin(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    login_id="test_admin",
    role="admin",
    is_active=True,
)


@pytest.fixture(autouse=True)
def authenticated_admin() -> None:
    """기능별 테스트에서는 DB 인증 대신 검증된 관리자를 주입한다."""

    app.dependency_overrides[get_current_admin] = lambda: TEST_ADMIN
    yield
    app.dependency_overrides.pop(get_current_admin, None)
