# Mini Project 개발 계획서

## 1. 프로젝트 목표

FastAPI로 다음 두 기능을 제공하는 백엔드를 완성한다.

- Gemini API를 이용해 사용자의 질문에 답하는 채팅 API
- Supabase에 상품을 저장하고 조회·수정·삭제하는 상품 API

개발 환경에서는 API 문서(`/docs`)와 자동화 테스트를 통해 기능을 확인하고, 운영 환경에서는 비밀값 관리와 인증을 적용한다.

## 2. 범위와 완료 기준

| 구분 | 완료 기준 |
| --- | --- |
| 채팅 | 유효한 요청에 Gemini 응답을 반환하고, 잘못된 요청과 외부 API 오류를 구분해 응답한다. |
| 상품 | 생성·단건 조회·목록 조회·수정·삭제가 Supabase `products` 테이블과 정상 연동된다. |
| 검증 | 필수값, 문자열 길이, 가격 범위를 Pydantic 모델에서 검증한다. |
| 테스트 | 정상 흐름, 422 검증 오류, 404 미존재 상품, 외부 서비스 실패를 테스트한다. |
| 보안 | API 키와 Supabase service-role 키는 `.env`로만 관리하고 Git에 포함하지 않는다. |

## 3. 목표 디렉터리 구조

```text
.
├── app/
│   ├── main.py                 # FastAPI 앱 및 라우터 등록
│   ├── core/
│   │   ├── api_response.py     # 공통 응답 모델
│   │   ├── chat_config.py      # Gemini 환경 변수 로드
│   │   └── supabase_client.py  # Supabase 클라이언트 생성
│   ├── routers/
│   │   ├── chat_router.py      # HTTP 요청/응답 처리
│   │   └── product_router.py
│   ├── schemas/
│   │   ├── chat_schema.py      # 채팅 요청/응답 검증 모델
│   │   └── product_schema.py
│   └── services/
│       ├── chat_service.py     # Gemini 호출
│       └── product_service.py  # 상품 CRUD
├── docs/
│   └── schema.sql              # Supabase 테이블 생성 SQL
├── tests/
│   ├── test_chat_router.py
│   └── test_product_router.py
├── .env.example                # 비밀값이 없는 환경 변수 예시(추가 예정)
├── PLAN.md
├── README.md
└── requirements.txt
```

## 4. 데이터베이스 계획

- Supabase SQL Editor에서 [docs/schema.sql](docs/schema.sql)을 실행한다.
- 현재 서비스 구현과 맞추어 상품 ID는 문자열(`text`)로 저장한다.
- 브라우저 클라이언트의 직접 접근은 RLS로 차단하고, 백엔드만 service-role 키로 접근한다.
- 이후 UUID 기반 ID 또는 `updated_at` 컬럼이 필요해지면 서비스·스키마·테스트를 한 번에 변경한다.

## 5. API 계획

| 기능 | 메서드 | 경로 | 성공 응답 |
| --- | --- | --- | --- |
| Gemini 채팅 | POST | `/chat/gemini` | 답변 텍스트 |
| 상품 생성 | POST | `/product/create` | 생성된 상품 |
| 상품 단건 조회 | GET | `/product/get/{product_id}` | 상품 한 건 |
| 상품 목록 조회 | GET | `/product/getall` | 상품 목록 |
| 상품 수정 | PUT | `/product/{product_id}` | 수정된 상품 |
| 상품 삭제 | DELETE | `/product/delete/{product_id}` | 삭제된 상품 |

## 6. 진행 순서

1. `.env.example`을 만들고 Gemini·Supabase 환경 변수를 문서화한다.
2. `docs/schema.sql`을 Supabase에 적용하고 테이블 생성을 확인한다.
3. 각 API의 정상 흐름을 `/docs`에서 수동 확인한다.
4. 외부 API·DB 예외를 500으로 노출하지 않도록 일관된 오류 응답을 구현한다.
5. 입력값 검증과 목록 정렬 기준을 확정한다.
6. 인증을 도입한 뒤 상품 생성·수정·삭제 API에 권한 검사를 추가한다.
7. 테스트를 확장하고 `pytest`가 항상 통과하는 상태를 유지한다.

## 7. 테스트 체크리스트

- 채팅: 정상 응답, 빈 요청값, Gemini 키 누락, Gemini 호출 실패
- 상품 생성: 정상 생성, 빈 이름, 음수/0 가격, DB 저장 실패
- 상품 조회: 존재하는 ID, 없는 ID, 빈 목록, 정렬 순서
- 상품 수정·삭제: 존재하는 ID, 없는 ID, 권한 없는 요청

## 8. 보안 및 운영 원칙

- `.env`는 저장소에 커밋하지 않는다.
- 로그에 채팅 프롬프트, 사용자 식별자, API 키를 기록하지 않는다.
- service-role 키는 백엔드 서버에서만 사용한다.
- 운영 공개 전에는 인증과 권한 검사를 적용한다.
