# Modified Progress Report

This file tracks sequential fix steps requested in the current review.

## 2026-07-19 Step 0 - Report Init
- Created this progress report file for step-by-step change logging.
- Scope baseline from audit follow-up: apply high-priority fixes in order.

## 2026-07-19 Step 1 - Make Stream GET Read-Only
- Goal: prevent implicit progress writes from `GET /api/media/stream` prefetch calls.
- Changed file:
  - `api/stream.py`
- Changes:
  - Updated stream route docstring to clarify read-only behavior.
  - Removed automatic progress recording block (`record_progress`) from GET stream handler.
  - Removed unused local variable `user_id` in the same handler.
- Expected effect:
  - Viewer prefetch/image fetch no longer mutates reading progress.
  - Progress updates remain explicitly controlled by `POST /api/media/progress`.
- Verification:
  - Code edit applied successfully.
  - Pending: run targeted runtime verification in app flow.

## 2026-07-19 Step 2 - Centralize Stream Permission Check
- Goal: enforce category permission (`user_category_permissions`) on stream file resolution paths.
- Changed files:
  - `services/stream_page_service.py`
  - `services/stream_service.py`
  - `api/stream.py`
  - `services/app_opds_viewer_service.py`
  - `api/app_opds.py`
- Changes:
  - Added shared permission clause builder in stream page service.
  - Added permission-aware lookup for `get_book_file_info` and `get_file_path` with `COALESCE(is_deleted, 0) = 0` guard.
  - Wired session user context (`user_id`, `role`) from media stream routes.
  - Wired authenticated user context from App OPDS routes to viewer service lookups.
- Expected effect:
  - Non-admin users can no longer resolve/read book files outside their allowed categories through stream/txt/pdf paths.
  - Deleted books are excluded from lookup at service layer.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## 2026-07-19 Step 3 - Scanner Canonical Path Unification
- Goal: remove mixed path key behavior in scanner compare/update flow.
- Changed files:
  - `tools/scanner/path_utils.py`
  - `tools/scanner/tasks.py`
  - `tools/scanner/engine.py`
- Changes:
  - Added shared canonical path helpers (`canonical_path`, `join_canonical`).
  - Replaced ad-hoc root/path joins in folder task processing with canonical helpers.
  - Normalized DB-loaded scanner cache keys (`db_books`, `db_files_cache`, `db_offsets_cached`, `db_folder_mtimes`, `scanned_folders`).
  - Normalized discovery keys (`found_file_paths`) and batch write/query path keys.
- Expected effect:
  - Reduced false diffs caused by mixed slash/backslash path keys.
  - More deterministic movement detection and scan skip/update matching.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 4: scanner 실패 상태 전파 보강 (queue completed 오판정 방지).

## 2026-07-19 Step 4 - Scanner Failure Propagation Hardening
- Goal: avoid queue `completed` false-positive when scanner actually fails.
- Changed files:
  - `services/scheduler_service.py`
  - `services/scanner_queue.py`
- Changes:
  - `run_scan_job` failure handler now re-raises after failure status/log update.
  - `lazy_scan` subprocess exit code is validated; non-zero exits raise runtime error.
- Expected effect:
  - Worker loop can mark failing scan tasks as `failed` consistently.
  - Lazy scanner failures are no longer silently treated as success.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 5: SQLite foreign_keys enforcement (connection init path).

## 2026-07-19 Step 5 - SQLite Foreign Key Enforcement
- Goal: enforce referential integrity at runtime connection level.
- Changed file:
  - `database.py`
- Changes:
  - Added `PRAGMA foreign_keys = ON;` in pooled SQLite connection initialization path.
- Expected effect:
  - Runtime inserts/updates/deletes now obey FK constraints declared in schema.
  - Reduces silent orphan data accumulation risk.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 6: PDF 단일 재스캔 db_type 전달 누락 보강.

## 2026-07-19 Step 6 - Single PDF Rescan db_type Propagation
- Goal: prevent single-book PDF rescan from scanning wrong DB scope.
- Changed files:
  - `services/book_scan_service.py`
  - `tools/lazy_scanner.py`
- Changes:
  - PDF isolated subprocess call now includes `--db-type` argument.
  - Lazy scanner CLI now supports `--db-type` and filters target DB loop accordingly.
- Expected effect:
  - Single-book rescan stays in the requested DB (`general`/`adult`) and avoids cross-DB side effects.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 7: trash 표지 삭제 시 참조수 보호(0건일 때만 물리 삭제).

## 2026-07-19 Step 7 - Trash Cover Reference Guard
- Goal: prevent shared cover file deletion when emptying trash.
- Changed file:
  - `services/trash_service.py`
- Changes:
  - Gathered unique cover targets per delete chunk.
  - Physical cover deletion now runs only when `books.cover_image` remaining reference count is 0.
- Expected effect:
  - Shared covers used by surviving books are preserved.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 8: (선택) Docker/worker startup 순서 안전화 또는 scanner os.walk partial-failure guard.

## 2026-07-19 Step 8 - Scanner Partial Traversal Safety Guard
- Goal: prevent false move/delete synchronization when filesystem traversal is incomplete.
- Changed file:
  - `tools/scanner/engine.py`
- Changes:
  - Added `os.walk(..., onerror=...)` warning capture.
  - Added traversal error accumulator and warning logs.
  - When traversal warnings are detected, scanner now skips move detection and deleted-book sync for that run.
- Expected effect:
  - Avoids accidental soft-delete/move misclassification caused by partial directory walk failures.
- Verification:
  - Diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 9: (선택) Docker entrypoint worker/web startup order hardening.

## 2026-07-19 Step 9 - Docker Startup Order Hardening
- Goal: reduce startup race between web app readiness and scanner worker launch.
- Changed file:
  - `entrypoint.sh`
- Changes:
  - Added web health wait helper (`/health`, max 120s).
  - Worker startup is now scheduled in background and launched after web health check (timeout fallback starts worker anyway).
  - Applied the same logic for both root and `media_user` execution paths.
- Expected effect:
  - Lower chance of early worker actions colliding with app/DB startup sequence.
- Verification:
  - Shell script diagnostics check completed: no reported errors.

## Next Planned Step
- Step 10: (선택) 동일 패턴을 `manage.sh start`에도 반영할지 검토.

## 2026-07-19 Step 10 - manage.sh Start Safety Alignment
- Goal: avoid worker-only startup when web process fails early.
- Changed file:
  - `manage.sh`
- Changes:
  - In `start()`, if web process PID check fails right after launch, return immediately with failure status.
  - This blocks subsequent health-wait/worker-start flow on failed app bootstrap.
- Expected effect:
  - Prevents orphan scanner worker startup when web server did not start.
- Verification:
  - Script diagnostics check completed: no reported errors.

## Next Planned Step
- Step 11: (선택) changelog 반영 및 릴리즈 노트 정리.

## 2026-07-19 Step 11 - Changelog / Release Notes Update
- Goal: reflect sequential hardening patches in release-visible notes.
- Changed file:
  - `CHANGELOG.md`
- Changes:
  - Added v1.1.8 entries for stream read-only progress semantics, stream permission centralization, scanner path canonicalization, queue failure propagation, SQLite foreign key enforcement, single-book PDF `db_type` propagation, trash cover reference guard, scanner partial traversal safety guard, and startup-order hardening.
- Expected effect:
  - Operators can track this patch series directly from release notes.
- Verification:
  - Markdown diagnostics check completed: no errors on touched files.

## Next Planned Step
- Step 12: (선택) 실제 런타임 스모크 테스트 시나리오 체크리스트 추가.
