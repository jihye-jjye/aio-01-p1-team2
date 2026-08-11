# 취업관리 MAP 관리자 프론트엔드

Streamlit으로 만든 취업관리 MAP의 관리자 콘솔입니다. 관리자 인증 후 사용자, 공지사항, 채용 공고, 로드맵 정보를 조회·관리하는 화면을 제공합니다.

## 주요 기능

- 관리자 로그인 및 세션 기반 접근 제어
- 운영 대시보드
  - 1~90일 기간 필터
  - 전체 사용자·활성 계정·신규 가입·퀘스트 완료율 KPI
  - 온보딩 완료율, 준비도 진단 현황, 가입자 추이
  - 활성/완료/만료 로드맵, 퀘스트·오늘 일정·지연 일정 요약
  - 최근 가입 사용자 표
- 사용자 목록 조회 및 역할·활성 상태·누적 EXP·최근 접속일 확인
- 사용자 상세 조회
  - 취업 목표, 보유 기술, 경험 요약, 선호 근무 환경
  - 준비도 진단 결과
  - 퀘스트 진행 현황과 최근 접속 정보
- 공지사항 목록 및 상세 조회
- 채용 공고 목록 및 상세 화면
- 관리자용 사이드바 내비게이션과 로그아웃

현재 로드맵 관리 화면과 공지/공고의 등록·수정·삭제 버튼은 화면 구조가 준비된 상태이며, 일부는 백엔드 API 연동이 추가로 필요합니다. 채용 공고 상세 화면은 현재 조회 전용입니다.

## 기술 구성

- Python 3.12+
- Streamlit 1.41.1
- httpx
- pandas / Altair
- streamlit-browser-session-storage

## 프로젝트 구조

```text
frontend_admin/
├── app.py                         # Streamlit 앱 진입점 및 페이지 내비게이션
├── app_pages/                     # 관리자 화면
│   ├── start.py                   # 관리자 로그인
│   ├── dashboard.py               # 기간별 운영 현황·KPI 대시보드
│   ├── user_management.py         # 사용자 목록
│   ├── user_management_detail.py  # 사용자 상세·프로필·퀘스트 현황
│   ├── notice.py                  # 공지사항 목록
│   ├── notice_detail.py           # 공지사항 상세
│   ├── recruitment_notice.py      # 채용 공고 목록
│   ├── recruitment_notice_detail.py # 채용 공고 상세(조회 전용)
│   └── loadmap.py                 # 로드맵 관리(확장 예정)
├── clients/                       # 화면별 관리자 API 호출 함수
│   ├── user_client.py
│   ├── dashboard_client.py         # 관리자 대시보드 API
│   ├── notice_client.py
│   ├── recruitment_notice_client.py
│   └── loadmap_client.py
├── core/
│   ├── auth.py                    # 로그인 상태·로그아웃 처리
│   ├── api_client.py              # HTTP 요청 및 오류 변환
│   └── datetime_format.py         # 날짜 표시 유틸리티
├── tab_pages/                     # 사용자 상세 화면의 프로필·퀘스트 UI 컴포넌트
├── resources/                     # 이미지 등 정적 자산
├── requirements.txt
└── setup.md
```

## 설치 및 실행

PowerShell에서 다음을 실행합니다.

```powershell
cd C:\miniProject\aio-01-p1-team2\frontend_admin
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

실행 후 터미널에 표시되는 로컬 주소(일반적으로 `http://localhost:8501`)로 접속합니다.

## 백엔드 연동

`core/api_client.py`는 역할에 따라 다음 API를 호출합니다.

| 구분 | 기본 주소 | 사용 목적 |
|---|---|---|
| 사용자 API | `https://aio-01-p1-team2-1.onrender.com/api/v1` | 사용자 관련 공통 데이터 참조 |
| 관리자 API | `https://aio-01-p1-team2.onrender.com/api/v1` | 관리자 로그인, 사용자·공지·공고 관리 |

현재 연결된 관리자 API 예시는 다음과 같습니다.

| 기능 | Method | Endpoint |
|---|---|---|
| 관리자 로그인 | POST | `/admin/auth/login` |
| 운영 대시보드 | GET | `/admin/dashboard?days={1..90}` |
| 사용자 목록 | GET | `/admin/users` |
| 사용자 상세 | GET | `/admin/users/by-login-id/{login_id}` |
| 사용자 종합 현황 | GET | `/admin/users/by-login-id/{login_id}/overview` |
| 공지 목록/상세 | GET | `/admin/notices`, `/admin/notices/{id}` |
| 채용 공고 목록 | GET | `/admin/saved-jobs` |

관리자 API 주소를 변경하려면 `core/api_client.py`의 `BACKEND_AMDIN_URL` 값을 배포 환경에 맞게 수정합니다. API는 Bearer access token을 사용하며, 로그인 성공 후 토큰은 Streamlit `session_state`에 보관됩니다.

## 사용 흐름

1. 로그인 화면에서 관리자 계정으로 로그인합니다.
2. 로그인 직후 대시보드에서 기간을 선택해 서비스 KPI와 최근 가입자 현황을 확인합니다.
3. 좌측 사이드바에서 사용자 관리, 로드맵 관리, 공지사항, 채용공고 관리 화면으로 이동합니다.
4. 사용자 관리에서 일반 사용자를 선택하면 프로필, 퀘스트 진행률, 최근 접속 정보를 확인합니다.
5. 공지사항 또는 채용공고 목록에서 항목을 선택해 상세 화면으로 이동합니다.
6. 로그아웃하면 현재 브라우저 세션의 access token과 사용자 ID가 제거됩니다.

## 개발 시 참고 사항

- API 요청 실패는 `BackendAPIError`로 변환해 화면에 표시합니다.
- 인증이 필요한 요청에는 `Authorization: Bearer <access_token>` 헤더를 자동으로 추가합니다.
- `app_test.py`, `app_pages/example.py`, `app_pages/chat_example.py`, `tab_pages/data`의 일부 파일은 UI 실험 또는 예제 코드입니다. 운영 진입점은 `app.py`입니다.
- `.venv`, `.env`, 로그 파일은 Git에 포함하지 않습니다.

## 향후 연동 항목

- 로드맵 관리 API 및 목록/상세 UI 연결
- 공지사항과 채용 공고의 등록·수정·삭제 API 연결
- 사용자 검색·역할·상태 필터의 서버 쿼리 연동
- AI 로그 조회 및 심화 통계·분석 화면 연결
- 관리자 권한 검증 실패 및 만료 토큰에 대한 로그인 화면 자동 전환
