# Gemini 자유대화 온보딩 구현 설계

## 현재 범위

이 문서는 AI 취업 코치 시연의 `login_id` 기반 가입/로그인 → Gemini 자유대화 → 프로필 review/수정 → confirm → Supabase 재조회 흐름을 정의한다. 클라이언트는 Rich 기반 인터랙티브 CLI, API는 FastAPI, 임시 상태는 Redis, 확정 데이터는 Supabase PostgreSQL에 둔다.

가입과 로그인은 구현 범위다. Refresh token rotate·logout·공고·로드맵·일정·알림 기능은 이번 범위에서 제외한다.

## 사용자 흐름

```text
가입 또는 로그인
→ 기존 프로필 우선 조회
→ 없으면 Gemini 첫 질문
→ 자유대화에서 8개 프로필 필드 수집
→ Gemini rubric 평가 + 서버 총점/등급
→ 사용자 review와 자연어 수정
→ 표시한 동일 revision confirm
→ profile/ai_result 단일 트랜잭션 저장
→ /profile 재조회 snapshot 검증
→ 종료·재로그인 후 동일 프로필 표시
```

수집 필드는 목표 직무, 기술, 경험, 목표일, 희망 기업, 희망 환경, 일일 알림 시각, 비서 스타일이다. `target_company=null`은 사용자가 희망 기업이 없다고 명시한 답변이며 미응답과 다르다.

## Gemini 경계

- `google-genai==2.17.0`
- 전 구간 `gemini-3.6-flash`
- 안정 API `v1` Interactions API
- `store=false`, `previous_interaction_id` 미사용
- Redis transcript를 매 호출 재전달
- 대화 `thinking_level=low`, 평가 `thinking_level=medium`
- temperature/top-p/top-k 미전송
- Pydantic JSON Schema를 system instruction과 함께 매 호출 재전달
- 구조 검증 실패 시 오류 내용을 포함한 repair 1회
- SDK retry 1 attempt, 논리 요청 전체 최대 provider 호출 2회
- 실제 모드에서 규칙 기반 평가로 fallback하지 않음

대화 응답은 assistant message, typed field updates, 사용자 turn ID·원문 인용 evidence, next focus를 반환한다. 서버는 evidence turn이 실제 사용자 발화인지, 인용문이 발화에 포함되는지, 기존 필드 변경이 최신 사용자 수정에 근거하는지 검증한다. review 진입과 missing fields는 서버가 계산한다.

## 평가 책임

Gemini는 기술 준비도 0~30, 경험 깊이 0~30, 목표 명확성 0~20, 실행 준비도 0~20과 각 근거를 생성한다. 서버는 점수를 합산하고 다음 등급을 계산한다.

- 0~39: beginner
- 40~74: intermediate
- 75~100: advanced

이는 취업 가능성 예측이 아니라 제공된 정보의 현재 준비도 평가다. provider/model/prompt/rubric/schema 버전과 시스템 metadata는 서버가 기록한다.

## 상태와 멱등성

Redis key는 `onboarding:v2:{user_id}:{session_id}`, TTL은 30분이다. phase, transcript, draft, answered/missing fields, draft revision, assessment, processed requests를 저장한다. 사용자 발화는 최대 12개, 각 4,000자다.

시작을 포함한 모든 상태 변경 POST는 UUID request ID를 받는다. `{text, action, expected_revision}` canonical JSON의 SHA-256 fingerprint를 비교해 동일 재시도는 캐시 응답을 반환하고 다른 payload 재사용은 409로 거부한다. provider나 평가 실패 전에는 state를 저장하지 않는다.

restart는 새 Gemini 첫 질문이 성공한 뒤에만 기존 대화/draft/평가를 초기화한다. confirm은 Gemini를 호출하지 않고 CLI 출력에 표시한 `expected_revision`과 현재 revision이 같을 때만 저장한다.

## PostgreSQL

confirm 트랜잭션은 다음 순서다.

1. canonical profile/assessment/revision snapshot의 SHA-256을 계산한다.
2. `ai_results(kind=profile_assessment)`를 request ID 멱등 INSERT한다.
3. 반환 ID를 `profiles.assessment_result_id`에 넣어 UPSERT한다.
4. 중복 request ID면 기존 snapshot hash를 비교해 같을 때만 저장 프로필을 반환한다.

`profiles(user_id, assessment_result_id)`는 `ai_results(user_id, id)` 복합 FK로 같은 사용자 소유를 강제한다. `ai_results.content`는 schema version, profile snapshot, assessment, draft revision, snapshot hash를 필수로 가진다. 전체 transcript와 raw provider step은 PostgreSQL에 저장하지 않는다.

깨끗한 bootstrap은 SQL 02/06/08에 계약이 포함되고, 기존 TP_dev는 `10_profile_assessment_link.sql`을 migration 관리자 권한으로 적용한다. runtime `app_api`에는 DDL 권한을 주지 않는다.

## API와 CLI

온보딩 응답 step은 `conversation`, `review`, `completed`다. payload는 revision, draft, answered/missing fields, assessment와 실제 engine 정보를 포함한다.

`app/cli/api.py`의 `CoachApiClient`는 로그인·프로필·온보딩 API를 호출하고 timeout/network 오류에서 같은 request ID로 한 번 재시도한다. `app/cli/app.py`의 `CliApp`은 ID 일반 프롬프트와 비밀번호 숨김 프롬프트, 단계별 명령, 재로그인, 종료 코드를 제어한다. `app/cli/renderer.py`의 `RichRenderer`는 터미널에 provider/model, `N/8`, draft/누락 항목, spinner와 review 준비도 평가 표를 렌더링한다.

`/help`와 `/quit`은 모든 단계에서 사용할 수 있고, `/confirm`과 `/restart`는 review에서만 사용한다. review의 일반 문장은 자연어 수정 요청으로 API에 보낸다. 기존 프로필은 로그인 뒤 즉시 출력하고 종료한다. 인증 또는 세션이 만료되면 로그인부터 다시 시작한다. EOF는 `0`, `Ctrl+C`는 `130`으로 종료한다.

confirm은 직전에 복사한 review payload를 기준으로 completed 응답과 `/profile` 재조회 결과를 모두 대조한다. 프로필 8개 필드, 평가, revision, assessment result ID, provider/model, prompt/rubric 버전, 64자 snapshot hash가 모두 연결·일치해야 검증 완료를 출력한다. 비밀번호, token, API key, provider raw response를 표시하지 않는다.

## 검증 기준

- Gemini adapter의 v1/store=false/model/schema/system instruction/retry/timeout/error mapping
- 다중 필드 추출, evidence 검증, KST 날짜, missing fields
- review 수정·revision·재평가와 점수 등급 경계
- confirm 전 DB 미저장, confirm snapshot 동일성
- request 멱등성, provider 실패 state 불변
- ai_result/profile 단일 트랜잭션, 복합 FK와 snapshot 충돌
- scripted input·fake API·Rich output recorder 기반 CLI 로그인/404/대화/spinner/review 자연어 수정/`/confirm`/DB 재조회/기존 프로필/오류 경로
- 실제 PTY `Ctrl+C` 종료 코드 `130`, EOF `0`, 단계별 명령과 인증·세션 만료 재로그인
- 기본 suite는 외부 호출 없음; `RUN_LIVE_GEMINI=1`에서만 실제 Gemini 호출
