# AI_JOB_COACH 미니 프로젝트 개발 계획서

## 1. 프로젝트 개요

AI_JOB_COACH는 사용자의 현재 역량과 취업 목표를 대화로 파악하고, 목표 기간 안에 취업 준비를 완료할 수 있도록 개인화된 로드맵과 매일 할 일을 제안하는 취업 준비 코칭 서비스다. 사용자는 관심 취업 공고를 AI 비서에게 입력하고, 제안된 변경 사항을 검토·승인한 뒤에만 자신의 로드맵과 할 일을 갱신한다.

### 핵심 가치

- 처음 대화만으로 목표 직무, 희망 기간, 현재 역량을 수집하고 초기 레벨을 산정한다.
- 예: “3개월 안에 백엔드 개발자로 취업”이라는 목표에 맞춰 완료 시 100%가 되는 로드맵을 제공한다.
- 오늘 해야 할 일을 명확히 보여 주고, 완료 기록으로 진행률·레벨을 갱신한다.
- 공고 요구 역량을 사용자의 기존 계획과 비교하여, **사용자가 승인한 경우에만** 계획을 업데이트한다.
- 목표 기간이 끝나도 이력·완료 기록·종료된 로드맵을 보존하며, 재시작 여부를 안내한다.
- 관리자는 별도 프론트엔드에서 사용자, 공고 분석, 로드맵 템플릿, 운영 현황을 관리한다.

## 2. 범위와 사용자 흐름

### 2.1 사용자 핵심 흐름

```text
회원가입/로그인
  → 첫 질문(비서와 대화, 목표·기간·경험·역량 파악)
  → 프로필 및 초기 레벨 확정
  → 개인 로드맵 생성
  → 매일 할 일 확인·완료
  → 레벨/진행률 갱신
  → 공고 입력·분석
  → 변경안 확인 및 사용자 승인
  → 로드맵/할 일 업데이트
  → 목표 기간 종료
  → 데이터 보존 + 재시작 안내
```

### 2.2 역할

| 역할 | 주요 권한 |
|---|---|
| 일반 사용자 | 본인 프로필, 로드맵, 할 일, 공고 분석·승인, 종료·재시작 관리 |
| 관리자 | 사용자 조회/상태 관리, 공고 분석 모니터링, 로드맵 템플릿·공지 관리, 운영 통계 조회 |

## 3. 기능 요구사항

### 3.1 인증 및 온보딩

- 이메일·비밀번호 기반 회원가입, 로그인, 로그아웃, 토큰 재발급을 제공한다.
- 중복 이메일, 약한 비밀번호, 미인증/만료 토큰을 안전하게 처리한다.
- 로그인 직후 온보딩 완료 여부를 확인한다. 미완료 사용자는 첫 질문 화면으로 이동한다.
- 첫 질문은 AI 비서 형태로 진행하며 최소한 목표 직무, 취업 목표일 또는 기간, 경험 수준, 보유 기술, 학습 가능 시간, 관심 공고/산업을 수집한다.
- 대화 결과는 사용자가 검토·수정한 뒤 확정하며, 확정값으로 프로필과 초기 레벨을 생성한다.

### 3.2 프로필 및 레벨 측정

- 프로필에는 목표 직무, 목표 기간, 경력 단계, 기술 스택, 주당 가능 시간, 포트폴리오·지원 현황을 저장한다.
- 초기 레벨은 온보딩 응답을 바탕으로 `입문/초급/중급/고급` 등 서비스 기준으로 산정하되, 산정 근거와 수정 기능을 제공한다.
- 레벨은 할 일 완료, 역량 검증, 로드맵 마일스톤 달성에 따라 변경할 수 있으며 변경 이력을 남긴다.

### 3.3 로드맵

- 목표 시작일·종료일, 직무, 초기 레벨, 가용 시간을 기반으로 주차별·단계별 로드맵을 생성한다.
- 모든 필수 항목을 계획대로 완료했을 때 목표 기간 종료 시점에 전체 진행률 100%가 되도록 작업 가중치와 일정을 배분한다.
- 사용자는 단계, 마일스톤, 예상 소요 시간, 진척도, 지연 여부를 확인한다.
- 로드맵은 활성/종료/보관 상태를 갖고, 종료 후에도 삭제하지 않는다.

### 3.4 매일 할 일

- 시스템은 활성 로드맵을 기준으로 오늘의 학습·프로젝트·지원·복습 과제를 생성한다.
- 사용자는 할 일을 완료, 건너뜀, 보류 처리하고 간단한 회고/증빙 링크를 남길 수 있다.
- 완료 시 진행률과 레벨 산정 데이터가 갱신된다. 과도한 재계산을 막기 위해 서버에서 일관되게 계산한다.
- 마감 임박, 누락된 할 일, 주간 마일스톤 상태를 알림으로 안내한다.

### 3.5 취업 공고 프롬프트 및 승인형 반영

- 사용자는 공고 URL, 원문, 또는 텍스트 요약을 입력한다.
- AI는 직무, 필수/우대 역량, 경력 요구, 핵심 키워드, 기존 프로필과의 적합도, 부족 역량을 추출한다.
- 시스템은 바로 로드맵을 변경하지 않고, 추가·수정·삭제할 로드맵 항목과 예상 일정 영향을 **변경 제안**으로 보여 준다.
- 사용자는 제안 전체를 승인/거절하거나 항목별로 선택한다.
- 승인된 항목만 새 로드맵 버전으로 반영하며, 기존 버전과 승인 이력을 보존한다. 거절된 제안은 사용자 계획에 반영하지 않는다.

### 3.6 기간 종료 및 재시작

- 목표 종료일이 지나면 활성 로드맵을 종료 처리하고, 완료율과 회고를 보여 준다.
- 완료율이 100%여도 종료된 데이터는 보존한다.
- “새 목표로 다시 시작하시겠습니까?” 메시지에서 재시작, 기존 계획 복제, 나중에 선택을 제공한다.
- 재시작하면 새 로드맵을 생성하되 이전 로드맵·할 일·공고·레벨 이력은 읽기 전용 보관 상태로 유지한다.

### 3.7 관리자 프론트엔드

- 관리자 로그인 및 역할 기반 접근 제어를 적용한다.
- 사용자 목록/상세, 온보딩 완료·활성·종료 상태, 목표 직무, 진행률을 조회한다.
- 공고 분석 요청, 승인율, 실패 건, 모델 응답 상태를 모니터링한다.
- 직무별 로드맵 템플릿, 과제 카탈로그, 공지/FAQ를 관리한다.
- 가입·활성 사용자·평균 완료율·공고 승인율·기간 종료/재시작 비율을 대시보드로 제공한다.

## 4. 화면 설계

### 4.1 화면 영역 분리

서비스는 **사용자 화면(User Web)** 과 **관리자 화면(Admin Web)** 을 명확히 분리하여 구현한다. 두 화면은 공통 디자인 토큰과 인증 기반은 공유할 수 있으나, 메뉴·라우팅·API 권한·배포 환경변수는 분리한다.

| 영역 | 접근 경로 예시 | 대상 | 목적 |
|---|---|---|---|
| 사용자 화면 | `/`, `/onboarding`, `/dashboard`, `/roadmaps`, `/tasks`, `/job-postings` | 일반 사용자 | 취업 준비, 개인 데이터 관리, 공고 승인 |
| 관리자 화면 | `/admin/login`, `/admin/dashboard`, `/admin/users`, `/admin/templates`, `/admin/job-postings` | `ADMIN` 권한 사용자 | 서비스 운영, 사용자·템플릿·분석 현황 관리 |

- 일반 사용자가 `/admin/*`에 접근하면 관리자 로그인 또는 권한 없음 화면을 표시한다.
- 관리자는 사용자 개인 기능을 대신 수정하지 않으며, 사용자 데이터 변경이 필요한 운영 행위는 감사 로그에 남긴다.
- 사용자 화면은 개인화·일일 실행 경험에 집중하고, 관리자 화면은 검색·필터·표·통계·운영 조치에 최적화한다.

### 4.2 제공된 화면 시안 반영 기준

본 계획의 프론트엔드 구현은 제공된 두 시안을 기준으로 한다. 관리자 화면은 밝은 운영 콘솔 스타일, 사용자 화면은 어두운 네온·픽셀아트 기반의 **JOB QUEST TERMINAL** 스타일을 유지한다. 기능을 추가할 때도 각 영역의 디자인 언어를 혼합하지 않는다.

| 구분 | 기준 시안 | 구현 원칙 |
|---|---|---|
| 관리자 화면 | `관리자 화면_네비게이션바_이벤트별.png` | 좌측 고정 사이드바, 상단 브레드크럼, 카드형 KPI, 표·검색·필터·페이지네이션, 목록→상세/편집 전환 |
| 사용자 화면 | `사용자 화면-1.png` | 다크 터미널, 네온 포인트 컬러(핑크·보라·그린), 픽셀 캐릭터/AI 비서, 레벨·EXP·진행률의 게이미피케이션 |

#### 관리자 화면 내비게이션 및 이벤트

관리자 사이드바는 시안의 흐름에 맞춰 `대시보드`, `사용자 관리`, `퀘스트 관리`, `로드맵 관리`, `취업공고 관리`, `공지사항 관리`, `통계/분석`, `시스템 설정`, `로그아웃`으로 구성한다.

| 메뉴/이벤트 | 목록 화면 | 상세·편집·연결 동작 |
|---|---|---|
| 대시보드 | 전체 사용자, 오늘 가입자, 활성 사용자, 월별 미션/공고 지표, 시스템 상태, 최근 가입 추이 | KPI 클릭 시 해당 필터 목록으로 이동 |
| 사용자 관리 | 이름·이메일 검색, 권한/상태 필터, 사용자 표, 페이지네이션 | 행 선택 시 프로필, 레벨·EXP, 보유 재화, 최근 활동·완료 퀘스트 상세 표시 |
| 퀘스트 관리 | 퀘스트 목록, 직무·상태 필터, 보상/EXP/기간 표시 | 추가·수정 화면에서 제목, 설명, 분류, 보상, 상태를 등록·저장 |
| 로드맵 관리 | 단계 순서, 단계명, 설명, 상태 목록 | 단계 추가/수정에서 직무·레벨·아이콘·정렬 순서·상태를 관리 |
| 취업공고 관리 | 회사·직무·마감일 검색, 상태 필터, 공고 목록 | 등록/편집에서 회사, 직무, 경력, 마감일, 원문/요약, 상태 관리 |
| 공지사항 관리 | 공지 목록, 등록일·조회수·상태 | 공지사항 작성/수정, 게시·비공개 전환 |
| 통계/분석 | 사용자 직무 분포, 가입 추이, 핵심 KPI | 기간 필터 및 지표별 상세 조회 |
| 시스템 설정 | 서비스명, AI 설정, 알림/메일, 파일 업로드 등 운영값 | 변경 전 검증·확인 후 저장, 변경 감사 로그 기록 |

관리자 공고 관리는 사용자가 입력한 공고 분석 내역을 모니터링하는 기능과, 운영자가 제공·관리하는 추천 공고 카탈로그를 구분해 표시한다. 사용자 승인 없이 개인 로드맵을 변경하는 관리 기능은 제공하지 않는다.

#### 사용자 화면의 화면 구성과 인터랙션

사용자 화면은 시안의 번호 흐름을 제품 여정으로 연결한다. 픽셀 캐릭터는 단순 장식이 아니라 AI 비서의 상태(안내, 격려, 분석 중, 완료)를 전달하는 피드백 요소로 사용한다.

| 시안 화면 | 서비스 기능 연결 | 핵심 인터랙션 |
|---|---|---|
| 01 로그인 | 회원가입/로그인 | 터미널형 입력폼, 로그인 유지, 회원가입 이동, 오류 메시지 |
| 02 AI 진단 대화 | 첫 질문·레벨 측정 | 대화형 질문, 진행 단계, 실시간 분석 노트, 목표 직무·기술·기간·희망 기업·학습 시간 수집 |
| 04 프로필 | 프로필·레벨 | 캐릭터, 목표·보유기술·경험·목표 기간, `LEVEL`, `EXP`, 진단 완료도, 프로필 수정 |
| 05 맞춤 로드맵 | 로드맵 | 주차 탭, 단계 진행률, 미션 상태(완료/진행 중/대기), 주차 완료 격려 |
| 06 오늘의 할 일 | 매일 할 일 | 체크박스, 예상 시간, 완료 보상 EXP, 오늘 보상·학습 추천, 완료 즉시 진행률 갱신 |
| 07 기업 & 공고 | 공고 탐색·분석 시작 | 추천/저장/지원 공고 탭, 공고 카드, 관심 표시, 상세 이동 |
| 08 공고 상세 | 공고 프롬프트·승인형 반영 | 공고 요구사항·기술 스택·마감일, 일정 등록, 저장, **로드맵 변경 제안 보기/승인**으로 연결 |
| 09 고민 상담소 | AI 취업 코치 상담 | 세션 시작, 대화형 진로·학습 조언, 공고 추천·활성 로드맵/일정 질의, 상담 종료 후 구조화 보고서 확인 |
| 10 서류 & 면접 지원 | 자기소개서·이력서·면접 지원 | 문서 유형별 초안·피드백·수정 이력, 직무/공고와 연결 |
| 11 AI 면접 연습 | 면접 연습 | 질문 제시, 음성/텍스트 답변, 타이머, 논리성·자신감·전달력 피드백 |
| 12 AI 비서 설정 | 비서 설정 | 차분한/팩폭 비서 모드 선택, 말투·알림 설정, 언제든 변경 가능 |

공고 상세 화면에는 시안의 `일정에 추가`와 `MY SCHEDULE`을 유지하고, 별도의 “AI 분석 결과/로드맵 변경 제안” 영역을 둔다. 이 영역은 `분석 중 → 제안 확인 → 항목별 선택 → 승인 또는 거절 → 반영 완료` 상태를 보여 주며, 승인 버튼을 누르기 전에는 기존 로드맵·오늘의 할 일을 변경하지 않는다.

#### 사용자 게이미피케이션 규칙

- `EXP`는 일일 할 일·로드맵 미션·면접 연습 완료 등 명확히 정의된 활동에만 부여한다. 보상량은 서버가 계산한다.
- `LEVEL`은 EXP와 핵심 역량 마일스톤을 조합해 계산하고, 프로필에서 다음 레벨까지의 진행도를 제공한다.
- 공고 저장, 일정 등록, 상담, 서류·면접 연습은 사용자 행동 이력으로 남기되, 개인 로드맵 반영은 공고 변경 제안의 명시적 승인 이후에만 수행한다.
- 네온 색상만으로 완료·경고 상태를 표현하지 않고 아이콘·텍스트·ARIA 레이블을 함께 제공한다.

| 구분 | 화면 | 주요 구성과 동작 |
|---|---|---|
| 사용자 | 회원가입/로그인 | 이메일, 비밀번호, 유효성 메시지, 로그인 상태 유지 |
| 사용자 | 첫 질문(온보딩 채팅) | AI 비서 대화, 진행 단계, 응답 수정, 프로필 확정 |
| 사용자 | 프로필 | 목표·역량·레벨·가용 시간 편집, 레벨 산정 근거, 이력 |
| 사용자 | 대시보드 | 오늘 할 일, 전체 진행률, 레벨, 임박 마일스톤, 최근 공고 제안 |
| 사용자 | 로드맵 | 단계/주차 타임라인, 진행률, 버전 비교, 보관 로드맵 열람 |
| 사용자 | 매일 할 일 | 오늘/예정/완료 목록, 완료·보류·증빙·회고 입력 |
| 사용자 | 공고 분석 | URL/텍스트 입력, 분석 결과, 적합도·갭, 로드맵 변경 제안 |
| 사용자 | 승인 검토 | 변경 전후 비교, 항목별 선택, 승인·거절·확인 모달 |
| 사용자 | 종료/재시작 | 종료 요약, 데이터 보존 안내, 새 목표/복제/나중에 선택 |
| 관리자 | 관리자 로그인 | 관리자 권한 인증 |
| 관리자 | 운영 대시보드 | 핵심 지표, 오류/분석 현황, 최근 활동 |
| 관리자 | 사용자 관리 | 검색·필터, 사용자 상세, 상태 관리 |
| 관리자 | 공고/제안 관리 | 분석 기록, 승인 상태, 실패 재시도/점검 |
| 관리자 | 템플릿 관리 | 직무별 로드맵·할 일 템플릿 CRUD, 게시 상태 |

공통 UX 원칙: 모바일·데스크톱 반응형, 로딩/빈 상태/오류 상태 제공, 파괴적 변경은 확인 모달 사용, 접근성(키보드 이동·명확한 레이블·색상 외 상태 표현)을 준수한다.

## 5. API 설계

### 5.1 공통 규칙

- Base URL: `http://<API_HOST>:8010/api/v1` (프론트 배포 시 동일 origin 또는 허용 목록 기반 reverse proxy 사용)
- 인증: `Authorization: Bearer <accessToken>`
- 성공 응답: 엔드포인트별 Pydantic 모델 JSON을 직접 반환한다. 별도 성공 envelope를 사용하지 않는다.
- 오류 응답: `{ error: { code, message, retryable, details } }` 형식을 사용한다.
- 날짜: 날짜는 `YYYY-MM-DD`, 시각은 시간대가 포함된 ISO-8601으로 처리하며 계획·목표일 기준 시간대는 Asia/Seoul(KST)이다.
- 멱등성: 온보딩 및 계획 제안 생성은 클라이언트 UUID `request_id`가 필수다. 네트워크 오류 또는 `retryable=true` 오류 재시도 때는 반드시 같은 본문과 같은 `request_id`를 재사용한다.
- 계획 조회 창: `start_on`, `days(1~28, 기본 7)`를 사용한다.
- 권한 오류는 존재 여부를 과도하게 노출하지 않으며, 관리 API는 `ADMIN` 역할만 허용한다.

### 5.2 사용자 API

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/auth/signup` | `login_id`, `login_pw`, `user_name` 가입 및 access/refresh token 발급 |
| POST | `/auth/login` | 로그인 및 access/refresh token 발급 |
| GET | `/auth/me` | JWT 기준 현재 사용자 ID·역할·세션 조회 |
| PATCH | `/auth/me` | 현재 계정의 `login_id` 또는 `user_name` 부분 수정 |
| DELETE | `/auth/me` | 현재 계정과 사용자 소유 데이터를 영구 삭제(204) |
| GET | `/profile` | 확정 프로필 및 준비도 평가 조회. 없으면 `404 PROFILE_NOT_FOUND` |
| GET | `/saved-jobs` | 모든 인증 사용자가 공유하는 공고 목록 조회(최신 등록순, 빈 목록은 `[]`) |
| GET | `/saved-jobs/recommendation` | 전체 프로필 기반 유효 공고 1건 추천; LLM 실패 시 키워드 대체, 공고가 없으면 `null` |
| POST | `/assistant/sessions` | 확정 프로필 snapshot 기반 AI 취업 코치 상담 시작 (`request_id`) |
| POST | `/assistant/sessions/{session_id}/messages` | 상담/공고 추천/활성 로드맵·일정 질의 (`request_id`, `expected_revision`) |
| POST | `/assistant/sessions/{session_id}/finalize` | 구조화 상담 보고서 확정 및 원문 대화 삭제 (`request_id`, `expected_revision`) |
| POST | `/onboarding/sessions` | `request_id`로 온보딩 세션·첫 질문 시작 |
| POST | `/onboarding/sessions/{session_id}/messages` | `request_id` + `text` 또는 `action`으로 답변·검토 수정·재시작 처리 |
| GET | `/onboarding/sessions/{session_id}/result` | review 단계의 서버 snapshot 조회 |
| POST | `/onboarding/sessions/{session_id}/confirm` | `request_id`, `expected_revision`으로 검토 결과 확정 |
| POST | `/plan-proposals` | 확정 프로필 또는 선택 공고(`saved_job_id`) 기반 계획 제안 생성 (`request_id`) |
| GET | `/plan-proposals/pending` | 대기 중 제안 조회 |
| GET | `/plan-proposals/{proposal_id}` | 제안 상세/일자 창 조회 |
| POST | `/plan-proposals/{proposal_id}/accept` | 제안 승인, 단일 트랜잭션으로 active 계획·일정 생성 |
| POST | `/plan-proposals/{proposal_id}/reject` | 제안 거절 및 이력 보존 |
| GET | `/plans/active` | 현재 활성 계획/마일스톤/일일 task 조회 |
| GET | `/plans/summary` | 모든 계획·통합 진행률·누적 EXP 요약 조회 |
| GET | `/plans/{plan_id}` | 활성·종료·보관 계획 조회 |
| PATCH | `/plans/{plan_id}/tasks/{task_id}` | `pending`/`completed` 전환 및 진행률 반환 |
| GET | `/quests/today` | KST 오늘 기준 활성 계획의 할 일·일일 달성·EXP 조회 |
| PATCH | `/quests/{task_id}` | 오늘의 할 일만 `pending`/`completed` 전환 |
| POST | `/plans/{plan_id}/complete` | 전체 task 완료 시 계획 종료·재시작 안내 상태 생성 |
| GET | `/notices` | 현재 게시 중인 공지 목록 조회(고정·게시일 순) |

### 5.3 관리자 API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/admin/dashboard` | 운영 지표 조회 |
| GET | `/admin/ai-logs/summary` | AI 요청량·오류율·평균 응답 시간 KPI |
| GET | `/admin/ai-logs` | AI 로그 목록(레벨·기간·엔드포인트 필터) |
| GET | `/admin/ai-logs/{id}` | AI 로그 상세 및 연결된 피드백 |
| GET | `/admin/users` | 사용자 검색·필터·목록 |
| GET/PATCH | `/admin/users/{id}` | 사용자 상세 및 상태 관리 |
| GET | `/admin/job-postings` | 공고 분석·승인 상태 조회 |
| POST | `/admin/job-postings/{id}/retry` | 실패 분석 재시도 |
| GET/POST | `/admin/roadmap-templates` | 로드맵 템플릿 목록/등록 |
| GET/PATCH/DELETE | `/admin/roadmap-templates/{id}` | 템플릿 상세/수정/비활성화 |
| GET | `/admin/task-templates` | 일일 과제 카탈로그 조회 |
| GET/POST | `/admin/quests` | 퀘스트 목록/등록 |
| GET/PATCH | `/admin/quests/{id}` | 퀘스트 상세/수정·활성화 |
| POST/PATCH | `/admin/notices` | 공지 관리 |

### 5.4 API_SPEC.md 반영 구현 규칙

- 이 문서의 사용자 API는 제공된 `API_SPEC.md`를 구현 기준으로 한다. 명세와 화면 기획의 API 이름이 충돌하면 API_SPEC.md의 경로·필드·상태 코드가 우선한다.
- access token은 JWT(HS256, 기본 30분), refresh token은 서버에 SHA-256 해시만 Redis에 저장하는 7일 토큰이다. 현재 명세에는 refresh·logout 엔드포인트가 없으므로 프론트는 access token 만료 시 로그인 화면으로 이동한다.
- 가입 ID는 `trim().casefold()` 정규화 후 4~50자의 `[a-z0-9._-]+`만 허용하고, 비밀번호는 8~128자, `user_name`은 trim 후 1~50자다. 로그인 5회 연속 실패 시 15분 잠금 처리한다.
- `PATCH /auth/me`는 `login_id`, `user_name` 중 하나 이상만 수정할 수 있으며 UUID·role·비밀번호는 변경할 수 없다. `DELETE /auth/me`는 refresh 세션을 먼저 제거한 뒤 프로필·계획/일정·AI 결과·알림·일일 달성 기록을 한 DB 트랜잭션으로 삭제한다. 공유 `saved_jobs`는 삭제하지 않으며, 성공한 클라이언트는 token·사용자 캐시를 즉시 지운다.
- 모든 Bearer API는 서명·만료뿐 아니라 DB의 현재 계정 존재·활성 상태도 확인한다. 비활성화·탈퇴된 계정의 기존 access token은 `401 UNAUTHORIZED`로 거부한다.
- 온보딩은 Redis에서 30분 TTL로 유지한다. `target_role`, `skills`, `experience_summary`, `target_date`, `target_company`, `preferred_environment`, `daily_notification_time`, `assistant_style`의 8개 필드를 수집한 후 review 단계에서만 확정한다.
- 준비도 평가는 기술 준비도 30점, 경험 깊이 30점, 목표 명확성 20점, 실행 준비도 20점으로 산정하며, `0~39 beginner`, `40~74 intermediate`, `75~100 advanced`를 사용한다.
- 계획 제안과 활성 계획은 사용자당 각각 pending 1개, active 1개만 허용한다. 승인 전 active 계획을 변경하지 않고, 승인 시 proposal/plan/schedule item을 하나의 DB 트랜잭션으로 갱신한다.
- 계획 진행률은 `completed_task_count * 100 // total_task_count`(내림)으로 백엔드에서 계산한다. task가 없는 경우 0으로 처리하며 프론트에서 직접 수정할 수 없다.
- `GET /plans/*`와 제안 조회는 1~28일의 날짜 창만 반환한다. 원본 Gemini 응답, 자격 증명, 원문 프롬프트, Redis checkpoint는 API 응답에 포함하지 않는다.
- `GET /saved-jobs`는 특정 사용자의 저장 목록이 아니라 모든 인증 사용자가 공통으로 조회하는 공고 카탈로그다. 최신 등록순으로 반환하며 v1에서는 pagination·공고 상세 API를 제공하지 않는다.
- `GET /saved-jobs/recommendation`은 목표 직무·기술·경험·목표일·희망 기업·희망 환경·알림 시각·비서 말투를 포함한 확정 프로필과 공고를 비교한다. 마감일이 지났거나 존재하지 않는 공고는 제외하고, 최신 공고 우선 최대 40건을 Gemini 후보로 전달한다.
- 추천 응답에는 `match_score(0~100)`, `matched_terms`, `reason`, `recommendation_source(llm|keyword_fallback)`, DB에서 다시 확인한 공고 데이터를 포함한다. Gemini 시간 초과·제한·공급자 오류·형식 검증 실패 시 희망 환경 키워드 방식으로 대체하며, 이 내부 오류를 사용자에게 노출하지 않는다.
- `POST /plan-proposals`는 선택 사항 `saved_job_id`를 받을 수 있다. 전달 시 해당 공고가 존재하고 마감되지 않았는지 검증한 뒤 공고 snapshot을 계획 생성의 입력·checkpoint·멱등성 범위에 고정한다. 없으면 기존 프로필 기반 생성 흐름을 사용한다.
- `GET /quests/today`와 `PATCH /quests/{task_id}`가 오늘의 할 일 화면의 실제 API다. 오늘(KST)·활성 계획 범위 밖의 task는 `TODAY_QUEST_NOT_FOUND`로 처리한다.
- 한 날짜의 모든 task를 처음 완료하면 `+20 EXP`, 완료를 취소해 날짜 달성이 해제되면 `-20 EXP`를 반영한다. 같은 상태 재요청과 이미 달성된 날짜 내부의 다른 task 변경은 EXP를 바꾸지 않는다.
- `GET /notices`는 로그인 사용자에게 현재 게시 중인 공지만 고정 여부·게시일·ID 순으로 반환하며, v1에서는 페이지네이션과 읽음 상태를 제공하지 않는다.
- `GET /plans/summary`는 active·completed·expired·superseded·rejected·draft 등 모든 내 계획을 생성일 내림차순으로 반환한다. 전체 task 수·완료 수·내림 진행률과 누적 `user_exp`를 함께 제공하며, 계획이 없으면 빈 배열과 0 지표를 반환한다.
- AI 취업 코치 상담은 온보딩과 별도 세션이다. 시작·메시지·종료 요청마다 UUID `request_id`를 사용하고, 메시지·종료 시에는 최근 성공 응답의 `revision`을 `expected_revision`으로 보낸다. 요청에 정의되지 않은 필드는 거부한다.
- 코치 세션 데이터는 생성 시점부터 최대 24시간 보관하며, 활성 상담은 생성 또는 마지막 사용자 입력 접수 후 120초에 종료된다. 사용자당 활성 세션은 최대 6개다. 성공한 사용자 메시지는 최대 20개, 사용자·AI 발화 합계는 40,000자, AI 응답은 12,000자를 넘을 수 없다.
- 코치 메시지는 일반 상담, 유효 공고 추천, 활성 로드맵/일정 조회를 지원한다. 공고 추천은 최대 1건, 일정 조회는 최대 28일 범위로 제한한다.
- `finalize`는 검증된 구조화 상담 보고서(JSONB, 세션당 1개·128KiB 이하)를 생성하고, 사용자 원문 대화는 삭제한다. 최초 성공은 201, 같은 멱등 요청 재전송은 200으로 동일 보고서를 반환하며 종료된 세션은 Redis tombstone으로 재사용을 막는다.
- 관리자·상담·서류·면접 API는 현재 사용자 API 명세의 범위 밖 확장 기능이다. 3일 MVP에서는 명세에 추가된 공고·오늘의 할 일·공지 API와 AI 로그 대시보드를 우선 구현하고, 나머지는 별도 OpenAPI 문서로 추가한 뒤 화면을 연결한다.

## 6. DB 설계

관계형 DB(MySQL 또는 PostgreSQL)를 기준으로 하며, PK는 UUID, 생성·수정 시각은 `created_at`, `updated_at`을 공통으로 둔다. 개인정보와 인증 정보는 분리하고, 중요 상태 변경은 이력 테이블로 추적한다.

### 6.1 API_SPEC.md 기준 MVP 물리 스키마

현재 구현의 DB 기준은 `app` 스키마의 아래 테이블이다. 아래 스키마가 사용자 인증·온보딩·계획의 실제 API와 연결되는 우선 모델이며, 이후 표의 퀘스트·상담·문서·면접·관리 기능은 확장 설계로 취급한다.

| 테이블 | 핵심 필드와 제약 |
|---|---|
| `user_accounts` | `id` UUID PK, `role(user/admin)`, `login_id`, `user_name`, `password_hash`, 누적 `user_exp`, `last_login_at`, `failed_login_count`, `locked_until`, `is_active`; `lower(login_id)` 유일, 일반 가입에서 role/EXP 입력 금지 |
| `profiles` | `user_id` PK/FK, 목표 직무·기술 배열·경험·목표일·희망 기업·환경·알림 시각·비서 말투, 준비도 평가/버전/snapshot hash, 온보딩 완료 시각 |
| `saved_jobs` | 모든 인증 사용자가 공유해 조회하는 공고 카탈로그. 원문/추출 결과·마감일·출처를 보관하며 사용자별 필터나 `(user_id, source_key)` 제약을 두지 않는다. |
| `plans` | 사용자별 계획, 출처 proposal·profile hash·assessment ID·선택 공고 snapshot, 제목·기간·상태·진행률·재시작 안내 상태; 사용자당 active 1개 partial unique index |
| `schedule_items` | `plan_id`·선택적 `saved_job_id`, milestone/task/interview 종류, 예정/완료 시각·상태·metadata; 사용자·부모 리소스 소유권을 복합 FK로 검증. 날짜별 모든 progress task 완료 여부·달성 시각·EXP를 트랜잭션으로 계산한다. |
| `ai_results` | 온보딩 평가·계획 제안·문서/면접 결과; proposal hash, profile/선택 공고 snapshot, model/prompt 버전, request ID 및 applied plan 연결; 사용자별 pending proposal 1개 제약 |
| `assistant_sessions` | 사용자 ID·확정 프로필 snapshot·revision·생성/만료 시각·상태·멱등성 cache key; 데이터 보관 상한 24시간, 120초 유휴 종료, 사용자별 활성 세션 6개 이하 |
| `assistant_reports` | 세션당 1개 불변 구조화 상담 보고서(JSONB, 128KiB 이하), 상태 `VALIDATED` 강제, 생성 후 원문 대화 삭제 및 tombstone 기록 |
| `assistant_tombstones` | 종료/만료 세션 식별자와 보고서 재전송 정보. 종료된 세션의 메시지 재사용·중복 보고서 생성을 차단 |
| `ai_logs` / `ai_feedbacks` | 실제 AI 호출의 request ID·상태·latency·오류 및 사용자 평가. 비밀번호·API 키·원문 민감 프롬프트는 저장 금지 |

`password_hash`는 Argon2id 해시만 저장하고 API/로그/에러 응답에서는 제외한다. Streamlit은 DB에 직접 접근하지 않으며, FastAPI의 JWT `sub`로 사용자 범위를 강제한다.

| 테이블 | 핵심 컬럼 | 설명 |
|---|---|---|
| users | id, email, password_hash, role, status, last_login_at | 계정·권한·활성 상태 |
| refresh_tokens | id, user_id, token_hash, expires_at, revoked_at | 세션/토큰 관리 |
| user_profiles | user_id, target_job, career_level, weekly_hours, skills_json, target_date, onboarding_status | 사용자 목표와 역량 |
| onboarding_conversations | id, user_id, status, summary, initial_level, confirmed_at | 첫 질문 대화 세션 |
| onboarding_messages | id, conversation_id, sender, content, sequence | 온보딩 대화 메시지 |
| level_histories | id, user_id, level, score, reason, source_type, source_id | 레벨 변화 및 근거 |
| roadmaps | id, user_id, parent_roadmap_id, version, title, status, start_date, end_date, progress_percent, closed_at | 활성·종료·복제 로드맵 |
| roadmap_phases | id, roadmap_id, sequence, title, weight, start_date, end_date, status | 단계별 계획과 가중치 |
| roadmap_items | id, phase_id, title, type, weight, estimated_hours, due_date, status | 학습/프로젝트/지원 단위 항목 |
| daily_tasks | id, user_id, roadmap_item_id, task_date, title, status, completed_at, reflection, evidence_url | 일일 할 일과 완료 기록 |
| quests | id, job_role, level, title, description, reward_exp, reward_coin, duration_minutes, status | 관리자 관리형 퀘스트 정의 |
| user_quests | id, user_id, quest_id, status, assigned_at, completed_at, evidence_url | 사용자 퀘스트 수행 이력 |
| job_postings | id, user_id, source_url, raw_text, title, company, analysis_status, analyzed_at | 입력 공고 및 분석 상태 |
| job_posting_skills | id, job_posting_id, skill_name, requirement_type, importance | 필수/우대 역량 추출값 |
| change_proposals | id, user_id, job_posting_id, roadmap_id, status, summary, impact_days, decided_at | 승인 전 변경 제안 |
| change_proposal_items | id, proposal_id, action, target_item_id, payload_json, selected, decision | 항목별 추가/수정/삭제안 |
| roadmap_change_logs | id, roadmap_id, proposal_id, actor_id, before_json, after_json, action | 승인 반영 및 버전 감사 로그 |
| roadmap_templates | id, job_role, level, title, content_json, is_active | 관리자용 로드맵 템플릿 |
| task_templates | id, job_role, level, category, content, estimated_minutes, is_active | 관리자용 과제 템플릿 |
| notifications | id, user_id, type, title, body, read_at, payload_json | 일일·종료·승인 안내 |
| saved_job_postings | id, user_id, job_posting_id, scheduled_at, application_status | 저장 공고·지원 일정 |
| assistant_settings | user_id, persona_mode, tone, notification_enabled | AI 비서 모드·알림 설정 |
| counseling_messages | id, user_id, sender, category, content, created_at | 고민 상담소 대화 이력 |
| career_documents | id, user_id, type, title, content, target_job_posting_id, version | 자기소개서·이력서·수정 이력 |
| interview_sessions | id, user_id, job_posting_id, status, overall_score, started_at, completed_at | AI 면접 연습 세션 |
| interview_answers | id, session_id, question, answer_text, duration_seconds, feedback_json, score | 질문별 답변·피드백 |
| ai_logs | id, user_id, session_id, request_id, level, endpoint, model_name, status_code, latency_ms, error_code, message, created_at | 실제 AI 요청/응답·오류·지연 시간 운영 로그 |
| ai_feedbacks | id, ai_log_id, user_id, score, comment, created_at | 사용자 AI 답변 평가 |
| audit_logs | id, actor_id, actor_role, action, entity_type, entity_id, metadata_json | 관리자 및 민감 행위 감사 |

주요 관계: `users 1:1 user_profiles`, `users 1:N roadmaps`, `roadmaps 1:N roadmap_phases 1:N roadmap_items`, `roadmap_items 1:N daily_tasks`, `job_postings 1:N change_proposals`, `change_proposals 1:N change_proposal_items`이다. `roadmaps.parent_roadmap_id`와 변경 로그로 재시작·공고 반영 전후를 추적한다.

### 데이터 무결성 규칙

- 한 사용자에게 활성 로드맵은 원칙적으로 하나만 허용한다(재시작 전 종료 처리).
- `APPROVED` 제안만 로드맵 변경 트랜잭션을 실행한다.
- 로드맵 진행률은 완료된 항목 가중치 합으로 계산하고 클라이언트 입력값을 신뢰하지 않는다.
- 사용자 삭제 요청 시 법적·운영 정책에 따른 익명화/보존 절차를 별도 적용한다. 일반적인 기간 종료는 삭제가 아니다.

## 7. 기술 설계 및 보안

- 프론트엔드: 현재 프로젝트의 Streamlit 구조를 유지한다. `frontend/app.py`는 사용자 화면, `frontend/admin_app.py`는 관리자 화면으로 분리해 각각 실행한다. 사용자 앱은 JOB QUEST TERMINAL 경험에, 관리자 앱은 표·필터·KPI 운영 UX에 집중한다.
- 접근 제어: 관리자 앱 진입 시에도 서버의 `ADMIN` 역할 검증을 수행한다. 화면 숨김만으로 권한을 통제하지 않는다.
- 백엔드: 현재 프로젝트의 FastAPI를 단일 API 서버로 유지하고, 인증 미들웨어·권한 검사·서비스·저장소 계층을 추가한다. Streamlit은 DB에 직접 연결하지 않고 FastAPI만 호출한다.
- 데이터 저장소: PostgreSQL/Supabase를 영속 데이터 저장소로 사용하며, Redis는 온보딩·AI 상담의 임시 세션 단계와 중복 요청 방지에 한정한다.
- AI 연동: 프롬프트 템플릿과 구조화된 JSON 응답 스키마를 사용하고, 모델 응답은 검증 후 저장한다. 원문 공고와 개인정보는 최소 전송 원칙을 적용한다.
- 비동기 작업: 공고 분석, 알림 발송, 목표일 종료 처리는 큐/스케줄러로 분리하고 재시도·실패 상태를 기록한다.
- 보안: 비밀번호 단방향 해시, HTTPS, 토큰 만료/폐기, 입력 검증, XSS/SQL Injection 방지, 속도 제한, 관리자 감사 로그를 적용한다.
- 관측성: 요청 ID, 구조화 로그, 오류 추적, AI 호출 지연·실패율, 배치 성공률을 수집한다.

### 7.1 현재 프로젝트 기반 목표 디렉터리 구조

현재 `aio-01-p1-team2/jobquest_style_app`의 `frontend/app.py`와 `backend/main.py`를 유지하되, 3일 프로젝트에서 과도한 재구성 없이 아래 구조로 확장한다. `.venv`, `__pycache__`, `.env`는 저장소와 산출물에서 제외한다.

```text
jobquest_style_app/
├── backend/
│   ├── main.py                 # FastAPI 앱 생성, 라우터 등록
│   ├── core/
│   │   ├── config.py           # 환경변수 설정
│   │   ├── security.py         # 비밀번호 해시, JWT, 역할 검사
│   │   ├── database.py         # PostgreSQL/Supabase 연결
│   │   └── redis_client.py     # AI 대화 단계의 임시 세션
│   ├── routers/
│   │   ├── auth.py             # 회원가입·로그인·내 정보
│   │   ├── user.py             # 프로필·온보딩·로드맵·할 일
│   │   ├── assistant.py        # AI 상담·공고 추천·승인 제안
│   │   └── admin.py            # 관리자 KPI·로그·관리 CRUD
│   ├── schemas/                # Pydantic 요청/응답 모델
│   ├── services/               # 도메인·Gemini·로그 처리
│   ├── repositories/           # DB 접근 계층
│   ├── tests/                  # FastAPI 단위/API 테스트
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app.py                  # 사용자 Streamlit 앱 진입점
│   ├── admin_app.py            # 관리자 Streamlit 앱 진입점
│   ├── components/
│   │   ├── user_components.py  # 캐릭터, EXP, 공고 카드, 상태 UI
│   │   ├── admin_components.py # KPI, 로그 표, 필터, 상태 UI
│   │   └── api_client.py       # FastAPI 호출, JWT 처리, 오류 매핑
│   ├── pages/                  # 사용자/관리자 세부 화면 함수
│   └── assets/                 # 제공된 캐릭터·화면 스타일 자산
├── supabase/
│   └── migrations/             # 스키마와 인덱스 SQL
├── docs/
│   ├── API_DESIGN.md
│   ├── SCREEN_DESIGN.md
│   ├── DB_DESIGN.md
│   └── DEMO_SCENARIO.md
├── run.ps1                     # 백엔드·사용자·관리자 앱 실행 안내
├── requirements.txt
├── README.md
└── develop_update_plan.md
```

실행은 FastAPI(예: `:8000`), 사용자 Streamlit(예: `:8501`), 관리자 Streamlit(예: `:8502`)으로 분리한다. 두 Streamlit 앱은 동일한 FastAPI API를 사용하며, 관리자 앱에서만 `/api/v1/admin/*` API를 호출한다.

### 7.2 AI 로그 및 피드백의 실제 운영 흐름

AI 기능은 사용자 화면의 장식 요소가 아니라 관리자 운영 화면까지 연결되는 핵심 흐름으로 구현한다.

```text
사용자 AI 상담/온보딩/공고 분석 요청
  → FastAPI request_id 생성 및 시작 시각 기록
  → Gemini API 호출
  → 성공/실패·상태 코드·응답 시간(latency) 측정
  → ai_logs 저장(민감 프롬프트·비밀번호·API 키 제외)
  → 사용자에게 결과 또는 재시도 UI 표시
  → 관리자 KPI/로그 목록/상세/필터에서 조회
  → 사용자가 답변 평가를 남기면 feedback으로 연결
```

`ai_logs`에는 최소한 `user_id`, `session_id`, `request_id`, `level`, `endpoint`, `model_name`, `status_code`, `latency_ms`, `error_code`, `message`, `created_at`을 저장한다. 관리자는 최신순 목록, `INFO/WARN/ERROR`, 기간, 엔드포인트 필터와 로그 상세를 제공한다.

## 8. 예외 처리 기준

| 상황 | 처리 기준 | 사용자 안내 |
|---|---|---|
| 인증 실패/토큰 만료 | 401 반환 후 로그인 상태를 정리하고 로그인 화면으로 이동한다. 현재 명세에는 자동 refresh API가 없다. | “로그인이 만료되었습니다. 다시 로그인해 주세요.” |
| 계정 수정/탈퇴 충돌 | 중복 ID는 `LOGIN_ID_ALREADY_EXISTS`, 이미 없어진 계정은 `ACCOUNT_NOT_FOUND`, 삭제 성공 시 204 후 로컬 token/cache 삭제 | “계정 정보가 변경되었거나 더 이상 사용할 수 없습니다.” |
| 권한 없는 관리자 접근 | 403 및 감사 로그 기록 | “접근 권한이 없습니다.” |
| 온보딩 필수 답변 누락 | 누락 필드와 재질문 반환, 확정 불가 | “목표 기간을 입력해 주세요.” |
| 목표일이 시작일보다 이른 경우 | 400 반환, 날짜 검증 | “목표 종료일은 시작일 이후여야 합니다.” |
| 공고 URL/텍스트 불량 | 형식 검증, 원문 재입력 요청 | “공고 내용을 확인할 수 없습니다. 텍스트를 붙여 넣어 주세요.” |
| 선택 공고 없음/마감 | `SAVED_JOB_NOT_FOUND`(404) 또는 `SAVED_JOB_EXPIRED`(422), 계획 제안 생성 차단 | “선택한 공고를 사용할 수 없습니다. 다른 공고를 선택해 주세요.” |
| AI 분석 실패/시간 초과 | `FAILED` 저장, 제한된 재시도·관리자 모니터링 | “분석이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.” |
| 코치 세션 충돌/한도 | 세션 만료·동시 요청·revision 불일치·활성 세션/발화/응답 길이 한도를 코드별로 반환하고 동일 request ID 재시도만 허용 | “상담 상태가 변경되었거나 한도에 도달했습니다. 최신 내용을 확인해 주세요.” |
| 승인 충돌(동시 변경) | 로드맵 버전 검사, 409 반환, 최신 제안 재조회 | “계획이 변경되었습니다. 최신 내용을 확인해 주세요.” |
| 이미 결정된 제안 재승인 | 멱등 처리 또는 409, 중복 반영 금지 | “이미 처리된 제안입니다.” |
| 종료된 로드맵 수정 | 읽기 전용 처리, 재시작으로 유도 | “종료된 계획입니다. 새 계획을 시작해 주세요.” |
| 일일 작업 중복 완료 | 멱등 처리 및 완료 시각 보존 | “이미 완료한 할 일입니다.” |
| 서버/DB 장애 | 표준 5xx, 세부 정보 비노출, 오류 추적 | “일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.” |

## 9. 팀 구성 및 역할 분담 (총 4명)

| 인원 | 역할 | 담당 범위 |
|---|---|---|
| 팀원 1 | 팀장 / 관리자 프론트엔드 | 일정·통합 관리, 관리자 로그인·대시보드·좌측 내비게이션, 사용자/퀘스트/로드맵/공고/공지/통계/시스템 설정 화면, 관리자 API 연동, 배포·발표 총괄 |
| 팀원 2 | 사용자 프론트엔드 | JOB QUEST TERMINAL 디자인 시스템, 로그인·회원가입, AI 진단/프로필, 맞춤 로드맵·오늘의 할 일·EXP, 공고/상담/서류·면접/AI 비서 설정 화면, 사용자 API 연동 |
| 팀원 3 | 사용자 백엔드 | 사용자 인증·프로필·온보딩·레벨, 로드맵·일일 할 일·퀘스트·EXP, 공고 분석·승인형 변경 제안, 상담·서류·AI 면접·비서 설정 API와 DB 설계 |
| 팀원 4 | 관리자 백엔드 | 관리자 인증·권한, 사용자/퀘스트/로드맵 템플릿/공고/공지/통계/시스템 설정 관리 API와 DB, 관리자용 검색·필터·페이지네이션, 감사 로그·운영 데이터 처리 |

공동 책임: API 명세 리뷰, 코드 리뷰, 데일리 동기화, 통합 테스트, 최종 시연 리허설. 인증·권한·공통 DB 스키마는 팀원 3·4가 API 계약을 확정하고, 팀원 1·2는 담당 화면별 계약 테스트를 수행한다. 팀원 1이 최종 병합·배포와 일정 조율을 담당한다.

## 10. 개발 일정 (총 3일)

프로젝트 일정은 **개발 2일 + 테스트·배포 1일**로 운영한다. 짧은 일정 안에 완성도를 확보하기 위해 핵심 사용자 여정과 관리자 운영 기능을 우선 구현하며, 부가 AI 기능은 화면과 API 계약을 우선 완성한 뒤 연동 범위를 조절한다.

| 일자 | 목표 | 사용자 화면 작업 | 관리자 화면 작업 | 백엔드·공동 산출물 |
|---|---|---|---|---|
| 1일 차 (개발) | 기반 구축 및 핵심 진입 여정 완성 | 팀원 2: JOB QUEST TERMINAL 디자인 시스템, 로그인/회원가입, AI 진단·프로필·레벨 화면 | 팀원 1: 관리자 로그인, 좌측 내비게이션, 대시보드·사용자 목록 UI | 팀원 3: 사용자 인증·프로필·온보딩 API/DB. 팀원 4: 관리자 인증·권한·사용자 조회 API/DB. 전원: ERD·API 계약·CI 확정 |
| 2일 차 (개발) | 취업 준비 핵심 기능과 관리자 운영 기능 통합 | 팀원 2: 로드맵, 오늘의 할 일/EXP, 공고·승인, 종료/재시작 UI | 팀원 1: 퀘스트·로드맵·공고·공지·통계·설정 관리 UI | 팀원 3: 로드맵·과제·공고 분석/승인 API. 팀원 4: 관리자 CRUD·통계·감사 로그 API. 전원: 화면/API 통합 |
| 3일 차 (테스트·배포) | 품질 검증, 오류 수정, 배포 및 발표 준비 | 팀원 2: 사용자 여정·반응형·접근성 점검 | 팀원 1: 관리자 여정 검증, 최종 병합·배포·발표 총괄 | 팀원 3: 사용자 API·AI 실패 예외 테스트. 팀원 4: 관리자 권한·CRUD·통계 테스트. 전원: E2E·스모크 테스트, 결함 수정, 문서 완성 |

### 3일 차 필수 검증 시나리오

1. 회원가입/로그인 → AI 진단 → 프로필·초기 레벨 → 로드맵 생성 → 오늘의 할 일 완료 및 EXP 반영
2. 공고 열람/입력 → AI 분석 → 변경 제안 확인 → 사용자 승인 → 로드맵 반영 및 이력 확인
3. 목표 기간 종료 → 로드맵 보관 → 재시작 안내 → 이전 데이터 유지 확인
4. 관리자 로그인 → 사용자 조회 → 퀘스트·로드맵·공고 관리 → 통계 대시보드 확인
5. 일반 사용자의 관리자 URL/API 접근 차단, 토큰 만료·AI 분석 실패·중복 승인 예외 처리 확인

## 11. 테스트 계획

### 단위 테스트

- 비밀번호 해시, JWT 검증, 권한 검사, 프로필 유효성 검사
- 레벨 산정·진행률 가중치 계산, 목표 기간 일정 배분
- 공고 분석 JSON 스키마 검증, 변경 제안 생성, 승인/거절·롤백 규칙
- 종료 처리, 재시작 시 상위/보관 로드맵 연결, 일일 할 일 상태 전이

### 통합/API 테스트

- 회원가입 → 로그인 → `GET /profile` 404 → 온보딩 세션 시작 → review snapshot → revision 일치 confirm → `GET /profile` 200 흐름
- 같은 `request_id`·같은 본문 재시도 시 동일 응답 반환, 같은 `request_id`에 다른 본문을 사용하면 `IDEMPOTENCY_KEY_REUSED` 반환
- 계획 제안 생성 → pending 조회 → 승인 → active 계획/일정 생성 → task 완료 → 진행률 재계산 → 전체 완료 흐름
- 승인 전 active 계획 유지, pending proposal/active plan 중복 생성 차단, 승인 트랜잭션 실패 시 이전 active 계획 보존
- 공용 공고 목록 빈 배열·최신순 정렬, 선호 환경 기반 공고 추천·일치 없음(0점)·공고 없음(null) 반환
- 추천 후보에서 마감 공고 제외, 최대 40건 후보 선택, Gemini 추천 결과의 DB 후보 검증, Gemini 실패 시 `keyword_fallback` 전환 검증
- 선택 공고 기반 계획 제안의 `saved_job_id` 존재·마감일 검증, 동일 `request_id`와 공고 snapshot 재시도, 선택 공고 없는 프로필 기반 제안 흐름 검증
- `GET /plans/summary`의 전체 상태 포함·생성일 내림차순·통합 진행률·계획 없음(0 지표) 반환 검증
- 계정 `login_id`/`user_name` 부분 수정, 중복 ID 거절, 탈퇴 시 사용자 소유 데이터·세션 삭제 및 공유 공고 보존 검증
- 탈퇴·비활성 계정의 기존 Bearer token 거절과 204 응답 후 클라이언트 token/cache 정리 검증
- 코치 세션 생성·revision CAS·request_id 멱등 재전송, 24시간 데이터 보관 상한·120초 유휴 종료·활성 6개·발화 20개·대화 40,000자·응답 12,000자 제한 검증
- 코치 종료 후 `VALIDATED` 구조화 보고서 생성, 원문 대화 삭제, 201 최초 응답·200 replay·종료 tombstone 재사용 차단 검증
- `GET /quests/today`의 활성 계획 없음/오늘 범위 밖/오늘 task 완료 상태와 `PATCH /quests/{task_id}`의 오늘 범위 제한 검증
- 날짜 최초 달성 시 `+20 EXP`, 달성 취소 시 `-20 EXP`, 같은 상태 재요청 시 `0 EXP` 및 누적 EXP 보존
- 게시 중 공지만 `GET /notices`에 고정 우선·게시일 내림차순으로 노출되는지 검증
- 관리자 권한과 일반 사용자 접근 차단, 페이징/필터, 오류 응답 형식
- 로그인 5회 실패 잠금, 토큰 만료, Gemini 실패·rate limit, 온보딩 revision 충돌, 만료 세션, 중복 승인 예외 처리

### E2E·수동 검증

- 사용자 핵심 여정과 관리자 핵심 여정을 실제 브라우저에서 검증한다.
- 모바일/데스크톱 반응형, 키보드 조작, 빈 화면·로딩·오류 메시지를 점검한다.
- 목표일 종료 배치와 재시작 이후 과거 데이터가 보존되는지 확인한다.
- 배포 환경에서 환경변수, CORS, HTTPS, 로그 및 롤백 절차를 확인한다.

## 12. 배포 및 최종 산출물

### 배포

- 프론트엔드와 백엔드를 분리 배포하고 운영/개발 환경변수를 분리한다.
- DB 마이그레이션, 시드 데이터, 관리자 초기 계정 발급 절차를 문서화한다.
- CI에서 린트·단위 테스트·빌드를 실행하고, 배포 후 헬스 체크와 핵심 API 스모크 테스트를 수행한다.
- 비밀값(API 키, DB 접속 정보, JWT 시크릿)은 저장소에 포함하지 않고 배포 플랫폼의 비밀 관리 기능을 사용한다.

### 미니 프로젝트 제출 산출물

- 소스 코드 저장소 및 README(실행 방법, 환경변수, 역할 분담, 배포 URL)
- 요구사항 정의서, 사용자 흐름도, 화면 설계서/와이어프레임
- API 명세서(Swagger/OpenAPI), ERD 및 테이블 정의서
- 테스트 계획·결과서와 주요 시나리오 캡처
- 배포 URL, 관리자 접속 방법, 시연 계정(제출 정책이 허용하는 경우)
- 발표 자료 및 데모 시나리오: 온보딩 → 로드맵 → 오늘 할 일 → 공고 승인 반영 → 종료/재시작 → 관리자 모니터링'

## 13. 완료 기준 (Definition of Done)

- 사용자가 회원가입/로그인 후 첫 질문을 완료하면 프로필과 초기 레벨이 생성된다.
- 목표 기간에 맞춘 개인 로드맵과 매일 할 일이 표시되고, 할 일 완료에 따라 진행률이 계산된다.
- 공고 분석 결과는 반드시 변경 제안으로 먼저 표시되며, 사용자 승인 전에는 로드맵을 변경하지 않는다.
- 승인된 변경은 이력과 함께 로드맵에 반영되고, 거절된 변경은 반영되지 않는다.
- 목표 기간 종료 후 데이터가 보관되며 사용자에게 재시작 안내가 노출된다.
- 관리자 프론트엔드에서 사용자·공고·템플릿·운영 지표를 관리할 수 있다.
- 핵심 API·사용자 여정·예외 시나리오 테스트가 통과하고 배포 환경에서 재현 가능하다.
