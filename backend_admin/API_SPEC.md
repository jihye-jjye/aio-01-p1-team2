# 관리자 백엔드 API 명세서

- 기준일: 2026-08-11
- 애플리케이션: `Admin Backend`
- 로컬 Base URL: `http://127.0.0.1:8000`
- API prefix: `/api/v1`
- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`
- 요청·응답 Content-Type: `application/json`

## 1. 인증

관리자 로그인 API를 제외한 `/api/v1/admin/**` API에는 관리자 Access Token이 필요하다.

```http
Authorization: Bearer {access_token}
```

토큰 검증 시 다음 조건을 모두 확인한다.

- JWT가 유효하고 만료되지 않았는가
- JWT scope가 관리자용인가
- 토큰의 사용자 UUID가 `app.user_accounts`에 존재하는가
- 현재 계정의 `role`이 `admin`인가
- 계정이 활성 상태인가
- 계정이 잠기지 않았는가

### 1.1 관리자 로그인

```http
POST /api/v1/admin/auth/login
```

Request body:

| 필드 | 타입 | 필수 | 제약 |
|---|---|---:|---|
| `login_id` | string | Y | 4~50자, 영문·숫자·`.`·`_`·`-` |
| `password` | string | Y | 1~256자 |

```json
{
  "login_id": "admin001",
  "password": "관리자 비밀번호"
}
```

Response `200`:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "admin": {
    "id": "00000000-0000-0000-0000-000000000000",
    "login_id": "admin001",
    "role": "admin"
  }
}
```

오류:

| HTTP | 상황 |
|---:|---|
| 401 | 아이디·비밀번호 불일치 또는 관리자 역할이 아님 |
| 403 | 비활성화되었거나 잠긴 관리자 계정 |
| 422 | 요청 형식 검증 실패 |
| 503 | 인증 저장소 또는 토큰 발급 오류 |

### 1.2 현재 관리자 확인

```http
GET /api/v1/admin/auth/me
```

Response `200`:

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "login_id": "admin001",
  "role": "admin"
}
```

## 2. 사용자 관리

### 2.1 사용자 목록·검색·필터

```http
GET /api/v1/admin/users
```

Query parameters:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---:|---:|---|
| `search` | string | N | - | 로그인 아이디 부분 검색 또는 UUID 정확 검색 |
| `role` | `user` \| `admin` | N | - | 역할 필터 |
| `is_active` | boolean | N | - | 활성 상태 필터 |
| `page` | integer | N | 1 | 1 이상 |
| `size` | integer | N | 20 | 1~100 |

Response `200`:

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000000",
      "login_id": "usertest",
      "role": "user",
      "user_exp": 20,
      "is_active": true,
      "last_login_at": "2026-08-11T01:00:00Z",
      "failed_login_count": 0,
      "locked_until": null,
      "created_at": "2026-08-01T01:00:00Z",
      "updated_at": "2026-08-11T01:00:00Z",
      "profile": null
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

### 2.2 사용자 상세 조회

```http
GET /api/v1/admin/users/by-login-id/{login_id}
```

Path parameter:

| 이름 | 타입 | 제약 |
|---|---|---|
| `login_id` | string | 4~50자, `^[a-zA-Z0-9._-]+$` |

Response `200`: 계정 정보와 선택적 `profile`을 반환한다. 비밀번호 해시는 반환하지 않는다.

Profile 주요 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `target_role` | string \| null | 목표 직무 |
| `skills` | string[] | 보유 기술 |
| `experience_summary` | string \| null | 경력 요약 |
| `target_date` | date \| null | 목표일 |
| `target_company` | string \| null | 목표 회사 |
| `preferred_environment` | string \| null | 선호 환경 |
| `assistant_style` | string | AI 응답 스타일 |
| `daily_notification_time` | time \| null | 일일 알림 시각 |
| `assessment_score` | integer \| null | 역량 평가 점수 |
| `assessment_level` | string \| null | 역량 평가 등급 |
| `assessment_summary` | object \| null | 역량 평가 요약 |
| `assessed_at` | datetime \| null | 평가 시각 |
| `onboarding_completed_at` | datetime \| null | 온보딩 완료 시각 |

오류: `404` 사용자 없음, `422` 로그인 아이디 형식 오류, `503` 저장소 오류.

### 2.3 사용자 종합 상세 조회

```http
GET /api/v1/admin/users/by-login-id/{login_id}/overview
```

Response `200` 구성:

| 필드 | 타입 | 설명 |
|---|---|---|
| `account` | AdminUserDetail | 계정·프로필 |
| `plans` | AdminPlanSummary[] | 전체 계획 |
| `quests` | AdminQuestItem[] | 전체 퀘스트 및 일정 |
| `quest_progress` | AdminQuestProgress | 활성 계획 진행률 |
| `roadmap_history` | AdminRoadmapHistoryItem[] | 계획별 퀘스트·진행률 |
| `last_login_at` | datetime \| null | 최근 로그인 시각 |

### 2.4 로드맵 이력 조회

```http
GET /api/v1/admin/users/by-login-id/{login_id}/roadmaps
```

Response `200`:

```json
{
  "login_id": "usertest",
  "items": [
    {
      "plan": {},
      "quests": [],
      "progress": {
        "total": 10,
        "completed": 4,
        "in_progress": 2,
        "pending": 4,
        "progress_percent": 40,
        "is_final": false
      }
    }
  ]
}
```

Plan 주요 필드:

`id`, `source_saved_job_id`, `proposal_result_id`, `previous_plan_id`, `title`, `summary`, `goal_snapshot`, `starts_on`, `ends_on`, `total_task_count`, `final_progress`, `status`, `activated_at`, `ended_at`, `archived_at`, `created_at`, `updated_at`.

### 2.5 퀘스트·진행률 조회

```http
GET /api/v1/admin/users/by-login-id/{login_id}/quests
```

Response `200`:

```json
{
  "login_id": "usertest",
  "quests": [],
  "active_plan_progress": {
    "total": 0,
    "completed": 0,
    "in_progress": 0,
    "pending": 0,
    "progress_percent": 0,
    "is_final": false
  }
}
```

Quest 주요 필드:

`id`, `plan_id`, `saved_job_id`, `kind`, `title`, `description`, `scheduled_at`, `remind_at`, `status`, `plan_day`, `slot`, `detail_status`, `counts_toward_progress`, `metadata`, `completed_at`, `created_at`, `updated_at`.

진행률은 `counts_toward_progress=true`이며 취소되지 않은 퀘스트를 대상으로 계산한다. 종료된 계획은 `final_progress`를 최종값으로 사용할 수 있다.

### 2.6 사용자 활성 상태 수정

```http
PATCH /api/v1/admin/users/{user_id}
```

```json
{
  "is_active": false
}
```

Response `200`: 변경된 사용자 계정·프로필 상세.

### 2.7 사용자 영구 삭제

```http
DELETE /api/v1/admin/users/{user_id}
```

Response `200`: 삭제 직전 계정 정보. `profile`은 `null`이다.

| HTTP | 상황 |
|---:|---|
| 404 | 사용자를 찾을 수 없음 |
| 409 | 관리자 역할 계정 삭제 시도 |
| 503 | 연관 데이터 또는 계정 삭제 실패 |

## 3. 공지사항 관리

### 3.1 공지 목록

```http
GET /api/v1/admin/notices?search={검색어}&page=1&size=20
```

- `search`: 제목 부분 검색, 최대 200자
- 최신 생성순 정렬
- `size`: 1~100

Response `200`: `items`, `page`, `size`, `total`, `total_pages`.

### 3.2 공지 상세

```http
GET /api/v1/admin/notices/{notice_id}
```

### 3.3 공지 등록

```http
POST /api/v1/admin/notices
```

```json
{
  "title": "서비스 점검 안내",
  "content": "점검 일정을 안내합니다."
}
```

- `title`: 1~200자
- `content`: 1~20,000자
- 성공: `201 Created`

### 3.4 공지 수정

```http
PATCH /api/v1/admin/notices/{notice_id}
```

```json
{
  "title": "변경된 제목",
  "content": "변경된 내용"
}
```

`title`, `content`는 선택 필드이나 최소 한 필드는 전달해야 한다.

### 3.5 공지 삭제

```http
DELETE /api/v1/admin/notices/{notice_id}
```

공지 응답 공통 필드: `id`, `title`, `content`, `created_at`, `updated_at`.

## 4. 관리자 대시보드

```http
GET /api/v1/admin/dashboard?days=7
```

| Query | 타입 | 기본값 | 제약 |
|---|---|---:|---|
| `days` | integer | 7 | 1~90 |

Response `200`:

```json
{
  "generated_at": "2026-08-11T01:00:00Z",
  "period": {
    "days": 7,
    "start_at": "2026-08-05T00:00:00Z",
    "end_at": "2026-08-11T01:00:00Z"
  },
  "users": {
    "total_users": 100,
    "active_accounts": 90,
    "inactive_accounts": 10,
    "new_users": 5
  },
  "onboarding": {
    "profile_count": 80,
    "completed_count": 60,
    "incomplete_count": 40,
    "completion_rate": 60.0
  },
  "assessment": {
    "assessed_users": 50,
    "average_score": 72.5,
    "level_distribution": {
      "beginner": 15,
      "intermediate": 25,
      "advanced": 10
    }
  },
  "roadmaps": {
    "users_with_plans": 55,
    "active_plans": 30,
    "completed_plans": 20,
    "expired_plans": 5,
    "status_distribution": {
      "draft": 3,
      "active": 30,
      "completed": 20,
      "expired": 5,
      "superseded": 2,
      "rejected": 1
    }
  },
  "quests": {
    "total": 500,
    "completed": 300,
    "in_progress": 80,
    "pending": 120,
    "completion_rate": 60.0,
    "scheduled_today": 20,
    "completed_today": 8,
    "overdue": 7,
    "interviews_today": 2
  },
  "daily_signups": [],
  "recent_users": []
}
```

DB 의존성: Supabase RPC `app.get_admin_dashboard(days)`.

## 5. 저장된 취업 공고

```http
GET /api/v1/admin/saved-jobs
```

읽기 전용 목록 API다.

| Query | 타입 | 기본값 | 설명 |
|---|---|---:|---|
| `source_type` | `url` \| `pasted_text` | - | 입력 출처 필터 |
| `page` | integer | 1 | 1 이상 |
| `size` | integer | 20 | 1~100 |

Response item:

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "source_type": "url",
  "source_url": "https://example.com/job/1",
  "source_key": "example-job-1",
  "company_name": "Example Corp",
  "job_title": "Backend Developer",
  "deadline": "2026-08-31",
  "posting_text": "채용 공고 본문",
  "extracted_data": {},
  "created_at": "2026-08-11T01:00:00Z",
  "updated_at": "2026-08-11T01:00:00Z"
}
```

## 6. AI 운영 로그

### 6.1 로그 목록

```http
GET /api/v1/admin/logs
```

| Query | 타입 | 기본값 | 설명 |
|---|---|---:|---|
| `level` | `INFO` \| `WARN` \| `ERROR` | - | 로그 레벨 |
| `endpoint` | string | - | 엔드포인트 필터 |
| `start_at` | datetime | - | 시작 시각 |
| `end_at` | datetime | - | 종료 시각 |
| `page` | integer | 1 | 페이지 |
| `size` | integer | 20 | 1~100 |

### 6.2 로그 KPI

```http
GET /api/v1/admin/logs/summary
```

```json
{
  "total_requests": 1000,
  "error_count": 20,
  "error_rate": 2.0,
  "average_latency_ms": 1250.5
}
```

### 6.3 로그 상세

```http
GET /api/v1/admin/logs/{log_id}
```

Log 필드:

`id`, `user_id`, `session_id`, `request_id`, `level`, `endpoint`, `model_name`, `status_code`, `latency_ms`, `error_code`, `message`, `created_at`.

DB 의존성: `app.ai_logs` 테이블과 `app.admin_log_summary` 뷰.

## 7. 같은 서버에 포함된 사용자 피드백 API

이 API는 관리자 API가 아니라 일반 사용자 JWT를 사용한다.

### 7.1 내 피드백 조회

```http
GET /api/v1/logs/{log_id}/feedback
```

Response `200`: FeedbackResponse 또는 `null`.

### 7.2 피드백 생성·수정

```http
POST /api/v1/logs/{log_id}/feedback
```

```json
{
  "score": 5,
  "comment": "도움이 되었습니다."
}
```

- `score`: 1~5
- `comment`: 선택, 최대 1,000자

Feedback 필드: `id`, `log_id`, `user_id`, `score`, `comment`, `created_at`, `updated_at`.

## 8. 공통 오류 응답

FastAPI 기본 오류 예시:

```json
{
  "detail": "오류 메시지"
}
```

검증 오류 `422`:

```json
{
  "detail": [
    {
      "loc": ["body", "field"],
      "msg": "오류 설명",
      "type": "검증 오류 유형"
    }
  ]
}
```

| HTTP | 공통 의미 |
|---:|---|
| 200 | 조회·수정·삭제 성공 |
| 201 | 생성 성공 |
| 401 | 토큰 없음, 만료, 유효하지 않음 또는 관리자 권한 없음 |
| 403 | 비활성·잠금 계정 |
| 404 | 리소스 없음 |
| 409 | 현재 상태와 요청이 충돌함 |
| 422 | Path·Query·Body 검증 실패 |
| 503 | Supabase, DB 함수 또는 저장소 오류 |

## 9. 프런트엔드 연동 순서

1. `POST /api/v1/admin/auth/login` 호출
2. 응답의 `access_token`을 세션에 보관
3. 관리자 API 요청마다 `Authorization: Bearer {token}` 전달
4. 앱 시작 또는 새로고침 시 `GET /api/v1/admin/auth/me`로 토큰과 관리자 상태 확인
5. `401`이면 로그인 화면으로 이동
6. `403`이면 비활성·잠금 안내
7. `422`이면 입력 필드 오류 표시
8. `503`이면 재시도 가능한 서버 오류 안내

> Access Token은 로그나 URL Query parameter에 기록하지 않는다.
