# AI Job Coach API 명세서

이 문서는 `backend_user/app` 코드 기준으로 AI Job Coach 백엔드의 HTTP API를 정리한다. 실제 구현과 다른 점이 있으면 코드가 정답이다.

- 작성일: 2026-08-11
- 대상 서버: FastAPI `app.main:app` (`title="AI Job Coach API"`, `version="0.1.0"`)
- 배포 Base URL: `https://aio-01-p1-team2-1.onrender.com/api/v1`
- 로컬 Base URL: `http://127.0.0.1:8010/api/v1` (`run.sh`는 `0.0.0.0:8010`에 bind)
- FastAPI 자동 문서: `GET /docs` (Swagger UI), `GET /openapi.json`
- 프론트엔드 전달 문서: [`FRONTEND_AUTH_ONBOARDING_HANDOFF.md`](FRONTEND_AUTH_ONBOARDING_HANDOFF.md)

### 검증 상태

- 1차 검증: FastAPI 라우트, Pydantic 요청/응답 모델, 예외 handler, OpenAPI schema와 대조
- 2차 검증: 인증·온보딩·프로필 기반 계획 생성과 계획 생명주기를 자동 테스트 및 정적 검사로 재검증
- 3차 검증: 날짜별 목표 달성, 누적 EXP, PATCH 멱등성·rollback·동시성 계약을 repository/API/CLI 테스트와 대조
- 4차 검증: 인증 사용자 공통 저장 공고 조회의 전역 범위·정렬·응답 계약을 repository/API/OpenAPI 테스트와 대조
- 5차 검증: 추천 공고 선택형 계획 생성의 요청·응답·checkpoint·멱등성·수락 투영 계약을 repository/API/CLI/OpenAPI 테스트와 대조
- 6차 검증: 로드맵 완료율 요약(`GET /plans/summary`)의 로드맵별·계정 통합 백분율, 정렬, 빈 상태, 경로 매칭 우선순위 계약을 repository/service/API/CLI/OpenAPI 테스트와 대조
- 7차 검증: 현재 계정 로그인 ID·이름 수정과 영구 삭제의 인증·검증·중복 처리·활성 계정 확인·삭제 트랜잭션·runtime 권한·OpenAPI 계약을 대조
- 8차 검증: AI 취업 코치 세션의 24시간 절대 보관 상한·120초 유휴 종료·활성 6개 제한·revision CAS·멱등성, 공고/일정 DB 사실 분리, 상담 종료 보고서·Redis tombstone·migration 19~21 계약을 API/service/store/repository/SQL 테스트와 대조
- 9차 검증: 실제 `TP_dev`에서 migration 21 등록, 수정된 보고서 CHECK의 `VALIDATED` 상태와 정상 보고서 허용·root/nested/array의 금지 키 거부를 확인하고 assistant 3개 POST 경로의 OpenAPI 응답 계약을 재검증
- 10차 검증: 로그인 로드맵 알림의 KST 7일 동기화, 트리거 집계, 소유권 격리, 미확인 feed, 명시적 확인, API/CLI 응답 검증 계약을 SQL·repository/service/API/CLI 테스트와 대조
- 검증일: 2026-08-11

## 목차

1. [공통 규약](#1-공통-규약)
2. [인증](#2-인증)
3. [엔드포인트](#3-엔드포인트)
   - [POST /auth/signup](#post-authsignup)
   - [POST /auth/login](#post-authlogin)
   - [GET /auth/me](#get-authme)
   - [PATCH /auth/me](#patch-authme)
   - [DELETE /auth/me](#delete-authme)
   - [GET /profile](#get-profile)
   - [POST /notifications/login-feed](#post-notificationslogin-feed)
   - [PATCH /notifications/{notification_id}/read](#patch-notificationsnotification_idread)
   - [GET /saved-jobs](#get-saved-jobs)
   - [GET /saved-jobs/recommendation](#get-saved-jobsrecommendation)
   - [AI 취업 코치 상담](#ai-취업-코치-상담)
   - [POST /assistant/sessions](#post-assistantsessions)
   - [POST /assistant/sessions/{session_id}/messages](#post-assistantsessionssession_idmessages)
   - [POST /assistant/sessions/{session_id}/finalize](#post-assistantsessionssession_idfinalize)
   - [POST /onboarding/sessions](#post-onboardingsessions)
   - [POST /onboarding/sessions/{session_id}/messages](#post-onboardingsessionssession_idmessages)
   - [GET /onboarding/sessions/{session_id}/result](#get-onboardingsessionssession_idresult)
   - [POST /onboarding/sessions/{session_id}/confirm](#post-onboardingsessionssession_idconfirm)
   - [계획 제안·활성 계획](#계획-제안활성-계획)
   - [GET /plans/summary](#get-planssummary)
4. [데이터 모델](#4-데이터-모델)
5. [에러 코드 전체 표](#5-에러-코드-전체-표)
6. [제한·정책 요약](#6-제한정책-요약)

---

## 1. 공통 규약

### 요청

- 본문은 `application/json`.
- 인증이 필요한 엔드포인트는 `Authorization: Bearer <access_token>` 헤더가 필요하다.
- 온볼딩 쓰기 요청(`POST /onboarding/...`)은 모두 클라이언트가 생성한 `request_id`(UUID)를 요구한다. 멱등성 키로 사용된다.
- 계획 제안 생성 `POST /plan-proposals`도 클라이언트가 생성한 `request_id`(UUID)를 멱등성 키로 요구하며, 선택한 추천 공고가 있으면 선택 필드 `saved_job_id`(UUID)를 함께 보낸다.
- AI 취업 코치의 세션 생성·메시지·종료 요청도 각각 새 `request_id`(UUID)를 요구한다. 메시지와 종료 요청에는 가장 최근 성공 응답의 `revision`을 `expected_revision`으로 보낸다.
- 인증된 요청의 사용자 ID는 access token에서만 결정한다. body나 path로 `user_id`를 보내지 않는다.
- 코치 API 요청 모델은 알 수 없는 필드를 거부한다(`extra="forbid"`). 응답은 비스트리밍 JSON이다.
- 날짜는 `YYYY-MM-DD`, 시각은 ISO time, timestamp는 timezone이 포함된 ISO 8601 문자열로 처리한다.

### 브라우저 연결 전제

- 현재 FastAPI 앱에는 CORS middleware가 없다.
- 브라우저 프론트엔드는 API와 동일 origin으로 서비스하거나 reverse proxy를 통해 `/api/v1`을 연결해야 한다.
- 다른 origin에서 직접 호출하려면 백엔드에 명시적인 CORS allowlist를 먼저 추가해야 한다. 임의의 `*` 허용은 인증 토큰 노출 위험 때문에 사용하지 않는다.

### 성공 응답

- 엔드포인트별 모델을 그대로 JSON으로 반환한다(별도 envelope 없음).

### 에러 응답

명세에 정의된 인증·검증·도메인·인프라 에러는 같은 envelope를 사용한다.

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "사람이 읽을 수 있는 한국어 메시지",
    "retryable": false,
    "details": {}
  }
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `code` | string | 기계가 분기할 수 있는 에러 코드 |
| `message` | string | 사용자 노출 가능한 메시지 |
| `retryable` | bool | 원인 해소 후 같은 요청을 재시도할 수 있다는 힌트. 즉시 재시도 성공을 보장하지 않으며, `request_id`가 있으면 같은 body와 ID를 유지 |
| `details` | object | 추가 정보. 없으면 빈 객체. `VALIDATION_ERROR`는 `errors`, `PLAN_NOT_COMPLETE`은 검증된 완료/전체 task 수만 담을 수 있다 |

PostgreSQL·Redis 인프라 예외는 응답에서 내부 메시지를 노출하지 않고 `503 SERVICE_UNAVAILABLE`, `retryable=true`로 정규화한다. 서버는 진단용으로 `error_type`, PostgreSQL `sqlstate`·`constraint_name`, HTTP method·path만 기록하며 요청 body, 사용자 대화, 프롬프트, provider 응답, raw 예외 메시지는 로그에 남기지 않는다.

---

## 2. 인증

### 토큰 종류

| 토큰 | 형식 | TTL (기본값) | 저장 |
| --- | --- | --- | --- |
| Access token | JWT (HS256) | 30분 (`ACCESS_TOKEN_EXPIRE_MINUTES`) | 클라이언트만 보관 |
| Refresh token | `{session_id}.{랜덤 secret}` 문자열 | 7일 (`REFRESH_TOKEN_EXPIRE_DAYS`) | 서버는 SHA-256 해시만 Redis에 저장 |

Access token 클레임:

| 클레임 | 설명 |
| --- | --- |
| `sub` | 사용자 UUID |
| `sid` | 세션 UUID (refresh token의 session_id와 동일) |
| `role` | `user` 또는 `admin` |
| `type` | 항상 `"access"` |
| `iat` / `exp` | 발급·만료 시각 (NumericDate). `iat`가 1분 이상 미래면 거부 |

> 현재 refresh token을 사용하는 갱신(rotate) 엔드포인트는 없다. 만료되면 다시 로그인한다.
> Logout 엔드포인트도 아직 구현하지 않았다.

### 클라이언트 인증 플로우

1. 가입이면 `POST /auth/signup`, 기존 사용자면 `POST /auth/login`을 호출한다.
2. 성공 응답의 access token을 이후 Bearer 요청에 사용한다. 로그인 응답에는 사용자 ID가 없으므로 필요하면 `GET /auth/me`를 호출한다. 보호 API는 JWT 검증 뒤 계정이 현재 존재하고 활성 상태인지 DB에서 확인한다.
3. 토큰을 저장한 직후 `POST /notifications/login-feed`를 호출해 활성 로드맵의 KST 7일 요약을 동기화·조회한다. 이 조회만으로 알림을 확인 처리하지 않는다.
4. 사용자가 명시적으로 고른 알림만 `PATCH /notifications/{notification_id}/read`로 확인 처리한다.
5. 이어서 `GET /profile`을 호출한다. 알림 feed/확인 요청이 실패해도 경고만 표시하고 이 단계는 계속하며, 알림 요청의 401만으로 방금 저장한 token을 폐기하지 않는다.
6. 프로필이 `200`이면 기존 프로필 화면으로, `404 PROFILE_NOT_FOUND`이면 온볼딩 시작으로 이동한다. 알림 외 보호 API의 401은 저장한 인증 상태를 폐기하고 로그인 화면으로 이동한다.
7. 계정 설정에서 `PATCH /auth/me`로 로그인 ID·이름을 바꾸거나 `DELETE /auth/me`로 계정을 영구 삭제할 수 있다. 삭제 성공 시 로컬 token과 사용자 캐시를 모두 폐기한다.

토큰과 비밀번호는 URL, analytics, console, 일반 로그에 기록하지 않는다. Refresh token은 응답되지만 사용할 API가 아직 없으므로 자동 갱신·서버 logout을 구현한 것처럼 처리하면 안 된다.

회원가입에서 `503`, client timeout, network error가 발생하면 DB 계정 생성만 성공했을 수 있다. 같은 회원가입을 자동 반복하지 말고 로그인 화면에서 같은 자격 증명으로 복구를 안내한다.

### 로그인 보안 정책

- 로그인 ID는 `strip().casefold()`로 정규화해 조회한다.
- 존재하지 않는 ID에 대해서도 dummy 해시 검증을 수행해 응답 시간 차이로 계정 유무를 추측하기 어렵게 한다.
- 비밀번호 5회 연속 실패 시 계정이 15분 잠긴다(`failed_login_count >= 5` → `locked_until = now + 15분`).
- 잠금·비활성 계정도 `INVALID_CREDENTIALS`로 응답한다(사유를 구분해 알려주지 않음).
- 로그인 성공 시 실패 카운터와 잠금이 초기화된다.
- Bearer 보호 요청은 서명·만료뿐 아니라 `user_accounts.is_active`도 확인하므로 삭제·비활성 계정의 기존 access token은 거부된다.

---

## 3. 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | `/auth/signup` | 불필요 | 계정 생성, 토큰 발급 (201) |
| POST | `/auth/login` | 불필요 | 로그인, 토큰 발급 |
| GET | `/auth/me` | Bearer | 현재 사용자 정보 |
| PATCH | `/auth/me` | Bearer | 현재 계정 로그인 ID·이름 부분 수정 |
| DELETE | `/auth/me` | Bearer | 현재 계정과 사용자 소유 데이터 영구 삭제 (204) |
| GET | `/profile` | Bearer | 저장된 프로필 조회 |
| POST | `/notifications/login-feed` | Bearer | 로그인 시 KST 7일 일정 알림 동기화 및 미확인 feed 조회 |
| PATCH | `/notifications/{notification_id}/read` | Bearer | 소유 알림 하나를 명시적으로 확인 처리 |
| GET | `/saved-jobs` | Bearer | 모든 인증 사용자가 공유하는 저장 공고 목록 조회 |
| GET | `/saved-jobs/recommendation` | Bearer | 온보딩 전체 프로필과 가장 가까운 유효 공고 추천 |
| POST | `/assistant/sessions` | Bearer | 완료 프로필 snapshot으로 코치 상담 시작 (201) |
| POST | `/assistant/sessions/{session_id}/messages` | Bearer | 커리어 상담, 공고 추천, 활성 로드맵 일정 조회 |
| POST | `/assistant/sessions/{session_id}/finalize` | Bearer | 구조화 보고서 저장 및 대화 원문 제거 (최초 201, replay 200) |
| POST | `/onboarding/sessions` | Bearer | 온볼딩 세션 시작 (201) |
| POST | `/onboarding/sessions/{session_id}/messages` | Bearer | 대화 답변 / review 확정·재시작 |
| GET | `/onboarding/sessions/{session_id}/result` | Bearer | 저장 전 review snapshot 조회 |
| POST | `/onboarding/sessions/{session_id}/confirm` | Bearer | review snapshot 확정 저장 |
| POST | `/plan-proposals` | Bearer | 프로필 또는 프로필+선택 공고 기반 계획 제안 생성 (201) |
| GET | `/plan-proposals/pending` | Bearer | 대기 중인 계획 제안 조회 |
| GET | `/plan-proposals/{proposal_id}` | Bearer | 계획 제안 조회 |
| POST | `/plan-proposals/{proposal_id}/accept` | Bearer | 제안 수락 및 활성 계획 생성 |
| POST | `/plan-proposals/{proposal_id}/reject` | Bearer | 제안 거절 |
| GET | `/plans/active` | Bearer | 활성 계획 조회 |
| GET | `/plans/summary` | Bearer | 모든 계획의 완료율과 계정 통합 완료율 요약 |
| GET | `/plans/{plan_id}` | Bearer | 활성/완료 계획 조회 |
| PATCH | `/plans/{plan_id}/tasks/{task_id}` | Bearer | task 상태 변경 |
| POST | `/plans/{plan_id}/complete` | Bearer | 모든 task 완료 후 계획 종료 |

---

### POST /auth/signup

`login_id`, `login_pw`, `user_name`으로 계정을 만들고 성공 즉시 access/refresh token을 발급한다. 이메일과 이메일 인증은 수집하지 않는다.

**요청**

```json
{
  "login_id": " New.User ",
  "login_pw": "password123",
  "user_name": " 홍길동 "
}
```

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `login_id` | string | trim/casefold 후 4~50자, `[a-z0-9._-]+` |
| `login_pw` | string | 공백을 보존하며 8~128자, 별도 조합 규칙 없음 |
| `user_name` | string | trim 후 1~50자 |

**응답 `201 Created`** — `SignupResult`

```json
{
  "user_id": "7f2ab98a-631b-4e23-9a66-88f368acf896",
  "login_id": "new.user",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "3fa85f64-5717-4562-b3fc-2c963f66afa6.x7q...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

서버는 Argon2 password hash만 `app.user_accounts`에 저장하며 role 등은 DB 기본값을 사용한다. Refresh secret 원문은 응답에만 포함하고 Redis에는 SHA-256 hash와 사용자 ID를 저장한다. DB 생성 후 Redis 저장이 실패하면 계정은 유지되며 응답은 503이다. 장애 복구 후 `/auth/login`으로 재진입할 수 있다.

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 409 | `LOGIN_ID_ALREADY_EXISTS` | 정규화된 로그인 ID 중복 |
| 422 | `VALIDATION_ERROR` | ID 문자·길이, 비밀번호 길이 또는 이름 길이·공백 위반 |
| 503 | `SERVICE_UNAVAILABLE` | DB/Redis 장애 (retryable) |

중복 오류의 message와 details에는 요청한 ID 값을 포함하지 않는다.

---

### POST /auth/login

로그인하고 access/refresh token을 발급받는다.

**요청**

```json
{
  "login_id": "demo.user",
  "login_pw": "비밀번호"
}
```

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `login_id` | string | 1~50자 |
| `login_pw` | string | 1~128자 |

**응답 `200 OK`** — `LoginResult`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "3fa85f64-5717-4562-b3fc-2c963f66afa6.x7q...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

| 필드 | 설명 |
| --- | --- |
| `expires_in` | access token 수명(초) |

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `INVALID_CREDENTIALS` | ID/비밀번호 불일치, 잠긴 계정, 비활성 계정 |
| 422 | `VALIDATION_ERROR` | 필드 길이 등 요청 스키마 위반 |
| 503 | `SERVICE_UNAVAILABLE` | DB/Redis 장애 (retryable) |

---

### GET /auth/me

JWT를 검증한 뒤 DB에서 해당 UUID의 활성 계정을 조회해 현재 사용자와 계정 정보를 반환한다. `role`과 `session_id`는 검증된 JWT claim을 사용하고, `login_id`와 `user_name`은 변경 사항이 즉시 반영되도록 DB 값을 사용한다.

**응답 `200 OK`** — `CurrentAccount`

```json
{
  "id": "7f2ab98a-631b-4e23-9a66-88f368acf896",
  "role": "user",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "login_id": "demo.user",
  "user_name": "홍길동"
}
```

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 헤더 없음, Bearer 스킴 아님, 토큰 만료·위조, 계정 삭제·비활성 |
| 503 | `SERVICE_UNAVAILABLE` | 계정 조회 중 DB 장애 (retryable) |

---

### PATCH /auth/me

현재 access token의 `sub` UUID로 식별한 계정의 로그인 ID 또는 사용자 이름을 부분 수정한다. UUID 기본 키, role, 비밀번호, 다른 사용자의 ID는 변경할 수 없다.

**요청**

```json
{
  "login_id": " Updated.User ",
  "user_name": " 새 이름 "
}
```

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `login_id` | string | 조건부 | trim/casefold 후 4~50자, `[a-z0-9._-]+` |
| `user_name` | string | 조건부 | trim 후 1~50자 |

- 두 필드 중 하나 이상을 보내야 한다.
- 명시적인 `null`과 정의되지 않은 필드는 `422 VALIDATION_ERROR`다.
- 로그인 ID만 또는 이름만 보낼 수 있으며 생략한 필드는 기존 값을 유지한다.

**응답 `200 OK` — `AccountSummary`**

```json
{
  "user_id": "7f2ab98a-631b-4e23-9a66-88f368acf896",
  "login_id": "updated.user",
  "user_name": "새 이름"
}
```

`user_id`는 변경되지 않는 계정 UUID다. Access/refresh token의 사용자 소유권도 UUID를 사용하므로 로그인 ID를 바꿔도 현재 세션은 유지된다. 이후 새 로그인에는 변경된 `login_id`를 사용한다.

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 또는 삭제·비활성 계정 |
| 404 | `ACCOUNT_NOT_FOUND` | 인증 확인 직후의 동시 삭제로 수정 대상이 사라짐 |
| 409 | `LOGIN_ID_ALREADY_EXISTS` | 정규화된 변경 로그인 ID 중복 |
| 422 | `VALIDATION_ERROR` | 빈 body, null, 알 수 없는 필드, 형식·길이 위반 |
| 503 | `SERVICE_UNAVAILABLE` | DB 장애 (retryable) |

---

### DELETE /auth/me

현재 access token의 `sub` UUID로 식별한 계정을 영구 삭제한다. 요청 body와 path parameter는 없다.

**응답 `204 No Content`**

응답 body가 없다. 서버는 먼저 현재 refresh 세션을 Redis에서 폐기하고, 다음 사용자 소유 데이터를 하나의 PostgreSQL 트랜잭션에서 삭제한 뒤 계정 행을 제거한다.

- 프로필
- 계획과 일정
- AI 결과
- 알림
- 날짜별 목표 달성 기록

`saved_jobs`는 모든 사용자가 공유하는 전역 공고이므로 삭제하지 않는다. 삭제 완료 뒤 Bearer 보호 API가 활성 계정 존재를 확인하므로 아직 만료되지 않은 access token도 `401 UNAUTHORIZED`로 거부된다. 클라이언트는 204를 받는 즉시 보관 중인 access/refresh token과 사용자 범위 캐시를 모두 제거해야 한다.

Redis 장애면 DB 삭제 전에 `503`으로 중단한다. Refresh 세션 폐기 뒤 DB 삭제가 실패하면 계정은 유지되지만 현재 refresh 세션은 이미 사라질 수 있으므로, 기존 access token으로 재시도하거나 다시 로그인할 수 있다.

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 또는 이미 삭제·비활성 계정 |
| 404 | `ACCOUNT_NOT_FOUND` | 인증 확인 직후의 동시 삭제로 대상이 사라짐 |
| 503 | `SERVICE_UNAVAILABLE` | Redis 또는 DB 장애 (retryable) |

---

### GET /profile

온볼딩 완료로 저장된 프로필을 조회한다. 404면 온보딩이 필요하고, 200이면 계획 제안 생성 선행 조건을 확인할 수 있다. 구현된 CLI 메인 메뉴·제안·활성 계획 사용자 흐름의 현재 계약은 [`CLI.md`](CLI.md)에서 다룬다.

**응답 `200 OK`** — `ProfileRecord`

```json
{
  "user_id": "7f2ab98a-631b-4e23-9a66-88f368acf896",
  "target_role": "백엔드 개발자",
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "experience_summary": "3년간 커머스 백엔드를 개발했습니다.",
  "target_date": "2026-12-31",
  "target_company": "네이버",
  "preferred_environment": "코드 리뷰가 활발한 팀",
  "daily_notification_time": "09:00:00",
  "assistant_style": "friendly",
  "assessment_score": 72,
  "assessment_level": "intermediate",
  "assessment_summary": {
    "disclaimer": "취업 가능성 예측이 아니라 제공된 정보의 현재 준비도 평가입니다.",
    "dimensions": {
      "skill_readiness": {"score": 22, "reason": "..."},
      "experience_depth": {"score": 21, "reason": "..."},
      "goal_clarity": {"score": 15, "reason": "..."},
      "execution_readiness": {"score": 14, "reason": "..."}
    }
  },
  "assessment_version": "onboarding-assessment-v2",
  "assessed_at": "2026-08-09T15:30:00+00:00",
  "onboarding_completed_at": "2026-08-09T15:30:00+00:00",
  "assessment_result_id": "b2c1de31-279d-4d0e-b9f1-3b5d691e3327",
  "assessment_source": {
    "provider": "google",
    "model": "gemini-3.6-flash",
    "prompt_version": "onboarding-assessment-v2",
    "rubric_version": "assessment-rubric-v2"
  },
  "draft_revision": 3,
  "snapshot_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

- 평가 관련 필드(`assessment_*`, `snapshot_hash` 등)는 저장 시점에 함께 쓰인다.

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 404 | `PROFILE_NOT_FOUND` | 저장된 프로필 없음 (온볼딩 미완료) |
| 503 | `SERVICE_UNAVAILABLE` | DB 장애 (retryable) |

---

### POST /notifications/login-feed

로그인 토큰 저장 직후 호출하는 body 없는 Bearer 요청이다. 서버는 JWT `sub`의 사용자만 대상으로 다음 작업을 한 트랜잭션에서 수행한다.

1. `plans.status='active'`인 계획의 `pending|in_progress` 일정을 KST 오늘부터 오늘+6일까지 조회한다.
2. 계획·날짜별로 `daily_tasks:{plan_id}:{YYYY-MM-DD}` 요약을 동기화한다. payload가 같으면 기존 확인 상태를 보존하고, payload가 달라졌거나 무효화된 요약이 다시 유효해지면 미확인으로 다시 연다. 범위에서 사라진 요약은 삭제하거나 읽음 처리하지 않고 `invalidated_at`을 기록한다.
3. 현재 사용자의 `is_read=false`, `invalidated_at is null`, `available_at <= now()` 알림만 반환한다.

요청 body와 `user_id` query/body 필드는 없다.

```http
POST /api/v1/notifications/login-feed
Authorization: Bearer <access_token>
```

**응답 `200 OK` — `NotificationFeed`**

```json
{
  "window_start": "2026-08-11",
  "window_end": "2026-08-17",
  "upcoming": [
    {
      "id": "92000000-0000-0000-0000-000000000001",
      "type": "daily_tasks",
      "title": "8월 11일 로드맵 일정",
      "message": "백엔드 로드맵: API 테스트 작성",
      "plan_id": "60000000-0000-0000-0000-000000000001",
      "schedule_item_id": null,
      "available_at": "2026-08-11T00:00:00Z",
      "is_read": false,
      "read_at": null,
      "payload": {
        "version": "daily_tasks.v1",
        "date": "2026-08-11",
        "plan_title": "백엔드 로드맵",
        "count": 1,
        "schedules": [
          {
            "id": "70000000-0000-0000-0000-000000000001",
            "kind": "task",
            "title": "API 테스트 작성",
            "scheduled_at": "2026-08-11T01:00:00Z",
            "status": "pending"
          }
        ]
      }
    }
  ],
  "changes": [
    {
      "id": "92000000-0000-0000-0000-000000000002",
      "type": "roadmap_changed",
      "title": "로드맵 일정이 변경되었습니다",
      "message": "API 테스트 보완",
      "plan_id": "60000000-0000-0000-0000-000000000001",
      "schedule_item_id": "70000000-0000-0000-0000-000000000001",
      "available_at": "2026-08-11T00:30:00Z",
      "is_read": false,
      "read_at": null,
      "payload": {
        "version": "roadmap_change.v1",
        "target": "schedule",
        "change_kind": "update",
        "affected_count": 1,
        "plan_id": "60000000-0000-0000-0000-000000000001",
        "schedule_ids": ["70000000-0000-0000-0000-000000000001"],
        "before": {
          "id": "70000000-0000-0000-0000-000000000001",
          "title": "API 테스트 작성",
          "status": "pending",
          "scheduled_at": "2026-08-11T01:00:00Z",
          "starts_on": null,
          "ends_on": null,
          "total_task_count": null
        },
        "after": {
          "id": "70000000-0000-0000-0000-000000000001",
          "title": "API 테스트 보완",
          "status": "pending",
          "scheduled_at": "2026-08-11T02:00:00Z",
          "starts_on": null,
          "ends_on": null,
          "total_task_count": null
        }
      }
    }
  ],
  "unread_count": 2
}
```

- `window_start`, `window_end`: KST 오늘과 오늘+6일. 양 끝을 포함한다.
- `upcoming`: `daily_tasks`만 날짜 오름차순, 최대 7건.
- `changes`: `daily_tasks`가 아닌 알림을 `available_at` 최신순, 최대 50건.
- `unread_count`: 두 배열의 상한을 적용하기 전 조건에 맞는 전체 미확인 알림 수다. 둘 중 하나가 상한(7/50)에 도달했을 때만 `upcoming.length + changes.length`보다 클 수 있고, 두 배열 모두 상한 미만이면 배열 길이의 합과 같다.
- feed 조회는 `is_read/read_at`을 변경하지 않는다.

`NotificationView`의 공통 필드는 다음과 같다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID | 알림 ID |
| `type` | enum | `daily_tasks`, `roadmap_changed`, `plan_ended`, 호환용 `interview_reminder`, `check_in` |
| `title`, `message` | string | 서버가 검증된 payload로 생성한 표시 문구 |
| `plan_id` | UUID \| null | 관련 계획. 삭제 이벤트는 payload의 원래 ID로 보완될 수 있음 |
| `schedule_item_id` | UUID \| null | 단일 일정 변경이면 관련 일정 ID |
| `available_at` | timestamp | feed 노출 가능 시각 |
| `is_read`, `read_at` | bool, timestamp \| null | 반드시 서로 일치하는 확인 상태 |
| `payload` | versioned object | 아래 타입 중 하나 |

버전된 payload 계약:

| version | 핵심 필드 | 설명 |
| --- | --- | --- |
| `daily_tasks.v1` | `date`, `plan_title`, `count`, `schedules[]`, 선택적 `plan_id` | 일정 원소는 `id`, `kind`(`milestone|task|interview`), `title`, `scheduled_at`, `status`(`pending|in_progress`). 계획 삭제로 FK가 비워질 때 원래 ID가 `plan_id`에 보존된다. |
| `roadmap_change.v1` | `target`, `change_kind`, `affected_count`, `plan_id`, `schedule_ids`, `before`, `after` | target은 `plan|schedule`, change_kind는 `activation|insert|update|delete`. 단일 변경의 before/after는 `id/title/status`와 선택 시각·기간·task 수를 담고, 대량 변경은 null일 수 있음 |
| `plan_ended.v1` | `ended_status`, `final_progress`, `plan_id`, `plan_title` | 종료 상태는 `draft|rejected|completed|expired|superseded|deleted`, 진행률은 0~100 |
| `legacy.v1` | `data` | 기존 `interview_reminder`, `check_in` payload 호환 래퍼 |

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 500 | `NOTIFICATION_DATA_INTEGRITY_ERROR` | 저장된 payload가 공개 모델과 불일치 |
| 503 | `SERVICE_UNAVAILABLE` | DB 장애 (retryable) |

### PATCH /notifications/{notification_id}/read

현재 사용자 소유 알림 하나만 확인 처리한다. body와 `user_id`는 보내지 않는다.

```http
PATCH /api/v1/notifications/92000000-0000-0000-0000-000000000001/read
Authorization: Bearer <access_token>
```

성공하면 위 `NotificationView` 한 건을 반환하며 `is_read=true`, `read_at=<최초 확인 시각>`이다. 같은 알림을 재호출해도 기존 `read_at`을 보존하므로 응답은 멱등적이다. 조회·feed 호출만으로는 이 상태가 바뀌지 않는다.

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 404 | `NOTIFICATION_NOT_FOUND` | ID가 없거나 다른 사용자 소유. 소유 여부를 구분해 노출하지 않음 |
| 422 | `VALIDATION_ERROR` | path가 UUID 형식이 아님 |
| 500 | `NOTIFICATION_DATA_INTEGRITY_ERROR` | 저장된 payload가 공개 모델과 불일치 |
| 503 | `SERVICE_UNAVAILABLE` | DB 장애 (retryable) |

fresh bootstrap은 `sql/07_notifications.sql`에 최종 스키마를 포함한다. 기존 DB에는 관리자 migration role로 `sql/22_notifications_login_roadmap.sql`을 명시적으로 적용한다. migration 22는 재실행 가능하며 `is_read/invalidated_at`, 읽음 일관성 CHECK, partial index, 계획·statement-level 일정 trigger, KST 로그인 동기화 함수를 추가한다. `supabase db push`를 전제로 하지 않는다.

---

### GET /saved-jobs

`saved_jobs`에 등록된 전체 공고를 envelope 없는 JSON 배열로 반환한다. Bearer token은 인증에만 사용하며 사용자 ID로 결과를 필터링하지 않는다. 결과는 `created_at DESC`, `id DESC` 순서로 정렬하고, 저장 공고가 없으면 `200 OK`와 빈 배열 `[]`을 반환한다. v1은 pagination과 상세 전용 endpoint를 제공하지 않는다.

**응답 `200 OK` — `SavedJobView[]`**

```json
[
  {
    "id": "30000000-0000-0000-0000-000000000001",
    "source_type": "url",
    "source_url": "https://example.com/jobs/backend",
    "source_key": "example-backend-2026",
    "company_name": "예시회사",
    "job_title": "백엔드 개발자",
    "deadline": "2026-08-31",
    "posting_text": "Python과 FastAPI 경험자를 찾습니다.",
    "extracted_data": {
      "skills": ["Python", "FastAPI"]
    },
    "created_at": "2026-08-10T18:00:00+09:00",
    "updated_at": "2026-08-10T18:00:00+09:00"
  }
]
```

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `id` | UUID | 저장 공고 ID |
| `source_type` | `url` \| `pasted_text` | 공고 입력 출처 |
| `source_url` | string \| null | URL 출처일 때 원본 URL |
| `source_key` | string | 전체 공고 중복 등록 방지 키 |
| `company_name` | string | 회사명 |
| `job_title` | string | 공고 직무명 |
| `deadline` | date \| null | 지원 마감일 |
| `posting_text` | string | 저장된 공고 원문 |
| `extracted_data` | object | 공고에서 추출한 구조화 데이터 |
| `created_at` | datetime | 저장 시각 |
| `updated_at` | datetime | 최종 수정 시각 |

| HTTP | code | 조건 |
| ---: | --- | --- |
| 401 | `UNAUTHORIZED` | Bearer token 누락·만료·검증 실패 |
| 503 | `SERVICE_UNAVAILABLE` | PostgreSQL 조회 실패 |

### GET /saved-jobs/recommendation

현재 사용자의 완료된 온보딩 전체 프로필과 전체 공유 공고 중 마감일이 지나지 않았거나 마감일이 미정인 공고를 Gemini가 비교해 가장 적합한 한 건을 반환한다. 목표 직무, 기술, 경험, 목표일, 희망 기업, 희망 환경, 알림 시각과 assistant style을 모두 전달하며 공고와 프로필 문자열은 지시가 아닌 비신뢰 데이터로 취급한다.

후보는 40건 단위로 병렬 심사하고 각 묶음의 우승 공고가 둘 이상이면 결선 심사를 한 번 더 수행한다. 서버는 Gemini가 반환한 ID가 해당 심사의 후보인지 확인하고 응답에는 DB 원본 공고만 사용한다. `match_score`는 전체 프로필 적합도 0~100이며 `matched_terms`와 `reason`은 제공된 프로필과 공고에 근거해야 한다.

Gemini timeout, rate limit, provider 오류 또는 구조화 응답 검증 실패가 발생하면 기존 희망 환경 키워드 포함률 방식으로 대체한다. `recommendation_source`가 `llm`이면 Gemini 판단, `keyword_fallback`이면 대체 결과다. 대체 결과는 provider 오류를 노출하지 않는다. 유효 후보 공고가 없으면 Gemini를 호출하지 않고 `200 OK`와 `null`을 반환한다.

**응답 `200 OK` — `SavedJobRecommendationView | null`**

```json
{
  "preferred_environment": "원격 근무와 코드 리뷰",
  "match_score": 94,
  "matched_terms": ["희망 직무", "Python", "원격 근무"],
  "recommendation_source": "llm",
  "reason": "희망 직무와 기술, 근무 환경이 모두 잘 맞습니다.",
  "job": {
    "id": "30000000-0000-0000-0000-000000000001",
    "source_type": "url",
    "source_url": "https://example.com/jobs/backend",
    "source_key": "example-backend-2026",
    "company_name": "예시회사",
    "job_title": "백엔드 개발자",
    "deadline": "2026-08-31",
    "posting_text": "원격 근무와 코드 리뷰를 지원합니다.",
    "extracted_data": {"location": "원격"},
    "created_at": "2026-08-10T18:00:00+09:00",
    "updated_at": "2026-08-10T18:00:00+09:00"
  }
}
```

| HTTP | code | 조건 |
| ---: | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 404 | `PROFILE_NOT_FOUND` | 완료된 온보딩 프로필 없음 |
| 503 | `SERVICE_UNAVAILABLE` | DB 장애 |

---

### AI 취업 코치 상담

완료된 프로필의 커리어 필드, 준비도 평가, `snapshot_hash`, `assessment_result_id`, `assistant_style`을 세션 시작 시 고정해 취업·커리어 상담에 사용한다. 상담 중 프로필을 바꿔도 기존 세션에는 섞지 않고 다음 세션부터 적용한다.

`friendly`는 공감→근거→행동 제안 순서로 답한다. `direct`는 거친 반말·한국 인터넷 말투와 가벼운 비속어를 허용한 로스트→냉정한 근거→즉시 행동 순서로 답한다. `direct`도 사용자의 준비 상태와 행동만 지적하며 차별, 외모·정체성·속성 공격, 위협, 결과 보장은 금지한다.

#### 프론트엔드 호출 순서

```text
POST /assistant/sessions
  → session_id, revision=0, expires_at 보관
  → POST /assistant/sessions/{session_id}/messages 반복
      매 요청: 현재 revision을 expected_revision으로 전송
      성공: 응답 revision으로 교체
  → POST /assistant/sessions/{session_id}/finalize
      최초 저장 201 또는 durable replay 200 모두 성공 처리
```

- “상담 종료”는 현재 세션을 `finalize`한다. “새 대화”는 `finalize` 성공 후 `POST /assistant/sessions`를 새 `request_id`로 호출한다.
- 논리 요청마다 새 `request_id`를 사용한다. timeout·network error 재시도에서만 같은 ID와 완전히 같은 payload를 재사용한다.
- 동일 `request_id`와 동일 payload는 최초 응답을 재생한다. 동일 ID의 payload·operation·session이 달라지면 `409 IDEMPOTENCY_KEY_REUSED`다.
- 성공한 사용자 메시지만 revision을 1 증가시킨다. stale `expected_revision`은 `409 ASSISTANT_REVISION_CONFLICT`이며 서버 상태를 바꾸지 않는다.
- 세션 없음, 만료, 다른 사용자의 session ID는 정보 노출 없이 모두 `409 ASSISTANT_SESSION_EXPIRED`다.
- 세션 원문과 멱등 데이터의 절대 보관 상한은 생성 시점부터 정확히 24시간이며 활동으로 연장되지 않는다. 활성 세션은 생성 또는 마지막 사용자 입력 접수 후 정확히 120초에 종료되고 활성 개수에서 제외된다. 사용자당 활성 세션은 최대 6개다.
- 유효한 메시지는 Gemini 처리 전에 Redis에서 원자적으로 접수되어 120초 유휴 기한을 갱신한다. 이미 접수된 요청은 처리 중 유휴 기한이 지나도 결과를 저장할 수 있지만 다음 새 요청은 `409 ASSISTANT_SESSION_EXPIRED`다. 완료된 동일 요청의 replay는 기존 멱등성 계약에 따라 원응답을 반환한다.
- 활성 인덱스는 유휴 점수 전용 `assistant:v2:*:active`를 사용한다. 배포 시 절대 만료 점수를 쓰는 구버전 인스턴스를 먼저 drain·중지하고 신버전만 트래픽을 받게 하며, 두 버전을 동시에 서비스하지 않는다.
- 한 세션의 성공한 사용자 턴은 최대 20개, 사용자 text는 턴당 1~4,000자, 사용자·assistant 대화 누계는 40,000자, assistant 자연어는 턴당 최대 12,000자다.

일반 질문은 첫 Gemini structured 호출의 답변을 사용한다. 공고·일정 질문은 같은 호출에서 허용된 intent와 일정 기간 인자만 결정하고, 서버가 DB 도구를 종류별 최대 한 번 실행한 뒤 두 번째 Gemini 호출로 코칭 문장만 만든다. 모델은 SQL, 사용자 ID, 임의 도구를 지정할 수 없다.

DB 사실은 `tool_results`와 `assistant_message`의 canonical fact block으로 서버가 렌더링한다. Gemini가 회사명·직무·마감일·일정 시각을 다르게 서술해도 사용하지 않는다. DB 조회 실패는 추측 없이 `503 SERVICE_UNAVAILABLE`이고, DB 조회 후 코칭 호출만 실패하면 정확한 `tool_results`와 스타일별 deterministic fallback을 `200 OK`로 반환한다.

#### POST /assistant/sessions

완료 프로필 snapshot과 24시간 절대 보관 만료 시각을 가진 상담을 시작한다. 첫 사용자 입력이 없으면 생성 120초 후 활성 상태가 종료된다.

**요청**

```json
{
  "request_id": "4ac80bf6-e52d-49d7-b92c-1a5a5a43463a"
}
```

**응답 `201 Created` — `AssistantSessionCreateResponse`**

```json
{
  "session_id": "f9e908ea-fbce-4212-a7fd-39748464d0f7",
  "revision": 0,
  "assistant_style": "friendly",
  "assistant_message": "반가워요. 지금 가장 답답한 취업·커리어 고민부터 편하게 이야기해주세요.",
  "expires_at": "2026-08-12T10:00:00+09:00"
}
```

동일 요청 replay도 `201`이다. 완료 프로필이 없으면 `404 PROFILE_NOT_FOUND`, 활성 세션이 이미 6개면 `409 ASSISTANT_SESSION_LIMIT_REACHED`다.

#### POST /assistant/sessions/{session_id}/messages

**요청**

```json
{
  "request_id": "af419f9d-9658-4515-aec8-827d0cac9242",
  "expected_revision": 0,
  "text": "내일 해야 할 일정과 지금 지원할 공고를 같이 알려줘"
}
```

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `request_id` | UUID | 논리 메시지별 멱등성 키 |
| `expected_revision` | integer | 0 이상, 마지막 성공 응답의 `revision` |
| `text` | string | 1~4,000자, 앞뒤 공백도 fingerprint에 포함 |

**응답 `200 OK` — `AssistantMessageResponse`**

```json
{
  "session_id": "f9e908ea-fbce-4212-a7fd-39748464d0f7",
  "revision": 1,
  "intent": "mixed",
  "assistant_message": "[공고 추천 사실]\n회사: 예시회사\n직무: 백엔드 개발자\n마감일: 2026-08-31\n...\n\n[일정 조회 사실]\n조회 기간: 2026-08-12 ~ 2026-08-12 (KST)\n...\n\n오늘 지원서 초안을 끝내고 내일 일정을 바로 진행해보세요.",
  "tool_results": [
    {
      "type": "job_recommendation",
      "status": "found",
      "observed_at": "2026-08-11T10:01:00+09:00",
      "job": {
        "id": "30000000-0000-0000-0000-000000000001",
        "company_name": "예시회사",
        "job_title": "백엔드 개발자",
        "source_url": "https://example.com/jobs/backend",
        "deadline": "2026-08-31",
        "created_at": "2026-08-10T18:00:00+09:00",
        "updated_at": "2026-08-10T18:00:00+09:00"
      },
      "match_score": 88,
      "matched_terms": ["Python", "백엔드"],
      "reason": "목표 직무와 핵심 기술이 일치합니다.",
      "recommendation_source": "keyword_fallback"
    },
    {
      "type": "schedule_lookup",
      "status": "found",
      "observed_at": "2026-08-11T10:01:00+09:00",
      "range_start": "2026-08-12",
      "range_end": "2026-08-12",
      "timezone": "Asia/Seoul",
      "plan_id": "1bd9a6e7-96c9-49e7-9597-f461577b9a7d",
      "plan_title": "백엔드 취업 로드맵",
      "items": [
        {
          "id": "7802ddec-2965-4a46-9867-b4b71a8ffddb",
          "kind": "task",
          "title": "이력서 성과 문장 수정",
          "description": null,
          "status": "pending",
          "scheduled_at": "2026-08-12T09:00:00+09:00",
          "plan_day": 2,
          "slot": 1
        }
      ]
    }
  ],
  "coaching": {
    "style": "friendly",
    "message": "오늘 지원서 초안을 끝내고 내일 일정을 바로 진행해보세요.",
    "source": "llm"
  },
  "expires_at": "2026-08-12T10:00:00+09:00"
}
```

`intent`는 `general`, `job_recommendation`, `schedule_lookup`, `mixed`, `clarification`, `out_of_scope` 중 하나다. 결과 없음, 모호한 날짜, 28일 초과 범위, 주제 이탈은 오류가 아니며 `200`으로 안내한다.

**`job_recommendation` tool result**

- KST 오늘보다 마감일이 지난 공고는 제외한다. 오늘 마감과 마감일 미정 공고는 후보에 포함한다.
- `job`은 DB의 공개 사실만 제공하며 `posting_text`, `extracted_data`는 코치 응답에 포함하지 않는다.
- `match_score`, `matched_terms`, `reason`, `recommendation_source`는 추천 판단이다. 현재 코치 오케스트레이션은 Gemini structured 호출 수를 두 단계로 제한하기 위해 기존 추천 알고리즘의 `keyword_fallback` 경로를 사용한다.
- 유효 공고가 없으면 `status="no_eligible_jobs"`, `job/match_score/reason/recommendation_source=null`, `matched_terms=[]`다.

**`schedule_lookup` tool result**

- 활성 로드맵의 `milestone|task`만 조회하고 `interview|cancelled`는 제외한다. 모든 조회는 JWT 사용자와 plan ID를 함께 조건으로 사용한다.
- KST 기준 `오늘`, `내일`, `이번 주(월~일)`, `다음 주`, 양 끝 포함 명시 범위를 지원한다. 명시 범위는 최대 28일이다.
- 모호하거나 28일을 넘는 범위는 추측하지 않고 `intent="clarification"`으로 기간을 다시 묻는다.
- 상태는 `found`, `empty`, `no_active_plan`이다. 일정은 시각, plan day, slot, ID 순으로 안정적으로 정렬한다.

#### POST /assistant/sessions/{session_id}/finalize

사용자 턴이 하나 이상인 상담을 구조화 보고서로 저장하고 Redis 대화 원문을 `report_id/revision`만 남긴 tombstone으로 교체한다.

**요청**

```json
{
  "request_id": "f29b8766-534d-42de-a5e9-f43521ddd2fc",
  "expected_revision": 1
}
```

**응답 — 최초 `201 Created`, 기존 보고서 durable replay `200 OK`**

```json
{
  "ai_result_id": "e6bb5226-d8aa-4ff9-9451-e1505864337e",
  "session_id": "f9e908ea-fbce-4212-a7fd-39748464d0f7",
  "session_revision": 1,
  "report": {
    "schema_version": "career-coach-report-v1",
    "status": "completed",
    "session_id": "f9e908ea-fbce-4212-a7fd-39748464d0f7",
    "session_revision": 1,
    "started_at_kst": "2026-08-11T10:00:00+09:00",
    "finalized_at_kst": "2026-08-11T10:05:00+09:00",
    "user_turn_count": 1,
    "profile_snapshot": {
      "target_role": "백엔드 개발자",
      "skills": ["Python"],
      "experience_summary": "API 개발 경험",
      "target_date": "2026-12-31",
      "target_company": null,
      "preferred_environment": "원격 근무",
      "daily_notification_time": "09:00:00",
      "assistant_style": "friendly"
    },
    "assessment_snapshot": {"score": 72, "level": "intermediate", "summary": {}, "version": "profile-assessment-v1"},
    "profile_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "assessment_result_id": "eeae1642-7a99-4270-bd5f-f077a927895b",
    "assistant_style": "friendly",
    "summary": "지원 준비의 우선순위와 다음 행동을 정리했습니다.",
    "strengths": ["목표 직무가 구체적입니다."],
    "improvements": ["지원서 성과 근거를 보강해야 합니다."],
    "priority_actions": ["오늘 이력서 성과 문장 한 개를 수치화합니다."],
    "evidence": [],
    "tool_snapshots": [],
    "excluded_tool_call_count": 0,
    "excluded_tool_calls_hash": null,
    "engine": {
      "provider": "google",
      "model": "gemini-3.6-flash",
      "prompt_version": "career-coach-report-v1",
      "schema_version": "career-coach-report-draft-v1"
    },
    "redaction_version": "career-coach-redaction-v1",
    "source_session_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "report_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  },
  "created_at": "2026-08-11T10:05:00+09:00"
}
```

- 보고서는 `app.ai_results.kind="career_coach_report"`, `decision_status="not_applicable"`이며 `saved_job_id`, `applied_plan_id`, `decided_at`은 `NULL`이다.
- 서술은 중립 요약, 강점·보완점 각 최대 5개, 우선순위 행동 1~7개다. 사용자 근거는 최대 8개이며 `{turn_id, quote, category, redacted}`, quote는 실제 사용자 발화의 부분 문자열이자 최대 200자다.
- 참조 tool snapshot은 최대 5개다. 공고는 공개 사실과 `posting_hash`만 보존하고 일정은 조회 당시 canonical snapshot을 보존한다. 제외한 호출은 count와 hash로 추적한다.
- 전체 보고서는 canonical JSONB 기준 128KiB 이하다. transcript, messages, assistant_message, raw provider response/prompt, posting_text, extracted_data, tool_results 키는 중첩 위치에서도 금지된다.
- DB commit이 실패하면 Redis 원문 세션을 유지한다. commit 후 Redis 정리만 실패해도 저장된 보고서를 성공 반환하고, 재시도는 DB에서 복구해 Gemini를 다시 호출하지 않는다.
- timeout, network error 또는 DB/Redis `503`에서는 클라이언트가 revision을 증가시키지 않고 동일한 `request_id`, `expected_revision`, payload로 재시도한다. 이미 DB commit이 끝난 요청이면 request/session durable replay가 같은 전체 보고서를 반환한다.
- 사용자 메시지가 없으면 `409 ASSISTANT_REPORT_EMPTY`다. 종료된 세션의 새 메시지는 `409 ASSISTANT_ALREADY_FINALIZED`다. 만료된 미종료 상담은 보고서를 자동 생성하지 않는다.
- `finalize`는 보고서 DB 저장 직전에 활성 상태를 다시 검증한다. 유휴 기한 전에 이 검증을 통과한 종료 요청은 durable 저장 중 기한이 지나더라도 완료되며, 이후 Redis 정리는 best-effort로 처리한다.
- 보고서 조회/list API는 제공하지 않는다. finalize 응답과 동일 요청 또는 동일 세션의 durable replay만 지원한다.

**DB 배포 계약**

- fresh bootstrap은 `sql/06_ai_results.sql`의 수정된 보고서 CHECK를 사용한다.
- 기존 DB는 migration role로 `19_career_coach_report.sql` → `20_private_app_schema.sql` → `21_career_coach_report_forbidden_key_check.sql` 순서로 적용한다. 공유 runtime role `app_api`로 migration을 실행하면 거부된다.
- migration 21은 PostgreSQL 17에서 객체가 아닌 JSON 노드까지 `keyvalue()`를 적용해 정상 보고서가 `NULL` 판정으로 거부되던 문제를 수정한다. 내용 CHECK만 drop/recreate/validate하며 보고서 unique index, UPDATE 방지 trigger, runtime 권한은 유지한다.
- `TP_dev`에는 `20260811054026_career_coach_report_forbidden_key_check`가 적용되어 있고 `ai_results_career_coach_report_content_check`는 `VALIDATED` 상태로 확인됐다.

---

### 온볼딩 서비스 플로우

#### 온볼딩 상태 전이와 호출 순서

```text
인증 성공
  → GET /profile
    ├─ 200: 기존 프로필 사용
    └─ 404 PROFILE_NOT_FOUND
         → POST /onboarding/sessions
         → conversation: text 전송 반복
         → review: 자연어 수정 또는 restart
           ├─ 자연어 수정: review 유지, 변경 시 revision +1 및 재평가
           ├─ restart: 같은 session_id로 conversation 초기화
           └─ GET /result: 서버 review snapshot 조회
                → POST /confirm: completed 응답
                → GET /profile: 영속 저장 결과 재조회
```

- `conversation`의 `draft_profile`은 일부 필드만 가진 객체일 수 있다. 화면은 `answered_fields`와 `missing_fields`를 기준으로 진행률을 표시한다.
- 8개 필드가 모두 채워지면 서버가 평가를 생성한 뒤 `review`로 전이한다. 이 시점까지 PostgreSQL에는 저장하지 않는다.
- `review`에서도 `text`로 자연어 수정을 보낼 수 있다. 실제 필드 변경이 있으면 `draft_revision`이 증가하고 평가가 다시 생성된다.
- `onboarding.restart`는 Gemini 첫 질문 생성에 성공한 뒤에만 draft와 대화를 초기화하며 `session_id`는 유지한다.
- 저장 직전 `GET /result`로 서버의 review snapshot을 읽고, 그 응답의 `draft_revision`을 `POST /confirm`에 보낸다. 저장 성공 후에는 새 confirm을 보내지 말고 `GET /profile`로 영속 결과를 확인한다.
- 기존 `POST /messages`의 `action="onboarding.confirm"`도 하위 호환으로 유지한다. 신규/기존 confirm은 같은 멱등 fingerprint와 응답 cache를 공유한다.
- `GET /result`는 review 단계 전용이며 transcript나 conversation 진행 상태를 반환하지 않는다. 따라서 conversation 중 새로고침 복구/resume API로 사용하면 안 된다.

#### request_id와 안전한 재시도

- 각 논리 요청마다 새 UUID를 만들고, 한 세션의 start/message/edit/confirm/restart 사이에서 재사용하지 않는다.
- timeout·network error 또는 `retryable=true` 오류를 재시도할 때만 **같은 `request_id`와 같은 필드 값**을 유지한다. JSON property 순서는 무관하지만 `text`의 앞뒤 공백을 포함한 문자열 값은 바꾸지 않는다.
- 같은 ID와 같은 payload는 캐시된 응답을 반환한다. 같은 ID에 text/action/revision 중 하나라도 다른 값을 보내면 `IDEMPOTENCY_KEY_REUSED`다.
- Confirm 응답을 받지 못했더라도 동일 request로 재시도할 수 있다. 전용 `/confirm`과 기존 `/messages` confirm 사이에서도 같은 `request_id`와 revision이면 같은 completed 응답을 반환하고 DB 저장을 반복하지 않는다. Confirm 성공 응답을 받은 뒤 profile 조회만 실패했다면 confirm하지 말고 `GET /profile`만 다시 호출한다.
- Gemini 호출 실패 전에는 transcript와 revision을 저장하지 않는다. 재시도 가능한 provider 오류에서 사용자가 입력한 text를 임의로 바꾸지 않는다.

#### 세션 수명

- 기본 TTL은 30분이다. 성공한 message/edit/confirm/restart가 저장될 때 세션 TTL이 다시 설정된다.
- `GET /result`는 Redis 상태를 저장하지 않으며 TTL을 갱신하지 않는다.
- 실패한 provider 요청은 상태를 저장하지 않으므로 TTL도 갱신하지 않는다.
- 세션이 만료되거나 access token 사용자와 세션 소유자가 다르면 동일하게 `ONBOARDING_SESSION_EXPIRED`로 응답한다.

---

### POST /onboarding/sessions

온볼딩 세션을 시작하고 Gemini가 생성한 첫 질문을 받는다. 세션 상태는 Redis에 저장되며 TTL은 30분(`ONBOARDING_SESSION_TTL_SECONDS`)이다.

**요청**

```json
{
  "request_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `request_id` | UUID | 멱등성 키. 같은 ID로 재요청하면 첫 응답을 그대로 반환 |

**응답 `201 Created`** — `OnboardingResponse` (아래 [공통 응답 구조](#온볼딩-공통-응답-구조-onboardingresponse) 참조)

```json
{
  "session_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
  "flow": "onboarding",
  "step": "conversation",
  "assistant_message": "안녕하세요! 어떤 직무를 준비하고 계신가요?",
  "choices": [],
  "payload": {
    "draft_revision": 0,
    "draft_profile": {},
    "answered_fields": [],
    "missing_fields": ["target_role", "skills", "experience_summary", "target_date", "target_company", "preferred_environment", "daily_notification_time", "assistant_style"],
    "assessment": null,
    "engine": {
      "provider": "google",
      "model": "gemini-3.6-flash",
      "api_version": "v1",
      "mode": "live",
      "conversation_prompt_version": "onboarding-conversation-v1",
      "assessment_prompt_version": "onboarding-assessment-v2"
    },
    "stored_profile": null
  },
  "completed": false
}
```

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 409 | `ONBOARDING_REQUEST_IN_PROGRESS` | 같은 사용자의 동일한 시작 `request_id`가 동시에 처리 중(잠금, retryable) |
| 422 | `VALIDATION_ERROR` | `request_id` 누락 또는 UUID 형식 오류 |
| 422 | `GEMINI_CONTENT_BLOCKED` | Gemini 콘텐츠 차단 |
| 429 | `GEMINI_RATE_LIMITED` | 사용자별 Gemini 호출 제한 초과 (retryable) |
| 502 | `GEMINI_UNAVAILABLE` / `GEMINI_CONFIGURATION_ERROR` / `GEMINI_INVALID_RESPONSE` | Gemini 호출 실패 |
| 503 | `SERVICE_UNAVAILABLE` | Redis 장애 (retryable) |

---

### POST /onboarding/sessions/{session_id}/messages

온볼딩의 모든 후속 상호작용을 처리한다. `text`(자유 답변)와 `action`(확정/재시작) 중 정확히 하나만 보내야 한다.

**요청 — 자유 답변**

```json
{
  "request_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "text": "백엔드 개발자가 목표고, Python과 FastAPI를 3년 썼습니다. 12월 31일까지 이직하고 싶어요."
}
```

**요청 — review 확정**

```json
{
  "request_id": "c9bf9e57-1685-4c89-bafb-ff5af3641a5b",
  "action": "onboarding.confirm",
  "expected_revision": 3
}
```

**요청 — 처음부터 다시**

```json
{
  "request_id": "54a3f7c2-3f5e-4d1e-9c8b-0a1b2c3d4e5f",
  "action": "onboarding.restart"
}
```

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `request_id` | UUID | 필수. 멱등성 키 |
| `text` | string \| null | 요청 schema 최대 4,000자. 서비스에서 trim 후 1자 이상이어야 하며 `action`과 동시 사용 불가 |
| `action` | string \| null | 최대 100자. 유효값은 `onboarding.confirm` 또는 `onboarding.restart`; `text`와 동시 사용 불가 |
| `expected_revision` | int \| null | `onboarding.confirm`에만 필수. CLI 출력에 표시된 `draft_revision`과 일치해야 함 |

**응답 `200 OK`** — `OnboardingResponse`

step별 응답 차이:

| `step` | 조건 | `choices` | `payload.assessment` | `payload.stored_profile` |
| --- | --- | --- | --- | --- |
| `conversation` | 아직 빈 필드가 있음 | `[]` | `null` | `null` |
| `review` | 8개 필드가 모두 채워짐 | `["onboarding.confirm", "onboarding.restart"]` | 평가 결과 존재 | `null` |
| `completed` | confirm으로 DB 저장 완료 | `[]` | 평가 결과 | 저장된 `ProfileRecord` |

confirm 성공 응답 예시(일부 생략):

```json
{
  "session_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
  "step": "completed",
  "assistant_message": "확인한 프로필과 준비도 평가를 저장했습니다.",
  "choices": [],
  "payload": {
    "draft_revision": 3,
    "draft_profile": { "...": "8개 필드 전체" },
    "answered_fields": ["target_role", "..."],
    "missing_fields": [],
    "assessment": {
      "score": 72,
      "level": "intermediate",
      "summary": { "disclaimer": "...", "dimensions": { "...": "..." } },
      "version": "onboarding-assessment-v2",
      "model_name": "gemini-3.6-flash",
      "provider": "google",
      "prompt_version": "onboarding-assessment-v2",
      "rubric_version": "assessment-rubric-v2",
      "schema_version": "profile-assessment-v1"
    },
    "stored_profile": { "assessment_result_id": "...", "snapshot_hash": "...", "...": "ProfileRecord" }
  },
  "completed": true
}
```

**에러**

| 상태 | code | 발생 조건 | retryable |
| --- | --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 | - |
| 409 | `ONBOARDING_SESSION_EXPIRED` | 세션 없음(TTL 만료) 또는 다른 사용자의 세션 | - |
| 409 | `ONBOARDING_REQUEST_IN_PROGRESS` | 같은 세션의 이전 요청 처리 중(잠금) | ✅ |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 같은 `request_id`에 다른 payload를 담아 재요청 | - |
| 409 | `ONBOARDING_REVISION_CONFLICT` | confirm의 `expected_revision`이 현재와 다름 | - |
| 409 | `ONBOARDING_SNAPSHOT_CONFLICT` | 같은 `request_id`로 다른 snapshot이 이미 저장됨(DB) | - |
| 422 | `VALIDATION_ERROR` | UUID/path 형식, text/action 동시·누락, text/action 최대 길이, confirm revision 누락, 음수 revision 등 요청 schema 위반 | - |
| 422 | `ONBOARDING_VALIDATION_ERROR` | 빈/공백 text, 지원하지 않는 action, review 전 confirm, 완료 세션의 새 요청, 사용자 발화 12개 초과 | - |
| 422 | `GEMINI_CONTENT_BLOCKED` | Gemini 안전 필터 차단 | - |
| 429 | `GEMINI_RATE_LIMITED` | 사용자별 Gemini 호출 제한 | ✅ |
| 502 | `GEMINI_UNAVAILABLE` | Gemini 일시 장애/타임아웃 | ✅ |
| 502 | `GEMINI_CONFIGURATION_ERROR` | API 키·모델 설정 오류 | - |
| 502 | `GEMINI_INVALID_RESPONSE` | Gemini 응답이 스키마/근거 검증 실패 (repair 후에도) | - |
| 503 | `SERVICE_UNAVAILABLE` | DB/Redis 장애 | ✅ |

---

### GET /onboarding/sessions/{session_id}/result

현재 access token 사용자가 소유한 세션의 서버 review snapshot을 조회한다. 응답에는 draft, revision, assessment와 engine 정보가 포함되며 transcript는 포함되지 않는다. 이 조회는 Redis 상태나 TTL을 변경하지 않는다.

**요청 body 없음**

**응답 `200 OK`** — `OnboardingResponse(step="review")`

`POST /messages`가 review로 전이할 때 반환한 것과 같은 서버 snapshot이다. 저장 직전 이 응답의 `payload.draft_revision`과 화면에 표시할 내용을 기준으로 삼는다.

**에러**

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 409 | `ONBOARDING_SESSION_EXPIRED` | 세션 없음(TTL 만료) 또는 다른 사용자의 세션 |
| 409 | `ONBOARDING_RESULT_NOT_READY` | 세션이 아직 `collecting` 단계 |
| 409 | `ONBOARDING_ALREADY_COMPLETED` | 이미 confirm된 세션. `GET /profile`을 사용해야 함 |
| 409 | `ONBOARDING_REQUEST_IN_PROGRESS` | 같은 세션의 상태 변경 요청이 잠금을 보유 중(retryable) |
| 503 | `SERVICE_UNAVAILABLE` | Redis 장애(retryable) |

---

### POST /onboarding/sessions/{session_id}/confirm

`GET /result`에서 확인한 서버 snapshot을 확정 저장한다. 기존 `/messages`의 `action="onboarding.confirm"`과 동일한 서비스 경로, fingerprint, revision 검사와 retry cache를 사용한다.

**요청**

```json
{
  "request_id": "c9bf9e57-1685-4c89-bafb-ff5af3641a5b",
  "expected_revision": 3
}
```

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `request_id` | UUID | 필수. confirm 멱등성 키 |
| `expected_revision` | int | 필수, 0 이상. 직전 `/result`의 `draft_revision`과 일치해야 함 |

두 필드 외의 추가 필드는 허용하지 않는다.

**응답 `200 OK`** — `OnboardingResponse(step="completed")`

기존 messages confirm과 같은 completed 응답이다. 성공하면 `GET /profile`로 DB 영속 결과를 다시 읽고, confirm 직전 review snapshot과 profile/assessment/revision을 대조한다. `/profile` 조회만 실패한 경우 confirm을 다시 만들지 말고 `/profile`만 재시도한다.

**에러**

`POST /messages` confirm과 동일하게 `ONBOARDING_SESSION_EXPIRED`, `ONBOARDING_REQUEST_IN_PROGRESS`, `IDEMPOTENCY_KEY_REUSED`, `ONBOARDING_REVISION_CONFLICT`, `ONBOARDING_SNAPSHOT_CONFLICT`, 요청 `VALIDATION_ERROR`, `ONBOARDING_VALIDATION_ERROR`, `SERVICE_UNAVAILABLE`을 반환할 수 있다.

---

### 온볼딩 공통 응답 구조 (OnboardingResponse)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `session_id` | UUID | 세션 식별자 |
| `flow` | string | 항상 `"onboarding"` |
| `step` | string | `conversation` / `review` / `completed` |
| `assistant_message` | string | Gemini가 생성한 다음 질문 또는 안내 (1~4,000자) |
| `choices` | string[] | review 단계에서만 `["onboarding.confirm", "onboarding.restart"]` |
| `payload.draft_revision` | int | draft 변경 revision. 한 text 응답에서 하나 이상의 필드가 바뀌면 필드 수와 무관하게 한 번 +1 |
| `payload.draft_profile` | object | 현재까지 추출된 필드 값. 8개가 다 차면 전체 스키마로 직렬화 |
| `payload.answered_fields` | string[] | 채워진 필드 목록 |
| `payload.missing_fields` | string[] | 남은 필드 목록. 빈 배열이 되면 review로 전이 |
| `payload.assessment` | object \| null | review 이후 준비도 평가 |
| `payload.engine` | object | 실행 엔진 정보 (provider/model/version 고정값) |
| `payload.stored_profile` | object \| null | confirm 후 DB에 저장된 프로필 |
| `completed` | bool | `step == "completed"`와 동일 |

`assistant_message`와 profile/assessment의 문자열은 신뢰되지 않은 사용자·모델 유래 값이다. 브라우저에서는 기본적으로 text로 렌더링하고, HTML로 사용할 경우 별도의 sanitizer를 적용한다.

---

### 계획 제안·활성 계획

온보딩을 완료하고 추적 가능한 assessment가 있는 현재 프로필을 기준으로 Gemini가 주차별 outline과 날짜별 task를 생성한다. `saved_job_id`를 지정하면 해당 저장 공고의 역할·요구사항·원문도 비신뢰 데이터로 함께 전달해 공고 맞춤형 계획을 생성한다. 서버는 최대 365일, 모든 날짜의 정확한 커버리지, 날짜당 task 1~3개, 제안/metadata hash를 검증한다.

요청의 사용자는 Bearer JWT의 `sub`로만 결정한다. 다른 사용자의 proposal, plan, task ID는 존재 여부를 노출하지 않고 해당 자원의 `*_NOT_FOUND`로 응답한다.

#### POST /plan-proposals

```json
{
  "request_id": "40000000-0000-4000-8000-000000000001",
  "saved_job_id": "30000000-0000-0000-0000-000000000001"
}
```

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `request_id` | UUID | 필수 | 생성 요청 멱등성 키 |
| `saved_job_id` | UUID \| null | 선택 | 맞춤 계획의 기준이 될 `saved_jobs.id`. 생략하거나 `null`이면 기존처럼 프로필만 사용 |

- 최초 생성은 `201 Created`와 `PlanProposalView`를 직접 반환한다.
- `saved_job_id`가 있으면 서버가 공고 전체를 조회해 immutable 생성 snapshot으로 고정하고 Gemini outline·task 생성, Redis checkpoint, proposal content에 동일 snapshot을 사용한다.
- 성공 응답 window는 proposal의 `starts_on`부터 기본 7일이며 끝일을 넘지 않도록 잘라낸다.
- 같은 사용자가 같은 `request_id`와 같은 `saved_job_id`를 재시도하면 이미 저장된 동일 proposal을 **다시 `201`**로 반환한다. 생성은 28일 배치, 최대 동시성 3으로 진행하며, 생성 입력과 검증된 outline/배치/완성 proposal checkpoint는 마지막 성공 write부터 1시간 동안 best-effort 재개에 쓰인다. checkpoint가 없거나 만료됐으면 같은 ID로 생성부터 다시 시작한다.
- 같은 `request_id`를 다른 `saved_job_id`로 바꾸거나 공고 선택 유무를 바꿔 재사용하면 `IDEMPOTENCY_KEY_REUSED`다. 다른 request ID의 pending 제안이 있으면 `PLAN_PROPOSAL_ALREADY_PENDING`이다.
- 활성 계획이 있으면 `ACTIVE_PLAN_EXISTS`이며, 프로필/평가가 없으면 `PROFILE_NOT_FOUND`이다.

`retryable=true` 오류 또는 client timeout/network error는 작업이 전혀 진행되지 않았다는 뜻이 아니다. 새 UUID를 만들지 말고 같은 `request_id`와 동일 body를 유지한다. 상태를 먼저 확인하려면 `GET /plan-proposals/pending`을 호출해 반환된 `request_id`를 대조하고, 일치하는 영속 제안이 없으면 같은 생성 요청을 재시도한다. 서버는 유효 checkpoint가 있으면 남은 생성 또는 DB 저장부터 이어서 처리한다.

**에러**

| 상태 | code | retryable | 발생 조건 |
| --- | --- | --- | --- |
| 401 | `UNAUTHORIZED` | - | 인증 실패 |
| 404 | `PROFILE_NOT_FOUND` | - | 확정 프로필 또는 추적 가능한 준비도 평가 없음 |
| 404 | `SAVED_JOB_NOT_FOUND` | - | `saved_job_id`에 해당하는 저장 공고 없음 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | - | 같은 request ID가 다른 작업 또는 다른 공고 선택에 이미 사용됨 |
| 409 | `PLAN_PROPOSAL_ALREADY_PENDING` | - | 다른 request ID의 pending 제안 존재 |
| 409 | `ACTIVE_PLAN_EXISTS` | - | 진행 중인 active plan 존재 |
| 409 | `PLAN_GENERATION_IN_PROGRESS` | ✅ | 같은 request ID의 생성 요청 처리 중 |
| 409 | `PLAN_PROFILE_CHANGED` | - | 생성 중 프로필 또는 assessment가 변경됨 |
| 409 | `PLAN_PROPOSAL_STALE` | - | 생성 중 KST 날짜가 변경됨 |
| 422 | `VALIDATION_ERROR` | - | request ID 또는 saved job ID 형식 오류 |
| 422 | `PLAN_TARGET_DATE_EXPIRED` | - | 프로필 목표일 경과 |
| 422 | `SAVED_JOB_EXPIRED` | - | 선택 공고의 마감일이 KST 오늘보다 이전 |
| 422 | `PLAN_HORIZON_TOO_LONG` | - | 생성 기간이 365일 초과 |
| 422 | `GEMINI_CONTENT_BLOCKED` | - | Gemini 안전 필터 차단 |
| 429 | `GEMINI_RATE_LIMITED` | ✅ | 사용자별 Gemini 호출 제한 초과 |
| 500 | `PLAN_DATA_INTEGRITY_ERROR` | - | 생성·저장 데이터 무결성 검증 실패 |
| 502 | `GEMINI_UNAVAILABLE` | ✅ | Gemini 일시 장애 |
| 502 | `GEMINI_CONFIGURATION_ERROR` / `GEMINI_INVALID_RESPONSE` | - | Gemini 설정 또는 구조화 응답 검증 실패 |
| 503 | `SERVICE_UNAVAILABLE` | ✅ | PostgreSQL 또는 Redis 처리 실패 |
| 504 | `PLAN_GENERATION_TIMEOUT` | ✅ | 생성 시간 초과; 같은 request ID로 재시도 |

#### GET /plan-proposals/pending · GET /plan-proposals/{proposal_id}

두 GET은 모두 선택 query `start_on=YYYY-MM-DD`, `days=1..28` 를 받는다. proposal의 기본 `start_on`은 제안의 `starts_on`이고 `days`는 7이다. `start_on`은 제안 기간 내에 있어야 하며 벗어나면 `PLAN_WINDOW_OUT_OF_RANGE`이다. `days`가 경계를 넘으면 마지막 날까지 잘라낸다.

두 endpoint 모두 성공 시 `200 OK`와 `PlanProposalView`를 직접 반환한다.

`PlanProposalView` top-level schema:

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `id` | UUID | `ai_results` proposal ID |
| `request_id` | UUID | 생성 멱등성 키 |
| `decision_status` | `pending` \| `applied` \| `rejected` | 현재 제안 결정 상태 |
| `title` | string | 계획 제안 제목 |
| `summary` | string | 계획 제안 요약 |
| `generated_on` | date | KST 생성 날짜 |
| `starts_on` | date | 전체 제안 시작일; `generated_on`과 같음 |
| `ends_on` | date | 전체 제안 종료일; 생성 시 프로필 목표일 |
| `duration_days` | integer | 시작/종료일을 모두 포함한 일수 |
| `milestones` | `PlanProposalMilestoneView[]` | window와 무관한 전체 주차 milestone |
| `days` | `PlanProposalDayView[]` | 요청 window에 포함된 날짜별 task |
| `total_task_count` | integer | 전체 제안 기간의 task 수 |
| `proposal_hash` | 64자 hex string | canonical proposal hash |
| `profile_hash` | 64자 hex string | 생성 기준 프로필 snapshot hash |
| `assessment_result_id` | UUID | 생성 기준 준비도 평가 result ID |
| `saved_job` | `SavedJobView` \| null | 선택 공고의 생성 시점 snapshot. 프로필만으로 생성했으면 `null` |
| `schema_version` | `profile-plan-proposal-v1` | proposal schema version |
| `model_name` | string | 저장된 생성 model |
| `prompt_version` | `profile-plan-proposal-v1` | 저장된 proposal prompt version |
| `api_version` | string | Gemini API version |
| `outline_prompt_version` | string | outline prompt version |
| `tasks_prompt_version` | string | task prompt version |
| `applied_plan_id` | UUID \| null | applied일 때 연결된 plan ID |
| `decided_at` | datetime \| null | 수락/거절 결정 timestamp |
| `created_at` | datetime | proposal 영속 생성 timestamp |
| `requested_start_on` | date | 실제 반환 window 시작일 |
| `requested_end_on` | date | 실제 반환 window 종료일 |
| `has_previous` | boolean | 이전 날짜 window 존재 여부 |
| `has_next` | boolean | 다음 날짜 window 존재 여부 |

`PlanProposalView` nested schema:

| 모델 | 필드 | 타입/의미 |
| --- | --- | --- |
| `PlanProposalMilestoneView` | `week_index` | integer; 1부터 시작하는 주차 |
|  | `starts_on` | date; milestone 시작일 |
|  | `ends_on` | date; milestone 종료일 |
|  | `title` | string; milestone 제목 |
|  | `description` | string; milestone 설명 |
| `PlanProposalDayView` | `plan_day` | integer; 전체 계획에서 1부터 시작하는 일차 |
|  | `date` | date; KST 지역 날짜 |
|  | `tasks` | `PlanProposalTaskView[]`; 해당 날짜 task 1~3개 |
| `PlanProposalTaskView` | `slot` | integer; 해당 날짜에서 1부터 시작하는 순서 |
|  | `title` | string; task 제목 |
|  | `description` | string; task 설명 |

datetime은 timezone을 포함한 ISO 8601 문자열이다. provider 원본 JSON, 내부 checkpoint/Redis key, 사용자 입력 원문, credential은 반환하지 않는다.

#### POST /plan-proposals/{proposal_id}/accept

요청 body는 없다. pending 제안을 수락하면 `200 OK`와 `PlanView`를 직접 반환한다. 응답 window는 KST 오늘을 plan 기간에 clamp한 날짜부터 기본 7일이다. 제안의 outline/task를 PostgreSQL schedule item으로 투영하고 모든 plan day의 미달성 `daily_goal_achievements` 행을 만든 뒤 plan을 `active`, proposal을 `applied`로 바꾸는 작업을 하나의 트랜잭션에서 수행한다. 선택 공고가 있는 제안은 `ai_results.saved_job_id`를 `plans.source_saved_job_id`로 승계한다. 날짜는 KST 지역 날짜, 시각은 수락 시점의 프로필 `daily_notification_time`으로 고정된다.

`plans.proposal_result_id`와 column `ai_results.applied_plan_id`의 상호 링크는 repository 트랜잭션에서 함께 갱신한다. DB의 기존 same-owner FK와 proposal당 단일 plan unique guard가 소유자/일대일 무결성을 보조한다. 모든 임의 update를 양방향으로 맞추는 일반화된 reciprocal trigger는 없다.

- 같은 applied proposal을 다시 accept하면 같은 plan을 반환한다.
- 수락 전 현재 프로필/hash/assessment가 바뀌었으면 `PLAN_PROFILE_CHANGED`, KST 생성일이 지났으면 `PLAN_PROPOSAL_STALE`다.
- 다른 활성 계획이 있으면 `ACTIVE_PLAN_EXISTS`, pending/applied가 아닌 제안은 `PLAN_PROPOSAL_NOT_PENDING`이다.

#### POST /plan-proposals/{proposal_id}/reject

요청 body는 없다. pending 제안을 `rejected`로 바꾸고 `200 OK`와 갱신된 `PlanProposalView`를 직접 반환한다. 응답 window는 proposal의 `starts_on`부터 기본 7일이다. 이미 `rejected`인 제안은 최초 `decided_at`을 보존해 멱등 반환하고, `applied`인 제안만 `PLAN_PROPOSAL_NOT_PENDING`이다.

#### GET /plans/active · GET /plans/{plan_id}

query는 proposal GET과 같은 `start_on`, `days=1..28`이다. 두 endpoint 모두 성공 시 `200 OK`와 `PlanView`를 직접 반환한다. plan의 기본 window 시작일은 KST 오늘을 plan 기간으로 clamp한 날짜이다. 즉 시작 전이면 `starts_on`, 종료 후이면 `ends_on`이다.

`PlanView` top-level schema:

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `id` | UUID | plan ID |
| `proposal_result_id` | UUID | 이 plan의 출처 proposal `ai_results.id` |
| `proposal_hash` | 64자 hex string | 수락된 canonical proposal hash |
| `profile_hash` | 64자 hex string | 제안 생성 기준 profile snapshot hash |
| `assessment_result_id` | UUID | 제안 생성 기준 준비도 평가 result ID |
| `title` | string | plan 제목 |
| `summary` | string | plan 요약 |
| `starts_on` | date | 전체 plan 시작일 |
| `ends_on` | date | 전체 plan 종료일 |
| `duration_days` | integer | 시작/종료일을 모두 포함한 일수 |
| `status` | `draft` \| `active` \| `completed` \| `expired` \| `superseded` \| `rejected` | plan 상태 |
| `milestones` | `PlanMilestoneView[]` | window와 무관한 전체 milestone |
| `days` | `PlanDayView[]` | 요청 window에 포함된 날짜/task |
| `total_task_count` | integer | 전체 progress task 수 |
| `completed_task_count` | integer | 완료된 progress task 수 |
| `percent` | integer | `completed_task_count * 100 // total_task_count` floor 값 |
| `user_exp` | integer | 사용자가 모든 plan에서 누적한 비음수 EXP |
| `schema_version` | `profile-plan-proposal-v1` | 출처 proposal schema version |
| `model_name` | string | 출처 생성 model |
| `prompt_version` | `profile-plan-proposal-v1` | 출처 proposal prompt version |
| `api_version` | string | Gemini API version |
| `outline_prompt_version` | string | outline prompt version |
| `tasks_prompt_version` | string | task prompt version |
| `activated_at` | datetime | plan 활성화 timestamp |
| `ended_at` | datetime \| null | plan 종료 timestamp |
| `restart_offer_status` | `not_due` \| `pending` \| `accepted` \| `declined` | 재시작 제안 상태 |
| `restart_prompted_at` | datetime \| null | 재시작 제안이 열린 timestamp |
| `requested_start_on` | date | 실제 반환 window 시작일 |
| `requested_end_on` | date | 실제 반환 window 종료일 |
| `has_previous` | boolean | 이전 날짜 window 존재 여부 |
| `has_next` | boolean | 다음 날짜 window 존재 여부 |

`PlanView` nested schema:

| 모델 | 필드 | 타입/의미 |
| --- | --- | --- |
| `PlanMilestoneView` | `id` | UUID; 영속 schedule item ID |
|  | `week_index` | integer; 1부터 시작하는 주차 |
|  | `starts_on` | date; milestone 시작일 |
|  | `ends_on` | date; milestone 종료일 |
|  | `scheduled_at` | datetime; `ends_on` + 수락 시 profile 알림 시각의 KST 스케줄 |
|  | `title` | string; milestone 제목 |
|  | `description` | string; milestone 설명 |
| `PlanDayView` | `plan_day` | integer; 전체 계획에서 1부터 시작하는 일차 |
|  | `date` | date; KST 지역 날짜 |
|  | `tasks` | `PlanTaskView[]`; 해당 날짜 task |
|  | `completed_task_count` | integer; 해당 날짜 완료 task 수 |
|  | `total_task_count` | integer; 해당 날짜 전체 task 수 |
|  | `achieved` | boolean; 해당 날짜 task가 모두 완료됐는지 여부 |
|  | `achieved_at` | datetime \| null; 마지막 task 완료 시각 또는 미달성 시 null |
|  | `earned_exp` | `0` \| `20`; 현재 날짜 달성으로 보유한 EXP |
| `PlanTaskView` | `id` | UUID; 영속 schedule item ID |
|  | `plan_day` | integer; 전체 계획 일차 |
|  | `slot` | integer; 해당 날짜의 task 순서 |
|  | `date` | date; KST 지역 task 날짜 |
|  | `scheduled_at` | datetime; task 날짜 + 수락 시 profile 알림 시각의 KST 스케줄 |
|  | `title` | string; task 제목 |
|  | `description` | string; task 설명 |
|  | `status` | `pending` \| `completed`; task 상태 |
|  | `completed_at` | datetime \| null; 완료 timestamp |

`PlanView`에서 EXP와 날짜별 달성 상태가 보이는 부분 예시는 다음과 같다. `days`는 요청한 window만 담지만 `user_exp`는 window나 현재 plan에 한정되지 않은 사용자 전체 누적값이다.

```json
{
  "days": [
    {
      "plan_day": 3,
      "date": "2026-08-12",
      "completed_task_count": 2,
      "total_task_count": 2,
      "achieved": true,
      "achieved_at": "2026-08-12T10:24:18.421000+09:00",
      "earned_exp": 20
    }
  ],
  "user_exp": 40
}
```

위 JSON은 관련 필드만 보여주는 부분 예시이므로 실제 `PlanView`에서는 앞의 top-level 및 nested schema에 정의된 나머지 필드도 모두 필수다. `tasks` 역시 실제 응답에서는 해당 날짜의 `PlanTaskView` 목록을 포함한다.

`PlanView`도 provider 원본 JSON, proposal 원문 JSON, 내부 checkpoint/Redis key, 사용자 입력 원문, credential을 반환하지 않는다.

#### GET /plans/summary

현재 사용자가 소유한 모든 plan의 완료율과 계정 통합 완료율을 반환한다. 요청 query와 body는 없다.

- `active`, `completed`, `expired`, `superseded`, `rejected`, `draft` 상태의 plan을 모두 포함한다.
- 사용자 ID는 Bearer access token의 `sub`로만 결정하며 본인 plan만 반환한다.
- plan은 `created_at` 내림차순, 같으면 `id` 내림차순으로 정렬한다.
- plan이 하나도 없으면 `plans`는 빈 배열이고 집계 필드는 모두 `0`이며 `user_exp`는 계정의 현재 누적값이다.

**응답 `200 OK`** — `PlanSummaryView`를 envelope 없이 직접 반환한다.

```json
{
  "user_exp": 40,
  "plan_count": 2,
  "aggregate_total_task_count": 6,
  "aggregate_completed_task_count": 5,
  "aggregate_percent": 83,
  "plans": [
    {
      "id": "60000000-0000-0000-0000-000000000001",
      "title": "백엔드 로드맵",
      "status": "active",
      "starts_on": "2026-08-10",
      "ends_on": "2026-08-16",
      "duration_days": 7,
      "total_task_count": 3,
      "completed_task_count": 2,
      "percent": 66,
      "activated_at": "2026-08-10T09:00:00+09:00",
      "ended_at": null
    }
  ]
}
```

`PlanSummaryView` top-level schema:

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `user_exp` | integer | 사용자가 모든 plan에서 누적한 비음수 EXP |
| `plan_count` | integer | 반환된 plan 수 |
| `aggregate_total_task_count` | integer | 모든 plan의 progress task 수 합계 |
| `aggregate_completed_task_count` | integer | 모든 plan의 완료된 progress task 수 합계 |
| `aggregate_percent` | integer | `aggregate_completed_task_count * 100 // aggregate_total_task_count` floor 값. 합계가 0이면 0 |
| `plans` | `PlanSummaryItemView[]` | 로드맵별 완료율 목록 (`created_at` 내림차순) |

`PlanSummaryItemView` schema:

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `id` | UUID | plan ID |
| `title` | string | plan 제목 |
| `status` | `draft` \| `active` \| `completed` \| `expired` \| `superseded` \| `rejected` | plan 상태 |
| `starts_on` | date | 전체 plan 시작일 |
| `ends_on` | date | 전체 plan 종료일 |
| `duration_days` | integer | 시작/종료일을 모두 포함한 일수 |
| `total_task_count` | integer | plan의 progress task 수 |
| `completed_task_count` | integer | 완료된 progress task 수 |
| `percent` | integer | `completed_task_count * 100 // total_task_count` floor 값. `total_task_count = 0`이면 0 |
| `activated_at` | datetime \| null | plan 활성화 timestamp |
| `ended_at` | datetime \| null | plan 종료 timestamp |

**에러**

| HTTP | code | 조건 |
| ---: | --- | --- |
| 401 | `UNAUTHORIZED` | Bearer token 누락·만료·검증 실패 |
| 500 | `PLAN_DATA_INTEGRITY_ERROR` | 저장된 plan·schedule 무결성 검증 실패 |
| 503 | `SERVICE_UNAVAILABLE` | PostgreSQL 장애 |

#### PATCH /plans/{plan_id}/tasks/{task_id}

```json
{
  "status": "completed"
}
```

`status`는 `pending` 또는 `completed`만 허용하고 추가 body 필드는 거절한다. 실제 상태 변경은 활성 plan의 소유 progress task에서만 하며, `completed`에서 `pending`으로 돌릴 수도 있다. 사용자 ID는 Bearer token에서 결정하며 다른 사용자·plan·task 조합은 존재 여부를 노출하지 않고 `PLAN_TASK_NOT_FOUND`로 처리한다.

성공 시 `200 OK`와 아래 `TaskUpdateView`를 envelope 없이 직접 반환한다. 상속된 `PlanTaskView` 9개 필드도 모두 필수다.

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `id`~`completed_at` | `PlanTaskView` | 변경 후 canonical task 9개 필드 |
| `completed_task_count` | integer | 변경 후 plan 전체 완료 progress task 수 |
| `total_task_count` | integer | plan 전체 progress task 수 |
| `percent` | integer | 변경 후 `completed_task_count * 100 // total_task_count` |
| `day_completed_task_count` | integer | 변경된 task 날짜의 완료 task 수 |
| `day_total_task_count` | integer | 변경된 task 날짜의 전체 task 수 |
| `achieved` | boolean | 변경 후 해당 날짜의 모든 task 완료 여부 |
| `achieved_at` | datetime \| null | 달성 시 해당 날짜 task들의 가장 늦은 `completed_at`, 미달성 시 null |
| `earned_exp` | `0` \| `20` | 해당 날짜가 현재 보유한 EXP; 이번 요청의 증감량이 아님 |
| `exp_delta` | `-20` \| `0` \| `20` | 이번 요청 하나가 누적 EXP에 반영한 증감량 |
| `user_exp` | integer | 트랜잭션 반영 후 사용자의 모든 plan 누적 EXP |

```json
{
  "id": "40000000-0000-0000-0000-000000000001",
  "plan_day": 3,
  "slot": 2,
  "date": "2026-08-12",
  "scheduled_at": "2026-08-12T09:00:00+09:00",
  "title": "지원 직무 예상 질문 정리",
  "description": "예상 질문과 답변 근거를 정리한다.",
  "status": "completed",
  "completed_at": "2026-08-12T10:24:18.421000+09:00",
  "completed_task_count": 4,
  "total_task_count": 12,
  "percent": 33,
  "day_completed_task_count": 2,
  "day_total_task_count": 2,
  "achieved": true,
  "achieved_at": "2026-08-12T10:24:18.421000+09:00",
  "earned_exp": 20,
  "exp_delta": 20,
  "user_exp": 40
}
```

일별 상태와 EXP 전이는 다음과 같다.

| 변경 전 일별 상태 | 변경 후 일별 상태 | `exp_delta` | 저장 결과 |
| --- | --- | ---: | --- |
| 미달성 | 미달성 | `0` | `achieved=false`, `achieved_at=null`, `earned_exp=0` |
| 미달성 | 달성 | `20` | `achieved=true`, 마지막 task 완료 시각, `earned_exp=20` |
| 달성 | 달성 | `0` | 기존 달성 시각과 `earned_exp=20` 보존 |
| 달성 | 미달성 | `-20` | `achieved=false`, `achieved_at=null`, `earned_exp=0` |

- 마지막 pending task가 완료되어 날짜가 미달성→달성이 되면 `+20 EXP`다.
- 달성 날짜의 task 하나를 pending으로 되돌리면 `-20 EXP`이고, 다시 모두 완료하면 새 달성 시각과 함께 `+20 EXP`다.
- 같은 task 상태 재요청은 `completed_at`, 날짜 달성 기록과 누적 EXP를 바꾸지 않는다. 일별 달성 여부가 바뀌지 않는 다른 task 변경도 `exp_delta=0`이다.
- 과거·오늘·미래 plan day를 같은 규칙으로 처리한다. 달력상의 오늘 여부는 적립 조건이 아니다.
- `user_exp`는 plan 사이에 누적되며 새 proposal 수락이나 plan 완료 시 초기화되지 않는다.
- 모든 날짜 task를 완료해도 plan이 자동으로 `completed`되지는 않는다. plan 종료는 별도 `POST /plans/{plan_id}/complete` 요청이다.
- 같은 목표 상태 재요청은 completed plan에서도 기존 timestamp를 보존해 반환하지만, 실제 상태를 바꾸려면 `PLAN_NOT_ACTIVE`다.
- plan, task/progress, 날짜 달성 행과 사용자 account를 잠그고 task·달성 기록·EXP를 하나의 PostgreSQL 트랜잭션에서 처리한다. 기록 누락/불일치, 0개 task인 날짜, 음수 EXP, admin account는 `PLAN_DATA_INTEGRITY_ERROR`로 전체 rollback한다.

Endpoint 오류 계약:

| HTTP | code | 조건 |
| ---: | --- | --- |
| 401 | `UNAUTHORIZED` | Bearer token 누락·만료·검증 실패 |
| 404 | `PLAN_TASK_NOT_FOUND` | 소유 plan의 progress task를 찾을 수 없음; 다른 사용자 소유도 동일 |
| 409 | `PLAN_NOT_ACTIVE` | completed 등 비활성 plan의 task를 다른 상태로 변경 |
| 422 | `VALIDATION_ERROR` | UUID/status 형식 오류 또는 추가 body 필드 |
| 500 | `PLAN_DATA_INTEGRITY_ERROR` | task·일별 달성 기록·account/EXP 무결성 실패; 변경 전체 rollback |
| 503 | `SERVICE_UNAVAILABLE` | PostgreSQL 처리 실패 |

#### GET /notices

Bearer 인증 사용자가 현재 게시 중인 공지를 envelope 없이 배열로 받는다. `published_at <= now()`이고 `expires_at`이 없거나 현재보다 뒤인 공지만 `is_pinned DESC`, `published_at DESC`, `id DESC` 순으로 반환한다. 각 항목은 `id`, `title`, `content`, `is_pinned`, `published_at`, `expires_at`을 포함하며 v1은 페이지네이션과 읽음 상태를 제공하지 않는다.

#### GET /quests/today

KST 오늘 기준 active plan의 task를 조회한다. 응답 필드는 `date`, nullable `plan_id`/`plan_title`, `quests`, `completed_count`, `total_count`, `percent`, `achieved`, `earned_exp`, `user_exp`다. active plan이 없으면 plan 필드와 목록이 비고, active plan이 오늘 범위 밖이면 plan 정보만 유지한 채 집계가 0이다. 계획 범위 안에서 오늘 task나 달성 원장이 누락·불일치하면 `500 PLAN_DATA_INTEGRITY_ERROR`다.

#### PATCH /quests/{task_id}

body는 `{"status":"pending"}` 또는 `{"status":"completed"}`만 허용한다. 서버가 KST 오늘의 active plan을 찾아 해당 날짜 progress task만 변경하며, 미존재·비소유·과거·미래 task는 모두 `404 TODAY_QUEST_NOT_FOUND`로 통일한다. 성공 응답은 `TaskUpdateView`이며 EXP 계약은 `earned_exp=0|20`, `exp_delta=-20|0|20`이다.

#### POST /plans/{plan_id}/complete

요청 body는 없다. 모든 progress task가 `completed`인 활성 plan을 `completed`로 종료하고 `200 OK`와 `restart_offer_status="pending"`인 `PlanView`를 직접 반환한다. 응답 window는 KST 오늘을 plan 기간에 clamp한 날짜부터 기본 7일이다. 완료 task가 부족하면 `409 PLAN_NOT_COMPLETE`이며 `details`에 소유 plan의 `completed_task_count`, `total_task_count`만 제공한다. 이미 완료된 plan의 재요청은 저장된 완료 view를 반환한다.

이후 restart offer 수락/거절 API는 아직 없다. 새 제안 생성은 완료 plan의 `restart_offer_status` 가 `pending`, `accepted`, `declined` 중 하나인 상태에서 허용된다.

---

## 4. 데이터 모델

### 프로필 필드 (8개)

| 필드 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `target_role` | string | 1~200자 | 목표 직무 |
| `skills` | string[] | 1~20개, 중복·공백 제거 | 보유 기술 |
| `experience_summary` | string | 1~4,000자 | 경험 요약 |
| `target_date` | date | KST 기준 오늘 이후 | 목표일 |
| `target_company` | string \| null | 최대 200자 | 목표 회사 (선택) |
| `preferred_environment` | string | 1~1,000자 | 선호 환경 |
| `daily_notification_time` | time | `HH:MM[:SS]` | 알림 시각 |
| `assistant_style` | string | `friendly` / `direct` | 어시스턴트 말투 |

모든 필드 업데이트는 Gemini가 **사용자 발화 인용 근거(evidence)** 를 함께 제시해야 하며, 서버는 인용이 실제 사용자 turn에 포함되는지 검증한다. 근거 없는 업데이트는 거부된다(`GEMINI_INVALID_RESPONSE`).

`target_company=null`은 사용자가 희망 기업이 없다고 명시한 유효한 답변이며 `answered_fields`에 포함된다. 사용자 text 요청은 conversation과 review 수정을 합쳐 세션당 최대 12개다.

### 준비도 평가 (ProfileAssessment)

| 항목 | 만점 | 설명 |
| --- | --- | --- |
| `skill_readiness` | 30 | 기술 준비도 |
| `experience_depth` | 30 | 경험 깊이 |
| `goal_clarity` | 20 | 목표 명확성 |
| `execution_readiness` | 20 | 실행 준비도 |
| **합계 `score`** | **100** | 4개 항목 합산 |

등급(`level`):

| 점수 | 등급 |
| --- | --- |
| 0~39 | `beginner` |
| 40~74 | `intermediate` |
| 75~100 | `advanced` |

`summary.disclaimer`에는 "취업 가능성 예측이 아니라 제공된 정보의 현재 준비도 평가입니다."가 포함된다.

---

## 5. 에러 코드 전체 표

| HTTP | code | retryable | 설명 |
| --- | --- | --- | --- |
| 401 | `INVALID_CREDENTIALS` | - | 로그인 실패 (잠금·비활성 포함) |
| 409 | `LOGIN_ID_ALREADY_EXISTS` | - | 회원가입 또는 계정 수정 로그인 ID 중복 |
| 401 | `UNAUTHORIZED` | - | access token 없음/만료/위조 또는 계정 삭제·비활성 |
| 404 | `ACCOUNT_NOT_FOUND` | - | 계정 수정·삭제 직전 대상 계정이 사라짐 |
| 404 | `PROFILE_NOT_FOUND` | - | 저장된 프로필 없음 |
| 404 | `NOTIFICATION_NOT_FOUND` | - | 알림이 없거나 다른 사용자 소유 |
| 500 | `NOTIFICATION_DATA_INTEGRITY_ERROR` | - | 저장된 알림 payload가 공개 모델과 불일치 |
| 409 | `ONBOARDING_SESSION_EXPIRED` | - | 세션 없음·만료 |
| 409 | `ONBOARDING_RESULT_NOT_READY` | - | result 조회 시 아직 collecting 단계 |
| 409 | `ONBOARDING_ALREADY_COMPLETED` | - | result 조회 시 이미 completed 단계 |
| 409 | `ONBOARDING_REQUEST_IN_PROGRESS` | ✅ | 세션 잠금 (이전 요청 처리 중) |
| 409 | `IDEMPOTENCY_KEY_REUSED` | - | request_id 재사용(payload 다름) |
| 409 | `ONBOARDING_REVISION_CONFLICT` | - | confirm revision 불일치 |
| 409 | `ONBOARDING_SNAPSHOT_CONFLICT` | - | request_id에 다른 snapshot 저장됨 |
| 409 | `ASSISTANT_SESSION_EXPIRED` | - | 코치 세션 없음·24시간 절대 만료·120초 유휴 종료·타 사용자 소유 |
| 409 | `ASSISTANT_SESSION_BUSY` | ✅ | 같은 코치 세션의 이전 요청 처리 중 |
| 409 | `ASSISTANT_REVISION_CONFLICT` | - | `expected_revision`이 최신 revision과 불일치 |
| 409 | `ASSISTANT_SESSION_LIMIT_REACHED` | - | 사용자당 활성 코치 세션 6개 초과 |
| 409 | `ASSISTANT_ALREADY_FINALIZED` | - | 종료된 코치 세션에 새 메시지 전송 |
| 409 | `ASSISTANT_REPORT_EMPTY` | - | 사용자 턴이 없는 코치 상담 종료 요청 |
| 422 | `VALIDATION_ERROR` | - | FastAPI 요청 스키마 위반 (`details.errors` 포함) |
| 422 | `ONBOARDING_VALIDATION_ERROR` | - | 빈 text, 지원하지 않는 action, 단계·발화 수 위반 |
| 422 | `ASSISTANT_TURN_LIMIT_REACHED` | - | 코치 상담의 성공한 사용자 턴 20개 초과 |
| 422 | `ASSISTANT_TRANSCRIPT_LIMIT_REACHED` | - | 코치 상담 대화 텍스트 누계 40,000자 초과 |
| 422 | `GEMINI_CONTENT_BLOCKED` | - | Gemini 콘텐츠 차단 |
| 429 | `GEMINI_RATE_LIMITED` | ✅ | Gemini 호출 제한 |
| 502 | `GEMINI_UNAVAILABLE` | ✅ | Gemini 일시 장애 |
| 502 | `GEMINI_CONFIGURATION_ERROR` | - | Gemini 설정 오류 |
| 502 | `GEMINI_INVALID_RESPONSE` | - | Gemini 응답 검증 실패 |
| 502 | `ASSISTANT_RESPONSE_TOO_LONG` | - | 코치 assistant 자연어가 12,000자 초과 |
| 500 | `ASSISTANT_DATA_INTEGRITY_ERROR` | - | 코치 내부 구조화 데이터 무결성 불일치 |
| 503 | `SERVICE_UNAVAILABLE` | ✅ | DB/Redis 인프라 장애 |
| 422 | `PLAN_TARGET_DATE_EXPIRED` | - | 프로필 목표일이 KST 오늘보다 이전 |
| 404 | `SAVED_JOB_NOT_FOUND` | - | 선택한 저장 공고를 찾을 수 없음 |
| 422 | `SAVED_JOB_EXPIRED` | - | 선택한 저장 공고의 마감일이 지남 |
| 422 | `PLAN_HORIZON_TOO_LONG` | - | 포함 기간이 365일 초과 |
| 409 | `PLAN_PROPOSAL_ALREADY_PENDING` | - | 다른 request ID의 pending 제안 존재 |
| 409 | `ACTIVE_PLAN_EXISTS` | - | 활성 계획 존재 |
| 409 | `PLAN_PROFILE_CHANGED` | - | 제안 생성 후 프로필/hash/assessment 변경 |
| 409 | `PLAN_PROPOSAL_STALE` | - | 제안의 KST 생성일이 지남 |
| 409 | `PLAN_GENERATION_IN_PROGRESS` | ✅ | 같은 계획 요청 생성 중 |
| 504 | `PLAN_GENERATION_TIMEOUT` | ✅ | 계획 생성 시간 초과; 같은 request ID로 재개 |
| 404 | `PLAN_PROPOSAL_NOT_FOUND` | - | 소유 계획 제안을 찾을 수 없음 |
| 409 | `PLAN_PROPOSAL_NOT_PENDING` | - | pending이 아닌 제안 변경 요청 |
| 404 | `PLAN_NOT_FOUND` | - | 소유 계획을 찾을 수 없음 |
| 404 | `PLAN_TASK_NOT_FOUND` | - | 소유 plan의 task를 찾을 수 없음 |
| 409 | `PLAN_NOT_ACTIVE` | - | 활성이 아닌 plan/task 변경 요청 |
| 409 | `PLAN_NOT_COMPLETE` | - | 완료되지 않은 task가 있음 |
| 422 | `PLAN_WINDOW_OUT_OF_RANGE` | - | `start_on`이 계획 기간 밖 |
| 500 | `PLAN_DATA_INTEGRITY_ERROR` | - | 계획 투영/출처/상태 무결성 검증 실패 |

> 참고: `CLIENT_TIMEOUT`, `CLIENT_NETWORK_ERROR`(503)는 서버가 아니라 CLI 클라이언트가 네트워크 오류 시 생성하는 코드다.

---

## 6. 제한·정책 요약

| 항목 | 값 | 비고 |
| --- | --- | --- |
| Access token TTL | 30분 | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh token TTL | 7일 | `REFRESH_TOKEN_EXPIRE_DAYS` |
| 로그인 잠금 | 5회 실패 시 15분 | 성공 시 초기화 |
| 가입 ID | 정규화 후 4~50자 | `[a-z0-9._-]+` |
| 가입 비밀번호 | 8~128자 | 공백 보존, 조합 규칙 없음 |
| 계정 수정 | `login_id`, `user_name` 부분 수정 | UUID·role·비밀번호 변경 불가 |
| 계정 삭제 | 사용자 소유 데이터 영구 삭제 | 전역 저장 공고 유지, 성공 시 token/cache 폐기 |
| Refresh/logout | 엔드포인트 미구현 | 만료 시 다시 로그인 |
| 온볼딩 result 조회 | review 단계만 지원 | 상태·TTL 변경 및 transcript 반환 없음 |
| 온볼딩 conversation resume | 미지원 | result API를 진행 중 대화 복구에 사용하지 않음 |
| 동시 편집 | 지원하지 않음 | 단일 탭·요청 직렬화 전제 |
| 온볼딩 세션 TTL | 30분 | `ONBOARDING_SESSION_TTL_SECONDS` (300~86400초 범위) |
| 사용자 발화 수 | 세션당 최대 12개 | 초과 시 `ONBOARDING_VALIDATION_ERROR` |
| `text` 길이 | 1~4,000자 | |
| `draft_revision` | 변경된 text 요청당 +1 | 한 요청에서 여러 필드가 바뀌어도 +1 |
| Gemini rate limit | 10분당 70회/사용자 | Redis 고정 윈도우 |
| 멱등성 캐시 | 세션당 최근 64개 request_id | 같은 request_id+같은 payload면 저장된 응답 재사용 |
| 세션 잠금 | Gemini 타임아웃×최대시도×2+30초 | 잠금 중 요청은 409 (retryable) |
| Gemini 호출 | 최대 2회 시도 (repair 1회 포함) | `GEMINI_MAX_ATTEMPTS`, 타임아웃 15초 |
| 코치 활성 세션 | 사용자당 최대 6개 | 종료·120초 유휴 만료 세션은 활성 세션 수에서 제외 |
| 코치 유휴 기한 | 생성 또는 마지막 사용자 입력 접수 후 120초 | 입력 접수 시 갱신, 정확한 경계부터 새 요청 거절, 자동 보고서 없음 |
| 코치 데이터 보관 상한 | 생성 시점 기준 절대 24시간 | 응답 `expires_at`, 원문·멱등 데이터 상한이며 활동으로 연장되지 않음 |
| 코치 사용자 턴 | 세션당 최대 20개 | 성공한 메시지만 revision과 턴 수 증가 |
| 코치 대화 누계 | 40,000자 | 사용자 text와 assistant_message 합계 |
| 코치 응답 길이 | 턴당 최대 12,000자 | 초과 시 `ASSISTANT_RESPONSE_TOO_LONG` |
| 코치 공고 도구 | 요청당 최대 1회 | KST 어제 마감 제외, 오늘 마감·마감 미정 포함 |
| 코치 일정 도구 | 요청당 최대 1회, 범위 최대 28일 | KST 양 끝 포함, 활성 plan의 milestone/task만 조회 |
| 코치 보고서 | 세션당 1개, canonical JSONB 128KiB 이하 | UPDATE 불가, finalize 응답/durable replay만 제공 |
| 날짜 기준 | Asia/Seoul (KST) | `target_date`는 KST 오늘 이후만 허용 |
| 로그인 알림 window | KST 오늘 포함 7일 | active 계획, `pending|in_progress` 일정만 날짜별 요약 |
| 로그인 알림 feed | upcoming 7건, changes 50건 | `unread_count`는 제한 전 전체 건수, 조회만으로 확인 처리하지 않음 |
| 계획 기간 | 1~365일 | 생성일과 목표일 모두 포함 |
| 계획 생성 checkpoint | 마지막 성공 write부터 1시간 | 프로필·assessment·선택 공고 snapshot을 고정하고 동일 `request_id`+`saved_job_id` 재시도를 best-effort 재개; 영속 proposal이 최종 기준 |
| 계획 조회 window | `days` 1~28, 기본 7 | `start_on`은 계획 기간 내 |
| 제안 제한 | 사용자당 pending 1개 | DB partial unique index 보조 |
| 활성 계획 제한 | 사용자당 active 1개 | 기존 DB partial unique index |
| task 상태 | `pending` / `completed` | 활성 plan에서만 변경 |
| schedule 시간 | KST 프로필 알림 시각 | accept 시점의 snapshot으로 고정 |
