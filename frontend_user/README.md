# Mini Frontend Multi Tab

`mini_frontend_tab`과 `mini_frontend_02`의 화면을 하나로 합친
초보자용 Streamlit 예제입니다.

## 화면 구조

```text
좌측 클릭 메뉴
├── 시작
│   ├── 홈 탭
│   └── 회원가입 탭
└── 데이터
    ├── 테이블 탭
    ├── 차트 탭
    ├── 로그 탭
    └── DB 탭
```

연습용 로그인 계정은 `id01` / `pwd01`입니다.

## 폴더 구조

```text
mini_frontend_multi_tab/
├── app.py
├── app_pages/
│   ├── 01_start.py
│   └── 03_data.py
├── tab_pages/
│   ├── start/
│   │   ├── home_tab.py
│   │   └── signup_tab.py
│   └── data/
│       ├── table_tab.py
│       ├── chart_tab.py
│       ├── log_tab.py
│       └── database_tab.py
└── core/
    └── auth.py
```

- `app.py`: 좌측 메뉴
- `app_pages`: 메뉴를 클릭했을 때 나타나는 화면
- `tab_pages`: 각 `app_pages` 화면별 탭 내용
- `core`: 로그인 상태와 공통 설정

로그인 화면은 모든 메뉴에서 사용할 수 있도록 왼쪽 사이드바에 표시됩니다.

## 실행

```powershell
cd mini_frontend_multi_tab
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
