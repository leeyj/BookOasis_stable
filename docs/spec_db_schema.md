# 🗄️ 데이터베이스 스키마 명세 (SQLite)

BookOasis는 SQLite 기반으로 `general`, `adult` 두 DB 파일을 사용합니다.

- 일반 DB: `db/media_general.db`
- 성인 DB: `db/media_adult.db`

이 문서는 코드 기준 최신 스키마 스냅샷(2026-07-17 기준, `database.py:init_databases`)과 테이블 역할을 정리합니다.

---

## 1. 스키마 개요

- 두 DB 모두 핵심 테이블은 동일한 구조를 공유합니다.
- 기동 시 `auto_migrate_schema(...)`로 선언 스키마에 없는 컬럼을 자동 보강합니다.
- 다만 과거 버전에서 올라온 운영 DB는 잔여 컬럼/인덱스가 남아 있을 수 있으므로, 코어/플러그인 쿼리는 호환성을 고려해야 합니다.

---

## 2. 공통 테이블 목록

두 DB 공통 테이블 (10개):

1. `books`
2. `book_offsets`
3. `libraries`
4. `settings`
5. `users`
6. `user_progress`
7. `user_reading_log`
8. `user_category_permissions`
9. `scanner_progress`
10. `folder_mtimes`

---

## 3. 테이블 상세

### books

도서 메타데이터 및 파일 식별 정보.

- PK: `id`
- 주요 FK: `library_id -> libraries.id`
- 주요 컬럼:
  - 식별/경로: `id`, `library_id`, `file_path`, `file_format`
  - 메타: `title`, `author`, `publisher`, `series_name`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`
  - 뷰어/커버: `total_pages`, `cover_image`, `cover_updated_at`, `has_offsets`
  - 상태/보호: `is_favorite`, `metadata_locked`, `created_at`
  - 운영 확장: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`

### book_offsets

압축 파일(예: ZIP) 내부 페이지 오프셋 캐시.

- PK: `id`
- 주요 FK: `book_id -> books.id`
- 컬럼: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`

### libraries

라이브러리 루트 및 스캔 설정.

- PK: `id`
- 컬럼: `name`, `physical_path`, `cron_schedule`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`, `hide_cover`
- `hide_cover`: 카테고리 단위로 대표/목록 커버 렌더링을 숨길지 여부를 저장 (`INTEGER DEFAULT 0`)
- 참고: 운영 DB에는 과거 마이그레이션 잔여 컬럼이 남아 있을 수 있음

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

### users

사용자 계정 및 권한.

- PK: `id`
- 컬럼: `username`, `password_hash`, `role`, `is_default_password`, `created_at`, `has_adult_access`

### user_progress

도서별 사용자 진행률.

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read`, `is_completed`, `last_read_at`, `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_updated_at`
- 참고: EPUB은 서버/클라이언트 세션 포인터(예: CFI, href, spine index) 기반 이어읽기에 이 컬럼들을 사용합니다.

### user_reading_log

사용자 읽기 활동 로그(일별 집계/통계 근거).

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read_delta`, `duration_seconds`, `read_date`

### user_category_permissions

사용자-라이브러리 접근 권한 매핑.

- PK: `id`
- 주요 FK: `user_id -> users.id`, `library_id -> libraries.id`
- 컬럼: `has_access`

### scanner_progress

스캐너의 폴더 단위 진행 상태 기록.

- 복합 키 성격 컬럼: `library_id`, `folder_path`

### folder_mtimes

폴더 변경 시각 캐시(증분 스캔 최적화).

- 키 성격 컬럼: `folder_path`
- 컬럼: `dir_mtime`, `meta_mtime`

---

## 4. 관계 요약

- `libraries (1) -> books (N)`
- `books (1) -> book_offsets (N)`
- `users (1) -> user_progress (N)`
- `books (1) -> user_progress (N)`
- `users (1) -> user_reading_log (N)`
- `books (1) -> user_reading_log (N)`
- `users (1) -> user_category_permissions (N)`
- `libraries (1) -> user_category_permissions (N)`

---

## 5. 플러그인 개발 시 DB 사용 원칙

- 직접 `import database`/`database.get_connection(...)` 대신 BaseProvider 헬퍼 사용
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- 설정 저장은 `settings` 테이블의 플러그인 키 규칙을 사용
- DB 간 컬럼 편차가 있을 수 있으므로, 신규 쿼리는 호환성을 고려해 작성

---

## 6. 코드 원문 스냅샷 (CREATE TABLE / INDEX)

아래 SQL은 `database.py:init_databases` 선언을 기준으로 정리한 원문 스냅샷입니다.

### 6.1 CREATE TABLE

```sql
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
  hide_cover INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  library_id INTEGER REFERENCES libraries(id),
  title TEXT NOT NULL,
  series_name TEXT,
  author TEXT,
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
  file_mtime REAL DEFAULT 0.0,
  file_size INTEGER DEFAULT 0
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

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT DEFAULT 'user',
  is_default_password INTEGER DEFAULT 1,
  has_adult_access INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_category_permissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  library_id INTEGER NOT NULL,
  has_access INTEGER DEFAULT 1,
  UNIQUE(user_id, library_id)
);
```

### 6.2 CREATE INDEX

```sql
CREATE INDEX IF NOT EXISTS idx_book_offsets_book_id ON book_offsets(book_id);
CREATE INDEX IF NOT EXISTS idx_book_offsets_book_page ON book_offsets(book_id, page_idx);
CREATE INDEX IF NOT EXISTS idx_books_series_name ON books(series_name);
CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
CREATE INDEX IF NOT EXISTS idx_books_is_favorite ON books(is_favorite);
CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);
CREATE INDEX IF NOT EXISTS idx_books_series_lib_title ON books(series_name, library_id, title);
CREATE INDEX IF NOT EXISTS idx_books_library_active_series ON books(library_id, COALESCE(is_deleted, 0), COALESCE(series_name, ''));
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_progress_book_user ON user_progress(book_id, user_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_last_read ON user_progress(user_id, last_read_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_progress_last_read_book ON user_progress(last_read_at DESC, book_id);
CREATE INDEX IF NOT EXISTS idx_user_reading_log_user_date ON user_reading_log(user_id, read_date);
CREATE INDEX IF NOT EXISTS idx_user_category_permissions_lookup ON user_category_permissions(user_id, library_id, has_access);
```
