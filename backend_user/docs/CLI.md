# AI Job Coach CLI 명령어 설명서

이 문서는 `backend_user/app/cli`의 사용자 흐름과 명령어 계약을 설명한다.

- 작성일: 2026-08-11
- 실행 환경: Python 3.12, `uv`, FastAPI `https://aio-01-p1-team2-1.onrender.com`
- 관련 문서: [`README.md`](../README.md), [`API_SPEC.md`](API_SPEC.md), [`TESTING.md`](../TESTING.md)

## 1. 실행

사용자 CLI:

```bash
cd backend_user
uv run --frozen ai-job-coach-cli
```

별도 CLI 인자는 없다. 로컬 시연 계정을 만드는 관리자 helper는 다음과 같다.

```bash
uv run --frozen create-demo-user --login-id demo.user
```

`create-demo-user`는 비밀번호를 두 번 숨김 입력으로 받고 Argon2id hash만 저장한다. 같은 ID가 있으면 비밀번호 hash와 계정 활성 상태를 갱신한다.

## 2. 인증과 온보딩

인증 화면에서는 다음 명령만 사용한다.

| 명령 | 동작 |
| --- | --- |
| `/signup` | 회원가입 입력으로 전환 |
| `/login` | 로그인 입력으로 전환 |
| `/help` | 현재 인증 단계 도움말 |
| `/quit` | 정상 종료 |

비밀번호 입력은 숨겨지며 비밀번호 프롬프트에서 `/`로 시작하는 일반 문자열도 비밀번호로 보존한다. 회원가입과 로그인 API는 각각 `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`이다.

회원가입/로그인 성공 응답에서 access token을 저장한 직후, `GET /api/v1/profile`보다 먼저 body 없는 `POST /api/v1/notifications/login-feed`를 호출한다. 서버는 KST 오늘 포함 7일의 활성 로드맵 일정을 동기화하고 미확인 feed를 반환한다.

- `다가오는 7일 일정`과 `최근 로드맵 변경` 두 Rich 섹션을 항상 표시한다. 빈 섹션도 빈 상태를 명시한다.
- 일정 섹션은 날짜 오름차순 최대 7건, 변경 섹션은 최신순 최대 50건이며 화면 번호는 두 섹션에 걸쳐 연속된다. 서버의 `unread_count`는 제한 전 전체 미확인 건수다.
- 제목, 메시지, 계획명, 일정명은 Rich markup으로 해석하지 않는 리터럴 텍스트다.
- 표시 후 `확인 처리할 알림 번호`에 쉼표 구분 번호를 입력한 경우에만 각 ID를 `PATCH /api/v1/notifications/{notification_id}/read`로 보낸다. Enter는 모두 건너뛰며 feed 조회 자체는 읽음 처리하지 않는다. 범위 밖 번호나 숫자가 아닌 입력은 원격 요청 없이 다시 안내한다.
- feed 또는 개별 확인 요청이 실패하면 경고만 출력한다. 다른 선택 알림과 `GET /profile`, 온보딩, 메인 메뉴 흐름은 계속한다. 이 best-effort 알림 단계의 401도 방금 저장한 token을 지우거나 로그인을 중단시키지 않는다.

알림 단계가 끝나면 `GET /api/v1/profile`을 호출한다.

- 기존 프로필이 있으면 프로필과 평가 출처를 출력한 뒤 종료하지 않고 메인 메뉴로 간다.
- 프로필이 없으면 `POST /api/v1/onboarding/sessions`로 온보딩을 시작한다.
- 일반 대화는 `POST /api/v1/onboarding/sessions/{session_id}/messages`로 보낸다.
- review 단계의 `/confirm`은 저장 직전 `GET /api/v1/onboarding/sessions/{session_id}/result`로 서버 review snapshot을 먼저 조회하고, 그 응답의 `payload.draft_revision`을 `POST /api/v1/onboarding/sessions/{session_id}/confirm`의 `expected_revision`으로 보낸다. 표시된 review의 revision과 서버 snapshot의 revision이 다르면 확정하지 않고 최신 review 확인을 안내한다.
- review 단계의 `/restart`는 같은 messages endpoint에 `action=onboarding.restart`를 보낸다.

대화 중 전역 명령은 `/help`, `/quit`이다. `/confirm`과 `/restart`는 review 단계에서만 유효하고, 다른 단계의 미정의 슬래시 입력은 API를 호출하지 않고 도움말을 표시한다.

확정 응답 뒤에는 `GET /api/v1/profile`로 저장 결과를 재검증한다. 조회 실패나 불일치가 발생하면 `/confirm`은 프로필 조회만 다시 수행하며 온보딩 확정을 다시 보내지 않는다. 검증이 성공하면 `GET /api/v1/saved-jobs/recommendation`을 한 번 호출해 전체 프로필 기반 일치도, 일치 단서, 판단 방식(`Gemini` 또는 `키워드 대체`), 추천 이유와 공고를 출력하고, 해당 공고를 로드맵 대상으로 선택할지 `y/n`으로 확인한다. 공고가 없으면 빈 상태를 안내하고, 추천 조회 실패는 이미 완료된 온보딩 결과를 되돌리지 않는다.

## 3. 메인 메뉴

메인 메뉴의 입력 계약은 다음 열 번호뿐이다.

```text
1. 프로필 보기
2. 로드맵 제안 생성·검토
3. 활성 로드맵
4. 내 로드맵 완료율 요약
5. 오늘 퀘스트
6. 전체 채용 공고
7. 온보딩 기반 추천 공고
8. 공지 사항
9. 프로필 재온보딩
10. 다른 계정으로 로그인
11. AI 취업 코치 상담
0. 종료
```

메인 메뉴에서는 `/help`, `/quit`도 사용할 수 있다. 그 밖의 입력은 API를 호출하지 않고 메인 메뉴 도움말을 표시한다.

### 1. 프로필 보기

현재 로그인 사용자의 프로필과 평가 메타데이터를 다시 표시하고 메인 메뉴를 유지한다.

### 2. 로드맵 제안 생성·검토

먼저 `GET /api/v1/plan-proposals/pending?days=7`로 기존 pending 제안을 조회한다. 기존 제안이 있으면 새 생성 요청 없이 그 제안을 연다. 없으면 장시간 생성이 시작된다는 안내와 확인 프롬프트를 먼저 표시하며, 사용자가 명시적으로 확인한 경우에만 UUID `request_id`를 만들어 다음 요청을 보낸다.

```http
POST /api/v1/plan-proposals
Content-Type: application/json

{"request_id":"<UUID>","saved_job_id":"<선택한 추천 공고 UUID>"}
```

생성 요청의 `request_id`는 멱등성 키다. 추천 공고를 선택하지 않았으면 `saved_job_id`를 생략해 기존 프로필 기반 로드맵을 생성한다. 공고 선택을 바꾸면 보관 중인 request ID를 폐기하고 다음 생성에 새 UUID를 사용한다.

- 제안 생성 성공 응답을 받거나 기존 pending 제안을 다시 확인하면 보관한 UUID를 지운다.
- 서버가 `retryable=true`로 반환한 오류, `PLAN_GENERATION_IN_PROGRESS`, `PLAN_GENERATION_TIMEOUT`, 클라이언트 timeout/network 오류 또는 생성 도중의 401에는 UUID를 보관한다.
- 오류 직후 요청을 자동 재생하지 않는다. 재로그인 또는 메인 메뉴 복귀 후 사용자가 다시 `2`를 선택해야만 보관한 같은 UUID로 재시도한다.
- 비재시도 오류에서는 보관한 UUID를 지운다. 다음 명시적 생성은 새 UUID를 사용한다.

제안 화면은 제목·요약·결정 상태·전체 기간·총 과제 수·생성 메타데이터, 요청 window, 이전/다음 페이지 가능 여부, 전체 milestone과 현재 window의 날짜별 task를 표시한다.

| 명령 | 동작 |
| --- | --- |
| `/next` | 다음 window 조회 |
| `/prev` | 이전 window 조회 |
| `/date YYYY-MM-DD` | 지정 날짜부터 조회 |
| `/accept` | 현재 pending 제안 수락 |
| `/reject` | 현재 pending 제안 거절 |
| `/back` | 메인 메뉴로 복귀 |
| `/help` | 제안 화면 도움말 |
| `/quit` | 정상 종료 |

window 조회는 `GET /api/v1/plan-proposals/{proposal_id}?start_on=YYYY-MM-DD&days=7`을 사용한다. `/date`는 정확한 `YYYY-MM-DD` 확장 형식만 허용한다. `/prev`의 시작일은 `requested_start_on - days`와 전체 제안 `starts_on` 중 늦은 날짜로 고정하므로, 시작일 직후의 짧은 이전 구간도 범위 밖 요청 없이 표시한다.

수락과 거절은 각각 `POST /api/v1/plan-proposals/{proposal_id}/accept`, `POST /api/v1/plan-proposals/{proposal_id}/reject`이고 body는 없다. 수락 POST 응답만으로 성공을 표시하지 않는다. 이어서 `GET /api/v1/plans/active?days=7`을 호출하고, 조회된 계획의 proposal linkage와 고정 요약 필드가 선택한 제안과 정확히 일치할 때만 수락 완료를 표시하고 계획 화면으로 이동한다. POST 뒤 GET 또는 일치 검증이 실패하면 성공을 표시하지 않고, 실패한 수락을 자동 재생하지 않는다.

### 3. 활성 로드맵

`GET /api/v1/plans/active?days=7`로 활성 계획을 연다. 화면은 계획 상태·전체 기간·완료 수·floor 백분율·누적 EXP, 생성 및 lifecycle 메타데이터, 요청 window, 페이지 가능 여부, 전체 milestone, 현재 window 날짜별 task 진행·달성 상태·획득 EXP와 task 상태를 표시한다.

| 명령 | 동작 |
| --- | --- |
| `/today` | 오늘을 계획 범위에 맞춰 조회 |
| `/next` | 다음 window 조회 |
| `/prev` | 이전 window 조회 |
| `/date YYYY-MM-DD` | 지정 날짜부터 조회 |
| `/done N` | 화면 번호 `N`의 task를 `completed`로 변경 |
| `/undo N` | 화면 번호 `N`의 task를 `pending`으로 변경 |
| `/finish` | 모든 task가 끝난 계획을 완료 |
| `/back` | 메인 메뉴로 복귀 |
| `/help` | 계획 화면 도움말 |
| `/quit` | 정상 종료 |

window 조회는 `GET /api/v1/plans/{plan_id}?start_on=YYYY-MM-DD&days=7`을 사용한다. `/date`는 정확한 `YYYY-MM-DD` 확장 형식만 허용하고, `/prev`는 이전 시작일이 전체 계획 `starts_on`보다 앞서지 않도록 clamp한다.

task 변경은 `PATCH /api/v1/plans/{plan_id}/tasks/{task_id}`에 `{"status":"completed"}` 또는 `{"status":"pending"}`를 보낸다. `earned_exp`는 해당 날짜가 현재 보유한 `0|20` EXP이고 `exp_delta`는 이번 PATCH가 누적값에 반영한 `-20|0|20` 변화량이다. CLI는 PATCH 응답을 보관하지만 그 응답만으로 화면이나 EXP 안내를 갱신하지 않는다. 이어서 `GET /api/v1/plans/{plan_id}?start_on=<현재 requested_start_on>&days=7`로 같은 plan/window를 다시 읽고, task 상태·plan/day 집계·달성 상태·획득 EXP·누적 EXP가 PATCH 응답과 정확히 일치할 때만 `일일 목표 달성 · +20 EXP` 또는 `일일 목표 달성 취소 · -20 EXP`와 최신 누적 EXP를 안내한다. `exp_delta=0`이면 달성/취소 안내를 만들지 않는다.

재조회가 실패하면 계획 화면은 조회 갱신 필요 상태로 유지하고 이전 번호 매핑을 폐기한다. 이후 `/done`, `/undo`, `/finish`는 차단하며, `/today`, `/date` 또는 가능한 `/next`, `/prev` 조회가 성공해 상태와 번호 매핑을 새로 만들 때까지 stale 번호로 mutation을 받거나 성공한 PATCH를 자동 재생하지 않는다. 재조회는 성공했지만 PATCH 응답과 canonical plan이 불일치하면 최신 plan은 표시하되 EXP 성공 안내 대신 검증 실패를 알린다. 계획 완료는 `POST /api/v1/plans/{plan_id}/complete`를 사용한다.

`N`은 매번 표시한 window에서 새로 부여한 사용자용 번호다. CLI는 서버 task UUID와 번호의 명시적 매핑만 사용하며, 목록 index·날짜·slot에서 번호를 추론하지 않는다. 서버 UUID는 `/done`, `/undo`의 사용자 입력 label로 표시하지 않는다. 새 window 또는 mutation 뒤 canonical 재조회를 성공적으로 읽을 때마다 매핑도 새로 만든다.

### 4. 내 로드맵 완료율 요약

`GET /api/v1/plans/summary`로 현재 사용자가 소유한 모든 로드맵의 완료율과 계정 통합 완료율을 조회한다. 로드맵이 없으면 빈 상태 안내를 출력하고 메인 메뉴로 돌아간다.

화면에는 통합 요약(로드맵 수, 전체 과제 완료 수, 통합 완료율, 누적 EXP)과 로드맵별 표(번호, 제목, 상태, 기간, 일수, 완료/전체 과제 수, 완료율, 활성화 시각, 종료 시각)를 표시한다. 완료율은 `completed_task_count * 100 // total_task_count` 정수 백분율이며, `total_task_count = 0`인 plan은 `0%`로 표시한다. 읽기 전용 화면이므로 별도 명령 없이 출력 후 메인 메뉴로 돌아간다.

### 5. 오늘 퀘스트

`GET /api/v1/quests/today`로 KST 오늘 기준 활성 계획의 task를 조회한다. 활성 계획이 없거나 오늘이 계획 범위 밖이면 plan 정보가 비고 집계가 0인 빈 상태를 출력하고 메인 메뉴로 돌아간다.

활성 계획이 있으면 계획 제목, 날짜, 완료 수, 백분율, 일일 달성 여부, 획득 EXP, 누적 EXP와 오늘 과제 표를 표시한다.

| 명령 | 동작 |
| --- | --- |
| `/done N` | 화면 번호 `N`의 과제를 `completed`로 변경 |
| `/undo N` | 화면 번호 `N`의 과제를 `pending`으로 변경 |
| `/back` | 메인 메뉴로 복귀 |
| `/help` | 오늘 퀘스트 도움말 |
| `/quit` | 정상 종료 |

task 변경은 `PATCH /api/v1/quests/{task_id}`에 `{"status":"completed"}` 또는 `{"status":"pending"}`를 보낸다. 미존재·비소유·과거·미래 task는 모두 `404 TODAY_QUEST_NOT_FOUND`로 통일된다. `earned_exp`는 해당 날짜가 현재 보유한 `0|20` EXP이고 `exp_delta`는 이번 PATCH가 누적값에 반영한 `-20|0|20` 변화량이다. CLI는 PATCH 응답만으로 화면이나 EXP 안내를 갱신하지 않고 이어서 `GET /api/v1/quests/today`로 다시 읽어와 task 상태·집계·달성 여부·EXP가 PATCH 응답과 정확히 일치할 때만 `일일 목표 달성 · +20 EXP` 또는 `일일 목표 달성 취소 · -20 EXP`와 최신 누적 EXP를 안내한다. `exp_delta=0`이면 달성/취소 안내를 만들지 않는다.

`N`은 매번 표시한 화면에서 새로 부여한 사용자용 번호다. CLI는 서버 task UUID와 번호의 명시적 매핑만 사용하며, 목록 index·날짜·slot에서 번호를 추론하지 않는다. 서버 UUID는 `/done`, `/undo`의 사용자 입력 label로 표시하지 않는다. 재조회를 성공적으로 읽을 때마다 매핑도 새로 만든다.

### 6. 전체 채용 공고

`GET /api/v1/saved-jobs`로 모든 인증 사용자가 공유하는 전체 공고를 조회한다. API 명세에 pagination과 상세 endpoint가 없으므로 CLI도 응답 전체를 최신 저장 순서 그대로 한 화면에 표시한다. 표시 항목은 번호, 회사명, 직무명, 마감일, 입력 출처와 지원 URL이며, 공고가 없으면 빈 상태 안내를 출력하고 메인 메뉴로 돌아간다.

### 7. 온보딩 기반 추천 공고

`GET /api/v1/saved-jobs/recommendation`로 온보딩 전체 프로필과 가장 가까운 유효 공고를 추천받는다. 추천이 없으면 빈 상태를 안내하고 메인 메뉴로 돌아간다. 추천이 있으면 일치도, 일치 단서, 판단 방식, 추천 이유와 공고를 출력하고 해당 공고를 로드맵 대상으로 선택할지 `y/n`으로 확인한다.

### 8. 공지 사항

`GET /api/v1/notices`로 현재 게시 중인 공지를 조회한다. `is_pinned` 여부, 제목, 게시 시각, 내용, 만료 시각을 항목별로 표시하며, 게시 중인 공지가 없으면 빈 상태 안내를 출력하고 메인 메뉴로 돌아간다. v1은 페이지네이션과 읽음 상태를 제공하지 않으므로 응답 전체를 한 화면에 표시한다.

### 9. 프로필 재온보딩

재온보딩을 시작하기 전에 pending 제안을 조회한다. pending 제안이 있으면 임의로 버리지 않고 사용자에게 먼저 보여준 뒤 명시적인 거절 확인을 받는다. 확인된 경우에만 reject API를 호출하고 온보딩을 시작한다. 사용자가 거절하지 않으면 pending 제안과 현재 프로필을 그대로 유지하고 메인 메뉴로 돌아간다.

### 10. 다른 계정으로 로그인

로컬 메모리에 있는 access token과 현재 사용자 범위로 보관한 proposal 생성 `request_id`만 지우고 로그인 화면으로 돌아간다. logout endpoint 호출, 서버 세션 삭제, 프로필·제안·계획 변경 같은 원격 mutation은 수행하지 않는다.

### 11. AI 취업 코치 상담

`POST /api/v1/assistant/sessions`로 완료 프로필과 비서 스타일을 고정한 상담 세션을 시작한다. 시작 응답의 `session_id`와 `revision=0`을 보관하고 코치의 첫 인사를 표시한다.

일반 입력은 `POST /api/v1/assistant/sessions/{session_id}/messages`로 보내며, 마지막 성공 응답의 revision을 `expected_revision`으로 사용한다. 성공 응답은 revision이 정확히 1 증가하고 같은 session ID인지 확인한 뒤 표시한다. 공고와 일정의 DB 사실은 서버가 만든 `assistant_message`만 리터럴 텍스트로 표시하고 내부 `tool_results` 원문은 출력하지 않는다.

활성 상담은 생성 또는 마지막 사용자 입력 접수 후 45초가 지나면 종료된다. 입력 접수 때마다 유휴 기한은 45초 뒤로 갱신되지만 응답의 24시간 절대 `expires_at`은 바뀌지 않는다. `ASSISTANT_SESSION_EXPIRED`를 받으면 현재 상담을 종료하고 새 상담을 시작하도록 안내한다. 유휴 종료만으로 보고서는 자동 생성되지 않는다.

| 명령 | 동작 |
| --- | --- |
| `/finish` | 한 번 이상 메시지를 보낸 상담을 종료하고 구조화 보고서 저장 |
| `/help` | 상담 화면 도움말 |
| `/quit` | 보고서를 만들지 않고 CLI 종료 |

`/finish`는 `POST /api/v1/assistant/sessions/{session_id}/finalize`에 마지막 revision을 보내며, 최초 `201`과 durable replay `200`을 모두 성공으로 처리한다. 성공하면 보고서 ID, 요약, 강점, 보완점, 우선 행동만 출력하고 메인 메뉴로 돌아간다. 메시지가 아직 없으면 finalize API를 호출하지 않고 먼저 상담 내용을 입력하도록 안내한다. 상담 화면에서 정의되지 않은 슬래시 명령은 API로 보내지 않는다.

## 4. 확인, 인증 만료와 재시도 안전 규칙

사용자 의사와 서버 상태를 바꾸는 다음 동작은 401 뒤 재로그인했다고 자동 재생하지 않는다.

- 제안 `/accept`, `/reject`
- 계획 `/done N`, `/undo N`, `/finish`
- 오늘 퀘스트 `/done N`, `/undo N`
- 코치 상담 메시지와 `/finish`
- 온보딩 시작과 review `/confirm`, `/restart`
- 로그인 알림의 명시적 확인 PATCH

일반 보호 API에서 401 또는 `UNAUTHORIZED`가 발생하면 로컬 access token을 지우고 친화적인 안내 뒤 로그인 화면으로 돌아간다. 로그인 직후 best-effort 알림 feed/확인 요청만 예외이며, 이 단계의 401은 경고 후 프로필 조회를 계속한다. 로그인 성공 후에는 실패했던 mutation을 자동으로 재생하지 않는다. proposal 생성 중 401일 때만 보관된 `request_id`를 유지하며, 이 경우에도 사용자가 메인 메뉴에서 다시 `2`를 선택하고 생성 확인에 동의해야 같은 UUID로 요청한다. 사용자가 메뉴 `10`으로 계정을 직접 전환하면 이 UUID도 지운다.

온보딩 확정이 이미 성공하고 프로필 재검증만 남은 상태라면 401 뒤 재로그인 후 `GET /api/v1/profile`만 계속한다. 확정 mutation 자체는 다시 보내지 않는다.

HTTP client는 온보딩 start/message/confirm/restart, 코치 상담 start/message/finalize, 제안 생성의 `CLIENT_TIMEOUT` 또는 `CLIENT_NETWORK_ERROR`에 한해 같은 `request_id`와 payload로 한 번 transport 재시도한다. 그 재시도까지 실패해 오류가 CLI 흐름으로 돌아온 뒤에는 자동으로 반복하지 않는다. accept/reject, task 상태 변경, 계획 완료는 client의 자동 transport 재시도 대상이 아니다.

## 5. 출력과 비밀정보 안전

- 비밀번호, JWT/access token, API key, Authorization header를 출력하지 않는다.
- provider 원본 응답, 내부 Redis key/checkpoint, SQL·서버 raw error/detail을 출력하지 않는다.
- 서버 오류는 allow-list된 한국어 메시지로 바꿔 표시한다.
- 프로필·제안·milestone·task·서버 메시지처럼 동적인 문자열은 Rich markup으로 해석하지 않고 `rich.text.Text`의 리터럴 텍스트로 출력한다.
- 로그인 알림·제안·계획·코치 상담·상담 보고서 화면은 API view의 허용된 필드만 표시한다.

## 6. 종료 코드와 터미널

| 코드 | 조건 |
| --- | --- |
| `0` | `0`, `/quit`, EOF(`Ctrl+D`) |
| `130` | `Ctrl+C`/`SIGINT` |

EOF와 Ctrl-C에서도 HTTP client를 닫는다. Ctrl-C가 숨김 비밀번호 입력 중 발생하면 터미널 echo 상태를 복구하고 traceback 없이 `130`으로 끝낸다.

## 7. API 경로 요약

| 목적 | 요청 |
| --- | --- |
| 회원가입 | `POST /api/v1/auth/signup` |
| 로그인 | `POST /api/v1/auth/login` |
| 로그인 알림 동기화·조회 | `POST /api/v1/notifications/login-feed` |
| 선택 알림 확인 | `PATCH /api/v1/notifications/{notification_id}/read` |
| 프로필 조회 | `GET /api/v1/profile` |
| 전체 채용 공고 | `GET /api/v1/saved-jobs` |
| 희망 환경 맞춤 공고 | `GET /api/v1/saved-jobs/recommendation` |
| 코치 상담 시작 | `POST /api/v1/assistant/sessions` |
| 코치 메시지 | `POST /api/v1/assistant/sessions/{session_id}/messages` |
| 코치 상담 종료·보고서 저장 | `POST /api/v1/assistant/sessions/{session_id}/finalize` |
| 온보딩 시작 | `POST /api/v1/onboarding/sessions` |
| 온보딩 대화·재시작 | `POST /api/v1/onboarding/sessions/{session_id}/messages` |
| review snapshot 조회 | `GET /api/v1/onboarding/sessions/{session_id}/result` |
| review 확정 저장 | `POST /api/v1/onboarding/sessions/{session_id}/confirm` |
| 제안 생성 | `POST /api/v1/plan-proposals` |
| pending 제안 | `GET /api/v1/plan-proposals/pending?start_on=YYYY-MM-DD&days=7` |
| 특정 제안 | `GET /api/v1/plan-proposals/{proposal_id}?start_on=YYYY-MM-DD&days=7` |
| 제안 수락·거절 | `POST /api/v1/plan-proposals/{proposal_id}/accept`, `POST /api/v1/plan-proposals/{proposal_id}/reject` |
| 활성 계획 | `GET /api/v1/plans/active?start_on=YYYY-MM-DD&days=7` |
| 내 로드맵 완료율 요약 | `GET /api/v1/plans/summary` |
| 특정 계획 | `GET /api/v1/plans/{plan_id}?start_on=YYYY-MM-DD&days=7` |
| task 상태 변경 | `PATCH /api/v1/plans/{plan_id}/tasks/{task_id}` |
| 계획 완료 | `POST /api/v1/plans/{plan_id}/complete` |
| 오늘 퀘스트 조회 | `GET /api/v1/quests/today` |
| 오늘 퀘스트 상태 변경 | `PATCH /api/v1/quests/{task_id}` |
| 공지 사항 | `GET /api/v1/notices` |

`start_on`은 선택 query이고 `days`는 1~28, CLI 기본값은 7이다. 응답의 `requested_start_on`, `requested_end_on`, `has_previous`, `has_next`를 화면 이동의 기준으로 사용한다.

## 8. 환경과 제한

- CLI 기본 백엔드 주소: `https://aio-01-p1-team2-1.onrender.com`
- HTTP timeout: 전체 응답 300초, connect 10초
- CLI 자체에는 backend 주소 인자가 없으며, 로컬 연결은 `BACKEND_BASE_URL=http://127.0.0.1:8010` 환경 변수로 덮어쓴다.
- backend 및 `create-demo-user` 설정은 `backend_user/.env.example`과 [`README.md`](../README.md)를 따른다.
- fresh DB는 `sql/07_notifications.sql`, 기존 DB는 관리자 migration role로 재실행 가능한 `sql/22_notifications_login_roadmap.sql`이 적용돼 있어야 한다. `supabase db push`를 전제로 하지 않는다.
