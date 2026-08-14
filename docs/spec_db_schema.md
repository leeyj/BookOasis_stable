# 🗄️ 데이터베이스 스키마 명세

BookOasis는 **SQLite(기본값)** 와 **MariaDB/MySQL(엔터프라이즈 권장)** 두 엔진을 선택적으로 지원하며, 두 경우 모두 논리적으로 동일한 스키마(테이블/컬럼 구성)를 유지합니다. `.env`의 `DB_ENGINE` 값(`sqlite` 또는 `mariadb`)에 따라 아래 중 하나로 동작합니다.

- **SQLite 모드**: `general`, `adult`, `audiobook` **3개의 독립 DB 파일** 사용
  - 일반 DB: `db/media_general.db`
  - 성인 DB: `db/media_adult.db`
  - 오디오북 DB: `db/media_audiobook.db`
- **MariaDB 모드**: `general`, `adult`, `audiobook` **3개의 독립 데이터베이스(스키마)** 사용 (기본 접두어 `media_`, `mariadb_database_prefix` 설정으로 변경 가능)
  - `media_general`, `media_adult`, `media_audiobook`
  - 전환/마이그레이션 절차는 [move_to_mariadb.md](./move_to_mariadb.md), [guide_admin.md](./guide_admin.md) 8절 참고

3개 DB(파일 또는 스키마) 모두 **동일한 전체 테이블 세트**가 생성됩니다. 예를 들어 `audiobook` DB에도 `books`/`user_favorites` 같은 도서 전용 테이블이 (미사용 상태로) 함께 생성되고, 반대로 `general`/`adult` DB에도 `audiobooks` 계열 테이블이 함께 생성됩니다. 실제로 의미 있게 쓰이는 테이블은 DB 종류에 따라 다릅니다.

이 문서는 코드 기준 최신 스키마 스냅샷(**2026-08-14 기준**, SQLite는 `database.py:init_databases`, MariaDB는 `tools/db_schema_updater.py:MARIADB_CENTRAL_SCHEMA`)과 테이블 역할을 정리합니다.

---

## 1. 스키마 개요

- SQLite 3개 DB 파일(general/adult/audiobook) 모두 `schema`(공통 SQL 문자열) 하나로 동일하게 초기화됩니다.
- MariaDB 3개 데이터베이스도 마찬가지로 `MARIADB_CENTRAL_SCHEMA` 하나로 동일하게 초기화됩니다.
- 기동 시 `auto_migrate_schema(...)`(SQLite) / `_ensure_mariadb_columns()`, `_ensure_mariadb_indexes()`(MariaDB)로 선언 스키마에 없는 컬럼·인덱스를 자동 보강합니다.
- 다만 과거 버전에서 올라온 운영 DB는 잔여 컬럼/인덱스가 남아 있을 수 있으므로, 코어/플러그인 쿼리는 호환성을 고려해야 합니다.
- MariaDB는 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin`을 사용하며, SQLite의 `INTEGER`/`TEXT`는 MariaDB에서 대체로 `BIGINT`/`VARCHAR(n)` 또는 `TEXT`로 매핑됩니다(컬럼별 실제 타입은 6절 코드 스냅샷 참고).

---

## 2. 공통 테이블 목록

두 엔진·3개 DB 공통 테이블 (총 23개):

**도서/라이브러리 핵심**
1. `library_groups`
2. `libraries`
3. `books`
4. `book_offsets`
5. `series_summary`
6. `series_summary_state`

**오디오북**
7. `audiobooks`
8. `audiobook_tracks`
9. `audiobook_progress`
10. `audiobook_track_progress`

**사용자/진행률**
11. `users`
12. `user_progress`
13. `user_reading_log`
14. `user_favorites`
15. `user_category_permissions`

**컬렉션**
16. `collections`
17. `collection_items`

**스캐너/운영**
18. `scanner_tasks`
19. `scan_history`
20. `scanner_progress`
21. `folder_mtimes`

**설정/플러그인**
22. `settings`
23. `plugin_load_events`

---

## 3. 테이블 상세

### library_groups

라이브러리를 묶는 상위 그룹(사이드바 폴더 그룹핑).

- PK: `id`
- 컬럼: `name`, `icon`, `color`, `sort_order`

### libraries

라이브러리 루트 및 스캔 설정.

- PK: `id`
- 주요 FK: `group_id -> library_groups.id`
- 컬럼: `name`, `physical_path`, `cron_schedule`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`, `hide_cover`, `group_id`, `sort_order`
- `hide_cover`: 카테고리 단위로 대표/목록 커버 렌더링을 숨길지 여부를 저장 (`INTEGER DEFAULT 0`)
- 참고: 운영 DB에는 과거 마이그레이션 잔여 컬럼이 남아 있을 수 있음

### books

도서 메타데이터 및 파일 식별 정보.

- PK: `id`
- 주요 FK: `library_id -> libraries.id`
- 주요 컬럼:
  - 식별/경로: `id`, `library_id`, `file_path`, `file_format`
  - 메타: `title`, `series_name`, `author`, `isbn`, `publisher`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`
  - 뷰어/커버: `total_pages`, `cover_image`, `cover_updated_at`, `has_offsets`
  - 상태/보호: `metadata_locked`, `created_at`
  - 정렬/별칭: `series_alias`, `title_alias`
  - 운영 확장: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`
- 비고: `is_favorite` 컬럼은 레거시 호환용으로 남아 있으나, 현재 즐겨찾기 실사용 저장소는 `user_favorites`입니다.

### book_offsets

압축 파일(예: ZIP) 내부 페이지 오프셋 캐시. 뷰어가 페이지 하나를 요청할 때마다 zip 전체를 열지 않고, 여기 저장된 offset으로 필요한 바이트 구간만 seek/read 합니다.

- PK: `id`
- 주요 FK: `book_id -> books.id`
- 컬럼: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`
- MariaDB에서는 offset 관련 컬럼이 `BIGINT`로, 4GB(ZIP64)를 넘는 대용량 원본 아카이브도 지원합니다.

### series_summary / series_summary_state

시리즈 그룹핑·대표 표지 사전 집계 캐시 (라이브러리 목록 렌더링 고속화용).

- `series_summary` PK: (`library_id`, `series_key`) 복합키
  - 컬럼: `representative_book_id`, `series_book_count`, `sort_series_name`
- `series_summary_state` PK: `id`
  - 컬럼: `is_ready`, `refreshed_at` — 백그라운드 재집계 완료 여부 플래그

### audiobooks

오디오북(작품 단위) 메타데이터.

- PK: `id`
- 주요 FK: `library_id -> libraries.id`
- 컬럼: `title`, `sort_title`, `web_id`, `author`, `publisher`, `code`, `poster`, `premiered`, `ratings`, `author_intro`, `description`, `folder_name`, `folder_path`(UNIQUE), `total_duration`, `total_tracks`, `file_type`, `is_favorite`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`

### audiobook_tracks

오디오북 개별 트랙(파일) 정보.

- PK: `id`
- 주요 FK: `audiobook_id -> audiobooks.id` (ON DELETE CASCADE)
- 컬럼: `track_number`, `track_code`, `filename`, `file_path`(UNIQUE), `file_mtime`, `file_size`, `duration`, `format`

### audiobook_progress / audiobook_track_progress

오디오북 사용자별 재생 진행률(작품 단위 / 트랙 단위).

- `audiobook_progress` 주요 FK: `audiobook_id -> audiobooks.id`, `current_track_id -> audiobook_tracks.id`
  - 컬럼: `user_id`, `current_time`, `total_progress_pct`, `playback_rate`, `is_completed`, `last_listened_at`
  - 제약: `UNIQUE(audiobook_id, user_id)`
- `audiobook_track_progress` 주요 FK: `audiobook_id -> audiobooks.id`, `track_id -> audiobook_tracks.id`
  - 컬럼: `user_id`, `current_time`, `progress_pct`, `is_completed`, `updated_at`
  - 제약: `UNIQUE(audiobook_id, track_id, user_id)`

### users

사용자 계정 및 권한.

- PK: `id`
- 컬럼: `username`(UNIQUE), `password_hash`, `role`, `is_default_password`, `has_adult_access`, `has_audiobook_access`, `created_at`

### user_progress

도서별 사용자 진행률.

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read`, `is_completed`, `last_read_at`, `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_fingerprint`, `last_epub_updated_at`
- 참고: EPUB은 서버/클라이언트 세션 포인터(예: CFI, href, spine index) 기반 이어읽기에 이 컬럼들을 사용합니다.
- 제약: `UNIQUE(book_id, user_id)`

### user_reading_log

사용자 읽기 활동 로그(일별 집계/통계 근거).

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read_delta`, `duration_seconds`, `read_date`

### user_favorites

사용자별 즐겨찾기 매핑 테이블.

- PK: `id`
- 주요 FK: `user_id -> users.id`, `book_id -> books.id`
- 컬럼: `user_id`, `book_id`, `created_at`
- 제약: `UNIQUE(user_id, book_id)`

### user_category_permissions

사용자-라이브러리 접근 권한 매핑.

- PK: `id`
- 주요 FK: `user_id -> users.id`, `library_id -> libraries.id`
- 컬럼: `has_access`
- 제약: `UNIQUE(user_id, library_id)`

### collections / collection_items

사용자 정의 컬렉션(도서/시리즈/오디오북을 자유롭게 묶는 모음).

- `collections` PK: `id`
  - 주요 FK: `user_id -> users.id`
  - 컬럼: `name`, `description`, `color`, `cover_image`, `created_at`, `updated_at`
- `collection_items` PK: `id`
  - 주요 FK: `collection_id -> collections.id`(CASCADE), `book_id -> books.id`(CASCADE, nullable), `audiobook_id -> audiobooks.id`(CASCADE, nullable)
  - 컬럼: `series_name`(nullable), `sort_order`, `created_at`
  - 제약: `UNIQUE(collection_id, book_id)`, `UNIQUE(collection_id, series_name)`, `UNIQUE(collection_id, audiobook_id)` — 도서/시리즈/오디오북 중 하나만 채워짐

### scanner_tasks

백그라운드 스캐너 작업 큐(대기/실행/완료 상태).

- PK: `id`
- 컬럼: `task_type`, `task_key`(UNIQUE), `status`, `kwargs`, `stage`, `worker_pid`, `enqueue_at`, `started_at`, `finished_at`, `error_message`

### scan_history

완료된 스캔 작업 이력(스캐너 로그/통계용).

- PK: `id`
- 컬럼: `task_type`, `task_key`, `status`, `kwargs`, `enqueue_at`, `started_at`, `finished_at`, `error_message`, `created_at`

### scanner_progress

스캐너의 폴더 단위 진행 상태 기록.

- 복합 키 성격 컬럼: `library_id`, `folder_path`(PK)

### folder_mtimes

폴더 변경 시각 캐시(증분 스캔 최적화).

- 키 성격 컬럼: `folder_path`(PK)
- 컬럼: `dir_mtime`, `meta_mtime`

### settings

전역/플러그인 설정 저장소.

- PK: `key`
- 컬럼: `key`, `value`, `updated_at`
- 주요 키 예시:
  - `TAG_FILTER_SEARCH_SCOPE_ALL`
  - `RCLONE_RC_URL`
- 플러그인 관련 키 예시:
  - `PLUGIN_ENABLED_<plugin_id>`
  - `PLUGIN_CONFIG_<plugin_id>`

### plugin_load_events

플러그인 로드/오류 이벤트 로그.

- PK: `id`
- 컬럼: `plugin_id`, `status`, `message`, `occurred_at`

---

## 4. 관계 요약

- `library_groups (1) -> libraries (N)`
- `libraries (1) -> books (N)`
- `libraries (1) -> audiobooks (N)`
- `books (1) -> book_offsets (N)`
- `books (1) -> user_progress (N)`
- `books (1) -> user_reading_log (N)`
- `books (1) -> user_favorites (N)`
- `books (1) -> collection_items (N)`
- `audiobooks (1) -> audiobook_tracks (N)`
- `audiobooks (1) -> audiobook_progress (N)`
- `audiobooks (1) -> audiobook_track_progress (N)`
- `audiobooks (1) -> collection_items (N)`
- `audiobook_tracks (1) -> audiobook_track_progress (N)`
- `users (1) -> user_progress (N)`
- `users (1) -> user_reading_log (N)`
- `users (1) -> user_favorites (N)`
- `users (1) -> user_category_permissions (N)`
- `users (1) -> collections (N)`
- `users (1) -> audiobook_progress (N)`
- `libraries (1) -> user_category_permissions (N)`
- `collections (1) -> collection_items (N)`

---

## 5. 플러그인 개발 시 DB 사용 원칙

- 직접 `import database`/`database.get_connection(...)` 대신 BaseProvider 헬퍼 사용
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- 설정 저장은 `settings` 테이블의 플러그인 키 규칙을 사용
- SQLite/MariaDB 간, 그리고 DB 간 컬럼 편차가 있을 수 있으므로, 신규 쿼리는 두 엔진 호환성을 고려해 작성 (예: `INTEGER` vs `BIGINT`, upsert 문법 차이 등)

---

## 6. 코드 원문 스냅샷 (CREATE TABLE / INDEX)

### 6.1 SQLite — `database.py:init_databases`

3개 DB 파일(general/adult/audiobook) 모두 아래 스키마 하나로 초기화됩니다.

```sql
CREATE TABLE IF NOT EXISTS library_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    icon TEXT DEFAULT 'fa-folder',
    color TEXT DEFAULT '#a855f7',
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS libraries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    physical_path TEXT NOT NULL,
    cron_schedule TEXT DEFAULT NULL,
    last_scanned_at DATETIME DEFAULT NULL,
    scan_status TEXT DEFAULT 'ready',
    is_remote INTEGER DEFAULT 0,
    vfs_refresh_before_scan INTEGER DEFAULT 0,
    rclone_rc_url TEXT DEFAULT NULL,
    icon TEXT DEFAULT 'fa-book',
    color TEXT DEFAULT '#94a3b8',
    hide_cover INTEGER DEFAULT 0,
    group_id INTEGER DEFAULT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scanner_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    task_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    kwargs TEXT,
    stage TEXT,
    worker_pid INTEGER DEFAULT NULL,
    enqueue_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME DEFAULT NULL,
    finished_at DATETIME DEFAULT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER REFERENCES libraries(id),
    title TEXT NOT NULL,
    series_name TEXT,
    author TEXT,
    isbn TEXT,
    file_path TEXT NOT NULL UNIQUE,
    file_format TEXT NOT NULL,
    total_pages INTEGER NOT NULL,
    has_offsets INTEGER DEFAULT 0,
    cover_image TEXT,
    publisher TEXT,
    link TEXT,
    score INTEGER,
    release_date TEXT,
    summary TEXT,
    genre TEXT,
    tags TEXT,
    is_favorite INTEGER DEFAULT 0,
    cover_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    metadata_locked INTEGER DEFAULT 0,
    series_alias TEXT,
    title_alias TEXT,
    file_mtime REAL DEFAULT 0.0,
    file_size INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS series_summary (
    library_id INTEGER NOT NULL,
    series_key VARCHAR(500) NOT NULL,
    representative_book_id INTEGER NOT NULL,
    series_book_count INTEGER NOT NULL DEFAULT 0,
    sort_series_name VARCHAR(500) NOT NULL DEFAULT '',
    PRIMARY KEY (library_id, series_key)
);

CREATE TABLE IF NOT EXISTS series_summary_state (
    id INTEGER PRIMARY KEY,
    is_ready INTEGER NOT NULL DEFAULT 0,
    refreshed_at DATETIME DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS audiobooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER REFERENCES libraries(id),
    title TEXT NOT NULL,
    sort_title TEXT,
    web_id TEXT,
    author TEXT,
    publisher TEXT,
    code TEXT,
    poster TEXT,
    premiered TEXT,
    ratings REAL DEFAULT 0.0,
    author_intro TEXT,
    description TEXT,
    folder_name TEXT NOT NULL,
    folder_path TEXT NOT NULL UNIQUE,
    total_duration REAL DEFAULT 0.0,
    total_tracks INTEGER DEFAULT 1,
    file_type TEXT DEFAULT 'multi',
    is_favorite INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS audiobook_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audiobook_id INTEGER REFERENCES audiobooks(id) ON DELETE CASCADE,
    track_number INTEGER NOT NULL,
    track_code TEXT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_mtime REAL DEFAULT 0.0,
    file_size INTEGER DEFAULT 0,
    duration REAL DEFAULT 0.0,
    format TEXT DEFAULT 'mp3'
);

CREATE TABLE IF NOT EXISTS audiobook_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audiobook_id INTEGER REFERENCES audiobooks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL DEFAULT 1,
    current_track_id INTEGER REFERENCES audiobook_tracks(id),
    current_time REAL DEFAULT 0.0,
    total_progress_pct REAL DEFAULT 0.0,
    playback_rate REAL DEFAULT 1.0,
    is_completed INTEGER DEFAULT 0,
    last_listened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(audiobook_id, user_id)
);

CREATE TABLE IF NOT EXISTS audiobook_track_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audiobook_id INTEGER REFERENCES audiobooks(id) ON DELETE CASCADE,
    track_id INTEGER REFERENCES audiobook_tracks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL DEFAULT 1,
    current_time REAL DEFAULT 0.0,
    progress_pct REAL DEFAULT 0.0,
    is_completed INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(audiobook_id, track_id, user_id)
);

CREATE TABLE IF NOT EXISTS user_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER REFERENCES books(id),
    user_id INTEGER NOT NULL,
    pages_read INTEGER DEFAULT 0,
    is_completed INTEGER DEFAULT 0,
    last_read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_epub_cfi TEXT,
    last_epub_href TEXT,
    last_epub_spine_index INTEGER,
    last_epub_percent INTEGER DEFAULT 0,
    last_epub_fingerprint TEXT,
    last_epub_updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS user_reading_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER REFERENCES books(id),
    user_id INTEGER NOT NULL,
    pages_read_delta INTEGER NOT NULL,
    duration_seconds INTEGER DEFAULT 0,
    read_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS user_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER REFERENCES books(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

CREATE TABLE IF NOT EXISTS book_offsets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER REFERENCES books(id),
    page_idx INTEGER,
    filename TEXT,
    local_header_offset INTEGER,
    compress_size INTEGER,
    file_size INTEGER,
    compress_type INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scanner_progress (
    library_id TEXT,
    folder_path TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS folder_mtimes (
    folder_path TEXT PRIMARY KEY,
    dir_mtime REAL,
    meta_mtime REAL
);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    task_key TEXT,
    status TEXT NOT NULL,
    kwargs TEXT,
    enqueue_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    is_default_password INTEGER DEFAULT 1,
    has_adult_access INTEGER DEFAULT 1,
    has_audiobook_access INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_category_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    library_id INTEGER NOT NULL,
    has_access INTEGER DEFAULT 1,
    UNIQUE(user_id, library_id)
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT NULL,
    color TEXT DEFAULT '#7c3aed',
    cover_image TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    book_id INTEGER DEFAULT NULL REFERENCES books(id) ON DELETE CASCADE,
    series_name TEXT DEFAULT NULL,
    audiobook_id INTEGER DEFAULT NULL REFERENCES audiobooks(id) ON DELETE CASCADE,
    sort_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, book_id),
    UNIQUE(collection_id, series_name),
    UNIQUE(collection_id, audiobook_id)
);

CREATE TABLE IF NOT EXISTS plugin_load_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_id TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT DEFAULT NULL,
    occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**SQLite 인덱스:**

```sql
CREATE INDEX IF NOT EXISTS idx_audiobook_tracks_audiobook_id ON audiobook_tracks(audiobook_id);
CREATE INDEX IF NOT EXISTS idx_audiobook_track_progress_lookup ON audiobook_track_progress(audiobook_id, user_id, track_id);
CREATE INDEX IF NOT EXISTS idx_audiobooks_library_id ON audiobooks(library_id);
CREATE INDEX IF NOT EXISTS idx_audiobooks_title ON audiobooks(title);
CREATE INDEX IF NOT EXISTS idx_book_offsets_book_id ON book_offsets(book_id);
CREATE INDEX IF NOT EXISTS idx_book_offsets_book_page ON book_offsets(book_id, page_idx);
CREATE INDEX IF NOT EXISTS idx_books_series_name ON books(series_name);
CREATE INDEX IF NOT EXISTS idx_books_series_alias ON books(series_alias);
CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
CREATE INDEX IF NOT EXISTS idx_libraries_group_id ON libraries(group_id);
CREATE INDEX IF NOT EXISTS idx_libraries_group_order ON libraries(group_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_books_is_favorite ON books(is_favorite);
CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);
CREATE INDEX IF NOT EXISTS idx_books_series_lib_title ON books(series_name, library_id, title);
CREATE INDEX IF NOT EXISTS idx_books_library_active_series ON books(library_id, COALESCE(is_deleted, 0), COALESCE(series_name, ''));
CREATE INDEX IF NOT EXISTS idx_series_summary_order ON series_summary(library_id, sort_series_name, representative_book_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_progress_book_user ON user_progress(book_id, user_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_last_read ON user_progress(user_id, last_read_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_progress_last_read_book ON user_progress(last_read_at DESC, book_id);
CREATE INDEX IF NOT EXISTS idx_user_reading_log_user_date ON user_reading_log(user_id, read_date);
CREATE INDEX IF NOT EXISTS idx_user_reading_log_book_user_date ON user_reading_log(book_id, user_id, read_date);
CREATE INDEX IF NOT EXISTS idx_user_favorites_user_book ON user_favorites(user_id, book_id);
CREATE INDEX IF NOT EXISTS idx_user_favorites_book ON user_favorites(book_id);
CREATE INDEX IF NOT EXISTS idx_user_category_permissions_lookup ON user_category_permissions(user_id, library_id, has_access);
CREATE INDEX IF NOT EXISTS idx_collections_user ON collections(user_id);
CREATE INDEX IF NOT EXISTS idx_collection_items_coll ON collection_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_plugin_load_events_plugin_time ON plugin_load_events(plugin_id, occurred_at DESC);
```

### 6.2 MariaDB — `tools/db_schema_updater.py:MARIADB_CENTRAL_SCHEMA`

`media_general`, `media_adult`, `media_audiobook` 3개 데이터베이스 모두 아래 스키마 하나로 초기화됩니다. SQLite와 논리 구조는 동일하되, `BIGINT`/`VARCHAR(n)` 타입과 인덱스가 `CREATE TABLE` 문 안에 인라인으로 선언되어 있는 점이 다릅니다. 기존 운영 DB에 누락된 컬럼/인덱스는 `_ensure_mariadb_columns()` / `_ensure_mariadb_indexes()`가 기동 시 자동 보강합니다(`ALTER TABLE ... ADD COLUMN`, `CREATE INDEX`).

```sql
CREATE TABLE IF NOT EXISTS library_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    icon VARCHAR(100) DEFAULT 'fa-folder',
    color VARCHAR(50) DEFAULT '#a855f7',
    sort_order INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS libraries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    physical_path TEXT NOT NULL,
    cron_schedule VARCHAR(255) DEFAULT NULL,
    last_scanned_at DATETIME DEFAULT NULL,
    scan_status VARCHAR(50) DEFAULT 'ready',
    is_remote INT DEFAULT 0,
    vfs_refresh_before_scan INT DEFAULT 0,
    rclone_rc_url TEXT DEFAULT NULL,
    icon VARCHAR(100) DEFAULT 'fa-book',
    color VARCHAR(50) DEFAULT '#94a3b8',
    hide_cover INT DEFAULT 0,
    group_id BIGINT DEFAULT NULL,
    sort_order INT DEFAULT 0,
    INDEX idx_libraries_group_id (group_id),
    INDEX idx_libraries_group_order (group_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS scanner_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_key VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    kwargs TEXT,
    stage TEXT,
    worker_pid INT DEFAULT NULL,
    enqueue_at VARCHAR(50),
    started_at VARCHAR(50),
    finished_at VARCHAR(50),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS books (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    series_name VARCHAR(500),
    author VARCHAR(500),
    isbn VARCHAR(100),
    file_path TEXT NOT NULL,
    file_format VARCHAR(50) NOT NULL,
    total_pages INT NOT NULL DEFAULT 0,
    has_offsets INT DEFAULT 0,
    cover_image TEXT,
    publisher VARCHAR(255),
    link TEXT,
    score INT,
    release_date VARCHAR(100),
    summary TEXT,
    genre VARCHAR(255),
    tags TEXT,
    is_favorite INT DEFAULT 0,
    cover_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    metadata_locked INT DEFAULT 0,
    series_alias VARCHAR(500),
    title_alias VARCHAR(500),
    file_mtime DOUBLE DEFAULT 0.0,
    file_size BIGINT DEFAULT 0,
    UNIQUE KEY uq_books_file_path (file_path(500)),
    INDEX idx_books_series_name (series_name(255)),
    INDEX idx_books_series_alias (series_alias(255)),
    INDEX idx_books_library_id (library_id),
    INDEX idx_books_title (title(255)),
    INDEX idx_books_isbn (isbn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS series_summary (
    library_id BIGINT NOT NULL,
    series_key VARCHAR(500) NOT NULL,
    representative_book_id BIGINT NOT NULL,
    series_book_count BIGINT NOT NULL DEFAULT 0,
    sort_series_name VARCHAR(500) NOT NULL DEFAULT '',
    PRIMARY KEY (library_id, series_key),
    INDEX idx_series_summary_order (library_id, sort_series_name, representative_book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS series_summary_state (
    id TINYINT NOT NULL PRIMARY KEY,
    is_ready TINYINT NOT NULL DEFAULT 0,
    refreshed_at DATETIME DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobooks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    sort_title VARCHAR(500),
    web_id VARCHAR(100),
    author VARCHAR(500),
    publisher VARCHAR(255),
    code VARCHAR(255),
    poster TEXT,
    premiered VARCHAR(100),
    ratings DOUBLE DEFAULT 0.0,
    author_intro TEXT,
    description TEXT,
    folder_name VARCHAR(500) NOT NULL,
    folder_path TEXT NOT NULL,
    total_duration DOUBLE DEFAULT 0.0,
    total_tracks INT DEFAULT 1,
    file_type VARCHAR(50) DEFAULT 'multi',
    is_favorite INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    UNIQUE KEY uq_audiobooks_folder_path (folder_path(500))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobook_tracks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    track_number INT NOT NULL,
    track_code VARCHAR(100),
    title VARCHAR(500),
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_mtime DOUBLE DEFAULT 0.0,
    file_size BIGINT DEFAULT 0,
    duration DOUBLE DEFAULT 0.0,
    format VARCHAR(50) DEFAULT 'mp3',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tracks_file_path (file_path(500)),
    INDEX idx_tracks_audiobook (audiobook_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobook_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL DEFAULT 1,
    current_track_id BIGINT,
    `current_time` DOUBLE DEFAULT 0.0,
    total_progress_pct DOUBLE DEFAULT 0.0,
    playback_rate DOUBLE DEFAULT 1.0,
    is_completed INT DEFAULT 0,
    last_listened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_audiobook_user_progress (audiobook_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobook_track_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    track_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL DEFAULT 1,
    `current_time` DOUBLE DEFAULT 0.0,
    progress_pct DOUBLE DEFAULT 0.0,
    is_completed INT DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_audiobook_track_user_progress (audiobook_id, track_id, user_id),
    INDEX idx_audiobook_track_progress_lookup (audiobook_id, user_id, track_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    pages_read INT DEFAULT 0,
    is_completed INT DEFAULT 0,
    last_read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_epub_cfi TEXT,
    last_epub_href TEXT,
    last_epub_spine_index INT,
    last_epub_percent INT DEFAULT 0,
    last_epub_fingerprint VARCHAR(255),
    last_epub_updated_at DATETIME,
    UNIQUE KEY uq_user_book_progress (book_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_reading_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    pages_read_delta INT NOT NULL,
    duration_seconds INT DEFAULT 0,
    read_date DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_favorite (user_id, book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS book_offsets (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    page_idx INT,
    filename VARCHAR(500),
    local_header_offset BIGINT,
    compress_size BIGINT,
    file_size BIGINT,
    compress_type INT,
    INDEX idx_offsets_book (book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(255) PRIMARY KEY,
    `value` TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS scan_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_key VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    kwargs TEXT,
    enqueue_at VARCHAR(50),
    started_at VARCHAR(50),
    finished_at VARCHAR(50),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS scanner_progress (
    library_id VARCHAR(100),
    folder_path VARCHAR(500) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS folder_mtimes (
    folder_path VARCHAR(500) PRIMARY KEY,
    dir_mtime DOUBLE,
    meta_mtime DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_default_password INT DEFAULT 1,
    has_adult_access INT DEFAULT 1,
    has_audiobook_access INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_category_permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    library_id BIGINT NOT NULL,
    has_access INT DEFAULT 1,
    UNIQUE KEY uq_user_cat_perm (user_id, library_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS collections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    color VARCHAR(50) DEFAULT '#7c3aed',
    cover_image TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_collections_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS collection_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    collection_id BIGINT NOT NULL,
    book_id BIGINT DEFAULT NULL,
    series_name VARCHAR(500) DEFAULT NULL,
    audiobook_id BIGINT DEFAULT NULL,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_coll_book (collection_id, book_id),
    UNIQUE KEY uq_coll_series (collection_id, series_name(255)),
    UNIQUE KEY uq_coll_audiobook (collection_id, audiobook_id),
    INDEX idx_collection_items_coll (collection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS plugin_load_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    plugin_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT DEFAULT NULL,
    occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_plugin_load_events_plugin_time (plugin_id, occurred_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
```

**참고**: 위 인라인 인덱스 외에, 기존 운영 DB 보강용으로 `_ensure_mariadb_indexes()`가 별도로 관리하는 인덱스도 있습니다(`idx_books_lib_del_series`, `idx_books_lib_del_title` 등 `(library_id, is_deleted, ...)` 복합 인덱스). 신규 설치는 최신 `MARIADB_CENTRAL_SCHEMA`에 이미 반영되어 있을 수 있으니, 정확한 최신 목록은 `tools/db_schema_updater.py`의 `_ensure_mariadb_indexes()` 함수를 직접 참고하세요.

---

## 7. 스캔 대상 파일과 실제 데이터 흐름 요약

- **로컬 파일**: 스캐너가 파일을 직접 열어 메타데이터/커버/오프셋을 추출 후 위 테이블에 저장.
- **원격 파일(rclone/Google Drive 마운트 등)**: `libraries.is_remote=1`인 라이브러리는 스캔 시 무거운 I/O(커버 추출 등)를 지연시키고, `book_offsets`만 우선 채워 뷰어 스트리밍(seek 기반 부분 읽기)을 즉시 가능하게 합니다. 자세한 내용은 [spec_scanner_logic.md](./spec_scanner_logic.md), [spec_feature_overview.md](./spec_feature_overview.md) 참고.
