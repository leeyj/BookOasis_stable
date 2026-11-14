# 🗄️ Database Schema Specification

BookOasis supports two engines, **SQLite (default)** and **MariaDB/MySQL**, with the same tables and columns in both. Pick one with `DB_ENGINE` in `.env` (`sqlite` or `mariadb`).

- **SQLite mode**: **4 DB files**
  - General `db/media_general.db`, adult `db/media_adult.db`, audiobook `db/media_audiobook.db`, video `db/media_video.db`
- **MariaDB mode**: **4 databases** — `media_general`, `media_adult`, `media_audiobook`, `media_video`
  - The `media_` prefix can be changed with `MARIADB_DATABASE_PREFIX`.
  - For switching, see [move_to_mariadb.md](./move_to_mariadb.md) and section 8 of [guide_admin_en.md](./guide_admin_en.md)

All 4 DBs get **the same full table set**. For example the `video` DB also has `books`, and the `general` DB also has `videos` (left empty). Which tables actually hold data depends on the DB type; see the "Used in" column in section 2.

This document describes what each table is **for and how tables relate**. For column types and defaults, the code is the source of truth (section 6). `tests/test_spec_db_schema_tables.py` compares the table list with the code, so when you add or drop a table you must update section 2 of this document for the test to pass.

---

## 1. Schema Overview

- The schema lives in two places: SQLite `_SCHEMA_SQL` in `services/db_migration_service.py`, MariaDB `MARIADB_CENTRAL_SCHEMA` in `services/schema_mariadb.py`. Both must define the same tables (a test checks this).
- At startup `run_full_migration()` applies the same schema to all 4 DBs and adds columns and indexes that are declared but missing in an existing DB (SQLite reads `_SCHEMA_SQL` and fills gaps automatically; MariaDB uses the `_ensure_mariadb_columns`/`_ensure_mariadb_indexes` backfill lists in `services/db_migration_service.py`).
- Production DBs upgraded from old versions may still have leftover columns or indexes, so core and plugin queries should stay tolerant.
- MariaDB uses `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin`; SQLite `INTEGER`/`TEXT` generally become `BIGINT`/`VARCHAR(n)` or `TEXT`.
- Global data (settings, the scan queue and history, notifications, MCP pending changes, kosync, per-user settings) is written **only to the general DB**. `users` is copied to all 4 DBs under the same username.

---

## 2. Shared Table List

The 45 tables shared by all 4 DBs. "Used in" is the DB where the data actually lives.

| Group | Tables | Used in |
| :--- | :--- | :--- |
| Categories | `library_groups`, `library_kinds`, `libraries`, `plugin_group_assignments` | All 4 (each DB has its own categories) |
| Books | `books`, `book_offsets`, `series_summary`, `series_summary_state` | general, adult |
| Audiobooks/music | `audiobooks`, `audiobook_tracks`, `audiobook_progress`, `audiobook_track_progress`, `audiobook_music_lookups` | audiobook |
| Video | `videos`, `video_episodes`, `video_progress`, `video_episode_progress` | video |
| Users/progress | `users`, `user_category_permissions` | All 4 |
| | `user_progress`, `user_reading_log`, `user_favorites` | general, adult |
| | `user_settings` | general |
| Reading extras | `book_annotations`, `epub_bookmarks`, `tts_progress` | general, adult |
| Collections | `collections`, `collection_items` | All 4 (per the request's `db_type` session) |
| TTS pre-generation | `tts_audio_books`, `tts_audio_pieces`, `tts_pregen_jobs` | general, adult |
| | `tts_audio_cache` | Unused (v2.7.9 legacy cache index, only cleared) |
| Google link | `gdrive_book_copies` | general, adult |
| External | `kosync_credentials`, `kosync_documents`, `kosync_progress` | general |
| | `mcp_pending_changes` | general |
| Scanner | `scanner_tasks`, `scan_history` | general (target DB in `kwargs.db_type`) |
| | `scanner_progress`, `folder_mtimes` | The category's own DB |
| Settings/plugins | `settings`, `plugin_load_events` | general |
| Notifications/problems | `problem_occurrences`, `problem_groups` | general (target DB in the `db_type` column) |

---

## 3. Table Details

### library_groups

Top-level grouping for libraries (sidebar folder grouping).

- PK: `id`
- Columns: `name`, `icon`, `color`, `sort_order`

### library_kinds

List of category type values (manga / book / magazine, ...). One table per session DB, defined by the administrator.

- PK: `code` (lowercase slug, `^[a-z][a-z0-9_-]{0,23}$`, immutable once created)
- Columns: `name` (display name, UNIQUE, max 25 chars), `is_builtin`, `sort_order`
- The four built-in kinds (`manga`/`novel`/`book`/`magazine`) are seeded only in the general/adult DBs (`is_builtin=1`); they can be renamed but not deleted. The audiobook DB is seeded with the built-in kind `music`; categories with this kind are scanned in music mode (folder = album, song tags shown). The video DB starts with an empty list.

### libraries

Library roots and scan/runtime options.

- PK: `id`
- Main FK: `group_id -> library_groups.id`
- Columns: `name`, `physical_path`, `cron_schedule`, `schedule_enabled`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`, `hide_cover`, `hide_title`, `cover_aspect_ratio`, `content_kind`, `group_id`, `sort_order`, `gdrive_copy_remote`, `gdrive_view_local_mirror_path`, `pending_delete`, `transfer_target_id`
- `schedule_enabled`: turns the scheduled scan on/off. `cron_schedule` is kept when off
- `scan_status`: `ready` / `scanning` / `cancelling` / `failed` / `interrupted` — transitions in [spec_scanner_queue_state_transitions_en.md](./spec_scanner_queue_state_transitions_en.md)
- `pending_delete`: 0 normal, 1 being deleted, 2 moving out to another session, 3 moving in (the target). `transfer_target_id` is the target category id. Deletes and moves run in chunks as scanner queue tasks (`library_delete`/`library_transfer`); list queries must filter with `COALESCE(pending_delete, 0)`
- `gdrive_copy_remote`, `gdrive_view_local_mirror_path`: the rclone remote name and the local metadata mirror path of a Google link category (beta)
- `hide_cover`: stores whether cover rendering should be hidden at library/category level (`INTEGER DEFAULT 0`).
- `content_kind`: category type code (logical reference to `library_kinds.code`). Defaults to `'unspecified'`. Plugins can read it as a classification criterion (e.g. telling manga from books in related-works search) (`TEXT NOT NULL DEFAULT 'unspecified'`, `VARCHAR(24)` on MariaDB).
- `hide_title`: per-category toggle to hide the grid card title text and show thumbnail only (Netflix style). UI only exposed for general/adult book sessions (`INTEGER DEFAULT 0`).
- `cover_aspect_ratio`: per-category grid card cover aspect ratio. Only `'4:3'` (default) or `'16:9'` allowed (`TEXT DEFAULT '4:3'`).
- Note: production DB files may contain legacy migration residue columns.

### books

Book metadata and file identity.

- PK: `id`
- Main FK: `library_id -> libraries.id`
- Major columns:
  - Identity/path: `id`, `library_id`, `file_path`, `file_format`
  - Metadata: `title`, `series_name`, `author`, `isbn`, `publisher`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`, `publication_status`, `cover_artist`, `teams`, `locations`, `characters`
  - Content rating: `books_lv` (compared with the user's `content_rating_max`)
  - Viewer/cover: `total_pages`, `cover_image`, `cover_updated_at`, `cover_align`, `has_offsets`
  - Banner: `banner_image`, `banner_updated_at` - optional detail-page hero image. Stored at `covers/<library_id>/banner_<hash>.webp` using the same file-path MD5 hash as the cover. The scanner fills it from a loose `banner.<ext>` file in the folder or a `banner` (Base64) field in the metadata YAML - left empty if neither is present (unlike the cover, it never force-extracts from inside a zip/epub)
  - State/protection: `metadata_locked`, `created_at`
  - Sort/alias: `series_alias`, `title_alias`
  - Runtime extensions: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`
- Note: `is_favorite` remains as a legacy compatibility column, but active favorites are now stored in `user_favorites`.

### book_offsets

Per-page byte-offset cache for compressed archives (e.g., ZIP). When the viewer requests a single page, it seeks/reads only the required byte range instead of opening the whole archive.

- PK: `id`
- Main FK: `book_id -> books.id`
- Columns: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`, `data_offset`
- `data_offset`: where the compressed data actually starts. For remote (FUSE) paths it is left NULL at scan time, because reading every page header would multiply remote requests — the viewer then falls back to reading the local header
- On MariaDB these offset columns are `BIGINT`, supporting source archives beyond 4GB (ZIP64).

### series_summary / series_summary_state

Pre-aggregated series grouping / representative-cover cache (speeds up library listing rendering).

- `series_summary` PK: composite (`library_id`, `series_key`)
  - Columns: `representative_book_id`, `series_book_count`, `sort_series_name`, `latest_added`
  - After a queued scan the whole table is rebuilt (`SeriesRepository.rebuild_summary`); direct scans that bypass the queue (path scan, webhook, webview download) recompute only the changed series rows (`track_direct_scan` in `services/scan_refresh_service.py`)
- `series_summary_state` PK: `id`
  - Columns: `is_ready`, `refreshed_at` — flags whether the background re-aggregation has completed

### audiobooks

Audiobook (work-level) metadata.

- PK: `id`
- Main FK: `library_id -> libraries.id`
- Columns: `title`, `sort_title`, `web_id`, `author`, `publisher`, `code`, `poster`, `premiered`, `ratings`, `author_intro`, `description`, `folder_name`, `folder_path`(UNIQUE), `total_duration`, `total_tracks`, `file_type`, `is_favorite`, `metadata_locked`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`

### audiobook_tracks

Individual audiobook track (file) info.

- PK: `id`
- Main FK: `audiobook_id -> audiobooks.id` (ON DELETE CASCADE)
- Columns: `track_number`, `track_code`, `filename`, `file_path`(UNIQUE), `file_mtime`, `file_size`, `duration`, `format`, `title`, `artist`
- `title`/`artist`: display title/artist of songs in music categories (kind `music`), from tags or the filename. NULL for audiobook tracks

### audiobook_progress / audiobook_track_progress

Per-user audiobook playback progress (work-level / track-level).

- `audiobook_progress` main FK: `audiobook_id -> audiobooks.id`, `current_track_id -> audiobook_tracks.id`
  - Columns: `user_id`, `current_time`, `total_progress_pct`, `playback_rate`, `is_completed`, `last_listened_at`
  - Constraint: `UNIQUE(audiobook_id, user_id)`
- `audiobook_track_progress` main FK: `audiobook_id -> audiobooks.id`, `track_id -> audiobook_tracks.id`
  - Columns: `user_id`, `current_time`, `progress_pct`, `is_completed`, `updated_at`
  - Constraint: `UNIQUE(audiobook_id, track_id, user_id)`
- `audiobook_music_lookups`: external album-info lookup results for music-category albums (`lookup_music_album` plugin fallback). PK `audiobook_id`
  - Columns: `status` (found/not_found/skipped), `source` (plugin id), `artist`, `year`, `genres`, `summary`, `cover_url`, `source_url`, `looked_up_at`
  - Kept apart from audiobooks so scans never overwrite it; shown only in empty fields. Each album is looked up once

### users

User account and privilege data.

- PK: `id`
- Columns: `username`(UNIQUE), `password_hash`, `role`, `is_default_password`, `has_adult_access`, `has_audiobook_access`, `has_video_access`, `has_download_access`, `content_rating_max`, `created_at`
- Copied to all 4 DBs under the same `username` (ids may differ per DB). Login and permissions use the general DB
- Audiobook and video access is actually enforced by `user_category_permissions` (per category). `has_audiobook_access`/`has_video_access` have no switch in the UI and are effectively always 1

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
  - Main FK: `collection_id -> collections.id`(CASCADE), `book_id -> books.id`(CASCADE, nullable), `audiobook_id -> audiobooks.id`(CASCADE, nullable), `video_id` (nullable, logical reference to `videos.id`)
  - Columns: `series_name`(nullable), `sort_order`, `created_at`
  - Constraints: `UNIQUE(collection_id, book_id)`, `UNIQUE(collection_id, series_name)`, `UNIQUE(collection_id, audiobook_id)` — exactly one of book/series/audiobook/video is populated per row

### scanner_tasks

Background scanner job queue. Finished tasks move to `scan_history` and their row is deleted here.

- PK: `id`
- Columns: `task_type`, `task_key`(UNIQUE), `status`, `kwargs`, `stage`, `worker_pid`, `cancel_requested`, `enqueue_at`, `started_at`, `finished_at`, `error_message`
- Task types, state transitions and cancellation: [spec_scanner_queue_state_transitions_en.md](./spec_scanner_queue_state_transitions_en.md)

### scan_history

History of completed scan jobs (scanner logs/stats and the source of "recent" items in the notification center).

- PK: `id`
- Columns: `task_type`, `task_key`, `status`, `kwargs`, `enqueue_at`, `started_at`, `finished_at`, `error_message`, `result_summary`, `created_at`
- `kwargs.trigger_type`: scan origin `manual` / `cron` / `lazy` / `webhook` (absent on older rows)
- `result_summary` (JSON): category scans `{"new_books", "errors", "report_file"}`, selected-book scans `{"books", "succeeded", "errors"}`. NULL for other jobs
- Retention: rows older than 90 days are pruned at server start

### problem_occurrences

Occurrence records behind the notification center's problem cards. **One row per target x code**; a recurrence only
bumps the count and last-seen time (UPSERT). Design: [plan_unified_notification_queue.md](plan_unified_notification_queue.md).

- PK: `id`, UNIQUE `(code, db_type, target_type, target_id)`
- Target: `db_type`, `library_id`, `target_path` (file path), `occurrence_count` (times it recurred)
- `code`: problem kind — scanner `file_missing`/`mass_missing`/`remote_unavailable`/`file_corrupt`/`cover_missing`/`unknown`,
  system `system_task_failed`, user report `user_report`, plugins `<plugin id>:<code>`
- `severity`: `action_required` (red dot) / `notice` / `auto_fixed`
- `source`: `scanner` / `system` / `viewer` / `plugin:<plugin id>`
- `target_type` + `target_id`: `book` (book_id) / `series` (`"library_id|series_name"`) / `library` (library_id) / `system` (task key, `-` for plugins)
- `series_key`: `"library_id|series_name"` (groups by series even after the book is deleted; not shown on screen)
- `group_key`: card key = `code|db_type|library_id` (plugins: `plugin:<id>|<code>|-`)
- `title`/`detail`: wording supplied by plugins (empty for core codes, which are shown through i18n keys)
- `message` (raw error, 500 chars), `context` (JSON: reporter, plugin id/name/action, ...)
- Times: `first_seen_ms`, `last_seen_ms`, `resolved_ms` (epoch ms — independent of DB time zones)
- `status`: `open` / `resolved`. Resolved rows are purged at server start after 30 days; deleting a category deletes its rows

### problem_groups

Per-card (group_key) state — "Got it" (mute).

- PK: `group_key`
- Columns: `muted_ms`, `muted_count` (open count when muted - the card shows again once it grows past that)
- Rows of cards that no longer have open rows are removed automatically

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

### plugin_group_assignments

Places a plugin's category tab in a sidebar group (`library_groups`).

- PK: `plugin_id`
- Columns: `group_id`, `sort_order`

### videos / video_episodes

Video courses (one folder = one course) and their episode files. Used only in the video DB.

- `videos` PK: `id`, main FK: `library_id -> libraries.id`
  - Columns: `title`, `sort_title`, `web_id`, `genres`, `poster`, `backdrop`, `premiered`, `description`, `folder_name`, `folder_path`(UNIQUE), `total_duration`, `total_episodes`, `is_favorite`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`
- `video_episodes` PK: `id`, main FK: `video_id -> videos.id`(CASCADE)
  - Columns: `episode_number`, `episode_code`, `title`, `filename`, `file_path`(UNIQUE), `file_mtime`, `file_size`, `duration`, `width`, `height`, `premiered`, `format`, `needs_transcode`, `subtitle_path`, `container_verified`
  - `needs_transcode`: 1 when the browser can't play the codec as is (played through ffmpeg). `duration`/`width`/`height`/`container_verified` are filled later by the lazy scanner with ffprobe

### video_progress / video_episode_progress

Per-user watch progress (per course / per episode). Same shape as audiobook progress.

- `video_progress` main FK: `video_id -> videos.id`(CASCADE), `current_episode_id -> video_episodes.id`
  - Columns: `user_id`, `current_time`, `total_progress_pct`, `playback_rate`, `is_completed`, `last_watched_at`
  - Constraint: `UNIQUE(video_id, user_id)`
- `video_episode_progress` main FK: `video_id`, `episode_id` (both CASCADE)
  - Columns: `user_id`, `current_time`, `progress_pct`, `is_completed`, `updated_at`
  - Constraint: `UNIQUE(video_id, episode_id, user_id)`

### user_settings

Per-user settings (key/value, like the global `settings`). Written only to the general DB.

- PK: `id`, constraint `UNIQUE(user_id, key)`
- Columns: `user_id`, `key`, `value`, `updated_at`

### book_annotations / epub_bookmarks

Highlights/notes and bookmarks made while reading EPUB/TXT.

- `book_annotations` main FK: `book_id -> books.id`
  - Columns: `user_id`, `format`, `chapter_idx`, `start_offset`, `end_offset`, `quote`, `prefix`, `suffix`, `color`, `note`, `plugin_marker`, `created_at`, `updated_at`
  - `quote`/`prefix`/`suffix`: surrounding text used to find the spot again if the text shifts a little. `plugin_marker`: marks annotations created by a plugin
- `epub_bookmarks` main FK: `book_id -> books.id`
  - Columns: `user_id`, `format`, `chapter_idx`, `percent`, `label`, `created_at`

### tts_progress

TTS (read-aloud) position. The listening position and the reading position are kept separately.

- PK: `id`, main FK: `book_id -> books.id`, constraint `UNIQUE(book_id, user_id)`
- Columns: `listen_chapter`, `listen_offset`, `listen_text_len`, `listen_anchor`, `listen_updated_ms`, `read_chapter`, `read_offset`, `read_text_len`, `read_anchor`, `read_updated_ms`, `voice`, `steps`, `speed`

### tts_audio_books / tts_audio_pieces / tts_pregen_jobs / tts_audio_cache

Optional server-side TTS pre-generation. Audio is stored in per-book `.pack` files under `tts_audio/`.

- `tts_audio_books`: one row per book × voice setting. Constraint `UNIQUE(book_id, voice, steps, speed, quality)`
  - Columns: `book_id`, `voice`, `steps`, `speed`, `quality`, `rel_dir`, `pieces`, `bytes`, `duration_sec`, `created_by`, `created_ms`, `last_used_ms`
- `tts_audio_pieces`: where each piece sits inside the `.pack`. PK `(audio_book_id, piece_key)`
  - Columns: `chapter`, `part`, `byte_offset`, `byte_length`, `duration_sec`
- `tts_pregen_jobs`: pre-generation jobs. `status` defaults to `queued`
  - Columns: `book_id`, `user_id`, `voice`, `steps`, `speed`, `quality`, `status`, `total_pieces`, `done_pieces`, `error`, `heartbeat_ms`, `created_ms`, `finished_ms`
- `tts_audio_cache`: the per-piece cache index from v2.7.9. No longer used; `clear_legacy_cache()` only empties it. PK `piece_key`

### gdrive_book_copies

State of book copies downloaded for opening in a Google link category (beta). A periodic job removes old copies.

- PK: `id`, main FK: `book_id -> books.id` (UNIQUE)
- Columns: `library_id`, `source_file_id`, `status` (`copied` / `unsupported`), `local_path`, `error_message`, `updated_at`

### kosync_credentials / kosync_documents / kosync_progress

KOReader progress sync (kosync). Written only to the general DB.

- `kosync_credentials`: PK `user_id`, columns `key_hash`, `updated_at`
- `kosync_documents`: KOReader document hash → book. PK `document`, columns `db_type`, `book_id`, `created_at`
- `kosync_progress`: PK `(user_id, document)`, columns `progress`, `percentage`, `device`, `device_id`, `timestamp`

### mcp_pending_changes

Changes from MCP write tools (Tier B) that wait for admin approval instead of applying at once. Written only to the general DB.

- PK: `id`
- Columns: `tool_name`, `db_type`, `target`, `payload` (JSON), `preview`, `status` (default `pending`), `created_at`, `decided_at`, `decided_by`, `decision_note`

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
- `libraries (1) -> videos (N)`, `videos (1) -> video_episodes (N)`, `videos (1) -> video_progress / video_episode_progress (N)`
- `books (1) -> book_annotations / epub_bookmarks / tts_progress (N)`
- `books (1) -> tts_audio_books (N)`, `tts_audio_books (1) -> tts_audio_pieces (N)`
- `books (1) -> gdrive_book_copies (0..1)`, `books (1) -> kosync_documents (N)`

**When you add a new table that hangs off a book**, also add it to these three cleanup lists. If you miss one, its rows are left behind when a category is deleted or moved, or when the trash is emptied.
- `purge_book_dependents` in `repositories/category_data_shared.py` (category delete/move)
- `repositories/trash_repository_shared.py` (permanent delete from trash)
- the 7-day auto purge in `tools/scanner/sync_detector.py`

---

## 5. Plugin DB Access Policy

- Avoid direct `import database` / `database.get_connection(...)` in plugins.
- Use BaseProvider helpers:
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- Store plugin state under `settings` with plugin key naming conventions.
- New queries should be written with cross-engine and cross-DB compatibility in mind (e.g., `INTEGER` vs `BIGINT`, upsert syntax differences).

---

## 6. Schema Source (column types, indexes)

Column types, defaults and indexes are not copied into this document (the old copy went stale quickly). Read the source directly:

- SQLite: `services/db_migration_service.py` — `_SCHEMA_SQL` (tables), `_INDEXES_SQL` (indexes)
- MariaDB: `services/schema_mariadb.py` — `MARIADB_CENTRAL_SCHEMA` (tables); the column/index backfill lists for existing DBs are in `services/db_migration_service.py`
- How to add a column (edit both sources, add it to the backfill list): [change_db_guide.md](./change_db_guide.md)

---

## 7. Scan Target Files and Data Flow Summary

- **Local files**: the scanner opens the file directly, extracting metadata/cover/offsets into the tables above.
- **Remote files (rclone/Google Drive mounts, etc.)**: libraries with `libraries.is_remote=1` defer heavy I/O (cover extraction, etc.) during scan and prioritize populating `book_offsets` first, so viewer streaming (seek-based partial reads) is available immediately. See [spec_scanner_logic_en.md](./spec_scanner_logic_en.md) and [spec_feature_overview_en.md](./spec_feature_overview_en.md) for details.
