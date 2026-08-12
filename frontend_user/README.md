# AI 취업 코치 · 사용자 프론트엔드

> AI와 함께 취업 목표를 정리하고, 개인화 로드맵과 오늘의 퀘스트를 실행하는 사용자용 Streamlit 애플리케이션입니다.

사용자 프론트엔드는 회원가입·로그인부터 AI 프로필 분석, 추천 공고, 로드맵, 오늘의 할 일, AI 커리어 상담까지의 사용자 여정을 담당합니다.

## 담당 기능

- 회원가입, 로그인, 로그아웃
- JWT access token 기반 인증 상태 관리
- AI 대화형 프로필 분석과 프로필 확정
- 사용자 취업 프로필 조회와 전체 프로필 재작성
- 프로필 기반 추천 공고 조회와 공고 원문 이동
- 개인화 취업 로드맵 제안, 수락, 조회
- 오늘의 퀘스트 완료·완료 취소와 진행률 표시
- 로그인 시 로드맵 일정·변경 알림 조회
- AI 커리어 상담 세션과 메시지 대화
- 로그인 ID·사용자 이름 수정과 회원 탈퇴
- AI 진단 점수 기반 4단계 성장 캐릭터 표시

## 사용자 흐름

```text
첫 화면
  → 사용자 모드 선택
  → 회원가입 또는 로그인
  → AI 프로필 분석
  → 취업 프로필 확정
  → 추천 공고 확인
  → 로드맵 제안 수락 및 시작
  → 오늘의 퀘스트 수행
  → AI 커리어 상담
```

프로필이 이미 완성된 사용자는 로그인 후 홈 대시보드로 이동합니다. 저장된 프로필이 없는 사용자는 AI 프로필 분석 화면으로 이동합니다.

## 화면 구성

| 화면 | 파일 | 역할 |
|---|---|---|
| 모드 선택 | `app_pages/home.py` | 사용자·관리자 모드 진입 |
| 로그인 | `app_pages/login.py` | 로그인, 토큰 저장, 알림·프로필 조회 |
| 회원가입 | `app_pages/signup.py` | 로그인 ID·비밀번호·이름으로 계정 생성 |
| AI 프로필 분석 | `app_pages/onboarding.py` | AI 대화로 취업 프로필 8개 항목 수집·확정 |
| 홈 대시보드 | `app_pages/dashboard.py` | 목표, 진행률, 오늘의 퀘스트, 빠른 메뉴 |
| 취업 프로필 | `app_pages/profile.py` | 확정 프로필과 성장 캐릭터 표시 |
| 추천 공고 | `app_pages/jobs.py` | 프로필 기반 추천 공고와 적합도 표시 |
| 취업 로드맵 | `app_pages/roadmap.py` | 4단계 성장 로드맵과 세부 목표 |
| 오늘 할 일 | `app_pages/today_quests.py` | 오늘의 퀘스트, 완료 상태, 진행률 표시 |
| AI 커리어 상담 | `app_pages/assistant.py` | 프로필 기반 AI 상담 |
| 사용자 정보 수정 | `app_pages/account_settings.py` | 로그인 ID·이름 수정, 회원 탈퇴 |

## 프로필과 성장 캐릭터

AI가 확정한 준비도 진단 점수 `assessment_score`에 따라 캐릭터를 표시합니다. 이 기준은 취업 프로필과 홈 대시보드에 동일하게 적용됩니다.

| 점수 | 단계 | 이미지 |
|---:|---|---|
| 0~25 | 1단계 · 새싹 | `assets/character_level_1.png` |
| 26~50 | 2단계 · 성장 | `assets/character_level_2.png` |
| 51~75 | 3단계 · 도전 | `assets/character_level_3.png` |
| 76~100 | 4단계 · 전문가 | `assets/character_level_4.png` |

## UI 테마

- 모드 선택·로그인·AI 프로필 분석·취업 프로필: 다크 게임 콘솔 톤
- 홈·로드맵·오늘 할 일·추천 공고·AI 상담: 밝은 작업 화면과 다크 사이드바 조합
- 공통 포인트 컬러: 핑크
- AI 상담 대화 영역: 가독성을 위해 화이트 배경
- 버튼과 사이드바 메뉴: 다크 배경·핑크 포인트로 통일

공통 버튼과 사이드바 스타일은 `core/styles.py`에서 관리합니다.

## 백엔드 연동

최종 배포 환경에서는 Render에 배포된 사용자 FastAPI를 사용합니다.

| 항목 | 값 |
|---|---|
| 사용자 API | `https://aio-01-p1-team2-1.onrender.com/api/v1` |
| 사용자 API Swagger | [https://aio-01-p1-team2-1.onrender.com/docs](https://aio-01-p1-team2-1.onrender.com/docs) |
| 공통 HTTP 처리 | `core/api_client.py` |
| 인증·프로필 | `clients/auth_client.py` |
| AI 프로필 분석 | `clients/onboarding_client.py` |
| 계획·로드맵 | `clients/plan_client.py` |
| 오늘의 퀘스트 | `clients/quest_client.py` |
| 추천 공고 | `clients/job_client.py` |
| AI 상담 | `clients/assistant_client.py` |
| 알림 | `clients/notification_client.py` |

인증이 필요한 요청에는 저장된 access token을 `Authorization: Bearer <access_token>` 헤더로 전달합니다. 사용자 ID는 요청 본문이 아니라 백엔드가 access token에서 결정합니다.

## 화면과 API 연결

| 사용자 액션 | API | 정상 처리 | 주요 예외 상태 |
|---|---|---|---|
| 회원가입 | `POST /auth/signup` | 토큰 저장 후 AI 프로필 분석 이동 | 중복 ID, 입력 형식, 서버 오류 |
| 로그인 | `POST /auth/login` | 토큰 저장 후 알림·프로필 조회 | 인증 실패, 네트워크 오류 |
| 프로필 조회 | `GET /profile` | 프로필 카드와 성장 캐릭터 표시 | 프로필 없음 시 AI 프로필 분석 이동 |
| AI 프로필 분석 | `POST /onboarding/sessions` | AI 질문·답변·프로필 확정 | 세션 만료, AI·서버 오류 |
| 추천 공고 | `GET /saved-jobs/recommendation` | 적합도·추천 이유·공고 링크 표시 | 프로필 없음, 공고 없음 |
| 로드맵 제안 | `POST /plan-proposals` | AI 계획 제안 표시 | 활성 계획 존재, 생성 중, 목표일 오류 |
| 로드맵 수락 | `POST /plan-proposals/{proposal_id}/accept` | 활성 계획과 오늘의 일정 생성 | 제안 만료, 프로필 변경 |
| 오늘의 퀘스트 | `GET /quests/today`, `PATCH /quests/{task_id}` | 완료 상태·진행률 갱신 | 계획 없음, 조회·수정 오류 |
| AI 상담 | `POST /assistant/sessions`, `POST /assistant/sessions/{session_id}/messages` | 세션 생성과 대화 표시 | 세션 만료, AI·서버 오류 |
| 내 정보 수정 | `PATCH /auth/me` | 로그인 ID·이름 갱신 | ID 중복, 입력 형식 오류 |
| 회원 탈퇴 | `DELETE /auth/me` | 토큰·사용자 캐시 삭제 후 첫 화면 이동 | 인증·서버 오류 |

## 상태 처리

주요 화면은 다음 상태를 사용자에게 표시합니다.

- Loading: `st.spinner()`로 API 요청 중 상태 표시
- Empty: 프로필·계획·퀘스트·공고가 없을 때 다음 행동 버튼 제공
- Error: 인증·입력·네트워크·서버 오류 메시지 표시
- Retry: 일시 오류 또는 세션 만료 시 다시 시도·새 대화 제공

## 환경 변수

`frontend_user/.env.example`을 참고해 `frontend_user/.env` 파일을 생성합니다.

### Render 배포 기준

```ini
BACKEND_URL=https://aio-01-p1-team2-1.onrender.com/api/v1
```

### 로컬 개발 기준

```ini
BACKEND_URL=http://127.0.0.1:8010/api/v1
```

`.env`, access token, refresh token, 비밀번호는 GitHub에 커밋하지 않습니다.

## 로컬 실행

로컬 실행은 개발과 화면 점검용입니다. 최종 배포에서는 Streamlit 환경 변수에 Render 사용자 API 주소를 등록합니다.

```powershell
cd frontend_user
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

실행 주소: `http://127.0.0.1:8501`

## 폴더 구조

```text
frontend_user/
├── app.py                    # Streamlit 페이지 등록과 인증 사이드바
├── app_pages/                # 사용자 화면
│   ├── home.py
│   ├── login.py
│   ├── signup.py
│   ├── onboarding.py
│   ├── dashboard.py
│   ├── profile.py
│   ├── jobs.py
│   ├── roadmap.py
│   ├── today_quests.py
│   ├── assistant.py
│   └── account_settings.py
├── clients/                  # 도메인별 백엔드 API 호출
├── core/                     # 토큰·세션·공통 스타일·HTTP 처리
├── assets/                   # 성장 캐릭터와 화면 이미지
├── requirements.txt
└── .env.example
```

## 점검 방법

```powershell
# Python 문법 검사
python -m compileall frontend_user

# 설치된 라이브러리 충돌 검사
python -m pip check
```

배포 후에는 다음 흐름을 확인합니다.

1. 회원가입 후 AI 프로필 분석과 프로필 저장
2. 로그인 후 홈 대시보드 이동과 알림 표시
3. 추천 공고·로드맵·오늘의 퀘스트 조회
4. 퀘스트 완료·취소에 따른 진행률 변경
5. AI 상담 세션 생성과 메시지 응답
6. 로그인 ID·이름 수정과 회원 탈퇴
7. access token 유효 시간 내 브라우저 새로고침 후 로그인 상태 복원

## 관련 문서

- [통합 프로젝트 README](../README.md)
- [사용자 API 명세](../backend_user/docs/API_SPEC.md)
