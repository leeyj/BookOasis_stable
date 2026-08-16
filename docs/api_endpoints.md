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
  | `group_id` | integer | 선택 | 가상 상위 그룹 ID. 비우면 미분류로 저장 |

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
  | `group_id` | integer | 선택 | 변경할 가상 상위 그룹 ID. 비우면 미분류로 이동 |

---

### `[POST]` `/api/media/libraries/delete`
* **설명**: 카테고리를 소거하며 하위 도서 메타데이터 및 독서 이력, 에러 보고서 파일을 연쇄 삭제(Cascade Delete)합니다.
* **권한**: `@admin_required`

---

### 가상 상위 그룹 API
* `POST /api/media/library-groups/add`: `type`, `name`으로 그룹 생성
* `POST /api/media/library-groups/edit`: `type`, `id`, `name`으로 그룹 이름 변경
* `POST /api/media/library-groups/delete`: `type`, `id`로 그룹 삭제
* `POST /api/media/libraries/move`: 카테고리의 그룹 소속과 그룹 내 순서를 일괄 저장
* **권한**: 모두 `@admin_required`
* **삭제 정책**: 그룹을 삭제해도 카테고리와 도서는 삭제되지 않으며 해당 카테고리는 미분류로 이동합니다.
* **조회**: `GET /api/media/libraries` 응답의 `groups`와 각 `libraries[].group_id`를 사용합니다. 일반 사용자에게는 접근 가능한 카테고리가 포함된 그룹만 반환합니다.
* **이동 요청**: JSON 본문으로 `type`과 모든 카테고리의 `items`를 전달합니다. `items`는 화면 순서대로 `{"id": 12, "group_id": 3}` 형식을 사용하며 미분류는 `group_id: null`입니다.
* **정렬 정책**: 서버가 전달 순서를 그룹별 `sort_order`로 재계산해 단일 트랜잭션으로 저장합니다.

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
* **비고**: 응답의 `is_favorite` 값은 로그인한 현재 사용자 기준으로 계산됩니다. (계정별 분리)
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
* **비고**: `books[].is_favorite` 값은 로그인한 현재 사용자 기준입니다. (계정별 분리)
* **쿼리 스트링**:
  * `type` (string, 필수): `general` / `adult`
  * `series` (string, 필수): 시리즈 명 (원본 `series_name` 또는 설정된 별칭 `series_alias` 수용 가능)
  * `library_id` (integer/string, 필수): 카테고리 ID (특정 ID 또는 `'all'`, `'home'` 등)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "meta": {
      "series_name": "나 혼자만 레벨업",
      "series_alias": "나혼렙 별칭",
      "author": "추공",
      "isbn": "9791167771234",
      "publisher": "디앤씨미디어",
      "link": "https://...",
      "score": 5,
      "summary": "재능 없는 E급 헌터 성진우의 기적 같은 레벨업 대서사시.",
      "genre": "판타지, 액션",
      "tags": "헌터물, 성장물",
      "cover_image": "/covers/1/cover_l1.jpg?t=1710203948"
    },
    "books": [
      {
        "id": 198,
        "title": "평범한 연애는 할 수 없어 01권 (리디)#198",
        "title_alias": "1권 별칭",
        "file_format": "imgdir",
        "total_pages": 192,
        "has_offsets": 1,
        "cover_image": "/covers/1/198.jpg?t=1710203948",
        "file_path": "/data/comics/평범한 연애는 할 수 없어/평범한 연애는 할 수 없어 01권 (리디)#198/__folder__.imgdir",
        "pages_read": 50,
        "is_completed": 0,
        "is_favorite": 0,
        "last_read_at": "2026-07-13 12:00:00"
      }
    ]
  }
  ```

### `[POST]` `/api/media/detail/edit`
* **설명**: 시리즈 메타정보를 수동으로 수정합니다. (관리자 전용)
* **권한**: `@admin_required`
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 필수 | DB 스코프 (`general` 또는 `adult`) |
  | `series` | string | 필수 | 수정 대상 시리즈명 |
  | `series_alias` | string | 선택 | 시리즈 표시 별칭(Alias) |
  | `author` | string | 선택 | 저자 |
  | `isbn` | string | 선택 | ISBN |
  | `publisher` | string | 선택 | 출판사 |
  | `summary` | string | 선택 | 줄거리 |
  | `link` | string | 선택 | 외부 링크 |
  | `genre` | string | 선택 | 장르(쉼표 구분) |
  | `tags` | string | 선택 | 태그(쉼표 구분) |
  | `cover_image` | file | 선택 | 표지 이미지 파일 |

### `[POST/PATCH]` `/api/media/series/alias`
* **설명**: 특정 시리즈 전용 표시 별칭(`series_alias`)을 수정/삭제합니다. (관리자 전용)
* **권한**: `@admin_required`
* **Content-Type**: `application/json` 또는 `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 선택 | DB 스코프 (기본값: `general`) |
  | `series` | string | 필수 | 원본 시리즈명 (`series_name`) |
  | `series_alias` | string | 선택 | 설정할 표시 별칭 (빈 값이면 기본 폴더명으로 원복) |

### `[POST/PATCH]` `/api/media/books/{book_id}/alias`
* **설명**: 단일 권수/도서 전용 표시 별칭(`title_alias`)을 수정/삭제합니다. (관리자 전용)
* **권한**: `@admin_required`
* **Content-Type**: `application/json` 또는 `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 선택 | DB 스코프 (기본값: `general`) |
  | `title_alias` | string | 선택 | 설정할 도서 표시 별칭 (빈 값이면 원본 제목으로 원복) |

### `[POST]` `/api/media/books/{book_id}/apply-metadata`
* **설명**: 메타데이터 검색(플러그인) 결과를 선택해 단일 도서에 적용합니다. (관리자 전용)
* **권한**: `@admin_required`
* **Content-Type**: `application/json` 또는 `application/x-www-form-urlencoded`
* **요청 바디(JSON) 예시**:
  ```json
  {
    "type": "general",
    "source": "aladin",
    "item_data": {
      "title": "도서명",
      "author": "저자",
      "isbn": "9791167771234",
      "publisher": "출판사",
      "description": "설명",
      "link": "https://..."
    }
  }
  ```
* **비고**: `item_data.isbn`이 제공되면 플러그인 apply 로직에서 `books.isbn`까지 함께 반영됩니다.

### `[POST]` `/api/media/meta/copy`
* **설명**: 추천 메타정보를 동일 시리즈에 일괄 복사합니다. (관리자 전용)
* **권한**: `@admin_required`
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 필수 | DB 스코프 (`general` 또는 `adult`) |
  | `target_series` | string | 필수 | 대상 시리즈명 |
  | `target_library_id` | integer | 필수 | 대상 라이브러리 ID |
  | `source_book_id` | integer | 필수 | 원본 메타를 가져올 도서 ID |
* **비고**: 복사 항목에 `isbn`이 포함됩니다.

---

### `[POST|PATCH]` `/api/media/books/{book_id}/favorite`
* **설명**: 단일 도서의 즐겨찾기 상태를 변경합니다.
* **권한**: 로그인 사용자
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 필수 | DB 스코프 (`general` 또는 `adult`) |
  | `is_favorite` | integer | 필수 | `1`: 즐겨찾기 추가, `0`: 즐겨찾기 해제 |
* **비고**: 즐겨찾기 저장은 계정별(`user_id`)로 분리되며, 다른 사용자 계정에는 영향이 없습니다.

### `[POST|PATCH]` `/api/media/series/favorite`
* **설명**: 특정 시리즈 전체 도서를 즐겨찾기/해제 처리합니다.
* **권한**: 로그인 사용자
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 필수 | DB 스코프 (`general` 또는 `adult`) |
  | `series_name` | string | 필수 | 대상 시리즈명 |
  | `is_favorite` | integer | 필수 | `1`: 즐겨찾기 추가, `0`: 즐겨찾기 해제 |
* **비고**: 처리 결과는 현재 로그인한 사용자 계정에만 적용됩니다.

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
    "db_type": "general",
    "book_id": 105,
    "page_idx": 7,
    "total_pages": 32,
    "epub_session": "..."
  }
  ```

---

### `[GET]` `/api/media/epub`
* **설명**: EPUB 압축 파일 내부의 챕터(XHTML/HTML) 목록을 정제하여 순차적인 JSON 배열 형태로 가져옵니다. (내부 삽화 이미지 태그 주소 치환 완료)
* **쿼리 스트링**:
  * `book_id` (integer, 필수): 도서 고유 번호
  * `db_type` (string, 필수): DB 종류 스코프 (`general` / `adult`)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "chapters": [
      {
        "id": "cover.xhtml",
        "title": "표지",
        "content": "<div class=\"epub-content\">...</div>"
      }
    ]
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

### `[GET]` `/opds/favorite` / `/opds/adult/favorite` / `/app-opds/favorite` / `/app-opds/adult/favorite`
* **설명**: 즐겨찾기 전용 피드(Atom XML)를 반환합니다.
* **비고**: Basic Auth로 인증된 사용자 계정 기준의 즐겨찾기만 반환합니다. (계정별 분리)

---

## 📡 6. 외부 연동 및 자동화용 웹훅 API (Webhook)

### `[GET]` 또는 `[POST]` `/api/webhook/scan`
* **설명**: 외부 마운트 제어(gd-poller 등)나 자동화 갱신 트리거 시, 세션 로그인 없이 헤더나 쿼리 스트링 보안 토큰만으로 라이브러리 스캔 작업을 즉시 대기열에 비동기 등록합니다. `path`를 함께 지정하면 라이브러리 전체가 아닌 해당 폴더(시리즈) 하나만 즉시 동기 스캔+등록합니다.
* **권한**: 비세션 인증 (단, `.env`의 `WEBHOOK_TOKEN`과 매칭 검증 필수)
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `token` | string | 필수 | `.env`에 정의된 `WEBHOOK_TOKEN` 보안 API 토큰값 |
  | `library_id` | integer | 필수 | 동기화 스캔을 수행할 대상 라이브러리 카테고리의 고유 ID |
  | `type` | string | 선택 | 라이브러리 데이터베이스 영역 (`general` 또는 `adult`, 디폴트: `general`) |
  | `path` | string | 선택 | 라이브러리 물리 경로 기준 상대경로. 지정 시 전체 스캔 대신 해당 폴더 하나만 즉시 동기 스캔 |

* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "\"만화_완결A (general)\" 스캔 작업이 대기열에 성공적으로 등록되었습니다."
  }
  ```
* **응답 예시 (401 Unauthorized - 토큰 오류)**:
  ```json
  {
    "success": false,
    "error": "Invalid webhook token."
  }
  ```

### `[GET]` `/api/webhook/plugins/status`
* **설명**: 외부 모니터링 프로그램(알림 봇, 헬스체크 스크립트 등)이 세션 로그인 없이 플러그인 로드 성공/실패 현황을 조회할 수 있는 read-only 웹훅 API. 관리자 대시보드 상단의 플러그인 상태 패널과 동일한 데이터를 반환합니다. `/api/webhook/scan`과 동일한 `WEBHOOK_TOKEN`을 공유하므로 별도 키 발급이 필요 없습니다.
* **권한**: 비세션 인증 (`WEBHOOK_TOKEN`을 쿼리스트링 `token` 또는 `X-Webhook-Token` 헤더로 전달)
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `token` | string | 조건부 필수 | `WEBHOOK_TOKEN` 값. `X-Webhook-Token` 헤더로 대신 전달해도 됨(둘 중 하나만 있으면 됨) |

* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "error_count": 1,
    "statuses": [
      {"plugin_id": "aladin", "status": "success", "message": null, "occurred_at": "2026-08-13 05:27:49"},
      {"plugin_id": "stats_dashboard", "status": "error", "message": "No module named 'foo'", "occurred_at": "2026-08-13 05:27:49"}
    ],
    "recent_events": [ "... 최근 상태 변화 이력 최대 50건 (statuses와 동일한 필드 구조) ..." ]
  }
  ```
* **응답 예시 (401 Unauthorized - 토큰 오류)**: `/api/webhook/scan`과 동일한 형식.
* **참고**: `statuses`는 플러그인별 가장 최근 상태 1건씩(현재 상태 스냅샷), `recent_events`는 상태가 실제로 바뀐 시점들의 이력(성공→실패, 실패→성공 전환 시마다 1건 기록, 상태 불변 시에는 기록 안 함)입니다.

### `[GET]` `/api/webhook/system/db-engine`
* **설명**: DB 게이트웨이(API)를 거치지 않고 DB에 직접 접속해야 하는 외부 연동 프로그램/플러그인이, 현재 운영 중인 DB 엔진이 SQLite인지 MariaDB인지 사전에 확인할 수 있는 read-only 웹훅 API. `DB_ENGINE`(또는 `DBMS`) 환경변수 판별 로직을 그대로 반영합니다.
* **권한**: 비세션 인증 (`WEBHOOK_TOKEN`을 쿼리스트링 `token` 또는 `X-Webhook-Token` 헤더로 전달)
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `token` | string | 조건부 필수 | `WEBHOOK_TOKEN` 값. `X-Webhook-Token` 헤더로 대신 전달해도 됨(둘 중 하나만 있으면 됨) |

* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "engine": "sqlite",
    "is_mariadb": false
  }
  ```
* **응답 예시 (401 Unauthorized - 토큰 오류)**: `/api/webhook/scan`과 동일한 형식.
* **참고**: `engine`은 `"sqlite"` 또는 `"mariadb"` 둘 중 하나이며(환경변수가 `mysql`이어도 `mariadb`로 정규화), `is_mariadb`는 동일 정보를 boolean으로 제공합니다.

#### 💡 외부 폴러(gd-poller 등) 연동 설정 예시 (YAML)

외부 Google Drive 변경 모니터링 도구인 [`gd-poller`](https://github.com/halfaider/gd-poller)와 연동하면, 스케줄러의 전체 디렉토리 스캔을 기다리지 않고 변경이 감지된 폴더(시리즈) 하나만 즉시 스캔+등록할 수 있습니다.

`gd-poller`에는 범용 HTTP 웹훅 디스패처가 없고, `CommandDispatcher`는 설정한 명령어 뒤에 `[action, file|directory, path, removed_path?]`를 그대로 인자로 append해서 실행하는 구조라 `curl`을 직접 command로 지정할 수 없습니다(경로가 쿼리스트링이 아닌 위치 인자로 붙습니다). 이를 위해 인자를 받아 라이브러리 상대경로로 변환한 뒤 `/api/webhook/scan`을 호출하는 브릿지 스크립트를 `tools/gdpoller_scan_bridge.py`에 포함해두었습니다.

**CommandDispatcher 설정 (gd-poller config.yaml)**
```yaml
- class: CommandDispatcher
  command: >-
    python3 /path/to/media_server/tools/gdpoller_scan_bridge.py
    --base-url http://your-bookoasis-ip:5930
    --token oasis_secure_api_token_1234
    --library-id 25
    --type general
    --root /path/that/gd-poller/sees/as/the/library/root
    --debounce 20
```

* `--root`는 gd-poller가 인식하는(= mappings 적용 후) 라이브러리 물리 경로의 루트입니다. 브릿지 스크립트가 변경된 파일의 부모 폴더를 이 루트 기준 상대경로로 변환해 `path` 파라미터로 넘깁니다.
* `--debounce`(초)는 동일 폴더에 대한 연속 이벤트를 로컬에서 걸러내는 값입니다. gd-poller의 `CommandDispatcher` 자체는 폴더 단위 버퍼링/그룹핑을 하지 않으므로(파일 단위로 즉시 dispatch), 다중 파일이 한꺼번에 올라오는 경우를 대비해 스크립트 쪽에서 최소한의 중복 호출 억제를 수행합니다.

### 아웃바운드 표준 이벤트 웹훅 (Outbound Standard Event Webhook)

BookOasis는 외부 수신 서버로 도서 이벤트를 `POST` 전송할 수 있습니다.

- 대상 URL 설정:
  - `WEBHOOK_EVENT_ENDPOINT` (단일)
  - `WEBHOOK_EVENT_ENDPOINTS` (다중, 쉼표/개행/세미콜론 구분)
- 관련 설정:
  - `WEBHOOK_EVENT_TIMEOUT` (초)
  - `WEBHOOK_EVENT_RETRY` (재시도 횟수)
  - `WEBHOOK_EVENT_SECRET` (설정 시 `X-BookOasis-Signature` HMAC-SHA256 헤더 포함)

* **발행 이벤트 타입**:
  - `book.new` : 신규 도서 감지 시
  - `book.read` : 독서 진행도 증가 시
  - `book.finish` : 완독 전이(미완료 -> 완료) 시

* **요청 메서드**: `POST`
* **Content-Type**: `application/json`
* **요청 바디 예시**:
  ```json
  {
    "event": "book.read",
    "user": true,
    "Account": {
      "id": 123456,
      "title": "사용자이름"
    },
    "Metadata": {
      "type": "book",
      "format": "epub",
      "title": "책 제목",
      "author": "저자 이름",
      "publisher": "출판사",
      "series": "시리즈 명",
      "seriesIndex": null,
      "progress": 45,
      "totalPages": null,
      "currentLocation": "epubcfi(/6/2[chap01]!/4/2/14)",
      "addedAt": 1690000000
    }
  }
  ```

* **포맷별 제약사항**:
  - EPUB/TXT는 물리 페이지가 고정되지 않아 `totalPages`가 `null`일 수 있습니다.
  - 진행도 해석은 `Metadata.progress`(0~100)를 우선 사용하십시오.
  - `Metadata.currentLocation`은 포맷별 포인터로 해석하십시오.
    - EPUB: `href`/`cfi`/`spine` 문자열
    - TXT: `chunk:N`
    - PDF/ZIP/CBZ: `page:N`

* **헤더 예시 (서명 사용 시)**:
  - `X-BookOasis-Event: book.read`
  - `X-BookOasis-Signature: sha256=<hexdigest>`

#### 이벤트 필드 보장/Nullable 규격표

| 필드 경로 | 타입 | 보장 여부 | Nullable | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| `event` | string | 항상 포함 | 아니오 | `book.new`, `book.read`, `book.finish` |
| `user` | boolean | 항상 포함 | 아니오 | 시스템 이벤트는 `false` 가능 |
| `Account.id` | integer | 항상 포함 | 아니오 | 시스템 이벤트는 `0` |
| `Account.title` | string | 항상 포함 | 아니오 | 시스템 이벤트는 `system` |
| `Metadata.type` | string | 항상 포함 | 아니오 | 현재 `book` |
| `Metadata.format` | string | 항상 포함 | 예 | 미확인 포맷은 빈 문자열 가능 |
| `Metadata.title` | string | 항상 포함 | 예 | 원본 메타 누락 시 빈 문자열 |
| `Metadata.author` | string | 항상 포함 | 예 | 원본 메타 누락 시 빈 문자열 |
| `Metadata.publisher` | string | 항상 포함 | 예 | 원본 메타 누락 시 빈 문자열 |
| `Metadata.series` | string | 항상 포함 | 예 | 시리즈 미매핑 시 `null` |
| `Metadata.seriesIndex` | integer | 항상 포함 | 예 | 현재 기본 `null` |
| `Metadata.progress` | integer | 항상 포함 | 아니오 | 0~100 정수 |
| `Metadata.totalPages` | integer | 항상 포함 | 예 | EPUB/TXT에서 `null` 가능 |
| `Metadata.currentLocation` | string | 항상 포함 | 예 | 포맷별 포인터(`epubcfi`, `chunk:N`, `page:N`) |
| `Metadata.addedAt` | integer | 항상 포함 | 예 | Unix timestamp seconds |

#### 이벤트별 권장 소비 규칙

- `book.new`: 신규 인덱싱 이벤트로 간주, 진행률 필드는 참고용
- `book.read`: 진행률 갱신 이벤트로 간주, `progress`를 1차 소스로 사용
- `book.finish`: 완독 확정 이벤트로 간주, 동일 도서/사용자 중복 처리(멱등) 권장

---

## 💻 7. 프론트엔드 연동용 전역 JavaScript API (Frontend JS API)

플러그인이나 커스텀 스크립트 등 프론트엔드 환경에서 특정 도서를 클릭했을 때 상세 뷰어 화면으로 페이지 전환을 유발하려는 경우, 아래의 전역 함수를 호출할 수 있습니다.

### `window.openBookDetail(event, seriesName, libraryId)`
* **설명**: 메인 대시보드 또는 그리드 화면을 숨기고 지정한 시리즈의 상세 단행본 목록 화면(`detail` view)을 활성화하여 렌더링합니다.
* **파라미터**:
  * `event` (Object, 선택/nullable): 마우스 클릭 이벤트 객체 (필요하지 않은 경우 `null` 입력)
  * `seriesName` (string, 필수): 이동하려는 시리즈명
  * `libraryId` (integer/string, 선택/nullable): 해당 시리즈가 소속된 라이브러리 카테고리 ID
    * *Tip*: `libraryId`를 모르는 경우 `null` 또는 `'all'`을 전달하면, 백엔드 서비스가 DB에서 해당 시리즈의 실제 소속 라이브러리를 역추적하여 매핑해주므로 안전하게 호출이 가능합니다.
* **호출 예시**:
  ```javascript
  // 시리즈 상세화면 강제 이동 (라이브러리 자동 매핑)
  window.openBookDetail(null, '평범한 연애는 할 수 없어');
  ```

### `window.openReader(bookId, format, title, pagesRead, totalPages)`
* **설명**: 지정된 도서 ID의 뷰어(책 읽기 화면) 모달을 즉시 실행하여 띄웁니다.
* **파라미터**:
  * `bookId` (integer, 필수): 대상 도서의 고유 ID (`books.id`)
  * `format` (string, 필수): 파일 포맷 (`'zip'`, `'cbz'`, `'epub'`, `'pdf'`, `'txt'`, `'imgdir'`)
  * `title` (string, 필수): 뷰어 상단에 표기될 도서명
  * `pagesRead` (integer, 선택): 기존 페이지 독서 진행도 (기본: `0`)
  * `totalPages` (integer, 선택): 도서의 총 페이지 수 (기본: `0`)
* **호출 예시**:
  ```javascript
  // 단일 도서 뷰어 즉시 열기
  window.openReader(198, 'imgdir', '평범한 연애는 할 수 없어 01권', 0, 192);
  ```

### 상세 딥링크 URL 규격 및 주소 복원 정책
* **목적**: 상세 화면 재진입(새로고침/뒤로가기/외부 공유 링크)을 안정적으로 지원하기 위한 프론트엔드 라우팅 규격입니다.
* **표준 딥링크 포맷**:
  * `/#detail?v=<URL-safe-Base64-token>`
  * `v` 토큰 payload에는 `series`, `libraryId`, `repBookId`, `displayTitle` 정보가 난독화되어 포함됩니다.
* **하위 호환 포맷**:
  * `/#detail?series=<...>&libraryId=<...>&repBookId=<...>&displayTitle=<...>`
  * 레거시 명시적 쿼리 파라미터도 계속 복원됩니다.
* **복원 정책 (현재 동작)**:
  * 진입 탭/세션 종류와 무관하게 `#detail?...` 해시가 유효하면 상세 화면 복원을 시도합니다.
  * 딥링크 파싱에 실패하거나 `series`가 비어 있으면 카테고리 뷰로 안전 폴백합니다.
* **인증 주의사항**:
  * 주소 복원은 프론트 라우팅 동작이며, 실제 상세 데이터 조회(`/api/media/detail`)는 로그인 세션이 필요합니다.
  * 비로그인 상태에서는 인증 절차 후 상세 데이터가 로드됩니다.

---

### 💡 대시보드 플러그인 위젯 카드 연동 규격 (Widget Item Click Contract)

대시보드 위젯(플러그인)용 API(`/api/media/dashboard/widgets/<pluginId>/data`)가 반환하는 `items` 리스트의 각 객체에 대해 다음 규칙이 자동으로 프론트엔드(`dashboard.js`) 단에서 융합 적용됩니다.

* **동작 규칙**:
  * 아이템 객체에 외부 링크 `link`가 없는 경우 (또는 `#`인 경우)에만 아래 라우팅 분기가 성립됩니다:
    1. **단일 도서 뷰어 즉시 열기**: `book_id` (또는 `bookId`)와 `file_format` (또는 `format`)이 동시에 존재하는 경우:
       * 해당 카드의 최상위 컨테이너에 클릭 시 `window.openReader(bookId, format, title, pagesRead, totalPages)`를 즉시 실행하도록 이벤트가 지정되며, `cursor: pointer` 스타일이 부여됩니다.
    2. **시리즈 상세 페이지로 이동**: 위 항목이 만족하지 않고 `series_name` (또는 `series`)만 존재하는 경우:
       * 해당 카드의 최상위 컨테이너에 클릭 시 `window.openBookDetail(event, series_name, library_id)` 함수가 작동하며, `cursor: pointer` 스타일이 부여됩니다.
  * 아이템 객체에 외부 링크 `link`가 있는 경우 (예: 외부 도서 리뷰 페이지 등):
    * 해당 클릭 훅은 무시되며, 카드 본문의 타이틀 링크(`<a>` 태그의 아웃링크)를 통해 기존처럼 외부 탭으로 안전하게 이동합니다.
  * 플러그인 개발 및 커스텀 이벤트를 위해, 위젯 카드 엘리먼트(`div.plugin-item-card`)에 `data-series-name`, `data-library-id`, `data-book-id`, `data-file-format` 속성이 항상 자동으로 주입됩니다.

---

## 🧩 8. 플러그인 & 듀얼 UI 아키텍처 API (`plugins` / `metadata_factory`)

### `[GET]` `/api/media/category-plugins`
* **설명**: 사이드바 및 뷰포트에 마운트할 활성화된 카테고리 레벨 플러그인 목록을 반환합니다. (일반 사용자의 경우 권한이 차단된 플러그인은 자동 필터링됨)
* **쿼리 파라미터**:
  * `type` (string, 선택): DB 구분 (`general` / `adult`)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "category_plugins": [
      {
        "id": "stats_dashboard",
        "name": "통계 대시보드 위젯",
        "category_id": "plugin_stats_dashboard",
        "title": "독서 통계 센터",
        "icon": "fa-solid fa-chart-column",
        "order": 90
      }
    ]
  }
  ```

---

### `[GET]` `/api/media/plugins/<plugin_id>/ui`
* **설명**: 듀얼 UI 서빙 사양에 따라 플러그인의 HTML5, CSS, JS 번들 템플릿 자원을 서빙합니다.
* **URL 파라미터**:
  * `plugin_id` (string, 필수): 플러그인 고유 ID (예: `stats_dashboard`)
* **쿼리 파라미터**:
  * `target` (string, 선택): 서빙 뷰 타겟 (`view` = 카테고리 풀페이지 뷰 (`index.html`), `settings` = 환경설정 카드 폼 (`settings.html`), 기본값: `view`)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "ui": {
      "html": "<div class=\"stats-view-container\">...</div>",
      "css": "/* style.css */",
      "js": "/* script.js */"
    }
  }
  ```

---

### `[GET]` `/api/media/plugins/add-plugin-check`
* **설명**: 비공개(private) 플러그인이 자기 자신의 선택적 활성화 여부를 스스로 판단할 수 있도록 하는 조회 API. 운영자가 `.env`/docker-compose override 또는 DB `settings` 테이블의 `ADD_PLUGIN` 값을 조회 대상 `plugin_id`와 정확히 일치하도록 설정해두지 않는 한 항상 `enabled: false`를 반환합니다. 베타 테스트 단계이므로 현재는 고정된 단일 plugin_id `-----`만 지원하며, 그 외 값은 항상 `enabled: false`입니다. 자세한 사용법은 [guide_plugins.md](./guide_plugins.md#비공개private-플러그인-선택적-활성화-add_plugin-베타-테스트-단계)를 참고하세요.
* **권한**: 없음 (로그인 세션 불필요, 다른 플러그인 부트스트랩용 API와 동일한 공개 조회 성격)
* **쿼리 파라미터**:
  * `plugin_id` (string, 필수): 활성화 여부를 확인할 플러그인 ID
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "plugin_id": "-----",
    "enabled": true
  }
  ```
* **참고**: 조회한 `plugin_id` 하나의 일치 여부만 반환하며, 서버에 설정된 `ADD_PLUGIN` 값 자체는 절대 노출하지 않습니다. 기존 `PLUGIN_ENABLED_{id}` DB 토글(관리자 UI on/off)과는 별개의 게이트입니다.

---

### `[GET]` `/api/media/dashboard/widgets/<plugin_id>/data`
* **설명**: 플러그인의 대시보드 미니 위젯 및 카테고리 풀페이지 전용 동적 쿼리 데이터(`stats`, `items`)를 조회합니다.
* **쿼리 파라미터**:
  * `type` (string, 선택): DB 구분 (`general` / `adult`, 기본값: `general`)
  * `limit` (integer, 선택): 위젯 아이템 노출 개수 (기본값: `3`)

---

### `[GET]` `/api/media/plugins/load-status`
* **설명**: 관리자 대시보드 상단 플러그인 상태 패널용 API. 조회 시점에 플러그인 discovery를 1회 갱신한 뒤, 플러그인별 최신 로드 성공/실패 상태와 최근 상태 변화 이력을 반환합니다. 세션 쿠키 인증이라 외부 프로그램은 대신 `/api/webhook/plugins/status`(토큰 인증)를 사용해야 합니다.
* **권한**: `@admin_required`
* **응답 형식**: `/api/webhook/plugins/status`와 동일(아래 6번 섹션 참고)

---

### `[GET]` `/api/media/metadata/plugins/manage`
* **설명**: 관리자 환경설정 탭에서 전체 등록된 플러그인 및 샘플 업데이트 상태 목록을 조회합니다.
* **권한**: `@admin_required`

---

### `[POST]` `/api/media/metadata/plugins/toggle`
* **설명**: 특정 플러그인의 활성화/비활성화 상태를 설정하고 영구 반영합니다.
* **권한**: `@admin_required`
* **요청 파라미터**:
  ```json
  {
    "plugin_id": "stats_dashboard",
    "enabled": true
  }
  ```

---

### `[POST]` `/api/media/metadata/plugins/save-config`
* **설명**: 플러그인 환경설정 카드 폼에서 변경된 스키마 설정값(`config_schema`)을 저장합니다.
* **권한**: `@admin_required`

---

## 🛡️ 9. 사용자 권한 관리 & 휴지통 API (`permissions` / `trash`)

### `[GET]` `/api/admin/permissions`
* **설명**: 전체 사용자 계정 목록 및 물리 카테고리/플러그인 접근 권한 매트릭스 정보를 조회합니다.
* **권한**: `@admin_required`
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "users": [{"id": 1, "username": "admin", "role": "admin", "has_adult_access": 1}],
    "categories": [
      {"id": 1, "name": "일반 소설", "db_type": "general"},
      {"id": "plugin_stats_dashboard", "name": "🧩 독서 통계 센터", "db_type": "plugin"}
    ],
    "permissions": {
      "1": {"general_1": true, "plugin_plugin_stats_dashboard": true}
    }
  }
  ```

---

### `[POST]` `/api/admin/permissions/update`
* **설명**: 특정 사용자 계정의 라이브러리 카테고리 또는 플러그인 접근 권한 토글을 개별 변경합니다.
* **권한**: `@admin_required`
* **요청 파라미터**:
  ```json
  {
    "user_id": 2,
    "library_id": "plugin_stats_dashboard",
    "has_access": true,
    "target_db": "plugin"
  }
  ```

---

### `[POST]` `/api/admin/permissions/update-adult`
* **설명**: 특정 사용자 계정의 성인 서재 접근 허용 여부를 글로벌 변경합니다.
* **권한**: `@admin_required`

---

### `[GET]` `/api/admin/trash`
* **설명**: 소프트 삭제(`is_deleted = 1`) 처리되어 휴지통에 보관된 도서 메타데이터 목록을 조회합니다.
* **권한**: `@admin_required`

---

### `[POST]` `/api/admin/trash/restore`
* **설명**: 휴지통에 보관된 선택 도서들을 정상 복구합니다.
* **권한**: `@admin_required`

---

### `[POST]` `/api/admin/trash/empty`
* **설명**: 휴지통에 보관된 도서 메타데이터 및 연결 파일을 영구 삭제합니다.
* **권한**: `@admin_required`

---

## ⚡ 10. 스캐너 & 비동기 작업 큐 API (`scan` / `system`)

### `[GET]` `/api/system/status`
* **설명**: 상단 스캔 활동 패널과 카테고리 스피너가 사용하는 경량 실시간 상태 API입니다. 실행 중 작업 1건, 대기 작업 목록, DB 튜닝 여부를 반환합니다.
* **권한**: 로그인 사용자 (`@login_required`)
* **캐시 정책**: `no-store`, `no-cache`
* **쿼리 파라미터**:
  * `type` (string, 선택): DB 스코프 (`general` / `adult` / `audiobook`, 기본값: `general`)
* **갱신 주기**: 기본 웹 UI에서 2초마다 조회합니다. 기존 카테고리 스피너와 스캔 활동 패널이 같은 응답을 공유하므로 추가 폴링은 발생하지 않습니다.
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "is_active": true,
    "tasks": [
      "[판타지 소설 (general)] 카테고리 도서 자동 스캔 동기화 진행 중...",
      "스캔 대기열: 1건"
    ],
    "raw_status": {
      "running": {
        "type": "library_scan",
        "key": "library_scan_general_12",
        "kwargs": {
          "db_type": "general",
          "library_id": 12
        },
        "enqueued_at": "2026-08-08 10:00:00",
        "started_at": "2026-08-08 10:00:03",
        "stage": null,
        "library_name": "판타지 소설"
      },
      "pending": [
        {
          "type": "cover_scan",
          "key": "cover_scan_general_13",
          "kwargs": {
            "db_type": "general",
            "library_id": 13
          },
          "enqueued_at": "2026-08-08 10:00:05",
          "stage": null,
          "library_name": "일반 만화"
        }
      ]
    },
    "has_running": true,
    "has_pending": true,
    "pending_count": 1
  }
  ```
* **필드 참고**:
  * `is_active`: 실행/대기 작업 또는 DB 튜닝이 하나라도 있으면 `true`
  * `tasks`: 사용자 표시용 상태 문구 배열
  * `raw_status.running`: 현재 실행 작업 1건 또는 `null`
  * `raw_status.pending`: 대기 작업 배열
  * `stage`: 워커가 세부 단계를 기록한 경우에만 값이 있으며 일반 스캔에서는 `null`일 수 있음
  * 파일 단위 진행률이나 현재 파일 경로는 현재 응답 계약에 포함되지 않음

---

### `[POST]` `/api/media/libraries/<int:library_id>/scan`
* **설명**: 지정한 라이브러리 카테고리의 풀 비동기 스캔 작업을 백그라운드 큐에 등록합니다.
* **권한**: `@admin_required`
* **요청 파라미터**:
  * `type` (string, 선택): DB 스코프 (기본값: `general`)
  * `force` (boolean/string, 선택): 강제 스캔 여부 (`true` / `1`)

---

### `[POST]` `/api/media/libraries/<int:library_id>/scan-path`
* **설명**: 라이브러리 전체를 다시 훑는 주기/전체 스캔과 달리, 방금 파일시스템에 추가/변경된 **도서 1권이 들어있는 폴더 또는 시리즈 폴더 하나만** 즉시 스캔하여 등록/갱신합니다. (도서 1권이라도 파일 단독이 아니라 그 파일이 들어있는 **폴더**를 대상으로 합니다 — 위 `path` 파라미터 경고 참고) 백그라운드 큐에 적재되지 않고 **동기(sync) 방식**으로 요청 응답 시점에 스캔이 완료되며, 이동/삭제 동기화도 해당 하위 경로로만 한정되어 라이브러리의 다른 도서에는 영향을 주지 않습니다.
* **권한**: `@admin_required` (세션 쿠키 로그인 필요 — 아래 "외부 연동 시 인증" 참고)
* **Content-Type**: `application/x-www-form-urlencoded`
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `type` | string | 선택 | DB 스코프 (`general` / `adult` / `audiobook`, 기본값: `general`) |
  | `path` | string | 필수 | **디렉토리(폴더) 경로**만 허용. 스캔할 폴더의 **라이브러리 `physical_path` 루트 기준 상대경로** (예: `작가A/시리즈B`). 라이브러리에 루트 경로가 여러 줄로 설정된 경우 각 루트에 순서대로 결합해 실제 존재하는 경로를 찾습니다. |
  | `force` | boolean/string | 선택 | 강제 재스캔 여부 (`true` / `1`). 이미 등록된 파일도 메타데이터를 다시 병합합니다. |

> ⚠️ **`path`는 반드시 폴더 경로여야 하며, `.zip`/`.cbz`/`.epub` 등 파일 경로는 지원하지 않습니다.**
> 외부 프로그램이 파일시스템 변경 감지 시 특정 파일(예: `작가A/시리즈B/03권.zip`) 하나만 캐치하더라도, 이 API에는 그 **파일의 부모 폴더** (`작가A/시리즈B`)를 넘겨야 합니다.
> 파일 경로를 그대로 넘기면 내부적으로 `os.walk()`가 해당 경로에서 아무 것도 찾지 못해 **조용히 아무 것도 스캔되지 않습니다** (에러 없이 무동작).
> 폴더 단위로 넘겨야 하는 이유는 단순 편의가 아니라 정확성 문제입니다 — `info.xml`/`kavita.yaml` 같은 시리즈 메타데이터 파일은 폴더 전체 목록을 봐야 인식되므로, 파일 하나만 좁혀서 넘기면 메타데이터 병합 로직이 그 폴더의 메타파일을 보지 못해 누락됩니다.
> 시리즈 폴더 전체가 아니라 볼륨 1권만 바뀐 경우에도, 상위 폴더(해당 볼륨이 들어있는 디렉토리) 단위로 호출하십시오. 같은 폴더의 기존 파일들은 `mtime`/`size` 비교로 자동 스킵되므로 재스캔 비용은 크지 않습니다.

* **동작 방식**:
  * `path`는 절대경로가 아니라 라이브러리 루트 아래의 상대경로입니다. 서버가 해당 라이브러리의 `physical_path`(멀티라인일 경우 각 줄)와 결합해 실제 존재하는 절대경로를 찾고, 결합 결과가 루트 바깥으로 벗어나면(`..` 등 경로 탈출) 거부합니다.
  * `type=audiobook`인 경우 기존 오디오북 전용 스캐너(`scan_audiobook_library`)를 그대로 재사용합니다.
  * 일반 도서(`general`/`adult`)는 지정한 하위 폴더(그 안의 하위 폴더 포함)만 순회하며, 신규 파일은 등록, 기존 파일은 메타/커버/오프셋을 갱신합니다.

* **요청 예시 (curl)**:
  ```bash
  curl -X POST "http://your-bookoasis-ip:5930/api/media/libraries/12/scan-path" \
    -b cookies.txt \
    -d "type=general" \
    -d "path=작가A/신작 시리즈" \
    -d "force=false"
  ```

* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "지정한 경로의 스캔 및 등록이 완료되었습니다."
  }
  ```

* **응답 예시 (404 - 경로를 찾을 수 없음)**:
  ```json
  {
    "success": false,
    "error": "해당 경로를 라이브러리 내에서 찾을 수 없습니다."
  }
  ```

* **외부 연동 시 인증**: 이 엔드포인트는 `/api/webhook/scan`과 달리 토큰 기반이 아니라 관리자 세션 쿠키 인증입니다. 외부 프로그램에서 호출하려면 먼저 `/login`에 관리자 계정으로 `POST`하여 세션 쿠키를 발급받고, 이후 요청에 동일 쿠키를 포함해야 합니다.
  ```bash
  # 1) 로그인하여 세션 쿠키 저장
  curl -c cookies.txt -X POST "http://your-bookoasis-ip:5930/login" \
    -d "username=admin" -d "password=your_password"

  # 2) 저장된 쿠키로 특정 경로 스캔 요청
  curl -b cookies.txt -X POST "http://your-bookoasis-ip:5930/api/media/libraries/12/scan-path" \
    -d "type=general" -d "path=작가A/신작 시리즈"
  ```
* **비고**: 응답이 올 때까지 스캔이 동기적으로 실행되므로, 대용량 시리즈(수백 권 단위)를 대상으로 호출하면 응답 지연이 길어질 수 있습니다. 폴더 하나(단행본/시리즈 1개) 단위 호출을 권장합니다.

---

### `[POST]` `/api/media/libraries/<int:library_id>/cancel-scan`
* **설명**: 지정한 라이브러리의 `scan_status`를 `cancelling`으로 변경하여 진행 중 스캔에 취소를 요청합니다.
* **권한**: `@admin_required`
* **주의**: 실행 프로세스를 즉시 강제 종료하는 API가 아니며, 워커가 취소 상태를 확인한 시점에 중단됩니다. 대기 작업 제거는 `/api/media/system/queue/cancel`을 사용합니다.

---

### `[POST]` `/api/media/libraries/<int:library_id>/scan-covers`
* **설명**: 지정한 라이브러리의 표지 전용 스캔(`cover_scan`)을 대기열에 등록합니다.
* **권한**: `@admin_required`
* **요청 파라미터**:
  * `type` (string, 선택): DB 스코프 (기본값: `general`)

---

### `[POST]` `/api/media/libraries/scan-all`
* **설명**: 등록된 전체 카테고리 서재에 대해 일괄 스캔을 백그라운드 큐에 스케줄링합니다.
* **권한**: `@admin_required`

---

### `[GET]` `/api/media/system/queue`
* **설명**: 관리자 큐 화면에서 실행 중 작업 1건과 대기 작업 목록을 조회합니다. 완료 작업 목록과 숫자 진행률은 반환하지 않습니다.
* **권한**: `@admin_required`
* **응답 구조**:
  ```json
  {
    "success": true,
    "queue": {
      "running": {
        "type": "library_scan",
        "key": "library_scan_general_12",
        "kwargs": {"db_type": "general", "library_id": 12},
        "enqueued_at": "2026-08-08 10:00:00",
        "started_at": "2026-08-08 10:00:03",
        "stage": null,
        "library_name": "판타지 소설 (general)"
      },
      "pending": []
    }
  }
  ```

---

### `[POST]` `/api/media/system/queue/clear`
* **설명**: 대기 중인 모든 백그라운드 작업을 취소하고 큐를 초기화합니다.
* **권한**: `@admin_required`

---

### `[POST]` `/api/media/system/queue/cancel`
* **설명**: 대기 중인 특정 작업 1건을 취소합니다. 실행 중 작업에는 적용되지 않습니다.
* **권한**: `@admin_required`
* **쿼리 또는 Form 파라미터**:
  * `task_id` (string, 필수): 취소할 작업의 `key` 값. 이름은 `task_id`지만 숫자 DB ID가 아니라 `library_scan_general_12` 같은 `task_key`를 전달합니다.
* **응답 코드**:
  * `200`: 취소 성공
  * `400`: `task_id` 누락
  * `404`: 해당 대기 작업을 찾지 못함

---

## 📖 11. 뷰어 스트리밍 & 보조 API (`stream` / `library`)

### `[GET]` `/api/media/txt`
* **설명**: TXT 소설 파일의 특정 청크/인덱스 텍스트를 JSON으로 스트리밍 서빙합니다.
* **쿼리 파라미터**: `id` (book_id), `chunk` (chunk_index), `type` (general/adult)

---

### `[GET]` `/api/media/epub/meta`, `/api/media/epub/chapter`, `/api/media/epub-image`
* **설명**: EPUB 전자책의 목차(TOC)/CFI 메타, 개별 장(Chapter) HTML 및 내장 이미지를 부분 서빙합니다.

---

### `[GET]` `/api/media/pdf`
* **설명**: PDF 도서의 바이너리 문서 스트림 또는 렌더링용 바이트 버퍼를 서빙합니다.

---

### `[GET]` `/covers/<path:filename>`
* **설명**: 추출된 도서 표지 이미지 파일 또는 고유 커버 썸네일을 보안 검증 후 정적 서빙합니다.

---

### `[POST]` `/api/media/unread`
* **설명**: 해당 도서의 독서 진척도(`user_progress`) 및 읽기 기록을 '안읽음' 상태로 초기화합니다.
* **요청 파라미터**: `book_id` (integer), `db_type` (string)





