# 🗄️ Database Schema Specification

BookOasis supports two selectable engines — **SQLite (default)** and **MariaDB/MySQL (enterprise, recommended)** — and keeps a logically identical schema (table/column layout) across both. The active engine is selected via `DB_ENGINE` in `.env` (`sqlite` or `mariadb`).

- **SQLite mode**: **3 independent DB files** — `general`, `adult`, `audiobook`
  - General DB: `db/media_general.db`
  - Adult DB: `db/media_adult.db`
  - Audiobook DB: `db/media_audiobook.db`
- **MariaDB mode**: **3 independent databases** — `general`, `adult`, `audiobook` (default prefix `media_`, configurable via `mariadb_database_prefix`)
  - `media_general`, `media_adult`, `media_audiobook`
  - See [move_to_mariadb.md](./move_to_mariadb.md) and section 8 of [guide_admin_en.md](./guide_admin_en.md) for migration steps.

All 3 DBs (files or schemas) get the **entire same table set** created in them. For example, the `audiobook` DB also gets book-related tables like `books`/`user_favorites` (unused there), and conversely `general`/`adult` also get the `audiobooks`-family tables (unused there). Which tables are actually meaningful depends on the DB type.

This document summarizes the latest code-based schema snapshot (**as of 2026-08-14**; SQLite from `database.py:init_databases`, MariaDB from `tools/db_schema_updater.py:MARIADB_CENTRAL_SCHEMA`) and table responsibilities.

---

## 1. Schema Overview

- All 3 SQLite DB files (general/adult/audiobook) are initialized from the same `schema` SQL string.
- All 3 MariaDB databases are likewise initialized from the same `MARIADB_CENTRAL_SCHEMA` string.
- On startup, `auto_migrate_schema(...)` (SQLite) / `_ensure_mariadb_columns()`, `_ensure_mariadb_indexes()` (MariaDB) automatically backfill columns/indexes missing from the declared schema.
- However, long-lived production DB files can still contain legacy columns/indexes, so queries should remain compatibility-friendly.
- MariaDB tables use `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin`; SQLite's `INTEGER`/`TEXT` generally map to `BIGINT`/`VARCHAR(n)` or `TEXT` (see the code snapshot in section 6 for exact per-column types).

---

## 2. Shared Table List

Tables common to both engines and all 3 DBs (23 total):

**Library / Book Core**
1. `library_groups`
2. `libraries`
3. `books`
4. `book_offsets`
5. `series_summary`
6. `series_summary_state`

**Audiobook**
7. `audiobooks`
8. `audiobook_tracks`
9. `audiobook_progress`
10. `audiobook_track_progress`

**User / Progress**
11. `users`
12. `user_progress`
13. `user_reading_log`
14. `user_favorites`
15. `user_category_permissions`

**Collections**
16. `collections`
17. `collection_items`

**Scanner / Ops**
18. `scanner_tasks`
19. `scan_history`
20. `scanner_progress`
21. `folder_mtimes`

**Settings / Plugins**
22. `settings`
23. `plugin_load_events`

---

## 3. Table Details

### library_groups

Top-level grouping for libraries (sidebar folder grouping).

- PK: `id`
- Columns: `name`, `icon`, `color`, `sort_order`

### libraries

Library roots and scan/runtime options.

- PK: `id`
- Main FK: `group_id -> library_groups.id`
- Columns: `name`, `physical_path`, `cron_schedule`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`, `hide_cover`, `group_id`, `sort_order`
- `hide_cover`: stores whether cover rendering should be hidden at library/category level (`INTEGER DEFAULT 0`).
- Note: production DB files may contain legacy migration residue columns.

### books

Book metadata and file identity.

- PK: `id`
- Main FK: `library_id -> libraries.id`
- Major columns:
  - Identity/path: `id`, `library_id`, `file_path`, `file_format`
  - Metadata: `title`, `series_name`, `author`, `isbn`, `publisher`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`
  - Viewer/cover: `total_pages`, `cover_image`, `cover_updated_at`, `has_offsets`
  - State/protection: `metadata_locked`, `created_at`
  - Sort/alias: `series_alias`, `title_alias`
  - Runtime extensions: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`
- Note: `is_favorite` remains as a legacy compatibility column, but active favorites are now stored in `user_favorites`.

### book_offsets

Per-page byte-offset cache for compressed archives (e.g., ZIP). When the viewer requests a single page, it seeks/reads only the required byte range instead of opening the whole archive.

- PK: `id`
- Main FK: `book_id -> books.id`
- Columns: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`
- On MariaDB these offset columns are `BIGINT`, supporting source archives beyond 4GB (ZIP64).

### series_summary / series_summary_state

Pre-aggregated series grouping / representative-cover cache (speeds up library listing rendering).

- `series_summary` PK: composite (`library_id`, `series_key`)
  - Columns: `representative_book_id`, `series_book_count`, `sort_series_name`
- `series_summary_state` PK: `id`
  - Columns: `is_ready`, `refreshed_at` — flags whether the background re-aggregation has completed

### audiobooks

Audiobook (work-level) metadata.

- PK: `id`
- Main FK: `library_id -> libraries.id`
- Columns: `title`, `sort_title`, `web_id`, `author`, `publisher`, `code`, `poster`, `premiered`, `ratings`, `author_intro`, `description`, `folder_name`, `folder_path`(UNIQUE), `total_duration`, `total_tracks`, `file_type`, `is_favorite`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`

### audiobook_tracks

Individual audiobook track (file) info.

- PK: `id`
- Main FK: `audiobook_id -> audiobooks.id` (ON DELETE CASCADE)
- Columns: `track_number`, `track_code`, `filename`, `file_path`(UNIQUE), `file_mtime`, `file_size`, `duration`, `format`

### audiobook_progress / audiobook_track_progress

Per-user audiobook playback progress (work-level / track-level).

- `audiobook_progress` main FK: `audiobook_id -> audiobooks.id`, `current_track_id -> audiobook_tracks.id`
  - Columns: `user_id`, `current_time`, `total_progress_pct`, `playback_rate`, `is_completed`, `last_listened_at`
  - Constraint: `UNIQUE(audiobook_id, user_id)`
- `audiobook_track_progress` main FK: `audiobook_id -> audiobooks.id`, `track_id -> audiobook_tracks.id`
  - Columns: `user_id`, `current_time`, `progress_pct`, `is_completed`, `updated_at`
  - Constraint: `UNIQUE(audiobook_id, track_id, user_id)`

### users

User account and privilege data.

- PK: `id`
- Columns: `username`(UNIQUE), `password_hash`, `role`, `is_default_password`, `has_adult_access`, `has_audiobook_access`, `created_at`

### user_progress

Per-user, per-book reading progress.

- PK: `id`
- Main FK: `book_id -> books.id`, `user_id -> users.id`
- Columns: `pages_read`, `is_completed`, `last_read_at`, `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_fingerprint`, `last_epub_updated_at`
- Note: these EPUB pointer fields are used by resume logic based on server/client session pointers (e.g., CFI, href, spine index).
- Constraint: `UNIQUE(book_id, user_id)`

### user_reading_log

Reading activity log rows used for stats and trends.

- PK: `id`
- Main FK: `book_id -> books.id`, `user_id -> users.id`
- Columns: `pages_read_delta`, `duration_seconds`, `read_date`

### user_favorites

Per-user favorites mapping table.

- PK: `id`
- Main FK: `user_id -> users.id`, `book_id -> books.id`
- Columns: `user_id`, `book_id`, `created_at`
- Constraint: `UNIQUE(user_id, book_id)`

### user_category_permissions

User-to-library access mapping.

- PK: `id`
- Main FK: `user_id -> users.id`, `library_id -> libraries.id`
- Columns: `has_access`
- Constraint: `UNIQUE(user_id, library_id)`

### collections / collection_items

User-defined collections that freely group books/series/audiobooks together.

- `collections` PK: `id`
  - Main FK: `user_id -> users.id`
  - Columns: `name`, `description`, `color`, `cover_image`, `created_at`, `updated_at`
- `collection_items` PK: `id`
  - Main FK: `collection_id -> collections.id`(CASCADE), `book_id -> books.id`(CASCADE, nullable), `audiobook_id -> audiobooks.id`(CASCADE, nullable)
  - Columns: `series_name`(nullable), `sort_order`, `created_at`
  - Constraints: `UNIQUE(collection_id, book_id)`, `UNIQUE(collection_id, series_name)`, `UNIQUE(collection_id, audiobook_id)` — exactly one of book/series/audiobook is populated per row

### scanner_tasks

Background scanner job queue (pending/running/completed state).

- PK: `id`
- Columns: `task_type`, `task_key`(UNIQUE), `status`, `kwargs`, `stage`, `worker_pid`, `enqueue_at`, `started_at`, `finished_at`, `error_message`

### scan_history

History of completed scan jobs (used for scanner logs/stats).

- PK: `id`
- Columns: `task_type`, `task_key`, `status`, `kwargs`, `enqueue_at`, `started_at`, `finished_at`, `error_message`, `created_at`

### scanner_progress

Folder-level scanner progress state.

- Composite-key-like columns: `library_id`, `folder_path`(PK)

### folder_mtimes

Folder mtime cache for incremental scan optimization.

- Key-like column: `folder_path`(PK)
- Columns: `dir_mtime`, `meta_mtime`

### settings

Global and plugin settings storage.

- PK: `key`
- Columns: `key`, `value`, `updated_at`
- Common key examples:
  - `TAG_FILTER_SEARCH_SCOPE_ALL`
  - `RCLONE_RC_URL`
- Plugin key examples:
  - `PLUGIN_ENABLED_<plugin_id>`
  - `PLUGIN_CONFIG_<plugin_id>`

### plugin_load_events

Plugin load/error event log.

- PK: `id`
- Columns: `plugin_id`, `status`, `message`, `occurred_at`

---

## 4. Relationship Summary

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

## 5. Plugin DB Access Policy

- Avoid direct `import database` / `database.get_connection(...)` in plugins.
- Use BaseProvider helpers:
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- Store plugin state under `settings` with plugin key naming conventions.
- New queries should be written with cross-engine and cross-DB compatibility in mind (e.g., `INTEGER` vs `BIGINT`, upsert syntax differences).

---

## 6. Source Snapshot (CREATE TABLE / INDEX)

### 6.1 SQLite — `database.py:init_databases`

All 3 DB files (general/adult/audiobook) are initialized from this single schema.

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

**SQLite indexes:**

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

All 3 MariaDB databases (`media_general`, `media_adult`, `media_audiobook`) are initialized from this single schema. The logical structure matches SQLite; the main differences are `BIGINT`/`VARCHAR(n)` types and indexes declared inline inside `CREATE TABLE`. Missing columns/indexes on existing production DBs are auto-backfilled at startup by `_ensure_mariadb_columns()` / `_ensure_mariadb_indexes()` (`ALTER TABLE ... ADD COLUMN`, `CREATE INDEX`).

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

**Note**: beyond the inline indexes above, `_ensure_mariadb_indexes()` separately maintains extra backfill indexes for existing production DBs (e.g., composite `(library_id, is_deleted, ...)` indexes like `idx_books_lib_del_series`, `idx_books_lib_del_title`). New installs may already have these folded into the latest `MARIADB_CENTRAL_SCHEMA`; check `_ensure_mariadb_indexes()` in `tools/db_schema_updater.py` directly for the authoritative current list.

---

## 7. Scan Target Files and Data Flow Summary

- **Local files**: the scanner opens the file directly, extracting metadata/cover/offsets into the tables above.
- **Remote files (rclone/Google Drive mounts, etc.)**: libraries with `libraries.is_remote=1` defer heavy I/O (cover extraction, etc.) during scan and prioritize populating `book_offsets` first, so viewer streaming (seek-based partial reads) is available immediately. See [spec_scanner_logic_en.md](./spec_scanner_logic_en.md) and [spec_feature_overview_en.md](./spec_feature_overview_en.md) for details.
