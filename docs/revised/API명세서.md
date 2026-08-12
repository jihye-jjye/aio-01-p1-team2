# API 명세서

## 1. 관리자 API 공통 규칙

관리자 로그인 이외의 `/api/v1/admin/**` 요청은 다음 헤더가 필요하다.

```http
Authorization: Bearer {access_token}
```

서버는 JWT 유효성·만료·관리자 scope와 함께 `app.user_accounts`의 역할, 활성 상태와 잠금 상태를 재검증한다. 요청과 응답은 기본적으로 `application/json`이다.

## 2. 관리자 인증

| Method | Endpoint                   | 인증 | 설명                              |
| ------ | -------------------------- | ---: | --------------------------------- |
| POST   | `/api/v1/admin/auth/login` |    N | 관리자 로그인과 Access Token 발급 |
| GET    | `/api/v1/admin/auth/me`    |    Y | 현재 관리자 정보 확인             |

로그인 요청:

```json
{
  "login_id": "admin001",
  "password": "관리자 비밀번호"
}
```

- `login_id`: 4~50자, 영문·숫자·`.`·`_`·`-`
- `password`: 1~256자

로그인 성공 응답:

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

`.env`에 관리자 아이디와 비밀번호를 직접 저장하는 방식이 아니다. `app.user_accounts`에 `role='admin'`, 유효한 `password_hash`, `is_active=true`인 계정이 있어야 로그인할 수 있다.

## 3. 사용자 관리

| Method | Endpoint                                              | 설명                                         |
| ------ | ----------------------------------------------------- | -------------------------------------------- |
| GET    | `/api/v1/admin/users`                                 | 목록, 검색, 역할·활성 상태 필터, 페이지 조회 |
| GET    | `/api/v1/admin/users/by-login-id/{login_id}`          | 계정·프로필 상세 조회                        |
| GET    | `/api/v1/admin/users/by-login-id/{login_id}/overview` | 계정·프로필·계획·퀘스트·진행률 종합 조회     |
| GET    | `/api/v1/admin/users/by-login-id/{login_id}/roadmaps` | 계획별 로드맵 이력 조회                      |
| GET    | `/api/v1/admin/users/by-login-id/{login_id}/quests`   | 전체 퀘스트와 활성 계획 진행률 조회          |
| PATCH  | `/api/v1/admin/users/{user_id}`                       | 사용자 활성 상태 수정                        |
| DELETE | `/api/v1/admin/users/{user_id}`                       | 일반 사용자 및 연관 데이터 영구 삭제         |

목록 Query:

| 이름        | 타입              | 기본값 | 제약·설명                                   |
| ----------- | ----------------- | -----: | ------------------------------------------- |
| `search`    | string            |      - | 로그인 아이디 부분 검색 또는 UUID 정확 검색 |
| `role`      | `user` \| `admin` |      - | 역할 필터                                   |
| `is_active` | boolean           |      - | 활성 상태 필터                              |
| `page`      | integer           |      1 | 1 이상                                      |
| `size`      | integer           |     20 | 1~100                                       |

상태 수정 요청:

```json
{"is_active": false}
```

종합 응답은 `account`, `plans`, `quests`, `quest_progress`, `roadmap_history`, `last_login_at`을 포함한다. 진행률은 `counts_toward_progress=true`이고 취소되지 않은 퀘스트를 대상으로 계산하며, 종료된 계획은 저장된 `final_progress`를 사용할 수 있다. 관리자 역할 계정 삭제는 `409`로 차단된다.

## 4. 공지사항 관리자 CRUD

| Method | Endpoint                            | 설명                       |
| ------ | ----------------------------------- | -------------------------- |
| GET    | `/api/v1/admin/notices`             | 제목 검색·페이지 기반 목록 |
| POST   | `/api/v1/admin/notices`             | 공지 등록 (`201`)          |
| GET    | `/api/v1/admin/notices/{notice_id}` | 공지 상세                  |
| PATCH  | `/api/v1/admin/notices/{notice_id}` | 제목 또는 내용 수정        |
| DELETE | `/api/v1/admin/notices/{notice_id}` | 공지 삭제                  |

등록 요청:

```json
{
  "title": "서비스 점검 안내",
  "content": "점검 일정을 안내합니다."
}
```

- `title`: 1~200자
- `content`: 1~20,000자
- 수정 시 두 필드는 선택 사항이지만 하나 이상 전달해야 한다.
- 응답 필드: `id`, `title`, `content`, `created_at`, `updated_at`

현재 관리자 서버에는 별도 공개 공지 라우터가 등록되어 있지 않다. 일반 사용자 공지 조회는 사용자 서버의 `GET /api/v1/notices`가 담당한다.

## 5. 관리자 대시보드

```http
GET /api/v1/admin/dashboard?days=7
```

- `days`: 1~90, 기본값 7
- Supabase RPC `app.get_admin_dashboard(days)` 사용
- 기준 시간대: `Asia/Seoul`
- 관리자 역할 계정은 사용자 지표에서 제외

응답 그룹:

| 필드            | 내용                                    |
| --------------- | --------------------------------------- |
| `period`        | 조회 일수와 시작·종료 시각              |
| `users`         | 전체·활성·비활성·신규 사용자            |
| `onboarding`    | 프로필·완료·미완료 수와 완료율          |
| `assessment`    | 평가 사용자·평균 점수·등급 분포         |
| `roadmaps`      | 계획 보유 사용자와 상태별 계획 수       |
| `quests`        | 전체·완료·진행·대기·오늘·지연·면접 지표 |
| `daily_signups` | 일별 가입 추이                          |
| `recent_users`  | 최근 가입 사용자 5명                    |

## 6. 저장된 취업 공고

```http
GET /api/v1/admin/saved-jobs
```

현재는 읽기 전용이다.

| Query         | 타입                   | 기본값 | 설명                |
| ------------- | ---------------------- | -----: | ------------------- |
| `source_type` | `url` \| `pasted_text` |      - | 공고 입력 출처 필터 |
| `page`        | integer                |      1 | 페이지              |
| `size`        | integer                |     20 | 1~100               |

응답 항목은 `id`, `source_type`, `source_url`, `source_key`, `company_name`, `job_title`, `deadline`, `posting_text`, `extracted_data`, `created_at`, `updated_at`을 포함한다.

## 7. AI 운영 로그와 피드백

| Method | Endpoint                         | 인증 주체   | 설명                         |
| ------ | -------------------------------- | ----------- | ---------------------------- |
| GET    | `/api/v1/admin/logs`             | 관리자      | 로그 목록·필터·페이지 조회   |
| GET    | `/api/v1/admin/logs/summary`     | 관리자      | 요청 수·오류율·평균 지연 KPI |
| GET    | `/api/v1/admin/logs/{log_id}`    | 관리자      | 로그 상세                    |
| GET    | `/api/v1/logs/{log_id}/feedback` | 일반 사용자 | 본인 피드백 조회             |
| POST   | `/api/v1/logs/{log_id}/feedback` | 일반 사용자 | 점수·의견 생성 또는 수정     |

로그 목록 필터: `level`, `endpoint`, `start_at`, `end_at`, `page`, `size`.

피드백 요청:

```json
{
  "score": 5,
  "comment": "도움이 되었습니다."
}
```

다만 현재 `backend_admin/sql`에는 코드가 참조하는 `app.ai_logs`, `app.admin_log_summary`, `app.feedback` 생성 SQL이 없다. 해당 객체가 Supabase에 별도로 존재하지 않으면 이 API들은 저장소 오류를 반환한다.

## 8. 사용자 API 구현 범위

사용자 서버는 `/api/v1` 아래 다음 도메인을 등록한다.

| 도메인            | 주요 기능                                 |
| ----------------- | ----------------------------------------- |
| `/auth`           | 회원가입, 로그인, 내 정보 조회·수정, 탈퇴 |
| `/onboarding`     | 대화형 온보딩, 세션·완료 처리             |
| `/profile`        | 사용자 프로필 조회                        |
| `/plan-proposals` | 로드맵 제안 생성·조회·수락·거절           |
| `/plans`          | 계획 목록·상세·상태 관리                  |
| `/quests`         | 오늘의 퀘스트와 완료 상태 변경            |
| `/saved-jobs`     | 공고 목록·추천 관련 조회                  |
| `/notifications`  | 알림 동기화·읽음 처리                     |
| `/notices`        | 공개 공지 조회                            |
| `/assistant`      | AI 취업 상담 세션                         |

정확한 요청·응답 모델은 `backend_user/docs/API_SPEC.md`와 런타임 OpenAPI를 기준으로 한다.

## 9. 오류 응답

일반 HTTP 오류:

```json
{"detail": "오류 메시지"}
```

FastAPI 검증 오류 `422`:

```json
{
  "detail": [
    {"loc": ["body", "field"], "msg": "오류 설명", "type": "오류 유형"}
  ]
}
```

| HTTP | 의미                                      |
| ---: | ----------------------------------------- |
|  200 | 조회·수정·삭제 성공                       |
|  201 | 생성 성공                                 |
|  401 | 토큰 없음·만료·무효 또는 관리자 인증 실패 |
|  403 | 비활성·잠금 계정                          |
|  404 | 리소스 없음                               |
|  409 | 현재 상태와 요청 충돌                     |
|  422 | Path·Query·Body 검증 실패                 |
|  503 | Supabase, RPC 또는 저장소 오류            |

## 10. 프론트엔드 연동 상태

관리자 프론트엔드에서 현재 연결된 기능은 로그인, 대시보드, 사용자 목록·상세·종합 정보, 로드맵 조회, 공지 목록·상세, 저장 공고 목록·상세이다. 공지 등록·수정·삭제, 저장 공고 변경, 사용자 상태 변경·삭제, AI 로그 화면은 API 또는 화면 일부가 있어도 프론트엔드에서 완전히 연결되지 않았다.

## 11. 주요 요청·응답 모델 명세

| 모델                   | 필드와 타입                                                                                               | 필수 여부      |
| ---------------------- | --------------------------------------------------------------------------------------------------------- | -------------- |
| `AdminLoginRequest`    | `login_id: str`, `password: str`                                                                          | 모두 필수      |
| `AdminIdentity`        | `id: UUID`, `login_id: str`, `role: Literal['admin']`                                                     | 모두 필수      |
| `AdminLoginResponse`   | `access_token: str`, `token_type: Literal['bearer']`, `expires_in: int`, `admin: AdminIdentity`           | 모두 필수      |
| `AdminUserUpdate`      | `is_active: bool`                                                                                         | 필수           |
| `NoticeCreate`         | `title: str`, `content: str`                                                                              | 모두 필수      |
| `NoticeUpdate`         | `title: str \| None`, `content: str \| None`                                                              | 하나 이상 필수 |
| `FeedbackCreate`       | `score: int`, `comment: str \| None`                                                                      | `score` 필수   |
| `AdminUserQueryParams` | `search: str \| None`, `role: UserRole \| None`, `is_active: bool \| None`, `page: int=1`, `size: int=20` | 모두 선택      |
| `SavedJobQueryParams`  | `source_type: Literal['url','pasted_text'] \| None`, `page: int=1`, `size: int=20`                        | 모두 선택      |

대표 중첩 Pydantic 구조:

```python
class AdminRoadmapHistoryItem(BaseModel):
    plan: AdminPlanSummary
    quests: list[AdminQuestItem]
    progress: AdminQuestProgress

class AdminUserOverview(BaseModel):
    account: AdminUserDetail
    plans: list[AdminPlanSummary]
    quests: list[AdminQuestItem]
    quest_progress: AdminQuestProgress
    roadmap_history: list[AdminRoadmapHistoryItem]
    last_login_at: datetime | None

class AdminDashboardResponse(BaseModel):
    generated_at: datetime
    period: DashboardPeriod
    users: DashboardUserMetrics
    onboarding: DashboardOnboardingMetrics
    assessment: DashboardAssessmentMetrics
    roadmaps: DashboardRoadmapMetrics
    quests: DashboardQuestMetrics
    daily_signups: list[DashboardDailySignup]
    recent_users: list[DashboardRecentUser]
```

종합 사용자 응답 예시:

```json
{
  "account": {
    "id": "d25519d6-9849-4adb-a7a8-074ef08e4398",
    "login_id": "roadmap_user",
    "role": "user",
    "user_exp": 40,
    "is_active": true,
    "last_login_at": "2026-08-12T09:30:00+09:00",
    "failed_login_count": 0,
    "locked_until": null,
    "created_at": "2026-08-01T10:00:00+09:00",
    "updated_at": "2026-08-12T09:30:00+09:00",
    "profile": {
      "user_id": "d25519d6-9849-4adb-a7a8-074ef08e4398",
      "target_role": "백엔드 개발자",
      "skills": ["Python", "FastAPI"],
      "assistant_style": "supportive",
      "created_at": "2026-08-01T10:10:00+09:00",
      "updated_at": "2026-08-11T18:00:00+09:00"
    }
  },
  "plans": [],
  "quests": [],
  "quest_progress": {
    "total": 0,
    "completed": 0,
    "in_progress": 0,
    "pending": 0,
    "progress_percent": 0,
    "is_final": false
  },
  "roadmap_history": [],
  "last_login_at": "2026-08-12T09:30:00+09:00"
}
```

## 12. 표준 오류 계약과 실제 구현 차이

프로젝트 가이드가 요구하는 목표 표준 오류 모델은 다음과 같다.

```python
class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None
    trace_id: str | None = None

class ErrorResponse(BaseModel):
    error: ErrorBody
```

```json
{
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "요청한 사용자를 찾을 수 없습니다.",
    "details": {"login_id": "missing_user"},
    "trace_id": null
  }
}
```

현재 관리자 API는 대부분 FastAPI 기본 `{"detail": ...}` 형식을 사용하므로 위 목표 형식과 일치하지 않는다. 제출 기준을 완전히 충족하려면 공통 예외 handler와 오류 코드를 구현해야 한다.

| 상황                | HTTP | 목표 오류 코드           | 현재 처리                        |
| ------------------- | ---: | ------------------------ | -------------------------------- |
| 로그인 실패         |  401 | `ADMIN_AUTH_FAILED`      | `detail` 반환                    |
| 비활성·잠금 관리자  |  403 | `ADMIN_ACCOUNT_DISABLED` | `detail` 반환                    |
| 사용자 없음         |  404 | `USER_NOT_FOUND`         | `detail` 반환                    |
| 관리자 삭제 시도    |  409 | `ADMIN_DELETE_FORBIDDEN` | `detail` 반환                    |
| 입력 검증 실패      |  422 | `VALIDATION_ERROR`       | FastAPI 오류 배열                |
| 호출 한도 초과      |  429 | `RATE_LIMITED`           | 사용자 AI 계층에서 도메인별 처리 |
| 내부 오류           |  500 | `INTERNAL_ERROR`         | 기본 서버 처리                   |
| DB·외부 저장소 장애 |  503 | `STORAGE_UNAVAILABLE`    | `detail` 반환                    |

## 13. 가이드 산출물 충족 점검

| 요구사항                        | 상태        | 근거·보완                                               |
| ------------------------------- | ----------- | ------------------------------------------------------- |
| 리소스 중심 URL·HTTP Method     | 충족        | 등록 라우터와 엔드포인트 표                             |
| API별 요청·응답 모델과 예시     | 부분 충족   | 핵심 관리자 모델 기재, 전체 사용자 API는 별도 명세 참조 |
| nested Pydantic 모델            | 충족        | 사용자 종합 상세와 대시보드 구조 기재                   |
| 코드·메시지·상세 포함 표준 오류 | 설계만 충족 | 현재 구현은 FastAPI `detail`, 공통 handler 필요         |
| 4xx·5xx 처리 규칙               | 충족        | 상태별 규칙과 구현 차이 기재                            |
