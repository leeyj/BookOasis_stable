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
  * `library_id` (integer/string, 필수): 카테고리 ID (특정 ID 또는 `'all'`, `'home'` 등)
* **응답 예시 (200 OK)**:
  ```json
  {
    "success": true,
    "meta": {
      "author": "추공",
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

---

## 📡 6. 외부 연동 및 자동화용 웹훅 API (Webhook)

### `[GET]` 또는 `[POST]` `/api/webhook/scan`
* **설명**: 외부 마운트 제어(gd-poller 등)나 자동화 갱신 트리거 시, 세션 로그인 없이 헤더나 쿼리 스트링 보안 토큰만으로 라이브러리 스캔 작업을 즉시 대기열에 비동기 등록합니다.
* **권한**: 비세션 인증 (단, `.env`의 `WEBHOOK_TOKEN`과 매칭 검증 필수)
* **요청 파라미터**:
  | 파라미터명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `token` | string | 필수 | `.env`에 정의된 `WEBHOOK_TOKEN` 보안 API 토큰값 |
  | `library_id` | integer | 필수 | 동기화 스캔을 수행할 대상 라이브러리 카테고리의 고유 ID |
  | `type` | string | 선택 | 라이브러리 데이터베이스 영역 (`general` 또는 `adult`, 디폴트: `general`) |

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

#### 💡 외부 폴러(gd-poller 등) 연동 설정 예시 (YAML)

외부 Google Drive 변경 모니터링 도구인 `gd-poller` 등과 연동할 때, 아래의 디스패처 설정을 활용해 북오아시스의 특정 라이브러리를 동적으로 재스캔할 수 있습니다.

**[Option A] WebhookDispatcher 설정**
```yaml
- class: WebhookDispatcher
  url: "http://your-bookoasis-ip:5930/api/webhook/scan"
  method: "GET"
  params:
    token: "oasis_secure_api_token_1234"  # .env의 WEBHOOK_TOKEN 설정값
    library_id: "25"                       # 대상 라이브러리 카테고리 ID
    type: "general"                        # general 또는 adult
  buffer_interval: 60                      # 변경 발생 시 60초 대기 후 누적 1회 트리거
```

**[Option B] CommandDispatcher (curl 쉘 스크립트 실행) 설정**
```yaml
- class: CommandDispatcher
  command: "curl -s 'http://your-bookoasis-ip:5930/api/webhook/scan?token=oasis_secure_api_token_1234&library_id=25&type=general'"
  buffer_interval: 60
```

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




