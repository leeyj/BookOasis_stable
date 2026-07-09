# 🗄️ Database Schema Specification (SQLite)

BookOasis uses two SQLite files: `general` and `adult`.

- General DB: `db/media_general.db`
- Adult DB: `db/media_adult.db`

This document summarizes the current schema snapshot (as of 2026-07-09) and table responsibilities.

---

## 1. Schema Overview

- Both databases share the same core table set.
- Some columns may differ depending on migration timing.
- Core and plugins should use compatibility-friendly queries and safe defaults where needed.

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
  - State: `is_favorite`, `created_at`
  - General DB extensions: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`

### book_offsets

Per-page offset cache for compressed content (e.g., ZIP).

- PK: `id`
- Main FK: `book_id -> books.id`
- Columns: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`

### libraries

Library roots and scan/runtime options.

- PK: `id`
- Columns: `name`, `physical_path`, `cron_schedule`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`
- Note: `media_adult.db` can include legacy migration residue such as `test_column`

### settings

Global and plugin settings storage.

- PK: `key`
- Columns: `key`, `value`, `updated_at`
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
- Common columns: `pages_read`, `is_completed`, `last_read_at`
- General DB EPUB pointer extensions:
  - `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_updated_at`

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
