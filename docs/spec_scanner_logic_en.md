# 📑 BookOasis Scanner Logic Technical Specifications

This document describes the core mechanics of the BookOasis media server's scanner and filesystem synchronization engine in detail.

The general (comic/ebook) scanner, the audiobook scanner and the video scanner are separate pipelines. Sections 1–2 cover the general scanner, Section 3 the audiobook scanner, Section 4 the video scanner, and Section 5 the post-scan work shared by all three. For the scan queue and state transitions see [spec_scanner_queue_state_transitions_en.md](./spec_scanner_queue_state_transitions_en.md). To add or modify a local metadata parser (`kavita.yaml`, `komga.yaml`, etc.), see [guide_scanner_parser.md](./guide_scanner_parser.md). For scan-completion webhooks/plugin hooks, see [guide_plugins.md](./guide_plugins.md).

---

## 1. Overall Scanner Flow (General/Adult Libraries)

The scanner iterates library configurations from the database (`media_general.db`, `media_adult.db`) and synchronizes the actual filesystem state with the DB. When `db_type` is `audiobook`, this flow is never entered at all — control is handed off immediately to the [Section 3 audiobook pipeline](#3-audiobook-scanner-a-fully-separate-pipeline). When `db_type` is `video`, it is handed off to the [Section 4 video pipeline](#4-video-scanner-a-separate-pipeline).

```mermaid
graph TD
    Start([Scan start tools/scanner/core.py]) --> GDriveCheck{Google Drive web link?}
    GDriveCheck -- "Yes" --> SkipWakeup[Skip local wake-up check]
    GDriveCheck -- "No" --> Wakeup[HDD/NAS wake-up retry<br/>up to 3-6 attempts, raises on failure]
    Wakeup --> VFS_Check{Remote VFS path?}
    SkipWakeup --> VFS_Check
    VFS_Check -- "Yes (Rclone)" --> VFS_Refresh[Call rclone VFS cache refresh API]
    VFS_Check -- "No (local)" --> AudiobookCheck
    VFS_Refresh --> AudiobookCheck{db_type == audiobook?}

    AudiobookCheck -- "Yes" --> AudiobookPipeline[Delegate to dedicated audiobook pipeline<br/>see Section 3, returns here]
    AudiobookCheck -- "No" --> SelfHeal[Pre-scan DB integrity check<br/>PRAGMA integrity_check, auto db_recovery.py on corruption]

    SelfHeal --> Thread_Config[Thread config: 4 local / 1 remote]
    Thread_Config --> Load_Checkpoint[Load scanner_progress checkpoint]
    Load_Checkpoint --> Walk_Dirs{Path type}
    Walk_Dirs -- "Regular folder" --> Walk_Local[Physical crawl via os.walk]
    Walk_Dirs -- "GDrive web share link" --> Walk_GDrive[Build virtual gdrive:// paths<br/>via fetch_gdrive_folder_files]

    Walk_Local --> Ignore_Filter{IgnoreFilter exclusion check}
    Ignore_Filter -- "Excluded dir" --> Prune_Dirs[In-place dirs[:] removal, blocks subtree walk]
    Ignore_Filter -- "Regular dir" --> Task_Collect[Collect per-folder tasks]
    Prune_Dirs --> Task_Collect
    Walk_GDrive --> Task_Collect

    Task_Collect --> Move_Detect{Book move/rename detected?<br/>basename match}
    Move_Detect -- "Yes" --> Update_Path[UPDATE DB path, keep book_id/reading history]
    Move_Detect -- "No" --> Task_Distribute[ThreadPoolExecutor run]
    Update_Path --> Task_Distribute

    subgraph "Per-folder task tools/scanner/tasks.py"
        FileSkip{Per-file mtime+size<br/>cache match?} -- "Yes" --> FastSkip[Ultra-fast skip]
        FileSkip -- "No" --> Parse_Meta[Auto-load plugin metadata parsers<br/>merge + ComicInfo.xml fallback]
        Parse_Meta --> Extract_Cover[4-stage cover fallback]
        Extract_Cover --> Parse_Offset[ZIP/CBZ offset analysis or<br/>offset-only fast path]
    end

    Task_Distribute --> FileSkip

    Parse_Offset --> Pending[Accumulate in-memory pending_inserts/updates]
    FastSkip --> Pending
    Pending --> FlushTrigger{Hybrid flush trigger<br/>100 changes or 50 folders}
    FlushTrigger -- "Met" --> RedisLock[Acquire Redis distributed lock,<br/>bulk-write to DB + record scanner_progress]
    FlushTrigger -- "Not met" --> Cancel_Check
    RedisLock --> JSONL_Log[Append committed items to .jsonl audit log]
    JSONL_Log --> Cancel_Check{Cancel check every 3 folders<br/>libraries.scan_status +<br/>scanner_tasks dual check}

    Cancel_Check -- "Yes" --> Terminate_Safe([Safe abort: revert status to ready and return])
    Cancel_Check -- "No" --> Memory_Check{Memory threshold exceeded?<br/>DB-configurable}

    Memory_Check -- "Yes" --> Terminate_OOM[Self-respawn via os.execv into<br/>scanner_worker.py, resumes afterward]
    Memory_Check -- "No" --> More_Folders{Folders remaining?}
    More_Folders -- "Yes" --> Task_Distribute
    More_Folders -- "No" --> Final_Flush[Final flush and JSONL cleanup]

    Final_Flush --> Remove_Check[Deletion watch: soft-delete +<br/>hard-delete after 7 days]
    Remove_Check --> Clear_Checkpoint[Clear scanner_progress, scan_status=ready]
    Clear_Checkpoint --> Event_Dispatch[Async new-book event dispatch<br/>scan.new_books_detected + book.new + plugin hooks]
    Event_Dispatch --> End([Scan complete])
```

---

## 2. Step-by-Step Mechanism (General Scanner)

### ① HDD/NAS Wake-up and Pre-flight Path Validation
* **Problem solved**: prevents scan failures caused by `FileNotFoundError` on a spun-down physical HDD or a slow-to-respond NAS/network mount right at scan start.
* **Mechanism** (`tools/scanner/core.py::scan_library`):
  - Google Drive web-share-link targets are not local disks, so the wake-up check is skipped for them.
  - Other paths are probed via repeated `os.path.exists()` calls to trigger disk spin-up / network session setup. Default is up to 3 attempts (1.0s interval); if the per-library DB setting `HDD_AGGRESSIVE_WARMUP=1` is on and the path is not remote, it switches to "aggressive warmup" mode with up to 6 attempts (3.0s interval).
  - Aggressive warmup additionally forces access via `os.scandir` + `stat()` on the first ~20 entries of the target folder and the first ~10 entries of its first subdirectory, to pre-warm disk/cache.
  - If any path remains inaccessible after all attempts, a `FileNotFoundError` is raised, aborting the scan entirely (to prevent false-positive deletions).

### ② Rclone VFS Cache Refresh
* **Target detection**: checked against both the library's `is_remote=1` DB flag and its `vfs_refresh_before_scan=1` setting (`tools/scanner/vfs.py::trigger_vfs_refresh`).
* **Mechanism**:
  - Tries a list of candidate relative-path refresh targets (`get_rclone_refresh_dirs`) in order, across multiple RC URLs (`RCLONE_RC_URL` supports comma-separated multiple endpoints).
  - Instead of refreshing the whole path, sends **`{"dir": rel_path}`** in the request body to pinpoint-refresh only the library's relative subpath, maximizing remote-drive refresh performance.
  - Validates the response body (`_is_vfs_refresh_success_response`) so that a `"file does not exist"` reply is never mistaken for success, and retries up to 3 times with a 2s delay if the RC server isn't ready yet (connection refused).
  - Every request carries a `User-Agent` header with the engine signature, so the origin can be traced in network logs even if this logic is copied/reused elsewhere.

* **Where the refresh happens**: for a category scan through the queue, `services/scheduler_service.py::run_scan_job` refreshes first using the category's DB and passes `skip_vfs_refresh` to the engine so it is not done twice. Direct scans that bypass the queue (path scan, webhook, webview download) go through `trigger_vfs_refresh`, which tells general/adult/audiobook/video apart by the DB file name and reads the category settings from that DB.
* **No RC calls when `is_remote=0`**: even if the path looks like an rclone mount, nothing is refreshed when remote drive is turned off for the category.

### ③ Pre-scan DB Integrity Self-Healing
* **Mechanism** (`tools/scanner/core.py::_run_db_self_recovery`):
  - Runs `PRAGMA integrity_check;` immediately before scanning (SQLite mode only).
  - If the result isn't `'ok'`, or a corruption exception occurs while accessing the DB, `tools/db_recovery.py --db <path> --yes` is auto-launched as a subprocess for unattended recovery (up to 300s wait).
  - Skipped entirely under MariaDB/MySQL engines (`DB_ENGINE`/`DBMS` env var).
  - A failure of this check itself does not block the scan — only a warning is logged.

### ④ Threading Model and Network I/O Optimization
* **Hybrid threading model**:
  - **Local paths**: parallelized with up to 4 threads (`MAX_SCANNER_THREADS = 4`) for maximum I/O throughput.
  - **Remote mount paths**: serialized to a single thread to avoid rate limits and network overload on the remote drive API.
  - **I/O saving policy**: on remote drives, heavy byte-offset analysis of `ZIP`/`CBZ` archives is skipped to reduce latency significantly.
  - This hybrid model does not apply to the audiobook scanner — audiobooks are always processed sequentially on a single thread (see [Section 3](#3-audiobook-scanner-a-fully-separate-pipeline)).

### ⑤ Checkpoint-Based Scan State Management and Cancellation
* **Checkpoint architecture**:
  - The `scanner_progress` table records a completion marker in the database every time a folder scan succeeds.
  - If a scan is cancelled mid-way or interrupted by OOM and later restarted, already-completed folders are skipped instantly and the scan resumes from where it left off.
  - Once a full library scan finishes without error, that library's checkpoint data is cleared in bulk.
* **Real-time early cancellation** (`tools/scanner/engine.py`):
  - Checked every 3 completed folders (not every folder). This check uses a **separate independent connection** rather than the scan's long-lived connection, because a long-lived connection's WAL snapshot isolation can prevent it from seeing another session's COMMIT (the cancel request) promptly.
  - Two signals are checked: `libraries.scan_status = 'cancelling'`, and a row in `scanner_tasks` with `task_key = library_scan_{db_type}_{library_id}` and `status = 'cancelled'`.
  - On cancellation, any pending data is flushed, `libraries.scan_status` is reverted to `'ready'`, and the function returns immediately (the checkpoint is preserved so the next scan resumes from this point).
  - `libraries.scan_status` is read from **the DB the category belongs to** (general/adult), and `scanner_tasks` from the general DB. Both used to be read from general, so adult category scans could not be stopped (fixed in 3.1.0, `tests/test_scan_cancel_db_type.py`).
  - Because the engine returns normally, the queue history (`scan_history`) records the task as `completed`.
  - The audiobook scanner has no checkpoint/cancel logic at all — on restart it only avoids redundant work via its coarse `skip_existing` folder policy.

### ⑥ Scan Ignore Filtering (IgnoreFilter & .bookoasisignore)
* **Mechanism**:
  - `tools/scanner/ignore_filter.py` processes global DB settings (`SCAN_IGNORE_PATTERNS`) and per-directory `.bookoasisignore` partition files in real time.
  - Trailing `/` patterns (e.g. `@eaDir/`, `#recycle/`, `.git/`, `.svn/`) are matched as **directory-only wildcards**, pruned in-place (`dirs[:] = [d for d in dirs if d not in ignored]`) during `os.walk()`, physically blocking subfolder traversal.
  - File wildcards (e.g. `*.tmp`, `*.sample.cbz`, `Thumbs.db`) filter out matching file entries during traversal, and every ignored directory/file is logged with the `[Scanner-Ignore]` prefix.
  - The same filter is applied to the Google Drive web-link scan path, based on relative folder/file names.

### ⑦ Book Movement (Path Change) Auto-Detection and History Preservation
* **Problem solved**: prevents a renamed file or a renamed parent folder from being treated as a brand-new book, which would otherwise wipe out existing reading-completion history and statistics.
* **Mechanism** (`tools/scanner/sync_detector.py::detect_and_handle_book_movement`):
  - Before cross-diffing the disappeared-path set (`deleted_paths`) against the newly-found-path set (`new_paths`), Windows/Linux path separator differences (`\` vs `/`) are normalized first.
  - If a pair with an exactly matching basename (filename) exists, it's treated as a "book move" and only `books.file_path` is `UPDATE`d to the new path.
  - IMGDIR virtual entries (`__folder__.imgdir`, see [⑫](#⑫-imgdir-virtual-books-image-only-folders)) always share the same filename, so they are explicitly excluded from this basename matching to avoid false positives.
  - **Stage 2 — renamed files** (`_match_renamed_files`): when stage 1 finds no pair because the basename changed, a vanished book and a new file whose **size + modification time (seconds)** match one-to-one are treated as the same file and the path is fixed. If the size or time is 0, or there is more than one candidate, nothing is moved (trash + new book, as before). If the title came from the old file name and the book is not `metadata_locked`, the title is changed to the new file name too. Renames keep the modification time on both local disks and Google Drive, which is what makes this comparison work.
  - This ensures the book's unique ID (`book_id`) and everything bound to it — `user_progress`, `user_reading_log` — survives intact.

### ⑧ Metadata Parsing and Merging: Plugin-Extensible Parser Loader
* **Architecture**: what used to be a hardcoded two-source merge (`info.xml` + `kavita.yaml`) has been replaced by a **dynamic plugin loader** (`tools/scanner/metadata/__init__.py::load_all_parsers`) that scans `tools/scanner/metadata/` and auto-loads/merges every `*.py` module exposing `TARGET_FILENAME` and `parse()`.
  - Community contributors can add a single self-contained module such as `komga_yaml.py`, and it is auto-discovered and merged whenever the target file (`komga.yaml`) exists in a folder. See [guide_scanner_parser.md](./guide_scanner_parser.md) for the authoring rules.
  - Built-in parsers today: `audio_json.py`, `comicinfo_xml.py` (excluded from folder-level merging, used separately per file), `info_xml.py`, `kavita_yaml.py`, `series_json.py` (webtoon-oriented `series.json`, supports a remote cover URL).
  - **Merge rule**: modules are loaded in alphabetical filename order; text fields are merged "first writer wins". `genre`/`tags` are comma-split, normalized, and deduplicated across sources; `cover_b64_map` is dict-merged (update); `is_webtoon`/`has_yaml` are OR-combined. Because `info_xml` sorts before `kavita_yaml` alphabetically, `info.xml` currently wins in practice — but this is an alphabetical side effect, not a hardcoded priority rule.
  - All text metadata is passed through HTML tag stripping and entity un-escaping.
* **ComicInfo.xml fallback**: `ComicInfo.xml` embedded inside a CBZ/ZIP is excluded from folder-level merging and is instead parsed per-file in `tasks.py`, only used to backfill author/publisher/summary/release_date/genre/tags fields that are still empty.
* **Remote-path resilience**: parsers requiring remote I/O (e.g. `info_xml.py`) apply a circuit breaker (blocks requests for 60s after 3 failures) and a 10s thread-join timeout, so an unresponsive remote file cannot stall the entire scan.

### ⑨ Staged Cover Image Extraction and Mapping Strategy
Cover images are resolved through the following fallback chain, designed to minimize server resource usage:

1. **YAML/parser Base64 mapping**: if a metadata parser returns Base64 cover data mapped by individual book filename, it is decoded directly and saved under `covers/{library_id}` with a unique MD5-hash filename.
2. **Shared series cover reuse / webtoon URL download**: if a cover has already been extracted for the same series folder, it is reused as-is; for JSON-only (no YAML) webtoon folders, the cover is downloaded from `cover_image_url`.
3. **1:1 individual match and shared series cover file match**: checks for a same-basename image file next to the book (e.g. `[title].jpg/.png/.webp`) or a representative cover file (`cover.jpg`, `folder.jpg`, etc.) in the folder. Filename lookup is delegated to [tools/scanner/folder_image.py](../tools/scanner/folder_image.py).
4. **In-archive first-page auto-extraction (non-remote paths and forced scans only)**:
   - **EPUB**: searches `META-INF/container.xml` and the manifest's cover entry to extract the original image directly.
   - **ZIP/CBZ**: naturally sorts (`natural_sort_key`) the archive's image entries and auto-extracts the very first one as the cover.
   - **PDF**: bulk PDF cover extraction is deliberately disabled in the main scan path (risk of OOM/worker timeout on large PDFs) and deferred to the [Lazy Scanner](#⑳-lazy-scanner-second-pass-repair-scanner).
* **Post-extraction safeguard**: if the extracted cover file is 0 bytes, it is immediately deleted and the result invalidated so it gets retried on the next scan.

### ⑩ Byte-Offset Metadata Analysis and DB Storage
* **Mechanism**:
  - Applies to `ZIP`/`CBZ` archive formats.
  - Without pre-extracting the whole archive, collects the byte offset (`local_header_offset`), compressed size, uncompressed size, and compression type for each internal image file.
  - The collected data is bulk-inserted (`executemany`) into `book_offsets`, and `books.has_offsets = 1` is flagged.
  - This data underpins the **ultra-fast partial-byte streaming viewer**: it lets the server jump straight to an arbitrary page and read only that byte range off the file channel.
* **Offset-only fast path**: a book that already has a complete cover/metadata but lacks offsets skips the entire heavy pipeline (cover extraction, ComicInfo parsing, etc.) and reads only the ZIP central directory to backfill offsets, minimizing rescan cost.

### ⑪ OOM (Memory Overrun) Self-Exit System
* **Watch mechanism** (`tools/scanner/memory_helper.py`):
  - When system available RAM drops below a threshold (`SYSTEM_MEM_LIMIT`, default 1536MB) or the current process's RSS exceeds a threshold (`PROCESS_RSS_LIMIT`, default 2048MB), the scan pauses to prevent memory leaks and system crashes.
  - Both thresholds are no longer fixed constants — they are **overridable values in the DB `settings` table**, cached in memory with a 300s TTL to avoid repeated lookups.
* **Auto-resume mechanism**:
  - All folders completed so far are flushed, `scanner_tasks.status` is set to `'exit_pending'` (stage message `"Paused due to memory limit (Auto-Resuming...)"`), the DB connection is closed, and the temporary JSONL file is cleaned up.
  - Rather than an external daemon noticing an exit and restarting it, the process **replaces itself in-place via `os.execv()`, re-executing `tools/scanner_worker.py`** — a true self-respawn. The freshly started process picks up from the saved checkpoint (`scanner_progress`).
  - The Lazy Scanner uses its own independent memory-watch logic; on exceeding its threshold it calls `sys.exit(10)` instead of `os.execv`, signaling "please reschedule me" to whatever runs it (see [Lazy Scanner](#⑳-lazy-scanner-second-pass-repair-scanner)).

### ⑫ IMGDIR Virtual Books (Image-only Folders)
* **Problem solved**: treats a folder containing only loose image files (no supported archive/ebook format at all) as a single virtual "book".
* **Mechanism** (`tools/scanner/tasks.py`):
  - A folder with zero supported archive/ebook formats (`SUPPORTED_FORMATS`) but at least one image file is registered as a single virtual entry represented by the synthetic filename **`__folder__.imgdir`**.
  - Unlike normal books ("current folder = series"), IMGDIR inverts the rule: **"current folder = book title", "parent folder = series"**.
  - Cache comparison uses folder mtime plus the summed size of all contained images (rather than per-file comparison), and the cover is taken from the first image in the folder.
  - It's excluded from book-move basename matching ([⑦](#⑦-book-movement-path-change-auto-detection-and-history-preservation)) since the filename is always identical.

### ⑬ Web-Share-Link (Google Drive) Scanning (beta)
* **Problem solved**: lets a library be built purely from a Google Drive folder share link, with no actual mount/sync. This is a beta feature; it only shows in the UI when `GDRIVE_LINK_BETA` (or `DEVELOP`) is on.
* **Mechanism** (`tools/scanner/engine.py`):
  - When a target path is identified via `is_gdrive_url()`, `os.walk()` is not used; virtual paths `gdrive://{folder_id}/...` are built from the remote listing.
  - **Listing**: if the category has an rclone remote (`libraries.gdrive_copy_remote`), `fetch_gdrive_folder_files_via_rclone()` calls `rclone lsjson` once. If that fails, the API-key listing (`fetch_gdrive_folder_files()`) is used instead, but this scan skips the deletion sync (a partial listing must not delete anything, so it counts as a traversal error). Only older categories without a remote use the API-key path from the start. The remote is the default because anonymous API-key downloads from a large shared folder were blocked by Google with 403 (2026-10-22).
  - **Metadata**: `kavita.yaml` and other metadata files are downloaded at once into a local mirror (`gdrive_meta_mirror_dir`) by `refresh_gdrive_meta_mirror()`, and the parsers read the mirror. If the mirror can't be fetched, books are still registered and the next scan tries again.
  - In remote mode books are read from a local copy when opened (`gdrive_book_copies`), so zip offsets are not precomputed with Range requests. Folders whose files have the same modification time and size in the listing are skipped.
  - IgnoreFilter applies identically to these virtual paths, based on relative folder/file names.
  - Listing and metadata failures are recorded in `SystemHealthService` and show up in the notification center. Step-by-step records are written with `beta_log` in `utils/gdrive_beta_log.py`.

### ⑭ JSONL Logging and Hybrid DB Flushing
* **Architectural change**: previously, worker threads wrote results to a `.jsonl` file that the main engine bulk-inserted in one pass after the scan finished. Today, results are instead **accumulated directly in in-memory `pending_inserts`/`pending_updates`/`pending_folders` lists** and flushed to the DB periodically.
* **Hybrid flush trigger**: a flush fires as soon as accumulated changes reach 100 items, or 50 folders have been processed (plus one final flush at scan end).
* **Redis distributed lock for write serialization**: every flush must acquire the `lock:db_write:{db_type}` Redis lock (TTL 90s, wait timeout 5–10s, exponential backoff retry) — this coordinates the assumption that multiple scanner processes/workers may write to the same DB concurrently. SQLite `database is locked` errors are also retried up to 12–20 times on commit (`_commit_with_retry`).
* **Current role of the JSONL file**: no longer the source of the DB write — it's now an **audit/debug log** appended right after each successful flush commit. It's deleted by default at scan completion, and only archived to `logs/jsonl/` when the environment variable `SCAN_JSONL_REMOVE=false` is set. Orphaned `.jsonl` files left over from a crashed prior run are also cleaned up at scan start.

### ⑮ Two-Tier mtime-Based Ultra-Fast Skip Algorithm
* **Problem solved**: dramatically reduces wasted I/O/CPU from re-scanning and re-parsing books/folders already fully registered in the DB.
* **Tier 1 — per-file skip** (`tools/scanner/tasks.py`): upon entering a folder, each file's mtime/size is first checked against the DB cache (`db_files_cache`), truncated to integer precision. Additional rules differ by format:
  - ZIP/CBZ: skip only if `has_offsets` is already cached.
  - TXT: skip immediately on mtime/size match, no cover/offset check needed.
  - Other formats (EPUB/PDF): require cover + author + publisher + summary to all be populated (`db_meta_full`).
  - IMGDIR virtual entries are compared separately via folder mtime and summed image size.
* **Tier 2 — folder-level skip**: for a folder where every file passed Tier 1 but a metadata file (`kavita.yaml`/`info.xml`) still exists, the folder modification time (`dir_mtime = os.path.getmtime(root)`) and the max mtime among metadata files (`meta_mtime`) are additionally compared against the `folder_mtimes` table cache. Only if both match is the whole folder skipped without invoking any parser.
* Folders with no metadata files at all are skipped immediately after Tier 1 alone. This near-zero-cost skip is what lets periodic re-syncs of large libraries run with negligible system load.

### ⑯ Real-Time Deletion Watch, Restoration, and Auto-Empty Trash Policy
* **Deletion detection and soft delete** (`tools/scanner/sync_detector.py::handle_deleted_books`):
  - A book that no longer appears anywhere in the physical file tree is soft-deleted: `books.is_deleted = 1`, `deleted_at = CURRENT_TIMESTAMP`.
  - **`deleted_at` keeps the time the book first went to the trash.** The scanner's "missing" list also contains books already in the
    trash; previously every scan re-stamped their time, so the 7-day auto-empty never happened for frequently scanned categories
    (fixed 2026-10-02). Only older rows with an empty time get the current time. MariaDB evaluates `SET` left to right, so
    `deleted_at` is assigned before `is_deleted`.
* **Pre-deletion safety gate** (`services/scan_problem_service.py::gate_deletions`, decided right before moving books to the trash):
  - **Category root/mount unreachable** (missing, empty or erroring) -> deletion sync is skipped entirely for this scan (including
    restore and the 7-day purge). A "remote drive disconnected" card (action required) appears and clears itself on the next scan
    after the connection is back. This check cannot be turned off.
    To keep network blips from flashing the card on and off, it only shows once the root has stayed unreachable for 10 minutes
    (`CATALOG['remote_unavailable']['grace_sec']`); the deletion hold still applies immediately. Scan jobs that failed because the root
    was unreachable are not shown as separate scan failures. Audiobook/video categories use the same card, cleared by the next scan that reaches the root.
  - **Root is fine but many books vanish in one scan** (20%+ of the category AND 20+ books, `get_mass_missing_thresholds`) ->
    moving the newly missing books to the trash is held and a "possible mass move/delete" card appears. When the admin presses
    [Move to trash], only books whose files are still missing are moved.
  - Otherwise books go to the trash as before and are recorded as `file_missing` (notice).
  - File errors (corrupt files, cover failures, ...) are also recorded in `problem_occurrences` and resolved automatically when the
    next scan finds them healthy. Problem records are written after the scan transaction commits (avoids SQLite lock conflicts).
    Admins can check one book at a time with book [Diagnose].
* **Restoration**: if a path that was previously soft-deleted reappears during a scan, it's automatically restored — `is_deleted = 0`, `deleted_at = NULL` — simply by putting the file back.
* **Auto hard-delete after 7 days**: books soft-deleted more than 7 days ago are permanently purged on every subsequent scan — the rows that hang off the book (progress, reading log, offsets, annotations, bookmarks, TTS, etc.) and the `books` record are all removed within one transaction, and the associated physical cover image file is deleted from disk too. This policy works in concert with the manual trash-management feature in [services/trash_service.py](../services/trash_service.py).
* **Emergency-brake safeguard**: if a scan finds **`0`** physical files, it's far more likely that a mounted network drive got unmounted or a path is misconfigured than that the user actually deleted everything. In this case all delete/restore processing is **force-cancelled**, a warning is logged, and the session exits immediately, to prevent the DB from being mass-wiped.

### ⑰ ZIP/CBZ Archive Handling and Partial-Byte Streaming Strategy
* **In-archive file ordering policy**:
  - Image files inside the archive (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`) are filtered and collected during ZIP/CBZ scanning.
  - The collected image files are sorted using **`natural_sort_key`** to match human-intuitive ordering (e.g. `page_2.jpg` always sorts before `page_10.jpg`).
* **Offset collection for partial-byte streaming**:
  - Instead of the traditional approach of pre-extracting the whole archive to a server directory, the individual files' internal ZIP structure info — **local header byte start (`local_header_offset`)**, **compressed size (`compress_size`)**, **uncompressed size (`file_size`)**, and **compression type (`compress_type`)** — is parsed and persisted into `book_offsets`.
  - When a user requests a specific page's image, the server looks up that page's offset range in the DB and uses **`f.seek()`** to read only that byte range of the physical file, dramatically minimizing disk I/O and CPU decompression overhead in the ultra-fast real-time streaming viewer.
* **Cover fallback auto-extraction**:
  - When neither a 1:1 individual image nor a folder-level representative cover exists, the **first image (index 0)** from the naturally sorted archive listing is physically extracted as the cover, auto-saved under `covers/{library_id}` with a hashed filename.
* **VFS (remote network drive) exception rule**:
  - On a remote cloud storage (e.g. Google Drive) mounted via Rclone VFS, the many Read/Seek calls needed to probe large ZIP file headers over the network can cause severe response latency (API bottleneck) and scanner freezing.
  - To prevent this, **when the physical path is identified as a remote mount (`is_remote` is true), in-archive ZIP/CBZ exploration (offset indexing and auto cover extraction) is forcibly skipped.**

### ⑱ Rclone RC ID/Password (Basic Auth) Support
* **Problem solved**: prevents Rclone VFS cache refresh requests from failing with HTTP 401 Unauthorized when the Rclone RC API server has credentials configured (`--rc-user`/`--rc-pass`).
* **Mechanism**:
  - Dynamically extracts `username` and `password` from the configured `RCLONE_RC_URL` (formatted as `http://user:pass@host:port`) via `urllib.parse`.
  - When credentials are found, builds and attaches an HTTP Basic Authentication header (`Authorization: Basic {base64_encoded}`) to the outgoing request.
  - Reconstructs the target URL with the user-info identifier stripped out, to avoid conflicts with Python's `urllib.request` parsing.
  - On exception, masks the credential portion as `****:****` in console/log output so passwords are never exposed.

### ⑲ Scan-Completion Event Dispatch (Community Plugin Integration)
* **Mechanism** (`tools/scanner/engine.py::_dispatch_new_books_to_plugin_hooks`, run asynchronously on a background thread after the scan completes):
  1. Fires the legacy webhook event `scan.new_books_detected`, summarizing the newly detected books.
  2. Fires a standard `book.new` event individually for each new book (with title/author/publisher/series/format metadata).
  3. Looks up every enabled metadata plugin via `MetadataFactory.get_available_providers()` and invokes its `on_scan_new_books_detected` hook if implemented.
* This 3-part dispatch runs at the end of every scan, both for the general/adult scanner described in this document and for the audiobook scanner in [Section 3](#3-audiobook-scanner-a-fully-separate-pipeline). For a working example (fan-out to multiple webhook targets), see `plugins/metadata/webhook_new_books_notify/` and [guide_plugins.md](./guide_plugins.md).

### ⑳ Lazy Scanner (Second-Pass Repair Scanner)
* **Problem solved**: revisits, in a separate background session, items the main scan deliberately deferred — heavy ZIP header analysis on remote paths, large PDF cover extraction, etc. — and backfills their covers/offsets.
* **Mechanism** (`tools/lazy_scanner.py`):
  - Scope is bounded by DB settings `LAZY_SCAN_MAX_FILE_SIZE_MB` (default 300MB) and `LAZY_SCAN_MAX_BATCH_SIZE_MB` (default 1024MB, cumulative per-session processing cap). A value of `0` removes the corresponding limit.
  - Has its own independent memory-watch logic, separate from the main scanner; on exceeding it, calls **`sys.exit(10)`** (rather than an `os.execv` self-respawn) to signal "needs to be rescheduled" to whatever runs it.
  - Uses a dedicated `ZipRotatingLogger` that rotates every 10MB.

---

## 3. Audiobook Scanner (A Fully Separate Pipeline)

Audiobook libraries (`media_audiobook.db`, `db_type == 'audiobook'`) are detected in `tools/scanner/core.py::scan_library`/`scan_library_path` and immediately delegated to, then returned from, `services/audiobook_scanner.py::scan_audiobook_library`. **None of Sections 1–2's thread pool, checkpointing (`scanner_progress`), cancellation detection, JSONL/Redis-lock-based flushing, or `book_offsets` byte-offset streaming mechanisms apply to the audiobook path at all.** Only HDD wake-up ([①](#①-hddnas-wake-up-and-pre-flight-path-validation)) and VFS cache refresh ([②](#②-rclone-vfs-cache-refresh)) are shared.

```mermaid
graph TD
    A([scan_audiobook_library starts]) --> B[Fetch existing folder paths<br/>from AudiobookRepository]
    B --> C[Single-threaded os.walk traversal]
    C --> D{audio.json present, or<br/>an audio-extension file present?}
    D -- "No" --> C
    D -- "Yes" --> E{force=False and<br/>folder already registered?}
    E -- "Yes" --> F[Skip; dirs.clear() blocks<br/>subtree traversal]
    F --> C
    E -- "No" --> G[scan_and_save_audiobook_folder]
    G --> H[dirs.clear() prevents<br/>nested-audiobook subtree traversal]
    H --> C
    C -- "traversal done" --> I[Async event dispatch<br/>for new items]
    I --> J([Done])
```

### ㉑ Folder-Unit Traversal and Skip Policy
* **Detection unit**: while walking via `os.walk`, any folder containing an `audio.json` file, or at least one file with a supported audio extension (`AUDIO_EXTENSIONS = .mp3, .m4b, .m4a, .flac, .aac, .wav, .ogg, .opus, .wma`), is treated as "one audiobook".
* **Nesting prevention**: once a folder is identified as an audiobook, `dirs.clear()` blocks recursion into its subfolders — the assumption being that an audiobook folder cannot contain another nested audiobook. Tracks are collected from subfolders too, so when both the folder itself and its subfolders hold audio, the subfolders are merged into that book (e.g. one audio file in the category folder → the whole category becomes one book). This is not split automatically; the notification card `audiobook_nested_audio` reports it ("action required" when the category folder itself is the book or a subfolder's metadata.json/audio.json was ignored, otherwise a notice). Guidance: move the audio files, then delete and re-add the category — the merged book's tracks hold the UNIQUE file paths, so saving the subfolders separately fails as a duplicate (that save failure is shown as an `audiobook_save_failed` card).
* **Skip policy**: unless `force=True`, already-registered folders are skipped without being opened. Registered folders are still compared by **file list signature** (`_audio_signature`: relative path + size of the audio files) against the tracks in the DB (`AudiobookRepository.get_track_signatures`); folders whose tracks were added, removed or renamed are processed again (`[AudiobookScanner][CHANGED]` log). Only listing information is used, so nothing is downloaded from remotes.
* **Folder moves and renames**: if a newly found folder contains all the tracks of exactly one existing book whose folder has vanished, that book is treated as moved and only its path is fixed (`_MovedAudiobookFinder`; id and playback history kept, no new-item event).
* **Hiding vanished books**: vanished books with no match are hidden at the end of the scan (soft delete, `_hide_unmatched_missing`). If the category folder is unreachable or many disappear at once (the same mass-missing rule as books, `is_mass_missing`), this is held and only logged.

### ㉒ Metadata Sources: `metadata.json` Preferred, `audio.json` Legacy Fallback
* **`metadata.json`** (preferred, richer schema): `title`, `publisher`, `description`, `publishedDate`/`publishedYear`, `isbn`, `web_id`, `authors[]` (array), `narrators[]` (array; abbreviated as "N others" past 3 names, appended to the author field), `chapters[{start, end}]` (per-chapter start/end seconds — when the chapter count matches the audio file count 1:1, track durations are taken from these values instead of probing files), `images.cover|poster` + `image_blobs` (embedded cover, see ㉓). The encoding is auto-detected as UTF-8 (with or without BOM), UTF-16 or UTF-32, with a retry as cp949 (Korean Windows ANSI) when that fails (`load_json_any_encoding`, also used for audio.json); a cp949 read is logged. Other ANSI code pages (cp1252, Shift-JIS, ...) are not supported and count as a parse failure. Other fields such as `files`/`title_sort`/`genres`/`tags`/`series` are not read.
* **`audio.json`** (legacy, used when `metadata.json` is absent or fails to parse - syntax error or a non-object top level): a flat structure with `title`, `author`, `publisher`, `code`, `web_id`, `poster`, `premiered`, `author_intro`, `desc`/`description`, `ratings`.
* Both of these parsers are **completely independent** of the [⑧](#⑧-metadata-parsing-and-merging-plugin-extensible-parser-loader) plugin loader under `tools/scanner/metadata/`, and never go through `merge_local_metadata()`.
* **Title/author fallback**: if neither JSON source supplies a title or author, the folder name is split on `" - "` and interpreted as an `"author - title"` pattern.

### ㉓ Poster (Cover) Discovery
* Candidate filenames tried in order: `poster.jpg` → `cover.jpg` → `folder.jpg` (plus `.png`/`.jpeg` variants) → failing all of those, the first `.jpg`/`.jpeg`/`.png`/`.webp` file found in the folder → failing that, if `metadata.json` has an `image_blobs` entry (base64) referenced by `images.cover` (else `images.poster`, or the sole blob when neither key exists), **the `metadata.json` path itself** is stored as the poster source (the base64 never goes into the DB). `utils/cover_helper.py` decodes it on the first cover request and leaves a `.none` marker when no cover is found, so the file is not parsed again.
* Unlike the general scanner's [⑨](#⑨-staged-cover-image-extraction-and-mapping-strategy) pipeline, there is no WebP conversion or hashed-filename re-save — the raw source file path is stored in the DB as-is.

### ㉔ Track Duration Analysis: Multi-Tier Fallback with a Remote Fast Path
The most intricate subsystem here, designed to estimate playback duration without opening entire audio files (`get_audio_duration_and_size`):
1. **`metadata.json` chapter ranges**: when the chapter count matches the audio file count exactly 1:1, `end - start` is used directly as each track's duration with no file probing at all.
   * **On remote categories with no chapter times, files are not opened at all** (music and audiobooks alike, `duration_source=deferred`, duration 0). With rclone VFS (cache-mode full, 256M read-chunk), reading just the length with mutagen downloads the whole m4a (faststart or not), and even an mp3 head read transfers ~252KB per file, using up the shared drive's daily quota (measured 2026-10-11). File sizes come from `os.stat` (listing info), which transfers nothing. `music_enrich_service` fills the length 15 s after a play request, from the already-cached file (zero extra transfer); for audiobooks it fills only the length (track titles/author are not overwritten from tags) and the cover when empty. Unplayed tracks show `-` as their time.
2. **Cache reuse**: if an existing track record exists and `file_path` + `file_size` + `file_mtime` (integer-truncated) all match, the stored duration is reused and re-analysis is skipped.
3. **MP3-only pure-Python frame-header analysis**: MP3 files bypass full-file analysis libraries like `mutagen`/`tinytag`, instead reading only the first/last up to 64KB of the file to locate the first MPEG frame header (`_find_first_mp3_frame`, `_parse_mp3_frame_header`). If a Xing/Info VBR header is present, duration is derived from the total frame count; otherwise it's derived from the CBR bitrate.
4. **Remote fast path (`remote_fast_path`)**: when the target folder is identified as a remote mount (`is_remote_path`), reading the file's tail buffer is skipped entirely to reduce remote-seek cost.
5. **Non-MP3 files and final fallback**: tried in order — `mutagen` → `tinytag` → (MP3 only) the pure-Python parser → an `ffprobe` subprocess (10s timeout).
* When the `AUDIOBOOK_SCAN_VERBOSE=1` environment variable is set, each track's analysis result is logged as `[AudiobookScanner][TRACK_ANALYZED]`, including the resolution source (cache/metadata/file_probe) and elapsed time.

### ㉕ DB Storage and Logging Conventions
* Storage goes through `AudiobookRepository.save_audiobook_scan()` into `media_audiobook.db`'s dedicated audiobook tables; the general scanner's `book_offsets`/`scanner_progress`/`folder_mtimes` tables are never touched. Audiobook streaming is based on HTTP Range requests against the whole audio file, not the ZIP byte-offset mechanism.
* Library-level start/completion is logged as `[AudiobookScanner][LIBRARY_SCAN_START]`/`[LIBRARY_SCAN_DONE]`; per-folder results as `[AudiobookScanner][BOOK_PROCESSED]`, which also records the duration-resolution mode (`cache_only`/`metadata_only`/`file_probe_only`/`mixed`, etc.) and cache-hit ratio for performance diagnostics. This is a distinct naming convention from the general scanner's `[Scanner-*]` log prefixes.
* After a scan, newly found audiobooks trigger the same `scan.new_books_detected` event and plugin-hook dispatch described in [⑲](#⑲-scan-completion-event-dispatch-community-plugin-integration) (`_dispatch_audiobook_new_items_events`). This dispatch was missing for a long time precisely because the audiobook scanner is a separate pipeline; it now reuses the same hook-calling path as the general scanner (`tools/scanner/engine.py::_dispatch_new_books_to_plugin_hooks`).


---

## 4. Video Scanner (A Separate Pipeline)

Video categories (`media_video.db`, `db_type == 'video'`) are handed off by `tools/scanner/core.py` to `services/video_scanner.py::scan_video_library`. Like audiobooks it uses the rule **one folder = one course**; the general scanner's thread pool, checkpoints, cancel detection and offset handling do not apply. HDD wake-up ([①](#①-hddnas-wake-up-and-pre-flight-path-validation)), the VFS refresh ([②](#②-rclone-vfs-cache-refresh)) and the root-unreachable card ("remote drive disconnected") are shared.

### ㉖ Traversal and episode registration
* **Detection unit**: `os.walk` treats a folder containing video files (`VIDEO_EXTENSIONS = .mp4, .mkv, .avi, .webm, .mov, .m4v, .ts`) as a course and does not descend further (`dirs.clear()`). Episodes are collected from subfolders too and sorted naturally.
* **Skip policy**: same as audiobooks. Registered courses are skipped, but if the file list signature (relative path + size) differs from the episodes in the DB (`VideoRepository.get_episode_signatures`), the course is processed again and new episodes are registered (`[VideoScanner][CHANGED]`).
* **Metadata**: a `show.yaml` (Plex TV-show style) in the course folder supplies course and episode info (first season only). Without it the folder name is the title.
* **Subtitles**: sidecar `.srt`/`.smi`/`.vtt` files with the same name are found. Language tags (`Movie.ko.srt`) are recognized, partial subtitles (`forced`) are skipped, and Korean and `srt` are preferred (`_find_sidecar_subtitle`).
* **Moved and vanished courses**: uses the same code as audiobooks (`_MovedAudiobookFinder`, `_hide_unmatched_missing`). If a newly found folder's episodes (relative path + size) include every episode of exactly one existing course whose folder is gone, only the paths are updated (`VideoRepository.relocate_video`; the id and watch history are kept; `[VideoScanner][MOVED]`). Unmatched vanished courses are hidden at the end of the scan (`is_deleted`); this is held when the category folder is unreachable or too many vanish at once (`[VideoScanner][MISSING_HELD]`). When a hidden course's folder comes back it is processed and restored (`[VideoScanner][RESTORED]`). Episode files that vanish inside a course are removed when the course is saved.

### ㉗ Duration/codec analysis and playback
* The scan stores only the file list and sizes; duration, resolution and codec analysis (ffprobe) is done **later by the lazy scanner** (the video step in `tools/lazy_scanner.py`). Episodes already analyzed reuse the cache when mtime and size match.
* If the analysis shows a codec or container the browser can't play as is, `video_episodes.needs_transcode = 1` is set and playback goes through ffmpeg (`is_browser_compatible`). Files whose extension doesn't match the real container are checked once more via `container_verified`.

---

## 5. Post-Scan Work (Shared)

### ㉘ Updating lists and events
* **When a queued scan finishes** (the worker loop in `services/scanner_queue.py`, on success or partial success):
  - The recently-added cache (`cache:recent_added*`) is cleared.
  - For the book DBs (general/adult) the series summary table is rebuilt (`SeriesRepository.rebuild_summary`). Failures are recorded in `SystemHealthService`.
* **Direct scans that bypass the queue** (path scan `/api/media/libraries/<id>/scan-path`, a webhook scan with a path `/api/webhook/scan`, plugin webview downloads):
  - Wrapped in `services/scan_refresh_service.py::track_direct_scan`, which compares series snapshots before and after the scan and recomputes **only the changed series rows** (`refresh_summary_keys`). With many changed series (more than 500) or no snapshot, the whole table is rebuilt.
  - Requests are batched briefly (1 second) and handled in the background, so the API response isn't delayed. Only one update per DB runs at a time.
* **New-item events**: newly registered items are announced through webhooks and plugin hooks ([⑲](#⑲-scan-completion-event-dispatch-community-plugin-integration)). They are sent from daemon threads so the scan thread isn't held up.
* **Scan result summary**: the number of new books, the error count and the report file name are stored in `scan_history.result_summary` and shown under "recently finished" in the notification center.

---
*Last Updated: 2026-11-08*
