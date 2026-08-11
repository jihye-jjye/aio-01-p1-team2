import json
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import pytest

from app.cli.api import ApiError, CoachApiClient

type ApiCall = Callable[[CoachApiClient], Awaitable[dict[str, object]]]


@pytest.mark.asyncio
async def test_signup_authenticates_follow_up_requests_and_returns_normalized_login_id() -> None:
    signup_requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal signup_requests
        if request.url.path == "/api/v1/auth/signup":
            signup_requests += 1
            assert request.method == "POST"
            assert json.loads(request.content) == {
                "login_id": " New.User ",
                "login_pw": "  password with spaces  ",
                "user_name": "홍길동",
            }
            return httpx.Response(
                201,
                json={
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "login_id": "new.user",
                    "access_token": "signup-access-token",
                    "refresh_token": "must-not-be-used-by-cli",
                    "token_type": "bearer",
                    "expires_in": 1800,
                },
            )
        assert request.url.path == "/api/v1/profile"
        assert request.headers["Authorization"] == "Bearer signup-access-token"
        return httpx.Response(200, json={"target_role": "백엔드 개발자"})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)

    login_id = await client.signup(" New.User ", "  password with spaces  ", "홍길동")
    profile = await client.profile()

    assert login_id == "new.user"
    assert profile == {"target_role": "백엔드 개발자"}
    assert signup_requests == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_saved_jobs_uses_authenticated_global_list_endpoint_without_query() -> None:
    saved_jobs = [{"id": "job-id", "company_name": "예시회사"}]
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=saved_jobs)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.saved_jobs()

    assert response == saved_jobs
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/saved-jobs"
    assert requests[0].url.query == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    assert requests[0].content == b""
    await http_client.aclose()


@pytest.mark.asyncio
async def test_saved_jobs_rejects_non_list_success_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.saved_jobs()

    assert raised.value.status_code == 502
    assert raised.value.code == "INVALID_RESPONSE"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_saved_job_recommendation_uses_authenticated_endpoint() -> None:
    recommendation = {
        "preferred_environment": "원격 근무",
        "match_score": 50,
        "matched_terms": ["원격"],
        "recommendation_source": "llm",
        "reason": "전체 프로필 기준 추천",
        "job": {"id": "job-id"},
    }
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=recommendation)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.saved_job_recommendation()

    assert response == recommendation
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/saved-jobs/recommendation"
    assert requests[0].url.query == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_signup_network_failure_is_not_retried() -> None:
    signup_requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal signup_requests
        signup_requests += 1
        raise httpx.ReadTimeout("timed out", request=request)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)

    with pytest.raises(ApiError) as raised:
        await client.signup("new.user", "password", "홍길동")

    assert raised.value.code == "CLIENT_TIMEOUT"
    assert signup_requests == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_state_change_retries_timeout_with_same_request_id() -> None:
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"step": "conversation"})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.message("session-id", "안녕하세요")

    assert response == {"step": "conversation"}
    assert len(requests) == 2
    assert requests[0]["request_id"] == requests[1]["request_id"]
    assert requests[0]["text"] == "안녕하세요"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_assistant_session_calls_use_authenticated_revisioned_endpoints() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"session_id": "session-id", "revision": 1})
        if request.url.path.endswith("/finalize"):
            return httpx.Response(201, json={"session_id": "session-id", "session_revision": 1})
        return httpx.Response(201, json={"session_id": "session-id", "revision": 0})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    started = await client.start_assistant_session()
    answered = await client.send_assistant_message("session-id", 0, "내일 일정을 알려줘")
    finalized = await client.finalize_assistant_session("session-id", 1)

    assert started == {"session_id": "session-id", "revision": 0}
    assert answered == {"session_id": "session-id", "revision": 1}
    assert finalized == {"session_id": "session-id", "session_revision": 1}
    assert [request.method for request in requests] == ["POST", "POST", "POST"]
    assert [request.url.path for request in requests] == [
        "/api/v1/assistant/sessions",
        "/api/v1/assistant/sessions/session-id/messages",
        "/api/v1/assistant/sessions/session-id/finalize",
    ]
    bodies = [json.loads(request.content) for request in requests]
    assert all(str(UUID(str(body["request_id"]))) == body["request_id"] for body in bodies)
    assert bodies[1]["expected_revision"] == 0
    assert bodies[1]["text"] == "내일 일정을 알려줘"
    assert bodies[2]["expected_revision"] == 1
    assert all(request.headers["Authorization"] == "Bearer access-token" for request in requests)
    await http_client.aclose()


@pytest.mark.asyncio
async def test_assistant_message_retry_preserves_request_id_revision_and_text() -> None:
    bodies: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"session_id": "session-id", "revision": 5})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.send_assistant_message("session-id", 4, "지원 전략을 알려줘")

    assert response == {"session_id": "session-id", "revision": 5}
    assert len(bodies) == 2
    assert bodies[0] == bodies[1]
    assert bodies[0]["expected_revision"] == 4
    assert bodies[0]["text"] == "지원 전략을 알려줘"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_assistant_success_with_invalid_json_becomes_sanitized_api_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, content=b"not-json")

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.start_assistant_session()

    assert raised.value.status_code == 502
    assert raised.value.code == "INVALID_RESPONSE"
    assert str(raised.value) == "서버 응답 형식을 확인할 수 없습니다."
    await http_client.aclose()


@pytest.mark.asyncio
async def test_confirmation_retry_keeps_revision_and_request_id() -> None:
    requests: list[httpx.Request] = []
    bodies: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        bodies.append(json.loads(request.content))
        if len(requests) == 1:
            raise httpx.ConnectError("disconnected", request=request)
        return httpx.Response(200, json={"step": "completed"})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.confirm("session-id", 7)

    assert response == {"step": "completed"}
    assert [request.method for request in requests] == ["POST", "POST"]
    assert [request.url.path for request in requests] == [
        "/api/v1/onboarding/sessions/session-id/confirm",
        "/api/v1/onboarding/sessions/session-id/confirm",
    ]
    assert bodies[0] == bodies[1]
    assert bodies[0]["expected_revision"] == 7
    assert "action" not in bodies[0]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_onboarding_result_reads_review_snapshot_without_body() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"step": "review", "payload": {"draft_revision": 4}})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.onboarding_result("session-id")

    assert response == {"step": "review", "payload": {"draft_revision": 4}}
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/onboarding/sessions/session-id/result"
    assert requests[0].url.query == b""
    assert requests[0].content == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_notices_reads_authenticated_global_list_endpoint() -> None:
    notices = [{"id": "notice-id", "title": "공지", "content": "내용"}]
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=notices)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.notices()

    assert response == notices
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/notices"
    assert requests[0].url.query == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_notices_rejects_non_list_success_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.notices()

    assert raised.value.status_code == 502
    assert raised.value.code == "INVALID_RESPONSE"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_today_quests_reads_authenticated_today_endpoint() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"date": "2026-08-10", "quests": []})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.today_quests()

    assert response == {"date": "2026-08-10", "quests": []}
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/quests/today"
    assert requests[0].url.query == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_plans_summary_reads_authenticated_summary_endpoint_without_query() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "user_exp": 40,
                "plan_count": 1,
                "aggregate_total_task_count": 3,
                "aggregate_completed_task_count": 2,
                "aggregate_percent": 66,
                "plans": [{"id": "plan-id", "percent": 66}],
            },
        )

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.plans_summary()

    assert response["aggregate_percent"] == 66
    assert response["plan_count"] == 1
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/plans/summary"
    assert requests[0].url.query == b""
    assert requests[0].content == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_plans_summary_does_not_retry_transport_failures() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.plans_summary()

    assert raised.value.code == "CLIENT_TIMEOUT"
    assert len(requests) == 1
    await http_client.aclose()
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "task-id", "status": "completed"})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.set_today_quest_status("task-id", "completed")

    assert response == {"id": "task-id", "status": "completed"}
    assert len(requests) == 1
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/api/v1/quests/task-id"
    assert json.loads(requests[0].content) == {"status": "completed"}
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param("timeout", id="timeout"),
        pytest.param("network", id="network"),
    ],
)
@pytest.mark.asyncio
async def test_create_plan_proposal_retries_once_with_byte_identical_supplied_uuid(
    failure: str,
) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("timed out", request=request)
            raise httpx.ConnectError("disconnected", request=request)
        return httpx.Response(201, json={"id": "proposal-id", "days": []})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.create_plan_proposal("40000000-0000-4000-8000-000000000001")

    assert response == {"id": "proposal-id", "days": []}
    assert len(requests) == 2
    assert [request.method for request in requests] == ["POST", "POST"]
    assert [request.url.path for request in requests] == [
        "/api/v1/plan-proposals",
        "/api/v1/plan-proposals",
    ]
    assert requests[0].content == requests[1].content
    assert json.loads(requests[0].content) == {"request_id": "40000000-0000-4000-8000-000000000001"}
    assert all(request.headers["Authorization"] == "Bearer access-token" for request in requests)
    await http_client.aclose()


@pytest.mark.asyncio
async def test_create_plan_proposal_sends_selected_saved_job_id() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"id": "proposal-id", "days": []})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    await client.create_plan_proposal(
        "40000000-0000-4000-8000-000000000001",
        saved_job_id="90000000-0000-4000-8000-000000000001",
    )

    assert json.loads(requests[0].content) == {
        "request_id": "40000000-0000-4000-8000-000000000001",
        "saved_job_id": "90000000-0000-4000-8000-000000000001",
    }
    await http_client.aclose()


@pytest.mark.asyncio
async def test_create_plan_proposal_stops_after_one_automatic_retry() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.create_plan_proposal("40000000-0000-4000-8000-000000000001")

    assert raised.value.code == "CLIENT_TIMEOUT"
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    await http_client.aclose()


@pytest.mark.asyncio
async def test_create_plan_proposal_does_not_retry_retryable_server_error() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "still processing",
                    "retryable": True,
                    "details": {},
                }
            },
        )

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await client.create_plan_proposal("40000000-0000-4000-8000-000000000001")

    assert raised.value.code == "SERVICE_UNAVAILABLE"
    assert raised.value.retryable is True
    assert len(requests) == 1
    await http_client.aclose()


@pytest.mark.parametrize(
    ("call", "expected_path", "expected_query"),
    [
        pytest.param(
            lambda client: client.pending_plan_proposal(),
            "/api/v1/plan-proposals/pending",
            "days=7",
            id="pending-default",
        ),
        pytest.param(
            lambda client: client.pending_plan_proposal(start_on="2026-08-11", days=5),
            "/api/v1/plan-proposals/pending",
            "start_on=2026-08-11&days=5",
            id="pending-window",
        ),
        pytest.param(
            lambda client: client.plan_proposal("proposal-id"),
            "/api/v1/plan-proposals/proposal-id",
            "days=7",
            id="proposal-default",
        ),
        pytest.param(
            lambda client: client.plan_proposal("proposal-id", start_on="2026-08-12", days=6),
            "/api/v1/plan-proposals/proposal-id",
            "start_on=2026-08-12&days=6",
            id="proposal-window",
        ),
        pytest.param(
            lambda client: client.active_plan(),
            "/api/v1/plans/active",
            "days=7",
            id="active-default",
        ),
        pytest.param(
            lambda client: client.active_plan(start_on="2026-08-13", days=8),
            "/api/v1/plans/active",
            "start_on=2026-08-13&days=8",
            id="active-window",
        ),
        pytest.param(
            lambda client: client.plan("plan-id"),
            "/api/v1/plans/plan-id",
            "days=7",
            id="plan-default",
        ),
        pytest.param(
            lambda client: client.plan("plan-id", start_on="2026-08-14", days=9),
            "/api/v1/plans/plan-id",
            "start_on=2026-08-14&days=9",
            id="plan-window",
        ),
    ],
)
@pytest.mark.asyncio
async def test_plan_window_reads_use_exact_paths_queries_and_direct_bodies(
    call: ApiCall,
    expected_path: str,
    expected_query: str,
) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"requested_start_on": "2026-08-11", "days": []})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await call(client)

    assert response == {"requested_start_on": "2026-08-11", "days": []}
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == expected_path
    assert requests[0].url.query.decode() == expected_query
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    assert requests[0].content == b""
    await http_client.aclose()


@pytest.mark.parametrize(
    ("call", "expected_path"),
    [
        pytest.param(
            lambda client: client.accept_plan_proposal("proposal-id"),
            "/api/v1/plan-proposals/proposal-id/accept",
            id="accept",
        ),
        pytest.param(
            lambda client: client.reject_plan_proposal("proposal-id"),
            "/api/v1/plan-proposals/proposal-id/reject",
            id="reject",
        ),
        pytest.param(
            lambda client: client.complete_plan("plan-id"),
            "/api/v1/plans/plan-id/complete",
            id="complete",
        ),
    ],
)
@pytest.mark.asyncio
async def test_plan_decisions_and_completion_post_without_a_body(
    call: ApiCall,
    expected_path: str,
) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "updated"})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await call(client)

    assert response == {"status": "updated"}
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == expected_path
    assert requests[0].url.query == b""
    assert requests[0].content == b""
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_set_plan_task_status_patches_exact_status_body() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "task-id", "status": "completed"})

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    response = await client.set_plan_task_status("plan-id", "task-id", "completed")

    assert response == {"id": "task-id", "status": "completed"}
    assert len(requests) == 1
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/api/v1/plans/plan-id/tasks/task-id"
    assert json.loads(requests[0].content) == {"status": "completed"}
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await http_client.aclose()


@pytest.mark.parametrize(
    ("call", "expected_method", "expected_path"),
    [
        pytest.param(
            lambda client: client.pending_plan_proposal(),
            "GET",
            "/api/v1/plan-proposals/pending",
            id="pending-read",
        ),
        pytest.param(
            lambda client: client.plan_proposal("proposal-id"),
            "GET",
            "/api/v1/plan-proposals/proposal-id",
            id="proposal-read",
        ),
        pytest.param(
            lambda client: client.active_plan(),
            "GET",
            "/api/v1/plans/active",
            id="active-read",
        ),
        pytest.param(
            lambda client: client.plan("plan-id"),
            "GET",
            "/api/v1/plans/plan-id",
            id="plan-read",
        ),
        pytest.param(
            lambda client: client.accept_plan_proposal("proposal-id"),
            "POST",
            "/api/v1/plan-proposals/proposal-id/accept",
            id="accept",
        ),
        pytest.param(
            lambda client: client.reject_plan_proposal("proposal-id"),
            "POST",
            "/api/v1/plan-proposals/proposal-id/reject",
            id="reject",
        ),
        pytest.param(
            lambda client: client.set_plan_task_status("plan-id", "task-id", "completed"),
            "PATCH",
            "/api/v1/plans/plan-id/tasks/task-id",
            id="task-patch",
        ),
        pytest.param(
            lambda client: client.complete_plan("plan-id"),
            "POST",
            "/api/v1/plans/plan-id/complete",
            id="complete",
        ),
    ],
)
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param("timeout", id="timeout"),
        pytest.param("network", id="network"),
    ],
)
@pytest.mark.asyncio
async def test_non_generation_plan_operations_do_not_retry_transport_failures(
    call: ApiCall,
    expected_method: str,
    expected_path: str,
    failure: str,
) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        raise httpx.ConnectError("disconnected", request=request)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    with pytest.raises(ApiError) as raised:
        await call(client)

    expected_code = "CLIENT_TIMEOUT" if failure == "timeout" else "CLIENT_NETWORK_ERROR"
    assert raised.value.code == expected_code
    assert len(requests) == 1
    assert requests[0].method == expected_method
    assert requests[0].url.path == expected_path
    await http_client.aclose()


@pytest.mark.asyncio
async def test_clear_access_token_is_local_idempotent_and_blocks_authenticated_requests() -> None:
    remote_requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal remote_requests
        remote_requests += 1
        return httpx.Response(500)

    http_client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    client = CoachApiClient(client=http_client)
    client._access_token = "access-token"

    client.clear_access_token()
    client.clear_access_token()

    with pytest.raises(ApiError) as raised:
        await client.profile()
    assert raised.value.status_code == 401
    assert raised.value.code == "UNAUTHORIZED"
    assert remote_requests == 0
    await http_client.aclose()
