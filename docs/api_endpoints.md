# 📖 BookOasis API Endpoints Specification (OpenAPI / Swagger Style)

이 문서는 BookOasis 미디어 서버 백엔드가 노출하는 모든 API 엔드포인트의 입력 파라미터, 요청 바디(Request Body), 응답 스키마(Response JSON) 및 권한 요구사항을 Swagger/OpenAPI 스타일로 정밀하게 명세한 개발자 참조서입니다.

---

## 🔐 전역 인증 및 공통 응답 규격

### 1. 인증 헤더 및 세션
* **Web API**: 쿠키 기반 Flask Session을 사용합니다. (`session['user_id']` 존재 여부 검사)
* **OPDS API**: HTTP Basic Authentication (`Authorization: Basic <base64>`)을 준수합니다.

### 2. 표준 에러 응답 규격 (JSON)
요청 처리 실패 시 HTTP 상태 코드와 함께 아래의 공통 JSON 객체를 반환합니다.
```json
{
  "success": false,
  "error": "에러 이유에 대한 다국어 설명문구"
}
```

---

## 📂 1. 라이브러리 및 카테고리 관리 API (`media_admin` / `library_routes`)

### `[POST]` `/api/media/libraries/add`
* **설명**: 새로운 미디어 라이브러리 카테고리를 시스템에 등록하고 백그라운드 큐에 비동기 스캔 작업을 스케줄링합니다.
* **권한**: `@admin_required` (관리자 전용)
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 필수 | DB 스코프 (`general` 또는 `adult`) |
  | `name` | string | 필수 | 카테고리 이름 (양끝 공백 제외 최대 25자, 고유값) |
  | `physical_path` | string | 필수 | 파일시스템 절대경로 (멀티경로 시 줄바꿈으로 구분) |
  | `is_remote` | string | 선택 | 원격 마운트 여부 (`1` / `0`) |
  | `rclone_rc_url` | string | 선택 | Rclone Remote Control 주소 (예: `http://localhost:5572`) |

* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "보관함이 생성되었으며 스캔이 대기열에 등록되었습니다."
  }
  ```

---

### `[POST]` `/api/media/libraries/edit`
* **설명**: 기존 카테고리의 이름, 경로 및 원격 연결 주소를 수정하고 재스캔을 트리거합니다.
* **권한**: `@admin_required` (관리자 전용)
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `id` | integer | 필수 | 수정 대상 라이브러리 ID |
  | `type` | string | 필수 | DB 스코프 (`general` 또는 `adult`) |
  | `name` | string | 필수 | 변경할 새 카테고리 명 |
  | `physical_path` | string | 필수 | 변경할 파일 시스템 절대 경로 |
  | `is_remote` | string | 선택 | 원격 연결 사용 플래그 |
  | `rclone_rc_url` | string | 선택 | Rclone 원격 API 서버 Endpoint 주소 |

---

### `[POST]` `/api/media/libraries/delete`
* **설명**: 카테고리를 소거하며 하위 도서 메타데이터 및 독서 이력, 에러 보고서 파일을 연쇄 삭제(Cascade Delete)합니다.
* **권한**: `@admin_required`

---

### `[GET]` `/api/media/libraries/schedules`
* **설명**: 전체 카테고리의 백그라운드 스캔 크론 스케줄 주기와 스캔 상태(Status) 목록을 가져옵니다.
* **권한**: `@admin_required`
* **쿼리 스트링**:
  * `type` (string, 필수): 조회 스코프 (`general` / `adult`)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "libraries": [
      {
        "id": 1,
        "name": "일반 만화",
        "physical_path": "/data/comics",
        "cron_schedule": "0 3 * * *",
        "last_scanned_at": "2026-07-04 18:27:11",
        "scan_status": "ready",
        "is_remote": 0,
        "vfs_refresh_before_scan": 0,
        "rclone_rc_url": ""
      }
    ]
  }
  ```

---

## 🔑 2. 인증 및 사용자 계정 API (`auth`)

### `[POST]` `/login`
* **설명**: 사용자의 신원을 인증하여 세션을 생성합니다.
* **Content-Type**: `application/json` 또는 `application/x-www-form-urlencoded`
* **요청 바디 / 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `username` | string | 필수 | 로그인 계정 아이디 |
  | `password` | string | 필수 | 계정 비밀번호 |
  | `remember_me` | boolean | 선택 | 자동로그인 설정 여부 |

* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "role": "admin",
    "is_default_password": 0
  }
  ```

---

### `[POST]` `/change-password`
* **설명**: 로그인된 세션의 사용자 비밀번호를 갱신합니다.
* **요청 바디 (JSON)**:
  ```json
  {
    "new_password": "NewSecretPassword12!"
  }
  ```

---

## 📚 3. 도서 탐색 및 메타데이터 서비스 API (`media_library` / `library`)

### `[GET]` `/api/media/libraries`
* **설명**: 현재 로그인된 사용자의 권한 등급 및 성인 인증 권한에 조인 필터링된 카테고리 탭 목록을 반환합니다.
* **쿼리 스트링**:
  * `type` (string, 필수): `general` / `adult`
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "libraries": [
      { "id": "home", "name": "전체보기", "physical_path": "" },
      { "id": 1, "name": "판타지 소설", "physical_path": "/data/novel" }
    ]
  }
  ```

---

### `[GET]` `/api/media/list`
* **설명**: 보관함 내의 시리즈(도서 묶음) 리스트를 무한 스크롤 및 검색 조건에 맞게 페이지네이션하여 반환합니다.
* **쿼리 스트링**:
  * `type` (string, 필수): `general` / `adult`
  * `library_id` (string, 선택): 특정 보관함 ID (전체일 경우 `home`)
  * `search` (string, 선택): 서칭 키워드
  * `page` (integer, 선택): 조회 페이지 번호 (기본: `1`)
  * `limit` (integer, 선택): 1회당 조회 목록 크기 (기본: 시스템 설정값)
  * `sort` (string, 선택): 정렬 기준 (`title_asc`, `title_desc`, `date_desc`, `date_asc`)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "series": [
      {
        "series_name": "나 혼자만 레벨업",
        "library_id": 1,
        "author": "추공",
        "publisher": "디앤씨미디어",
        "created_at": "2026-06-01 12:00:00",
        "has_books_count": 8,
        "is_favorite": 1,
        "cover_image": "/covers/1/cover_l1.jpg"
      }
    ],
    "has_more": true
  }
  ```

---

### `[GET]` `/api/media/detail`
* **설명**: 특정 시리즈의 메타 정보 및 속해 있는 단행본 권차 목록을 순서대로 조회합니다.
* **쿼리 스트링**:
  * `type` (string, 필수): `general` / `adult`
  * `series` (string, 필수): 시리즈 명
  * `library_id` (integer, 필수): 카테고리 ID

---

## ⚡ 4. 실시간 미디어 스트리밍 및 진행률 API (`media_stream` / `stream`)

### `[GET]` `/api/media/stream`
* **설명**: 압축 해제 없이 ZIP/CBZ 압축 파일 내 특정 페이지 파일을 실시간으로 추출 및 트랜스코딩 서빙합니다.
* **쿼리 스트링**:
  * `book_id` (integer, 필수): 도서 고유 번호
  * `page` (integer, 필수): 0-indexed 열람 대상 페이지 번호
  * `type` (string, 선택): DB 종류 스코프
* **헤더 응답**: `Content-Type: image/webp` 또는 `image/jpeg` (동적 이미지 바이너리)

---

### `[POST]` `/api/media/progress`
* **설명**: 사용자의 독서 페이지 진행 현황을 실시간으로 추적/기록하여 메인 뷰어 재진입 시 복원할 수 있도록 저장합니다.
* **요청 바디 (JSON)**:
  ```json
  {
    "book_id": 105,
    "type": "general",
    "pages_read": 45,
    "is_completed": 0
  }
  ```

---

## 📱 5. OPDS 및 모바일 외부 앱 연동 API (OPDS)

모든 OPDS API는 HTTP Basic Authentication (`Authorization: Basic <base64>`) 인증을 공통적으로 적용받습니다.

### `[GET]` `/opds`
* **설명**: 일반 도서 전용 OPDS 카탈로그의 네비게이션 최상위 피드(Atom XML)를 가져옵니다.

### `[GET]` `/opds-adult`
* **설명**: 성인 도서 전용 OPDS 카탈로그의 네비게이션 최상위 피드(Atom XML)를 가져옵니다. (관리자 권한 필수)

### `[GET]` `/opds/search`
* **설명**: 일반 OPDS 피드 내의 책 검색을 지원합니다.
* **쿼리 스트링**:
  * `q` 또는 `query` (string, 선택): 검색할 책 제목, 시리즈명, 저자 키워드.
* **응답 규격**:
  * 키워드(`q`)가 비어 있을 경우: OpenSearch Description XML 문서 (`application/opensearchdescription+xml`)
  * 키워드(`q`)가 존재할 경우: 검색 결과 매칭 도서 목록 Atom XML 피드 (`application/atom+xml`)

---

### `[GET]` `/app-opds` / `/app-opds-adult`
* **설명**: 타치요미/미혼(Tachiyomi/Mihon) 등 비표준 OPDS 클라이언트를 위한 전용 엔드포인트입니다. 내부 성능 캐시를 탑재하고 있습니다.

### `[GET]` `/app-opds/search` / `/app-opds-adult/search`
* **설명**: 타치요미/미혼 전용 캐시 기능이 결합된 검색 엔드포인트입니다.
* **쿼리 스트링**:
  * `q` 또는 `query` (string, 선택): 검색할 책 제목, 시리즈명, 저자 키워드.
* **응답 규격**:
  * 키워드(`q`)가 비어 있을 경우: OpenSearch Description XML 문서
  * 키워드(`q`)가 존재할 경우: 검색 결과 매칭 도서 목록 Atom XML 피드

