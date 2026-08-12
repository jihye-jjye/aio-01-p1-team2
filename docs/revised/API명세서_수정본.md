# AI_JOB_COACH API 명세서 — 현재 구현 기준 수정본

> 기준: 2026-08-12 로컬 `main` 브랜치. 원본 다운로드 문서는 변경하지 않았다.

## 공통 규칙

- 관리자 API prefix: `/api/v1`
- 사용자 백엔드는 현재 공통 `/api/v1` prefix를 사용하지 않는다.
- 데이터 형식: `application/json`이 기본이며 Item 이미지 업로드는 `multipart/form-data`를 사용한다.
- 관리자 인증이 필요한 API는 `Authorization: Bearer <access_token>`을 사용하도록 작성되어 있다.
- FastAPI 검증 실패는 기본적으로 `422`를 반환한다.

## 현재 실행 상태

| 서버 | 상태 | 비고 |
|---|---|---|
| `backend_admin` | 실행 가능 | `/health`, 사용자·공지·로그·피드백 라우트 등록 |
| `backend_user` | 실행 불가 | `auth_router.py`가 존재하지 않는 `app.schemas.auth_scheme`을 import함 |

## 관리자 백엔드

### 상태 확인

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| GET | `/health` | N | 서버 상태 확인 |

### 사용자 관리

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| GET | `/api/v1/admin/users` | Y | 사용자 목록·검색·필터·페이지네이션 |
| GET | `/api/v1/admin/users/{user_id}` | Y | 사용자 계정·프로필 상세 조회 |
| PATCH | `/api/v1/admin/users/{user_id}` | Y | 사용자 `is_active` 변경 |
| DELETE | `/api/v1/admin/users/{user_id}` | Y | 사용자 삭제 |

목록 Query:

| 이름 | 타입 | 기본값 | 설명 |
|---|---|---:|---|
| `search` | string | - | 로그인 아이디 부분 검색 또는 UUID 검색 |
| `role` | `user` \| `admin` | - | 역할 필터 |
| `is_active` | boolean | - | 활성 상태 필터 |
| `page` | integer | 1 | 1 이상 |
| `size` | integer | 20 | 1~100 |

사용자 수정 요청:

```json
{
  "is_active": false
}
```

### 공지사항 관리

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| GET | `/api/v1/admin/notices` | Y | 공지 목록·제목 검색·페이지네이션 |
| POST | `/api/v1/admin/notices` | Y | 공지 등록 |
| GET | `/api/v1/admin/notices/{notice_id}` | Y | 공지 상세 |
| PATCH | `/api/v1/admin/notices/{notice_id}` | Y | 공지 수정 |
| DELETE | `/api/v1/admin/notices/{notice_id}` | Y | 공지 삭제 |
| GET | `/api/v1/notices` | N | 일반 공지 목록 |
| GET | `/api/v1/notices/{notice_id}` | N | 일반 공지 상세 |

공지 등록 요청:

```json
{
  "title": "서비스 안내",
  "content": "공지 내용"
}
```

- `title`: 1~200자
- `content`: 1~20,000자

### AI 운영 로그

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| GET | `/api/v1/admin/logs` | Y | 로그 목록과 필터 |
| GET | `/api/v1/admin/logs/summary` | Y | 요청 수·오류율·평균 지연 KPI |
| GET | `/api/v1/admin/logs/{log_id}` | Y | 로그 상세 |

로그 목록 Query: `level`, `endpoint`, `start_at`, `end_at`, `page`, `size`.

> DB 의존성: 코드가 `app.ai_logs` 테이블과 `app.admin_log_summary` 뷰를 참조하지만 이를 생성하는 SQL은 현재 저장소에 없다.

### 사용자 피드백

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| GET | `/api/v1/logs/{log_id}/feedback` | 사용자 JWT | 본인의 AI 응답 피드백 조회 |
| POST | `/api/v1/logs/{log_id}/feedback` | 사용자 JWT | 점수·의견 생성 또는 수정 |

```json
{
  "score": 5,
  "comment": "도움이 되었습니다."
}
```

> DB 의존성: 코드가 `app.feedback` 테이블을 참조하지만 생성 SQL은 현재 저장소에 없다.

## 사용자 백엔드 — 소스에 선언된 API

`backend_user`는 현재 import 오류로 OpenAPI 생성과 서버 실행이 불가능하다. 아래 목록은 Router 소스에 선언된 경로다.

### 인증

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/auth/create` | 샘플 회원 생성 |
| PUT | `/auth/update` | 샘플 회원 수정 |
| POST | `/auth/signin` | 샘플 로그인 |
| GET | `/auth/signout/{input_id}` | 샘플 로그아웃 |
| GET | `/auth/mypage/{input_id}` | 샘플 마이페이지 조회 |

### Gemini 채팅

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/chat/gemini` | Gemini 단일 채팅 호출 |

### Product 실습 API

| Method | Endpoint |
|---|---|
| POST | `/product/create` |
| GET | `/product/get/{product_id}` |
| GET | `/product/getall` |
| PUT | `/product/{product_id}` |
| DELETE | `/product/delete/{product_id}` |

### Item 실습 API

| Method | Endpoint |
|---|---|
| POST | `/item/create` |
| GET | `/item/get/{item_id}` |
| GET | `/item/select/all` |
| GET | `/item/search` |
| PUT | `/item/update/{item_id}` |
| DELETE | `/item/delete/{item_id}` |

## 현재 미구현 API

원본 명세에 있었으나 현재 `main`에는 구현되지 않은 주요 기능:

- Refresh Token 기반 인증
- 프로필·온보딩 API
- 로드맵 생성·승인·퀘스트 완료 API
- 공고 추천·검색·저장 API
- AI 코치 세션 API
- 관리자 로그인 API
- 관리자 대시보드 API
- 관리자 저장 공고 목록 API

## 공통 오류

| HTTP | 의미 |
|---:|---|
| 400 | 잘못된 요청 |
| 401 | 인증 실패 또는 토큰 문제 |
| 403 | 권한 없음 또는 비활성 계정 |
| 404 | 리소스 없음 |
| 409 | 현재 상태와 요청 충돌 |
| 422 | Path·Query·Body 검증 실패 |
| 503 | Supabase 또는 저장소 오류 |
