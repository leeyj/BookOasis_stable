# 📑 BookOasis Scanner Logic Technical Specifications

This document provides a detailed technical specification of the background synchronization scanner engine, which maps the physical directory's books/comics to the database schema.

---

## 1. Scanner Workflow Overview

The BookOasis scanner runs on a background thread pool to crawl directories, parse metadata, write offsets, and generate covers while maintaining responsive Web UI interactions.

```mermaid
graph TD
    Start[1. Trigger Scan] --> VFS[2. Rclone VFS Cache Refresh]
    VFS --> FetchDB[3. Fetch Database Cache Map]
    FetchDB --> Loop[4. Crawl Directories]
    
    Loop --> MtimeCheck{5. dir_mtime & meta_mtime Match?}
    MtimeCheck -- Yes --> Skip[6. Ultra-fast Skip Folder]
    MtimeCheck -- No --> Parse[7. Parallel Parse Comic Archives]
    
    Parse --> JSONL[8. Serialize Parser Output to JSONL]
    JSONL --> Bulk[9. Bulk Transaction Write to SQLite]
    Bulk --> Clean[10. Clean Unused Cover Files]
    Clean --> End[11. Scan Completed]
```

---

## 2. Step-by-Step Mechanism

### ① Thread Pool Execution & Concurrency
* **Executor**: Utilizes Python's `ThreadPoolExecutor` to crawl folders in parallel.
* **Worker Pools**: Spawns multiple worker threads based on processor cores to parse metadata concurrently.
* **DB Lock Mitigation**: Workers do not write to the SQLite database directly during parsing to avoid thread lockups.

### ② Rclone VFS Cache Refresh
* **Scenario**: If the library path is marked as a remote mount (`is_remote = 1`) and `vfs_refresh_before_scan` is enabled.
* **Action**: Invokes the Rclone Remote Control API (`rclone rc vfs/refresh`) to pull the latest file structure before starting the crawl.

### ③ Database Cache Retrieval
* **Cache Map**: Retrieves existing database entries into localized memory maps (`db_meta_full`, `db_offsets_cached`, and `db_folder_mtimes`) to avoid redundant database reads.

### ④ Directory Crawling
* **Method**: Walk through directories using recursive iteration.
* **Filtering**: Non-book files and temporary directory structures are ignored automatically.

### ⑤ Double Mtime Check (Ultra-fast Skip)
* **Action**: Calculates the folder modification time (`dir_mtime = os.path.getmtime(root)`) and the maximum modification time among metadata files such as `kavita.yaml` or `info.xml` (`meta_mtime = max(meta_mtimes_list)`).
* **Comparison**: Compares these two values with the cached values stored in the `folder_mtimes` table.
* **Decision**: If both timestamps match and all child files exist in the cache, the scanner skips the entire folder in `0.001s` without executing parser routines.

### ⑥ Parallel Comic Parsing
* **Archive Formats**: Parses `ZIP` and `CBZ` structures.
* **Natural Sorting**: Applies `natural_sort_key` sorting to the list of image files to ensure correct page orders (e.g., `page_2.jpg` precedes `page_10.jpg`).
* **Offset Indexing**: Pre-calculates the byte offset (`local_header_offset`), compressed size (`compress_size`), and uncompressed size (`file_size`) for each page inside the archive, storing them in `book_offsets`.
* **VFS Exemption**: If `is_remote` is active, offset parsing and auto-cover extraction are bypassed to avoid API rate limits and network latency.

### ⑦ Cover Extraction and Fallback
* **Manual Cover Check**: Checks if a designated cover image (e.g., `cover.jpg`) exists in the directory.
* **Archive Fallback**: If no standalone cover exists, the scanner extracts the first page (index 0) from the sorted archive list, converts it to WebP format, and saves it under the `covers/{library_id}` directory.

### ⑧ JSONL Serialization & Bulk Database Writing
* **JSONL Serialization**: Parsed structures are serialized and written line-by-line to a temporary `.jsonl` file.
* **Bulk Import**: The main scanner thread reads the `.jsonl` file and executes a bulk database transaction (`INSERT OR REPLACE`). This minimizes database write operations, maintaining a highly responsive UI dashboard.

### ⑨ Unused Cover File Cleanup
* **Action**: Post-scan cleanup walks through the `covers/{library_id}` directories and matches them against the active book list. Abandoned cover files are purged to reclaim disk space.

### ⑩ Support for ID/Password Authentication (Basic Auth) in Rclone RC
* **Issue Solved**: Prevents Rclone VFS cache refresh failures (HTTP 401 Unauthorized errors) when the Rclone RC API server requires credentials (`--rc-user` and `--rc-pass`).
* **Mechanism**:
  - Dynamically extracts the `username` and `password` from the configured `RCLONE_RC_URL` (formatted as `http://user:pass@host:port`) using `urllib.parse`.
  - Automatically compiles and appends an HTTP Basic Authentication header (`Authorization: Basic {base64_encoded}`) to the outgoing HTTP request.
  - Reconstructs the target URL by stripping user credentials to prevent parsing anomalies within the standard Python `urllib.request` library.
  - Ensures password security by masking credential segments as `****:****` in console warnings and scanner logs during exception handling.

---
*Last Updated: 2026-07-05*
