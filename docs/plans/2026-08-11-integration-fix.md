# Frontend–Backend Integration Fix Plan

Date: 2026-08-11

## 1. Repair the user assistant contract

Files:

- `frontend_user/tests/test_assistant_client.py`
- `frontend_user/clients/assistant_client.py`
- `frontend_user/app_pages/assistant.py`

Steps:

1. Add a failing client test asserting a POST to `/assistant/sessions/{session_id}/messages` with a UUID `request_id`, the current revision, and normalized question text.
2. Add failing validation tests for a mismatched session, a non-sequential revision, and an empty assistant message.
3. Change `send_chat_message` to accept `session_id`, `expected_revision`, and `text`, and return the validated response object.
4. Track session revision and a pending question in Streamlit state.
5. Send submitted questions, append the assistant response, and require explicit retry after API failure.
6. Run the assistant client tests and compile the page.

## 2. Normalize frontend endpoint configuration

Files:

- `frontend_user/core/api_client.py`
- `frontend_user/.env.example`
- `frontend_admin/core/api_client.py`
- `frontend_admin/.env.example`

Steps:

1. Preserve environment-first configuration with Render defaults.
2. Normalize all request paths to exactly one slash at the base/path boundary.
3. Reject unsupported administrator-client roles and surface every non-success HTTP response consistently.
4. Replace the user example’s private-IP default with the deployed Render user API.
5. Document both administrator backend overrides.

## 3. Activate the administrator roadmap flow

Files:

- `frontend_admin/tests/test_loadmap_client.py`
- `frontend_admin/clients/loadmap_client.py`
- `frontend_admin/app_pages/loadmap.py`

Steps:

1. Assert that the client uses `/admin/users/by-login-id/{login_id}/roadmaps`.
2. Fix the missing slash.
3. Add a target login-ID input and load action to the page.
4. Render the returned roadmap and show backend errors without exposing secrets.

## 4. Align deployment and cross-frontend navigation

Files:

- `frontend_user/app_pages/home.py`
- `backend_user/app/cli/api.py`
- `backend_user/run.sh`
- `backend_admin/run.sh`
- `render.yaml`

Steps:

1. Point the CLI’s no-argument default to the deployed user Render service while retaining an environment override.
2. Make both backend launchers bind to `0.0.0.0` and honor `PORT` without development reload.
3. Declare the existing Render service names and production commands in a Blueprint.
4. Expose the separately deployed administrator Streamlit application through `ADMIN_FRONTEND_URL`; show configuration guidance when absent.

## 5. Record and verify the operating contract

Files:

- `docs/FRONTEND_BACKEND_INTEGRATION.md`

Steps:

1. Record backend/Streamlit URL ownership, override variables, entry points, request contracts, deployment commands, and the CORS decision.
2. Run focused frontend tests and syntax checks.
3. Run the available full test suites and distinguish pre-existing/concurrent failures from regressions.
4. Search executable configuration for stale private-IP, localhost, non-Render backend defaults, and malformed API paths.
5. Review `git diff` and do not commit.
