# AI 취업관리맵 미니 프로젝트 계획서

> **레거시 기획 문서:** 아래 `email/password/name`, Supabase Auth, `success/data/message` 인증 예시는 초기 아이디어이며 현재 API 계약이 아니다. 구현 기준은 [`docs/API_SPEC.md`](docs/API_SPEC.md)의 `login_id/login_pw` 기반 `/api/v1/auth/signup`·`/api/v1/auth/login`이다.

## 1. 프로젝트 개요

### 1.1 프로젝트명

**AI Job Map — 맞춤형 취업 로드맵 및 채용공고 추천 서비스**

### 1.2 프로젝트 목표

사용자가 목표 직무, 희망 취업 기간, 현재 보유 기술을 입력하면 다음 기능을 제공하는 AI 기반 취업관리 서비스이다.

1. LLM을 활용한 맞춤형 취업 로드맵 생성
2. 사용자의 목표와 기술 스택에 맞는 채용공고 추천
3. RAG 기반 취업 컨설팅 챗봇
4. 로드맵 할 일 체크 및 목표 달성률 시각화
5. 관리자의 채용공고, 사용자, 컨설팅 자료 관리

### 1.3 프로젝트 기간 및 인원

- 개발 기간: 3일
- 총 인원: 5명
- Frontend: 2명
- Backend: 2명
- Tester: 1명

### 1.4 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | Streamlit, Python |
| Backend | FastAPI, Python |
| Database | Supabase, PostgreSQL |
| Authentication | Supabase Auth 또는 간단한 JWT 인증 |
| AI | OpenAI API 또는 호환 LLM API |
| RAG | 문서 임베딩, Redis Vector Search 또는 단순 벡터 검색 |
| Cache/Session | Redis |
| API 통신 | HTTP REST API, requests 또는 httpx |
| 개발 환경 | VS Code |
| 형상 관리 | Git, GitHub |
| API 테스트 | Postman, Swagger UI |
| 테스트 | pytest, FastAPI TestClient, 수동 UI 테스트 |

---

## 2. MVP 범위

3일 프로젝트에서는 다음 기능을 필수 구현 대상으로 한다.

### 2.1 사용자 기능

1. 회원가입 및 로그인
2. 취업 목표 등록 및 수정
3. AI 취업 로드맵 생성
4. 로드맵 세부 할 일 조회 및 완료 처리
5. 목표 달성률 조회
6. 사용자 맞춤 채용공고 추천
7. RAG 기반 AI 취업 상담

### 2.2 관리자 기능

1. 관리자 로그인
2. 사용자 목록 및 목표 현황 조회
3. 채용공고 등록, 조회, 수정, 삭제
4. RAG용 컨설팅 자료 등록 및 조회

### 2.3 제외 또는 선택 기능

다음 기능은 시간이 남는 경우에만 구현한다.

- 자기소개서 첨삭
- 이력서 파일 분석
- 실제 채용 사이트 크롤링
- 소셜 로그인
- 관리자 통계 차트 고도화
- 이메일 알림
- 복잡한 권한 체계

---

## 3. 시스템 구성

```text
[사용자/관리자]
       |
       v
[Streamlit Frontend]
       |
       | REST API
       v
[FastAPI Backend]
   |       |       |
   |       |       +---- [LLM API]
   |       |
   |       +------------ [Redis / Vector Search]
   |
   +-------------------- [Supabase PostgreSQL/Auth]
```

### 3.1 Frontend 역할

- 사용자 입력 폼 제공
- FastAPI 호출
- API 응답 표시
- 로드맵, 진행률, 채용공고 시각화
- 사용자와 관리자 화면 분리

### 3.2 Backend 역할

- 인증 및 권한 검증
- 사용자 목표와 로드맵 CRUD
- 채용공고 CRUD 및 추천
- LLM 프롬프트 구성 및 호출
- RAG 문서 검색 및 답변 생성
- Redis 캐시 및 벡터 검색
- 공통 예외 처리

### 3.3 Supabase 역할

- 사용자 기본 정보 저장
- 사용자 목표 저장
- 로드맵 및 할 일 저장
- 채용공고 저장
- 상담 기록 저장
- 관리자 데이터 저장

### 3.4 Redis 역할

- 자주 조회하는 채용공고 캐시
- 로그인 세션 또는 임시 토큰 저장
- RAG 문서 임베딩 저장
- 사용자 질문과 유사한 문서 검색
- 동일한 AI 요청 결과 임시 캐시

---

## 4. 권장 디렉터리 구조

한 저장소에서 frontend와 backend를 함께 관리하는 모노레포 구조를 권장한다.

```text
ai-job-map/
├── README.md
├── plan.md
├── .gitignore
├── .env.example
├── docker-compose.yml             # 선택: Redis 로컬 실행
├── requirements.txt               # 공통 또는 통합 의존성
│
├── frontend/
│   ├── app.py                     # Streamlit 실행 진입점
│   ├── requirements.txt
│   ├── pages/
│   │   ├── 01_login.py
│   │   ├── 02_user_dashboard.py
│   │   ├── 03_goal_setting.py
│   │   ├── 04_roadmap.py
│   │   ├── 05_job_recommendation.py
│   │   ├── 06_ai_consulting.py
│   │   └── 90_admin_dashboard.py
│   ├── components/
│   │   ├── header.py
│   │   ├── sidebar.py
│   │   ├── progress_bar.py
│   │   ├── roadmap_card.py
│   │   ├── job_card.py
│   │   └── error_message.py
│   ├── services/
│   │   ├── api_client.py           # FastAPI 공통 호출 함수
│   │   ├── auth_service.py
│   │   ├── roadmap_service.py
│   │   ├── job_service.py
│   │   └── chat_service.py
│   ├── utils/
│   │   ├── session.py
│   │   ├── validators.py
│   │   └── constants.py
│   └── assets/
│       └── logo.png
│
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 실행 진입점
│   │   ├── core/
│   │   │   ├── config.py           # 환경변수 설정
│   │   │   ├── security.py         # JWT, 비밀번호 검증
│   │   │   ├── exceptions.py       # 사용자 정의 예외
│   │   │   ├── exception_handlers.py
│   │   │   └── logging.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── endpoints/
│   │   │           ├── auth.py
│   │   │           ├── users.py
│   │   │           ├── goals.py
│   │   │           ├── roadmaps.py
│   │   │           ├── jobs.py
│   │   │           ├── consulting.py
│   │   │           └── admin.py
│   │   ├── schemas/
│   │   │   ├── common.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── goal.py
│   │   │   ├── roadmap.py
│   │   │   ├── job.py
│   │   │   └── consulting.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── goal.py
│   │   │   ├── roadmap.py
│   │   │   ├── job.py
│   │   │   └── chat.py
│   │   ├── repositories/
│   │   │   ├── user_repository.py
│   │   │   ├── goal_repository.py
│   │   │   ├── roadmap_repository.py
│   │   │   ├── job_repository.py
│   │   │   └── chat_repository.py
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── goal_service.py
│   │   │   ├── roadmap_service.py
│   │   │   ├── job_service.py
│   │   │   ├── recommendation_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── rag_service.py
│   │   │   └── redis_service.py
│   │   ├── db/
│   │   │   ├── supabase.py
│   │   │   └── redis.py
│   │   └── prompts/
│   │       ├── roadmap_prompt.py
│   │       └── consulting_prompt.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_goals.py
│   │   ├── test_roadmaps.py
│   │   ├── test_jobs.py
│   │   └── test_consulting.py
│   └── requirements.txt
│
├── scripts/
│   ├── seed_jobs.py                # 채용공고 샘플 데이터 입력
│   ├── seed_admin.py
│   └── load_rag_documents.py
│
├── docs/
│   ├── api-spec.md
│   ├── db-schema.md
│   ├── test-cases.md
│   └── presentation.md
│
└── sample_data/
    ├── jobs.json
    └── consulting_documents/
        ├── backend_guide.md
        ├── frontend_guide.md
        └── interview_guide.md
```

### 4.1 3일 프로젝트용 단순화 구조

시간이 부족하면 repository와 model 계층을 줄여 다음 구조로 구현할 수 있다.

```text
backend/app/
├── main.py
├── config.py
├── database.py
├── dependencies.py
├── exceptions.py
├── routers/
├── schemas/
├── services/
└── utils/
```

단, endpoint 파일에서 Supabase와 LLM을 직접 호출하지 않고 `services` 계층을 거치도록 한다.

---

## 5. 데이터베이스 설계

### 5.1 users

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 사용자 ID |
| email | varchar | UNIQUE, NOT NULL | 이메일 |
| name | varchar | NOT NULL | 사용자명 |
| role | varchar | NOT NULL | USER 또는 ADMIN |
| created_at | timestamptz | DEFAULT now() | 가입일 |

### 5.2 employment_goals

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 목표 ID |
| user_id | uuid | FK, NOT NULL | 사용자 ID |
| target_job | varchar | NOT NULL | 목표 직무 |
| target_company | varchar | NULL | 목표 기업 |
| target_date | date | NOT NULL | 목표 취업일 |
| current_skills | jsonb | DEFAULT [] | 보유 기술 |
| experience_level | varchar | NOT NULL | BEGINNER, JUNIOR 등 |
| status | varchar | DEFAULT ACTIVE | 목표 상태 |
| created_at | timestamptz | DEFAULT now() | 생성일 |
| updated_at | timestamptz | DEFAULT now() | 수정일 |

### 5.3 roadmaps

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 로드맵 ID |
| user_id | uuid | FK, NOT NULL | 사용자 ID |
| goal_id | uuid | FK, NOT NULL | 목표 ID |
| title | varchar | NOT NULL | 로드맵 제목 |
| summary | text | NULL | AI 생성 요약 |
| created_by_ai | boolean | DEFAULT true | AI 생성 여부 |
| created_at | timestamptz | DEFAULT now() | 생성일 |

### 5.4 roadmap_tasks

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 할 일 ID |
| roadmap_id | uuid | FK, NOT NULL | 로드맵 ID |
| week_no | integer | NOT NULL | 주차 |
| title | varchar | NOT NULL | 할 일 제목 |
| description | text | NULL | 상세 설명 |
| priority | varchar | DEFAULT MEDIUM | 우선순위 |
| is_completed | boolean | DEFAULT false | 완료 여부 |
| completed_at | timestamptz | NULL | 완료일 |
| sort_order | integer | DEFAULT 0 | 정렬 순서 |

### 5.5 job_posts

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 공고 ID |
| company_name | varchar | NOT NULL | 기업명 |
| title | varchar | NOT NULL | 공고명 |
| job_category | varchar | NOT NULL | 직무 분류 |
| required_skills | jsonb | DEFAULT [] | 필수 기술 |
| preferred_skills | jsonb | DEFAULT [] | 우대 기술 |
| description | text | NOT NULL | 공고 내용 |
| location | varchar | NULL | 근무 지역 |
| employment_type | varchar | NULL | 정규직, 인턴 등 |
| apply_url | text | NULL | 지원 URL |
| deadline | date | NULL | 마감일 |
| is_active | boolean | DEFAULT true | 게시 여부 |
| created_at | timestamptz | DEFAULT now() | 등록일 |

### 5.6 chat_histories

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 대화 ID |
| user_id | uuid | FK, NOT NULL | 사용자 ID |
| question | text | NOT NULL | 질문 |
| answer | text | NOT NULL | AI 답변 |
| references | jsonb | DEFAULT [] | 참고 문서 또는 공고 |
| created_at | timestamptz | DEFAULT now() | 생성일 |

### 5.7 consulting_documents

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | uuid | PK | 문서 ID |
| title | varchar | NOT NULL | 문서 제목 |
| category | varchar | NOT NULL | BACKEND, FRONTEND, INTERVIEW 등 |
| content | text | NOT NULL | 문서 본문 |
| source | text | NULL | 출처 |
| created_at | timestamptz | DEFAULT now() | 등록일 |

---

## 6. 공통 API 규칙

### 6.1 Base URL

```text
/api/v1
```

### 6.2 인증 헤더

```http
Authorization: Bearer {access_token}
Content-Type: application/json
```

### 6.3 성공 응답 형식

```json
{
  "success": true,
  "data": {},
  "message": "요청이 정상적으로 처리되었습니다."
}
```

### 6.4 실패 응답 형식

```json
{
  "success": false,
  "error": {
    "code": "GOAL_NOT_FOUND",
    "message": "취업 목표를 찾을 수 없습니다.",
    "details": null
  }
}
```

### 6.5 페이지네이션 응답

```json
{
  "success": true,
  "data": {
    "items": [],
    "page": 1,
    "size": 10,
    "total": 24,
    "total_pages": 3
  }
}
```

---

## 7. API 명세

## 7.1 인증 API

### 회원가입

```http
POST /api/v1/auth/signup
```

Request

```json
{
  "email": "user@example.com",
  "password": "Password123!",
  "name": "홍길동"
}
```

Response `201 Created`

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "홍길동",
    "role": "USER"
  },
  "message": "회원가입이 완료되었습니다."
}
```

주요 예외

- `400 INVALID_INPUT`: 이메일 또는 비밀번호 형식 오류
- `409 EMAIL_ALREADY_EXISTS`: 이미 가입된 이메일
- `503 AUTH_SERVICE_UNAVAILABLE`: Supabase Auth 연결 실패

### 로그인

```http
POST /api/v1/auth/login
```

Request

```json
{
  "email": "user@example.com",
  "password": "Password123!"
}
```

Response `200 OK`

```json
{
  "success": true,
  "data": {
    "access_token": "jwt-token",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "uuid",
      "name": "홍길동",
      "role": "USER"
    }
  },
  "message": "로그인에 성공했습니다."
}
```

주요 예외

- `400 INVALID_INPUT`: 필수 입력 누락
- `401 INVALID_CREDENTIALS`: 이메일 또는 비밀번호 불일치
- `403 ACCOUNT_DISABLED`: 비활성화 계정

### 내 정보 조회

```http
GET /api/v1/users/me
```

Response `200 OK`

주요 예외

- `401 UNAUTHORIZED`: 토큰 없음 또는 만료
- `404 USER_NOT_FOUND`: 사용자 정보 없음

---

## 7.2 취업 목표 API

### 목표 등록

```http
POST /api/v1/goals
```

Request

```json
{
  "target_job": "백엔드 개발자",
  "target_company": "네이버",
  "target_date": "2026-12-31",
  "current_skills": ["Python", "SQL"],
  "experience_level": "BEGINNER"
}
```

Response `201 Created`

주요 예외

- `400 INVALID_TARGET_DATE`: 목표일이 현재 날짜보다 이전
- `400 INVALID_INPUT`: 목표 직무 또는 경험 수준 누락
- `409 ACTIVE_GOAL_ALREADY_EXISTS`: 활성 목표가 이미 존재

### 내 목표 조회

```http
GET /api/v1/goals/me
```

주요 예외

- `401 UNAUTHORIZED`
- `404 GOAL_NOT_FOUND`

### 목표 수정

```http
PATCH /api/v1/goals/{goal_id}
```

Request

```json
{
  "target_company": "카카오",
  "target_date": "2027-01-31",
  "current_skills": ["Python", "SQL", "FastAPI"]
}
```

주요 예외

- `403 FORBIDDEN`: 다른 사용자의 목표 수정 시도
- `404 GOAL_NOT_FOUND`
- `400 INVALID_TARGET_DATE`

---

## 7.3 로드맵 API

### AI 로드맵 생성

```http
POST /api/v1/roadmaps/generate
```

Request

```json
{
  "goal_id": "goal-uuid"
}
```

Response `201 Created`

```json
{
  "success": true,
  "data": {
    "roadmap_id": "roadmap-uuid",
    "title": "백엔드 개발자 12주 취업 로드맵",
    "summary": "Python과 SQL 기초를 바탕으로 FastAPI 프로젝트와 면접 준비를 진행합니다.",
    "tasks": [
      {
        "id": "task-uuid-1",
        "week_no": 1,
        "title": "Python 문법 복습",
        "description": "함수, 클래스, 예외 처리 학습",
        "priority": "HIGH",
        "is_completed": false
      }
    ]
  },
  "message": "AI 로드맵이 생성되었습니다."
}
```

주요 예외

- `404 GOAL_NOT_FOUND`: 목표 없음
- `409 ROADMAP_ALREADY_EXISTS`: 동일 목표의 로드맵이 이미 존재
- `422 GOAL_DATA_INSUFFICIENT`: AI 생성에 필요한 목표 데이터 부족
- `429 LLM_RATE_LIMITED`: LLM 호출 한도 초과
- `502 LLM_INVALID_RESPONSE`: LLM 응답 파싱 실패
- `503 LLM_SERVICE_UNAVAILABLE`: LLM 연결 실패

### 내 로드맵 조회

```http
GET /api/v1/roadmaps/me
```

Response `200 OK`

주요 예외

- `404 ROADMAP_NOT_FOUND`

### 로드맵 할 일 완료 상태 변경

```http
PATCH /api/v1/roadmaps/tasks/{task_id}
```

Request

```json
{
  "is_completed": true
}
```

Response `200 OK`

```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid",
    "is_completed": true,
    "completed_at": "2026-08-06T10:00:00Z",
    "progress_rate": 40
  },
  "message": "할 일 상태가 변경되었습니다."
}
```

주요 예외

- `403 FORBIDDEN`
- `404 ROADMAP_TASK_NOT_FOUND`
- `400 INVALID_TASK_STATUS`

### 목표 달성률 조회

```http
GET /api/v1/roadmaps/{roadmap_id}/progress
```

Response `200 OK`

```json
{
  "success": true,
  "data": {
    "roadmap_id": "roadmap-uuid",
    "total_tasks": 10,
    "completed_tasks": 4,
    "progress_rate": 40
  }
}
```

계산 기준

```text
진행률 = 완료한 할 일 수 / 전체 할 일 수 * 100
```

전체 할 일이 0개이면 진행률은 0으로 처리한다.

---

## 7.4 채용공고 API

### 채용공고 목록 조회

```http
GET /api/v1/jobs?page=1&size=10&job_category=backend&keyword=python
```

Query Parameters

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| page | N | 1 | 페이지 번호 |
| size | N | 10 | 페이지 크기 |
| job_category | N | null | 직무 필터 |
| keyword | N | null | 기업명 또는 공고명 검색 |
| active_only | N | true | 활성 공고만 조회 |

주요 예외

- `400 INVALID_PAGE_PARAMETER`
- `500 JOB_LIST_FETCH_FAILED`

### 맞춤 채용공고 추천

```http
GET /api/v1/jobs/recommendations?limit=5
```

Response `200 OK`

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "job-uuid",
        "company_name": "ABC Tech",
        "title": "주니어 백엔드 개발자",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "match_score": 87,
        "match_reasons": [
          "목표 직무와 일치",
          "보유 기술 Python과 일치"
        ],
        "apply_url": "https://example.com/jobs/1"
      }
    ]
  },
  "message": "맞춤 채용공고를 조회했습니다."
}
```

추천 기준 예시

- 목표 직무 일치: 40점
- 필수 기술 일치율: 30점
- 우대 기술 일치율: 20점
- 목표 기업 일치: 10점

주요 예외

- `404 GOAL_NOT_FOUND`
- `404 RECOMMENDATION_NOT_FOUND`: 추천 가능한 공고 없음
- `503 REDIS_SERVICE_UNAVAILABLE`: 벡터 검색 실패 시 DB 기반 추천으로 대체 가능

### 관리자 채용공고 등록

```http
POST /api/v1/admin/jobs
```

Request

```json
{
  "company_name": "ABC Tech",
  "title": "주니어 백엔드 개발자",
  "job_category": "BACKEND",
  "required_skills": ["Python", "FastAPI"],
  "preferred_skills": ["Redis", "Docker"],
  "description": "백엔드 API 개발 담당",
  "location": "서울",
  "employment_type": "FULL_TIME",
  "apply_url": "https://example.com/jobs/1",
  "deadline": "2026-09-30"
}
```

주요 예외

- `401 UNAUTHORIZED`
- `403 ADMIN_REQUIRED`
- `400 INVALID_JOB_DATA`
- `409 JOB_ALREADY_EXISTS`

### 관리자 채용공고 수정

```http
PATCH /api/v1/admin/jobs/{job_id}
```

### 관리자 채용공고 삭제

```http
DELETE /api/v1/admin/jobs/{job_id}
```

실제 삭제 대신 `is_active=false`로 변경하는 소프트 삭제를 권장한다.

---

## 7.5 AI 컨설팅 API

### AI 상담 요청

```http
POST /api/v1/consulting/chat
```

Request

```json
{
  "question": "백엔드 취업을 위해 어떤 프로젝트를 만들면 좋을까요?"
}
```

Response `200 OK`

```json
{
  "success": true,
  "data": {
    "answer": "FastAPI와 PostgreSQL을 사용한 REST API 프로젝트를 추천합니다.",
    "references": [
      {
        "type": "DOCUMENT",
        "title": "백엔드 포트폴리오 가이드"
      },
      {
        "type": "JOB_POST",
        "title": "주니어 백엔드 개발자"
      }
    ]
  },
  "message": "AI 상담 답변이 생성되었습니다."
}
```

처리 흐름

```text
질문 입력
→ 입력 검증
→ Redis Vector Search로 관련 문서 검색
→ 사용자 목표 및 관련 문서를 프롬프트에 포함
→ LLM 호출
→ 답변과 참고자료 반환
→ 상담 기록 저장
```

주요 예외

- `400 EMPTY_QUESTION`: 질문이 비어 있음
- `400 QUESTION_TOO_LONG`: 질문 길이 제한 초과
- `422 UNSUPPORTED_QUESTION`: 취업과 무관한 요청
- `404 RAG_CONTEXT_NOT_FOUND`: 관련 문서를 찾지 못함
- `429 LLM_RATE_LIMITED`
- `502 LLM_INVALID_RESPONSE`
- `503 REDIS_SERVICE_UNAVAILABLE`
- `503 LLM_SERVICE_UNAVAILABLE`

Redis 또는 RAG 검색 실패 시 완전한 오류로 종료하지 않고 다음처럼 제한된 답변을 제공할 수 있다.

```json
{
  "success": true,
  "data": {
    "answer": "현재 참고자료 검색이 원활하지 않아 일반적인 취업 준비 기준으로 안내드립니다.",
    "references": [],
    "is_fallback": true
  },
  "message": "일반 AI 상담 답변이 생성되었습니다."
}
```

### 상담 기록 조회

```http
GET /api/v1/consulting/history?page=1&size=20
```

---

## 7.6 관리자 API

### 사용자 목록 조회

```http
GET /api/v1/admin/users?page=1&size=20&keyword=hong
```

### 사용자 상세 조회

```http
GET /api/v1/admin/users/{user_id}
```

### 대시보드 통계 조회

```http
GET /api/v1/admin/dashboard
```

Response 예시

```json
{
  "success": true,
  "data": {
    "total_users": 35,
    "active_goals": 28,
    "total_job_posts": 52,
    "average_progress_rate": 46.7,
    "popular_job_categories": [
      {"name": "BACKEND", "count": 14},
      {"name": "FRONTEND", "count": 9}
    ]
  }
}
```

### RAG 문서 등록

```http
POST /api/v1/admin/documents
```

Request

```json
{
  "title": "백엔드 면접 가이드",
  "category": "INTERVIEW",
  "content": "REST API, 트랜잭션, 인덱스 관련 질문을 준비합니다.",
  "source": "팀 내부 샘플 문서"
}
```

처리 흐름

```text
문서 저장
→ 문서 분할
→ 임베딩 생성
→ Redis Vector 저장
```

주요 예외

- `403 ADMIN_REQUIRED`
- `400 EMPTY_DOCUMENT_CONTENT`
- `400 DOCUMENT_TOO_LARGE`
- `409 DOCUMENT_ALREADY_EXISTS`
- `503 EMBEDDING_SERVICE_UNAVAILABLE`
- `503 REDIS_SERVICE_UNAVAILABLE`

---

## 8. HTTP 상태 코드 및 에러 코드

| HTTP 상태 | 의미 | 사용 예시 |
|---|---|---|
| 200 | 정상 조회/수정 | 로그인, 조회, 상태 변경 |
| 201 | 생성 성공 | 회원가입, 목표 등록, 로드맵 생성 |
| 204 | 응답 본문 없는 성공 | 삭제 처리 |
| 400 | 잘못된 입력 | 날짜 형식, 필수값 누락 |
| 401 | 인증 실패 | 토큰 없음, 토큰 만료 |
| 403 | 권한 없음 | 일반 사용자의 관리자 API 호출 |
| 404 | 리소스 없음 | 목표, 로드맵, 공고 없음 |
| 409 | 데이터 충돌 | 중복 이메일, 중복 목표 |
| 422 | 처리할 수 없는 요청 | AI 생성에 필요한 데이터 부족 |
| 429 | 요청 한도 초과 | LLM 호출 제한 |
| 500 | 서버 내부 오류 | 예상하지 못한 오류 |
| 502 | 외부 API 비정상 응답 | LLM 응답 파싱 실패 |
| 503 | 외부 서비스 사용 불가 | Supabase, Redis, LLM 장애 |

### 8.1 권장 공통 에러 코드

```text
INVALID_INPUT
VALIDATION_ERROR
UNAUTHORIZED
TOKEN_EXPIRED
FORBIDDEN
ADMIN_REQUIRED
RESOURCE_NOT_FOUND
DATABASE_ERROR
SUPABASE_SERVICE_UNAVAILABLE
REDIS_SERVICE_UNAVAILABLE
LLM_SERVICE_UNAVAILABLE
LLM_RATE_LIMITED
LLM_INVALID_RESPONSE
INTERNAL_SERVER_ERROR
```

---

## 9. 대표 예외 상황 처리

### 9.1 입력값 검증

- 이메일 형식 검증
- 비밀번호 최소 길이 검증
- 목표 날짜가 오늘 이후인지 검증
- 질문이 공백인지 검증
- 문자열 최대 길이 검증
- 배열 데이터의 최대 개수 검증
- 허용된 enum 값인지 검증

FastAPI의 Pydantic 스키마에서 우선 검증한다.

```python
from datetime import date
from pydantic import BaseModel, Field, field_validator


class GoalCreateRequest(BaseModel):
    target_job: str = Field(min_length=2, max_length=50)
    target_company: str | None = Field(default=None, max_length=100)
    target_date: date
    current_skills: list[str] = Field(default_factory=list, max_length=20)
    experience_level: str

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: date) -> date:
        if value <= date.today():
            raise ValueError("목표 날짜는 오늘 이후여야 합니다.")
        return value
```

### 9.2 인증 및 권한 예외

- Authorization 헤더가 없으면 `401`
- 토큰이 만료되었으면 `401 TOKEN_EXPIRED`
- 사용자 토큰으로 관리자 API 호출 시 `403 ADMIN_REQUIRED`
- 다른 사용자의 목표나 로드맵 접근 시 `403 FORBIDDEN`

### 9.3 데이터 없음

조회 결과가 없을 때 빈 객체를 임의로 반환하지 않는다.

- 단일 데이터 조회: `404`
- 목록 조회: 빈 배열과 `200`
- 추천 결과 없음: `404` 또는 빈 목록과 안내 메시지 중 팀 규칙으로 통일

권장 방식

```text
단일 리소스 없음 → 404
검색/목록 결과 없음 → 200 + items: []
```

### 9.4 중복 요청

- 중복 회원가입
- 활성 목표 중복 등록
- 동일 목표에 로드맵 중복 생성
- 동일한 채용공고 중복 등록

중복 시 `409 Conflict`를 사용한다.

### 9.5 외부 서비스 장애

#### Supabase 장애

- 연결 시간 제한 설정
- DB 오류 원문을 사용자에게 노출하지 않음
- 서버 로그에 실제 오류 기록
- 사용자에게 `503 SUPABASE_SERVICE_UNAVAILABLE` 반환

#### Redis 장애

- 채용 추천: PostgreSQL 기반 키워드 추천으로 대체
- RAG 상담: 일반 LLM 답변으로 대체하거나 제한 메시지 반환
- 캐시 실패가 핵심 기능을 중단하지 않도록 설계

#### LLM 장애

- 호출 타임아웃 설정
- 최대 1회 재시도
- 응답 JSON 파싱 실패 처리
- 사용자에게 API 키, 프롬프트, 스택트레이스 노출 금지
- 로드맵 생성 실패 시 기존 데이터 저장 금지

### 9.6 타임아웃

권장 타임아웃

| 대상 | 타임아웃 |
|---|---:|
| Supabase 조회 | 5초 |
| Redis 조회 | 2초 |
| LLM 생성 | 20~30초 |
| Streamlit → FastAPI | 30초 |

Frontend에서는 LLM 요청 중 spinner를 표시하고 중복 버튼 클릭을 방지한다.

### 9.7 트랜잭션 처리

로드맵 생성 시 다음 데이터는 하나의 작업 단위로 처리한다.

```text
roadmaps 저장
+ roadmap_tasks 여러 건 저장
```

할 일 저장 중 오류가 발생하면 불완전한 로드맵이 남지 않도록 롤백하거나 생성된 로드맵을 삭제한다.

### 9.8 공통 예외 핸들러 예시

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


class AppException(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": None,
            },
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    # 실제 프로젝트에서는 logger.exception(exc) 사용
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "서버 내부 오류가 발생했습니다.",
                "details": None,
            },
        },
    )
```

### 9.9 Streamlit API 오류 처리 예시

```python
import requests
import streamlit as st


def request_api(method: str, url: str, **kwargs):
    try:
        response = requests.request(method, url, timeout=30, **kwargs)
        data = response.json()

        if response.ok:
            return data.get("data")

        message = data.get("error", {}).get(
            "message", "요청 처리 중 오류가 발생했습니다."
        )
        st.error(message)
        return None

    except requests.Timeout:
        st.error("서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")
    except requests.ConnectionError:
        st.error("백엔드 서버에 연결할 수 없습니다.")
    except ValueError:
        st.error("서버 응답 형식이 올바르지 않습니다.")
    except Exception:
        st.error("예상하지 못한 오류가 발생했습니다.")

    return None
```

---

## 10. LLM 및 RAG 설계

### 10.1 로드맵 생성 프롬프트 입력

```json
{
  "target_job": "백엔드 개발자",
  "target_company": "네이버",
  "target_date": "2026-12-31",
  "current_skills": ["Python", "SQL"],
  "experience_level": "BEGINNER"
}
```

### 10.2 LLM 출력 규칙

LLM 응답은 자유 형식 문장이 아니라 JSON 형식으로 강제한다.

```json
{
  "title": "백엔드 개발자 취업 로드맵",
  "summary": "12주 동안 API 개발과 포트폴리오를 준비합니다.",
  "tasks": [
    {
      "week_no": 1,
      "title": "Python 복습",
      "description": "예외 처리와 클래스 학습",
      "priority": "HIGH"
    }
  ]
}
```

검증 규칙

- `tasks`가 비어 있지 않아야 한다.
- `week_no`는 1 이상의 정수여야 한다.
- `priority`는 HIGH, MEDIUM, LOW 중 하나여야 한다.
- 동일한 제목이 과도하게 반복되지 않아야 한다.
- 최대 할 일 수를 제한한다. 예: 20개

### 10.3 RAG 문서 검색

3일 프로젝트에서는 문서 수를 작게 유지한다.

권장 샘플 문서

- 백엔드 취업 준비 가이드
- 프론트엔드 취업 준비 가이드
- 데이터/AI 직무 준비 가이드
- 기술 면접 준비 가이드
- 포트폴리오 작성 가이드
- 샘플 채용공고 20~30건

문서 처리 과정

```text
문서 등록
→ 300~500자 단위 분할
→ 임베딩 생성
→ Redis에 vector + metadata 저장
→ 질문 임베딩 생성
→ 유사 문서 Top 3 검색
→ LLM Context로 전달
```

### 10.4 프롬프트 인젝션 최소 대응

- 시스템 프롬프트에 역할과 답변 범위를 명시
- 검색 문서 안의 명령문을 지시사항이 아닌 참고자료로 취급
- API 키, 시스템 프롬프트, 내부 환경변수 출력 금지
- 취업과 무관한 요청에는 범위를 안내
- 사용자 입력 최대 길이 제한

---

## 11. Streamlit 화면 구성

### 11.1 사용자 화면

#### 로그인

- 이메일
- 비밀번호
- 로그인 버튼
- 회원가입 화면 이동

#### 사용자 대시보드

- 사용자 목표 요약
- 목표일까지 남은 기간
- 현재 진행률
- 오늘의 추천 할 일
- 추천 채용공고 상위 3개

#### 목표 설정

- 목표 직무
- 목표 기업
- 목표 취업일
- 현재 보유 기술
- 경험 수준
- 저장 버튼

#### 로드맵

- 주차별 할 일
- 완료 체크박스
- 우선순위 표시
- 진행률 Progress Bar

#### 채용공고 추천

- 기업명
- 공고명
- 요구 기술
- 매칭 점수
- 추천 이유
- 지원 링크

#### AI 상담

- 채팅 입력창
- 답변 표시
- 참고 문서 표시
- 최근 상담 기록

### 11.2 관리자 화면

- 사용자 수
- 활성 목표 수
- 채용공고 수
- 사용자 목록
- 채용공고 CRUD
- RAG 문서 등록

### 11.3 Streamlit 세션 상태

```python
st.session_state["access_token"]
st.session_state["user"]
st.session_state["role"]
st.session_state["selected_goal_id"]
```

토큰이 없으면 사용자 페이지 접근 시 로그인 화면으로 이동시킨다.

---

## 12. 팀 역할 분담

### Frontend 1

- 로그인 및 회원가입 화면
- 사용자 대시보드
- 목표 설정 화면
- 공통 API Client
- 세션 상태 관리

### Frontend 2

- 로드맵 화면
- 진행률 시각화
- 채용공고 추천 화면
- AI 상담 화면
- 관리자 화면

### Backend 1

- FastAPI 프로젝트 기본 구성
- 인증 및 권한
- 사용자/목표 API
- 로드맵 및 진행률 CRUD
- Supabase 연동

### Backend 2

- LLM 로드맵 생성
- RAG 상담 기능
- Redis 연동
- 채용공고 추천
- 관리자 채용공고/문서 API

### Tester

- API 테스트 케이스 작성
- Swagger/Postman 테스트
- Streamlit 화면 테스트
- 인증 및 권한 테스트
- 예외 상황 테스트
- GitHub Issues에 버그 등록
- 최종 시연 시나리오 점검

---

## 13. 3일 일정

### Day 1 — 기본 기능 및 연동

#### 공통

- GitHub 저장소 생성
- 브랜치 규칙 결정
- 환경변수 공유 방식 결정
- API 요청/응답 규격 확정
- Supabase 테이블 생성

#### Frontend

- Streamlit 기본 페이지 구성
- 로그인/회원가입 UI
- 목표 설정 UI
- API Client 작성

#### Backend

- FastAPI 프로젝트 생성
- Supabase 연결
- 인증 API
- 목표 CRUD API
- 샘플 데이터 입력

#### Tester

- API 명세 검토
- 테스트 케이스 초안 작성
- Swagger 기본 API 테스트

### Day 2 — 핵심 AI 기능

#### Frontend

- 로드맵 화면
- 진행률 UI
- 채용공고 추천 화면
- AI 상담 화면

#### Backend

- LLM 로드맵 생성
- 로드맵 저장 및 조회
- 추천 로직
- Redis 및 RAG 기능
- AI 상담 API

#### Tester

- 정상/비정상 입력 테스트
- 인증/권한 테스트
- AI 응답 실패 테스트
- 발견 버그 GitHub Issues 등록

### Day 3 — 관리자, 통합, 발표

#### 공통

- 관리자 기능 최소 구현
- 전체 통합 테스트
- UI 정리
- 예외 메시지 정리
- 샘플 사용자 및 공고 데이터 준비
- README 작성
- 발표 자료와 시연 시나리오 준비

#### 마감 기준

- 새로운 기능 추가는 오후 이전에 중단
- 치명적 버그 우선 수정
- LLM 실패 시 시연 가능한 fallback 데이터 준비
- main 브랜치 최종 병합
- 배포 또는 로컬 실행 절차 확인

---

## 14. Git/GitHub 협업 규칙

### 14.1 브랜치 전략

```text
main
└── develop
    ├── feature/frontend-login
    ├── feature/frontend-roadmap
    ├── feature/backend-auth
    ├── feature/backend-rag
    └── test/api-cases
```

- `main`: 최종 시연 가능한 코드
- `develop`: 통합 개발 브랜치
- `feature/*`: 기능 개발
- `fix/*`: 버그 수정
- `test/*`: 테스트 코드 및 테스트 문서

### 14.2 브랜치 이름 예시

```text
feature/frontend-dashboard
feature/backend-roadmap-api
feature/backend-rag-chat
fix/login-token-error
test/roadmap-api
```

### 14.3 커밋 메시지 규칙

```text
feat: 새로운 기능
fix: 버그 수정
refactor: 코드 구조 개선
test: 테스트 코드
docs: 문서 수정
chore: 설정 및 기타 작업
```

예시

```text
feat: 취업 목표 등록 API 구현
feat: Streamlit 로드맵 진행률 화면 추가
fix: 만료 토큰 처리 오류 수정
test: 채용공고 추천 API 테스트 추가
docs: API 명세 업데이트
```

### 14.4 Pull Request 규칙

PR 본문에 다음 내용을 포함한다.

```markdown
## 작업 내용
- 목표 등록 API 구현
- 목표 날짜 유효성 검증 추가

## 테스트
- 정상 목표 등록
- 과거 날짜 입력 시 400 확인

## 관련 이슈
- closes #12
```

가능하면 1명 이상의 리뷰 후 병합한다. 3일 프로젝트이므로 긴 리뷰 대신 충돌 여부와 API 규격 일치 여부를 우선 확인한다.

### 14.5 GitHub Issues 사용

라벨 예시

```text
frontend
backend
ai
bug
test
urgent
```

버그 이슈 예시

```markdown
## 발생 화면/API
POST /api/v1/roadmaps/generate

## 재현 절차
1. 목표 등록
2. 로드맵 생성 버튼 두 번 클릭

## 예상 결과
로드맵 1개만 생성

## 실제 결과
로드맵 2개 생성

## 우선순위
High
```

---

## 15. 환경변수

`.env.example`

```env
APP_ENV=local
APP_NAME=AI_JOB_MAP
API_V1_PREFIX=/api/v1

SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_ROLE_KEY=

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

LLM_API_KEY=
LLM_MODEL=
EMBEDDING_MODEL=

JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

BACKEND_BASE_URL=http://localhost:8000
```

주의사항

- `.env` 파일은 Git에 커밋하지 않는다.
- 실제 API 키는 GitHub, 메신저 공개 채널, 발표 화면에 노출하지 않는다.
- `.env.example`에는 값 없이 변수 이름만 공유한다.

---

## 16. 실행 방법

### 16.1 Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Windows PowerShell

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger

```text
http://localhost:8000/docs
```

### 16.2 Frontend

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

접속 주소

```text
http://localhost:8501
```

### 16.3 Redis

Docker 사용 시

```bash
docker run --name ai-job-map-redis -p 6379:6379 -d redis:7
```

Redis가 실행되지 않는 경우 추천과 상담 기능이 fallback 방식으로 동작하도록 처리한다.

---

## 17. 테스트 계획

### 17.1 필수 API 테스트

| ID | 테스트 | 예상 결과 |
|---|---|---|
| AUTH-01 | 정상 회원가입 | 201 |
| AUTH-02 | 중복 이메일 가입 | 409 |
| AUTH-03 | 잘못된 비밀번호 로그인 | 401 |
| GOAL-01 | 정상 목표 등록 | 201 |
| GOAL-02 | 과거 날짜 목표 등록 | 400 |
| ROADMAP-01 | 정상 로드맵 생성 | 201 |
| ROADMAP-02 | 목표 없이 로드맵 생성 | 404 |
| ROADMAP-03 | LLM 장애 | 503 또는 fallback |
| TASK-01 | 할 일 완료 처리 | 200 및 진행률 증가 |
| JOB-01 | 추천 공고 조회 | 200 |
| JOB-02 | 추천 가능한 공고 없음 | 빈 목록 또는 404 |
| CHAT-01 | 정상 상담 | 200 |
| CHAT-02 | 빈 질문 | 400 |
| CHAT-03 | Redis 장애 | 일반 LLM fallback |
| ADMIN-01 | 일반 사용자의 관리자 API 호출 | 403 |
| ADMIN-02 | 관리자 채용공고 등록 | 201 |

### 17.2 UI 테스트

- 로그인 전 보호 페이지 접근 차단
- 로그인 성공 후 대시보드 이동
- 목표 저장 성공/실패 메시지
- 로드맵 생성 중 spinner 표시
- 생성 버튼 중복 클릭 방지
- 할 일 완료 시 진행률 즉시 반영
- 채용공고 지원 링크 정상 동작
- AI 상담 오류 시 사용자 친화적 메시지
- 관리자 메뉴가 관리자에게만 표시

### 17.3 발표 전 확인

- 샘플 계정 로그인 가능
- 샘플 목표 데이터 존재
- AI 로드맵 생성 가능
- LLM 장애 대비 샘플 응답 준비
- 추천 공고 최소 5건 존재
- 관리자 계정 로그인 가능
- API 키와 개인정보가 화면에 노출되지 않음

---

## 18. 완료 기준

다음 조건을 만족하면 MVP 완료로 판단한다.

- 사용자가 로그인할 수 있다.
- 사용자가 취업 목표를 등록할 수 있다.
- 목표를 바탕으로 AI 로드맵을 생성할 수 있다.
- 로드맵 할 일을 완료 처리하고 진행률을 확인할 수 있다.
- 사용자에게 맞는 채용공고를 추천할 수 있다.
- RAG 또는 fallback 기반으로 AI 취업 상담을 받을 수 있다.
- 관리자가 채용공고를 등록하고 수정할 수 있다.
- 대표적인 오류 상황에서 서버가 중단되지 않고 표준 오류 응답을 반환한다.
- README에 실행 방법이 작성되어 있다.
- main 브랜치에서 시연 가능한 상태이다.

---

## 19. 구현 우선순위

### Priority 1 — 반드시 구현

1. 로그인
2. 목표 등록
3. AI 로드맵 생성
4. 할 일 완료 및 진행률
5. 채용공고 추천
6. AI 상담

### Priority 2 — 가능하면 구현

1. 관리자 채용공고 CRUD
2. 상담 기록
3. 사용자 현황 조회
4. Redis 캐시

### Priority 3 — 시간이 남을 때

1. 관리자 통계 차트
2. 자기소개서 피드백
3. 문서 파일 업로드
4. 고급 추천 알고리즘

---

## 20. 시연 시나리오

1. 일반 사용자 로그인
2. 목표 직무 `백엔드 개발자`, 목표 기간 입력
3. AI 로드맵 생성
4. 생성된 주차별 할 일 확인
5. 할 일 1개 완료 후 진행률 변화 확인
6. 맞춤 채용공고 추천 목록 확인
7. AI 상담에서 `FastAPI 포트폴리오는 어떻게 만들면 좋나요?` 질문
8. 답변과 참고 문서 확인
9. 관리자 로그인
10. 신규 채용공고 등록
11. 사용자 화면에서 등록된 공고 확인

이 시나리오를 기준으로 기능을 개발하면 3일 동안의 구현 범위를 통제하면서 LLM, RAG, Redis, Supabase, FastAPI, Streamlit을 모두 시연할 수 있다.
