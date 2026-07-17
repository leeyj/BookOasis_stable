# 🗄️ Database Schema Specification (SQLite)

BookOasis uses two SQLite files: `general` and `adult`.

- General DB: `db/media_general.db`
- Adult DB: `db/media_adult.db`

This document summarizes the latest code-based schema snapshot (as of 2026-07-17, `database.py:init_databases`) and table responsibilities.

---

## 1. Schema Overview

- Both databases share the same core table set.
- On startup, `auto_migrate_schema(...)` adds missing declared columns automatically.
- However, long-lived production DB files can still contain legacy columns/indexes, so queries should remain compatibility-friendly.

---

## 2. Shared Table List

Tables common to both databases (10):

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

## 3. Table Details

### books

Book metadata and file identity.

- PK: `id`
- Main FK: `library_id -> libraries.id`
- Major columns:
  - Identity/path: `id`, `library_id`, `file_path`, `file_format`
  - Metadata: `title`, `author`, `publisher`, `series_name`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`
  - Viewer/cover: `total_pages`, `cover_image`, `cover_updated_at`, `has_offsets`
  - State/protection: `is_favorite`, `metadata_locked`, `created_at`
  - Runtime extensions: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`

### book_offsets

Per-page offset cache for compressed content (e.g., ZIP).

- PK: `id`
- Main FK: `book_id -> books.id`
- Columns: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`

### libraries

Library roots and scan/runtime options.

- PK: `id`
- Columns: `name`, `physical_path`, `cron_schedule`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`, `hide_cover`
- `hide_cover`: stores whether cover rendering should be hidden at library/category level (`INTEGER DEFAULT 0`).
- Note: production DB files may contain legacy migration residue columns.

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

### users

User account and privilege data.

- PK: `id`
- Columns: `username`, `password_hash`, `role`, `is_default_password`, `created_at`, `has_adult_access`

### user_progress

Per-user, per-book reading progress.

- PK: `id`
- Main FK: `book_id -> books.id`, `user_id -> users.id`
- Columns: `pages_read`, `is_completed`, `last_read_at`, `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_updated_at`
- Note: these EPUB pointer fields are used by resume logic based on server/client session pointers (e.g., CFI, href, spine index).

### user_reading_log

Reading activity log rows used for stats and trends.

- PK: `id`
- Main FK: `book_id -> books.id`, `user_id -> users.id`
- Columns: `pages_read_delta`, `duration_seconds`, `read_date`

### user_category_permissions

User-to-library access mapping.

- PK: `id`
- Main FK: `user_id -> users.id`, `library_id -> libraries.id`
- Columns: `has_access`

### scanner_progress

Folder-level scanner progress state.

- Composite-key-like columns: `library_id`, `folder_path`

### folder_mtimes

Folder mtime cache for incremental scan optimization.

- Key-like column: `folder_path`
- Columns: `dir_mtime`, `meta_mtime`

---

## 4. Relationship Summary

- `libraries (1) -> books (N)`
- `books (1) -> book_offsets (N)`
- `users (1) -> user_progress (N)`
- `books (1) -> user_progress (N)`
- `users (1) -> user_reading_log (N)`
- `books (1) -> user_reading_log (N)`
- `users (1) -> user_category_permissions (N)`
- `libraries (1) -> user_category_permissions (N)`

---

## 5. Plugin DB Access Policy

- Avoid direct `import database` / `database.get_connection(...)` in plugins.
- Use BaseProvider helpers:
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- Store plugin state under `settings` with plugin key naming conventions.
- New queries should be written with cross-DB compatibility in mind.

---

## 6. Source Snapshot (CREATE TABLE / INDEX)

The SQL below is a direct snapshot of declarations in `database.py:init_databases`.

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
