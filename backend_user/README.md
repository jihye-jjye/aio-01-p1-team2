# AI 취업 코치 백엔드 (backend_user)

Gemini `gemini-3.6-flash` 자유대화 온보딩을 FastAPI, Redis, Supabase PostgreSQL, Rich 기반 인터랙티브 CLI로 연결하는 사용자 백엔드 서버입니다.

자체 계정 API는 `login_id/login_pw` 기반 회원가입과 로그인을 지원합니다. 회원가입 성공 시 access/refresh token을 즉시 발급합니다.

활성 계획은 날짜별 task를 모두 완료하는 순간 일일 목표를 달성하고 `+20 EXP`를 누적합니다. 완료 task를 되돌려 날짜가 다시 미달성이 되면 `-20 EXP`, 재완료하면 다시 `+20 EXP`가 반영되며 과거·미래 날짜에도 같은 규칙이 적용됩니다.

```bash
curl -X POST http://192.100.200.209:8010/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"login_id":"new.user","login_pw":"password123"}'
```

중복 ID는 `409 LOGIN_ID_ALREADY_EXISTS`, 입력 오류는 `422 VALIDATION_ERROR`, DB/Redis 장애는 `503 SERVICE_UNAVAILABLE`, Gemini 장애는 `502`로 응답합니다.

---

## 빠른 시작

```bash
# 서버 실행 (기본: 192.100.200.209:8010)
./run.sh

# 호스트/포트 변경
HOST=0.0.0.0 PORT=9000 ./run.sh

# CLI 앱 실행 (서버 실행 후 별도 터미널)
uv run --frozen ai-job-coach-cli
```

로컬 기본 백엔드 포트는 `8010`입니다.

---

## 디렉터리 구조

```
backend_user/
├── app/                    # FastAPI 애플리케이션
│   ├── main.py             # 앱 팩토리, lifespan(DB/Redis/Gemini 초기화), 예외 핸들러
│   ├── structured.py       # provider-neutral 구조화 출력 검증 에러
│   ├── api/                # HTTP 라우터, 스키마, 의존성 주입
│   │   ├── dependencies.py # 서비스·리포지토리·토큰 의존성 공급자
│   │   ├── errors.py       # APIErrorEnvelope, UnauthorizedError, ProfileNotFoundError
│   │   ├── router.py       # /api/v1 하위 전체 라우트 통합
│   │   ├── schemas.py      # 회원가입·로그인·온보딩·계획 요청 Pydantic 모델
│   │   └── routes/         # 엔드포인트 라우트 모듈
│   │       ├── auth.py             # /auth — signup, login
│   │       ├── onboarding.py       # /onboarding — 세션 시작, 메시지, confirm
│   │       ├── plan_proposals.py   # /plan-proposals — 제안 생성·조회·수락·거절
│   │       ├── plans.py            # /plans — 활성 계획 조회, task 상태 변경
│   │       └── profile.py          # /profile — 확정 프로필 조회
│   ├── auth/               # 인증 도메인
│   │   ├── errors.py       # LoginIdAlreadyExistsError
│   │   ├── models.py       # AccountAuthRecord, CurrentUser, LoginResult
│   │   ├── passwords.py    # Argon2 해싱/검증 (pwdlib)
│   │   ├── service.py      # AuthService — signup/login/refresh/logout
│   │   ├── stores.py       # RedisRefreshTokenStore — refresh token TTL 저장
│   │   └── tokens.py      # JWT access token 발급/검증
│   ├── cli/                # 터미널 CLI 클라이언트
│   │   ├── api.py          # CoachApiClient — HTTP API 래퍼
│   │   ├── app.py          # CLI 메인 — 인터랙티브 플로우, 명령 디스패치
│   │   ├── create_demo_user.py # 데모 사용자 직접 DB 삽입
│   │   └── renderer.py     # RichRenderer — rich 기반 터미널 렌더링
│   ├── core/               # 공통 설정
│   │   ├── config.py       # Settings — DB/Redis/JWT/Gemini/풀 설정
│   │   ├── api_response.py  # 범용 ApiResponse 모델
│   │   ├── chat_config.py  # 레거시 채팅 .env 로더
│   │   ├── password.py     # 레거시 PBKDF2 해싱
│   │   ├── supabase_config.py # 레거시 Supabase 클라이언트
│   │   └── upload_config.py  # 이미지 업로드 상수
│   ├── db/                 # PostgreSQL 영속성 계층
│   │   ├── pool.py         # psycopg AsyncConnectionPool 팩토리
│   │   ├── repositories.py # PsycopgAccountRepository, PsycopgProfileRepository
│   │   └── plan_repository.py # 계획 제안·계획·task·체크포인트 리포지토리
│   ├── gemini/             # Gemini (Google GenAI) 통합
│   │   ├── client.py       # create_genai_client — Gemini 클라이언트 팩토리
│   │   ├── structured.py   # GeminiStructuredClient — 구조화 출력, 재시도, 검증
│   │   ├── adapter.py      # GeminiOnboardingAdapter — 온보딩 대화/평가
│   │   ├── plan_adapter.py # GeminiProfilePlanAdapter — 계획 outline/task 생성
│   │   ├── rate_limit.py   # RedisGeminiRateLimiter — Lua 스크립트 기반 호출 제한
│   │   └── errors.py       # GeminiError 계층 (502, 429)
│   ├── onboarding/         # 온보딩 대화 도메인
│   │   ├── models.py       # ProfileField, OnboardingState, OnboardingResponse
│   │   ├── service.py      # OnboardingService — 세션·메시지·confirm 오케스트레이션
│   │   stores.py           # RedisOnboardingSessionStore — 분산 락, TTL
│   │   └── flow.py         # OnboardingValidationError
│   ├── plans/              # 커리어 계획 도메인
│   │   ├── models.py       # ProfilePlanOutlineV1, ProfilePlanTasksV1 등
│   │   ├── records.py      # StoredPlanProposal, StoredTaskUpdate
│   │   ├── generation.py   # ProfilePlanGenerator — outline/task 배치 생성
│   │   ├── checkpoints.py  # GenerationCheckpoint — 재개 가능한 생성 상태
│   │   ├── service.py      # PlanProposalService, PlanManagementService
│   │   ├── stores.py       # Redis 체크포인트 스토어 (Lua)
│   │   ├── errors.py       # PlanDomainError 계층
│   │   └── views.py        # PlanProposalView, PlanView 응답 빌더
│   └── profiles/           # 사용자 프로필 도메인
│       └── models.py       # ProfileOnboardingData, ProfileAssessment, ProfileRecord
├── sql/                    # 데이터베이스 스키마 및 마이그레이션 SQL
├── .env                    # 환경 변수 (DB, Redis, Gemini, JWT)
├── pyproject.toml          # 프로젝트 의존성 및 도구 설정
├── requirements.txt        # pip 의존성
├── run.sh                  # 서버 실행 스크립트
├── PLAN.md                 # 프로젝트 계획
└── README.md               # 이 파일
```

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| [docs/API_SPEC.md](docs/API_SPEC.md) | 전체 API 엔드포인트 명세 |
| [docs/BACKEND.md](docs/BACKEND.md) | 백엔드 아키텍처 및 구조 가이드 |
| [docs/CLI.md](docs/CLI.md) | CLI 앱 사용법 |
| [docs/FRONTEND_AUTH_ONBOARDING_HANDOFF.md](docs/FRONTEND_AUTH_ONBOARDING_HANDOFF.md) | 프론트엔드 인증·온보딩 연동 가이드 |
| [docs/supabase/README.md](docs/supabase/README.md) | Supabase 데이터베이스 설정 |
| [docs/supabase/TP_DEV_RUNTIME_CONFIGURATION.md](docs/supabase/TP_DEV_RUNTIME_CONFIGURATION.md) | 개발 환경 런타임 설정 |
| [TESTING.md](TESTING.md) | 테스트 실행법 및 진행 상황 |
| [AI_JOB_COACH_IMPLEMENTATION_PLAN.md](AI_JOB_COACH_IMPLEMENTATION_PLAN.md) | 설계 및 완료 조건 |
| [PLAN.md](PLAN.md) | 프로젝트 계획 |

별도 동의 없이 Git commit을 만들지 않습니다.
