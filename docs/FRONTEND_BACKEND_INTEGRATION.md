# 프론트엔드–백엔드 연동 운영 문서

최종 점검일: 2026-08-11

## 1. 배포 URL 계약

| 구분 | 코드 기본값 또는 설정값 | 소유 설정 |
|---|---|---|
| 사용자 API | `https://aio-01-p1-team2-1.onrender.com/api/v1` | `frontend_user`: `BACKEND_URL` |
| 관리자 API | `https://aio-01-p1-team2.onrender.com/api/v1` | `frontend_admin`: `BACKEND_ADMIN_URL` |
| 관리자 화면의 사용자 API | `https://aio-01-p1-team2-1.onrender.com/api/v1` | `frontend_admin`: `BACKEND_USER_URL` |
| 사용자 Streamlit | 배포 시 발급된 실제 `https://*.streamlit.app` 주소 | Streamlit Community Cloud |
| 관리자 Streamlit | 배포 시 발급된 실제 `https://*.streamlit.app` 주소 | 사용자 앱의 `ADMIN_FRONTEND_URL` |

실행 코드의 백엔드 기본값은 모두 Render HTTPS 주소다. 로컬 개발이 필요할 때만 `.env` 또는 Streamlit secrets로 덮어쓴다.

Streamlit Community Cloud의 실제 공개 앱 도메인은 `*.streamlit.app`이다. `share.streamlit.io`는 배포 화면에 접근할 때 보이는 도메인이며, 앱의 base URL로 하드코딩하지 않는다. 저장소에서는 실제 관리자 앱 주소를 알 수 없으므로 `ADMIN_FRONTEND_URL`에 임의 주소를 넣지 않는다.

## 2. URL 조합 규칙

- 프론트 base URL은 `/api/v1`까지 포함하고 끝의 `/`는 제거한다.
- 각 client path는 선행 `/` 유무와 관계없이 공통 HTTP client에서 정확히 한 개의 `/`로 정규화한다.
- 사용자 frontend의 기본 override 이름은 `BACKEND_URL`이다.
- 관리자 frontend는 사용자/관리자 서버를 구분해 `BACKEND_USER_URL`, `BACKEND_ADMIN_URL`을 사용한다.
- 관리자로 인증하는 호출만 관리자 서버를 선택한다. 알 수 없는 role 값은 조용히 사용자 서버로 보내지 않고 오류로 처리한다.

## 3. 수정된 주요 API 계약

### 사용자 AI 상담

세션 생성:

```text
POST {BACKEND_URL}/assistant/sessions
{"request_id": "UUID"}
```

메시지 전송:

```text
POST {BACKEND_URL}/assistant/sessions/{session_id}/messages
{
  "request_id": "UUID",
  "expected_revision": 0,
  "text": "질문"
}
```

프론트는 응답의 `session_id`가 요청 세션과 같은지, `revision`이 `expected_revision + 1`인지, `assistant_message`가 비어 있지 않은지 확인한다. 실패한 메시지는 같은 `request_id`와 revision을 보존하고 사용자가 재시도 버튼을 누를 때만 다시 보낸다.

### 관리자 사용자 로드맵

```text
GET {BACKEND_ADMIN_URL}/admin/users/by-login-id/{login_id}/roadmaps
Authorization: Bearer {admin_access_token}
```

관리자 페이지에서 조회 대상의 로그인 ID를 명시적으로 입력한다. 로그인한 관리자 자신의 ID를 대상 사용자 ID로 재사용하지 않는다.

## 4. Streamlit 설정

사용자 앱 엔트리포인트: `frontend_user/app.py`

사용자 Streamlit secrets의 root에 다음 값을 설정한다.

```toml
BACKEND_URL = "https://aio-01-p1-team2-1.onrender.com/api/v1"
ADMIN_FRONTEND_URL = "https://example-admin.streamlit.app"
```

두 번째 값은 형식 예시다. 반드시 실제로 배포한 관리자 앱 주소로 교체한다. 값이 없으면 사용자 홈의 관리자 이동 버튼은 비활성화되어 잘못된 내부 placeholder 페이지로 이동하지 않는다.

관리자 앱 엔트리포인트: `frontend_admin/app.py`

관리자 Streamlit secrets의 root에 다음 값을 설정한다.

```toml
BACKEND_USER_URL = "https://aio-01-p1-team2-1.onrender.com/api/v1"
BACKEND_ADMIN_URL = "https://aio-01-p1-team2.onrender.com/api/v1"
```

Streamlit root-level secrets는 환경 변수로도 노출되므로 현재 `os.getenv` 기반 설정과 호환된다.

## 5. Render 설정

저장소 루트의 `render.yaml`은 다음 두 web service를 정의한다.

| Render service | root directory | start command |
|---|---|---|
| `aio-01-p1-team2-1` | `backend_user` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `aio-01-p1-team2` | `backend_admin` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Blueprint 생성 또는 동기화 시 `sync: false` 항목에 실제 비밀값을 입력한다.

사용자 backend 필수값:

- `DATABASE_URL`
- `UPSTASH_REDIS_URL`
- `JWT_SECRET_KEY`
- `GEMINI_API_KEY`

관리자 backend 필수값:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JWT_SECRET_KEY`

사용자 backend의 `DATABASE_URL`과 관리자 backend의 Supabase 설정은 같은 프로젝트/데이터를 가리켜야 관리자 화면에서 사용자 상태와 로드맵을 조회할 수 있다.

두 backend의 `run.sh`도 `HOST=0.0.0.0`을 기본으로 하고 Render가 주는 `PORT`를 따른다. production 실행에는 `--reload`를 사용하지 않는다.

## 6. CORS 판단

현재 두 Streamlit 앱은 브라우저 JavaScript의 `fetch`가 아니라 Streamlit Python 프로세스의 `httpx`로 backend를 호출한다. 따라서 현재 연동에는 FastAPI CORS middleware가 필요하지 않다. 브라우저가 Render API를 직접 호출하도록 구조를 바꿀 때만 실제 `*.streamlit.app` origin을 허용 목록에 추가한다.

## 7. 검증 명령

```bash
python -m compileall -q frontend_user frontend_admin
bash -n backend_user/run.sh backend_admin/run.sh
pytest -q frontend_user/tests
pytest -q frontend_admin
```

전체 backend 회귀 검증은 각 폴더의 환경에서 실행한다.

```bash
cd backend_user && uv run --frozen pytest
cd backend_admin && pytest -q
```

URL 정적 점검에서는 실행 코드와 `.env.example`, `render.yaml`을 대상으로 사설 IP, localhost, 잘못된 `/api/v1admin` 조합이 남아 있지 않은지 확인한다. 역사 문서나 등록되지 않은 교육용 `item` 예제는 실제 navigation/API 계약에 포함하지 않는다.

## 8. 참고 자료

- Render Blueprint specification: <https://render.com/docs/blueprint-spec>
- Streamlit Community Cloud 배포: <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>
- Streamlit secrets 관리: <https://docs.streamlit.io/develop/concepts/connections/secrets-management>
