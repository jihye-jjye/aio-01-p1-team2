# Frontend–Backend Integration Fix Design

Date: 2026-08-11

## Goal

Make the two Streamlit frontends call the deployed Render backends through one explicit configuration contract, repair the currently disconnected user-assistant and administrator-roadmap flows, and leave deployment/verification guidance in the repository.

## Current failures

- The user frontend assistant posts to the nonexistent `/chat/gemini` endpoint and the page never invokes the method.
- The backend assistant contract is session based: `POST /api/v1/assistant/sessions/{session_id}/messages` with `request_id`, `expected_revision`, and `text`.
- The administrator roadmap client omits the leading slash, producing a URL shaped like `/api/v1admin/...`; its page does not invoke the client.
- The administrator frontend hardcodes both backend URLs instead of allowing deployment configuration.
- `frontend_user/.env.example`, the user backend CLI, and `backend_user/run.sh` retain a private-IP development default.
- The user page’s administrator-mode button points at an internal placeholder instead of the separately deployed administrator Streamlit app.
- There is no repository-owned Render Blueprint or end-to-end integration runbook.

## Design

### URL ownership

- User API default: `https://aio-01-p1-team2-1.onrender.com/api/v1`
- Administrator API default: `https://aio-01-p1-team2.onrender.com/api/v1`
- User frontend override: `BACKEND_URL`
- Administrator frontend overrides: `BACKEND_USER_URL`, `BACKEND_ADMIN_URL`
- Administrator Streamlit link: `ADMIN_FRONTEND_URL`; it deliberately has no guessed default because the actual Community Cloud subdomain is deployment-owned.

All HTTP clients strip trailing slashes from base URLs and add exactly one leading slash to request paths. Environment values take precedence over the safe Render defaults.

### User assistant flow

The page creates a backend session and stores its `session_id` and `revision`. Each submitted question is retained as a pending message, sent exactly once with a generated UUID request ID, and accepted only when the response session and next revision match. A failed request remains visible and requires an explicit retry, preventing an uncontrolled rerun loop.

### Administrator roadmap flow

The roadmap page requires the target user’s login ID. It calls the actual administrator route, `GET /api/v1/admin/users/by-login-id/{login_id}/roadmaps`, with an administrator-authenticated request and renders the response. The signed-in administrator’s own ID is not silently used as the target.

### Deployment

The root `render.yaml` declares the existing user and administrator Render service names, separate root directories, dependency installation, and production Uvicorn commands. Backend shell launchers bind to `0.0.0.0`, honor `PORT`, and do not enable reload by default.

Streamlit deployments keep their actual `*.streamlit.app` URLs outside source control. Root-level Streamlit secrets can supply the same variable names used by `os.getenv`.

### CORS

No CORS middleware is added. Both Streamlit apps currently make API requests from their Python server processes through `httpx`; they do not make browser-side cross-origin `fetch` calls. CORS must be added only if that architecture changes.

## Verification

- Contract tests cover assistant request/response validation and administrator URL/path composition.
- Targeted frontend tests run before broad backend suites.
- Static searches verify that executable defaults no longer point at the private IP and that Render backend URLs remain the only backend defaults.
- Existing unrelated changes under `backend_user/app/coach/` are excluded from this work and reported separately if they affect the full suite.
