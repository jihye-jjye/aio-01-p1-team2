# AI_JOB_COACH — 현재 구현 기준 README

AI_JOB_COACH를 목표로 개발 중인 팀 프로젝트 저장소다. 현재 `main`에는 FastAPI·Streamlit·Supabase 교육용 샘플과 일부 관리자 관리 API가 포함되어 있다. 목표 기능 전체가 완성된 상태는 아니다.

## 현재 디렉터리

```text
aio-01-p1-team2/
├── backend_user/      # 사용자 백엔드 샘플
├── backend_admin/     # 관리자 사용자·공지·로그·피드백 API
├── frontend_user/     # 사용자 Streamlit 샘플
├── frontend_admin/    # 관리자 Streamlit 샘플
├── docs/revised/      # 현재 구현 기준 수정 문서
└── develop_update_plan.md
```

## 현재 구현

### 관리자 백엔드

- 사용자 목록·검색·역할·활성 상태 필터
- 사용자 계정·프로필 상세 조회
- 사용자 활성 상태 변경과 삭제
- 공지사항 관리자 CRUD
- 일반 공지사항 조회
- AI 운영 로그 목록·상세·KPI 코드
- 사용자 피드백 조회·등록 코드
- `/health` 상태 확인

### 사용자 백엔드

- 회원·상품·Item·Gemini 채팅 교육용 샘플
- 현재 `auth_scheme` import 오타로 앱 시작 불가

### 프런트엔드

- Streamlit Multi Tab 샘플
- 고정 샘플 로그인
- 차트·DataFrame·상품·Item·채팅 예제
- 실제 취업 코치 사용자·관리자 화면은 미구현

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | Streamlit, HTTPX |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Database | Supabase PostgreSQL |
| AI | Google Gemini SDK |
| 인증 기반 | JWT(PyJWT), PBKDF2 helper |
| 테스트 | Pytest |

Redis·Refresh Token·Argon2는 목표 설계에는 있으나 현재 `main` 구현으로 확인되지 않는다.

## 실행

### 관리자 백엔드

```powershell
cd backend_admin
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

필수 환경변수 예시:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 프런트엔드 샘플

```powershell
cd frontend_user
pip install -r requirements.txt
python -m streamlit run app.py
```

관리자 샘플은 `frontend_admin`에서 같은 방식으로 실행한다.

## 테스트

```powershell
backend_admin\.venv\Scripts\python.exe -m pytest backend_admin\tests -q
```

현재 테스트는 관리자 Router와 일부 사용자·공지 Service를 대상으로 한다. 전체 사용자 여정 E2E 테스트는 없다.

## 알려진 제한사항

- 사용자 백엔드는 import 오류를 수정해야 실행된다.
- 관리자 로그인·대시보드·저장 공고 API는 현재 `main`에 등록되어 있지 않다.
- AI 로그·피드백 DB 생성 SQL이 없다.
- 프런트엔드는 실제 백엔드 인증 및 취업 도메인 API와 통합되지 않았다.
- 루트의 완성형 제품 설명과 현재 구현 사이에 차이가 있다.

## 브랜치 상태 참고

현재 로컬 `main`은 `origin/main`을 모두 포함하지만 로컬 커밋이 추가된 상태다. `origin/develop`에는 `main`에 병합되지 않은 기능 커밋들이 있으므로 통합 전에 차이와 충돌을 검토해야 한다.
