# -*- coding: utf-8 -*-
import os
import sys
import gc
import time
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import database
from tools.scanner.vfs import trigger_vfs_refresh
from services.webhook_dispatcher import dispatch_webhook_event
from services.webhook_dispatcher import build_book_event_payload, dispatch_standard_book_event
from services.metadata_factory import MetadataFactory
from utils.drive_helper import is_remote_path
from tools.scanner.memory_helper import check_memory_exceeded
from tools.scanner.path_utils import canonical_path, join_canonical
from tools.scanner.db_writer import update_book_metadata, insert_new_book_v2, save_book_offsets, bulk_update_books, bulk_insert_books, bulk_save_book_offsets
from tools.scanner.tasks import process_folder_task, process_folder_covers, SUPPORTED_FORMATS, SUPPORTED_IMAGE_FORMATS, IMGDIR_VIRTUAL_FILENAME
from tools.scanner.sync_detector import detect_and_handle_book_movement, handle_deleted_books

MAX_SCANNER_THREADS = 4
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')

# 우아한 종료 시그널 감지 플래그
stop_requested = False


def _is_db_locked_error(exc):
    try:
        return isinstance(exc, sqlite3.OperationalError) and 'locked' in str(exc).lower()
    except Exception:
        return False


def _commit_with_retry(conn, context_label, max_attempts=6):
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            conn.commit()
            return True
        except Exception as e:
            last_exc = e
            if not _is_db_locked_error(e):
                raise
            try:
                conn.rollback()
            except Exception:
                pass
            wait_sec = min(3.0, 0.2 * (2 ** (attempt - 1)))
            print(f"[Scanner-DB] {context_label} commit locked (attempt {attempt}/{max_attempts}). Retrying in {wait_sec:.2f}s...")
            time.sleep(wait_sec)

    if last_exc:
        raise last_exc
    return False


def _dispatch_new_books_to_plugin_hooks(db_type, event_payload):
    """Call optional on_scan_new_books_detected hook on each enabled metadata plugin."""
    try:
        providers = MetadataFactory.get_available_providers()
    except Exception as discover_err:
        print(f"[Scanner-PluginHook] provider discovery failed: {discover_err}")
        return

    for meta in providers:
        try:
            if not meta.get('enabled'):
                continue

            provider_id = meta.get('id')
            if not provider_id:
                continue

            provider = MetadataFactory.get_provider_by_id(provider_id)
            hook = getattr(provider, 'on_scan_new_books_detected', None)
            if not callable(hook):
                continue

            result = hook(db_type, dict(event_payload))
            print(f"[Scanner-PluginHook] provider={provider_id} result={result}")
        except Exception as hook_err:
            print(f"[Scanner-PluginHook] provider={meta.get('id')} failed: {hook_err}")

def _scan_library_internal(conn, db_path, library_id, physical_path, force, db_type, target_paths, is_remote, threads_to_use, library_errors):
    cursor = conn.cursor()

    def log_pool_stats(tag):
        try:
            s = database.get_pool_stats(db_type)
            state = 'ready' if s.get('initialized') else 'cold'
            print(
                f"[DB-Pool] ({db_type}) [{tag}] state={state} "
                f"allocated={s['allocated']} in_use={s['in_use']} idle={s['idle']} "
                f"max={s['max_size']} util={s['utilization_pct']:.1f}%"
            )
        except Exception as e:
            print(f"[DB-Pool] ({db_type}) [{tag}] stats read failed: {e}")

    cursor.execute("""
        SELECT id, file_path, has_offsets,
               cover_image, author, publisher, summary, file_mtime, file_size
        FROM books WHERE library_id = ?
    """, (library_id,))
    all_rows = cursor.fetchall()
    db_books = {}          
    db_meta_full = set()   
    db_offsets_cached = set() 
    db_files_cache = {}
    for row in all_rows:
        norm_path = canonical_path(row['file_path'])
        db_books[norm_path] = row['id']
        db_files_cache[norm_path] = (row['file_mtime'] or 0.0, row['file_size'] or 0)
        if row['has_offsets'] == 1:
            db_offsets_cached.add(norm_path)
        if (row['cover_image'] and not row['cover_image'].startswith('series_') and
                row['author'] and row['publisher'] and row['summary']):
            db_meta_full.add(norm_path)

    cursor.execute("SELECT folder_path, dir_mtime, meta_mtime FROM folder_mtimes")
    db_folder_mtimes = {canonical_path(row['folder_path']): (row['dir_mtime'], row['meta_mtime']) for row in cursor.fetchall()}

    # 0. Load completely scanned folders from previous checkpoint
    cursor.execute("SELECT folder_path FROM scanner_progress WHERE library_id = ?", (str(library_id),))
    scanned_folders = set(canonical_path(row['folder_path']) for row in cursor.fetchall())
    if scanned_folders:
        print(f"[Scanner-Progress] 🔄 Previous scan progress detected ({len(scanned_folders)}folders completed). Resuming scan.")

    # 1. Traverse physical folder tree and pre-collect file list
    tasks = []
    found_file_paths = set()
    traversal_errors = []

    def _walk_onerror(err):
        traversal_errors.append(str(err))
        print(f"[Scanner] os.walk traversal warning: {err}")

    print(f"[Scanner] Scanning physical folder tree...")
    folder_count = 0
    for t_path in target_paths:
        if not os.path.exists(t_path):
            print(f"[Scanner] Warning: Path does not exist, skipping: {t_path}")
            continue
        for root, dirs, files in os.walk(t_path, onerror=_walk_onerror):
            root = canonical_path(root)
            media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
            image_files = [f for f in files if f.lower().endswith(SUPPORTED_IMAGE_FORMATS)]
            has_imgdir_candidate = bool(image_files) and not media_files
            if not media_files and not has_imgdir_candidate:
                continue
            for f in media_files:
                found_file_paths.add(join_canonical(root, f))
            if has_imgdir_candidate:
                found_file_paths.add(join_canonical(root, IMGDIR_VIRTUAL_FILENAME))
            
            if root in scanned_folders:
                continue
                
            tasks.append((root, files, t_path))

    # 순회가 부분 실패한 경우 삭제/이동 동기화를 건너뛰어 오탐 soft-delete를 방지한다.
    if traversal_errors:
        print(
            f"[Scanner] Traversal completed with {len(traversal_errors)} warning(s). "
            "Move/delete synchronization is skipped for safety."
        )
        deleted_paths = set()
    else:
        # ── [Book movement detection and history preservation layer - pre-process before thread execution] ──
        deleted_paths = detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached)
        _commit_with_retry(conn, 'pre-move-detection')

    # 2. Run thread pool and streaming process (as_completed)
    print(f"[Scanner] Multithread scan pool created (threads: {threads_to_use})")
    log_pool_stats('scan-start')
    
    processed_folders_count = 0
    import json
    import threading
    import datetime
    import re
    from dotenv import load_dotenv

    cursor.execute("SELECT name FROM libraries WHERE id = ?", (library_id,))
    lib_row = cursor.fetchone()
    library_name = lib_row['name'] if lib_row else f"Lib_{library_id}"
    safe_lib_name = re.sub(r'[\\/*?:"<>|]', "", library_name)
    scan_time_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    scan_temp_file = os.path.join(DB_DIR, f'{safe_lib_name}_{scan_time_str}.jsonl')
    
    # ── [Orphan File Cleanup] ──
    try:
        for f in os.listdir(DB_DIR):
            if f.endswith('.jsonl') and f != os.path.basename(scan_temp_file):
                try:
                    os.remove(os.path.join(DB_DIR, f))
                    print(f"[Scanner] Orphan JSONL removed: {f}")
                except Exception:
                    pass
    except Exception:
        pass

    if os.path.exists(scan_temp_file):
        os.remove(scan_temp_file)
    file_lock = threading.Lock()

    def process_batch(cur, ins_list, upd_list):
        if upd_list:
            update_data = []
            for d in upd_list:
                if d.get('is_offset_only'):
                    continue
                meta = d['merged_meta']
                score = meta.get('score', 0)
                update_data.append((
                    d.get('series_name', ''),
                    d['cover_image'], d['cover_image'], d['cover_image'],
                    meta.get('author',''), meta.get('isbn',''), meta.get('publisher',''), meta.get('link',''),
                    score, score, meta.get('summary',''), meta.get('release_date',''),
                    meta.get('genre',''), meta.get('tags',''),
                    d.get('file_mtime', 0.0), d.get('file_size', 0),
                    canonical_path(d['full_path'])
                ))
            if update_data:
                bulk_update_books(cur, update_data, force=force)
            
        if ins_list:
            insert_data = []
            for d in ins_list:
                meta = d['merged_meta']
                title = d.get('title')
                if not title:
                    title, _ = os.path.splitext(d['filename'])
                insert_data.append((
                    d['library_id'], title, d['series_name'], meta.get('author',''), meta.get('isbn',''),
                    canonical_path(d['full_path']), d['file_format'], 100 if d['file_format'] == 'epub' else 0,
                    d['cover_image'], meta.get('publisher',''), meta.get('link',''),
                    meta.get('score',0), meta.get('summary',''), meta.get('release_date',''),
                    meta.get('genre',''), meta.get('tags',''),
                    d.get('file_mtime', 0.0), d.get('file_size', 0)
                ))
            bulk_insert_books(cur, insert_data)

        all_paths = [canonical_path(d['full_path']) for d in ins_list] + [canonical_path(d['full_path']) for d in upd_list if d.get('offsets_data')]
        if all_paths:
            path_to_id = {}
            for i in range(0, len(all_paths), 900):
                chunk = all_paths[i:i+900]
                placeholders = ','.join(['?']*len(chunk))
                cur.execute(f"SELECT id, file_path FROM books WHERE file_path IN ({placeholders})", chunk)
                for row in cur.fetchall():
                    path_to_id[canonical_path(row['file_path'])] = row['id']
            
            offsets_to_save = []
            for d in upd_list + ins_list:
                if d.get('offsets_data'):
                    bid = path_to_id.get(canonical_path(d['full_path']))
                    if bid:
                        for off in d['offsets_data']:
                            offsets_to_save.append((bid, *off))
                            
            if offsets_to_save:
                bulk_save_book_offsets(cur, offsets_to_save)

    pending_inserts = []
    pending_updates = []
    pending_folders = []
    detected_new_books = []

    def flush_pending_data(is_final=False):
        if not pending_inserts and not pending_updates and not pending_folders:
            print(f"[Scanner-DB] Flush skipped: 0 pending items (is_final={is_final})")
            return True

        max_attempts = 15 if is_final else 6
        lock_timeout = 10.0 if is_final else 1.0
        for attempt in range(1, max_attempts + 1):
            gate_token = None
            try:
                from utils.redis_helper import redis_acquire_lock, redis_release_lock

                gate_token = redis_acquire_lock(f"lock:db_write:{db_type}", ttl=90, wait_timeout=lock_timeout)
                if not gate_token:
                    wait_sec = min(4.0, 0.25 * (2 ** (attempt - 1)))
                    print(
                        f"[Scanner-DB] DB write gate busy (attempt {attempt}/{max_attempts}, is_final={is_final}) "
                        f"db={db_type} ins={len(pending_inserts)} upd={len(pending_updates)} folders={len(pending_folders)} "
                        f"Retrying in {wait_sec:.2f}s..."
                    )
                    time.sleep(wait_sec)
                    continue

                print(
                    f"[Scanner-DB] Flush start (attempt {attempt}/{max_attempts}, is_final={is_final}) "
                    f"ins={len(pending_inserts)} upd={len(pending_updates)} folders={len(pending_folders)}"
                )
                # 1. DB Bulk Update
                if pending_inserts or pending_updates:
                    process_batch(cursor, pending_inserts, pending_updates)

                # 2. Scanner Progress Update
                for pf in pending_folders:
                    cursor.execute("INSERT OR IGNORE INTO scanner_progress (library_id, folder_path) VALUES (?, ?)", (str(library_id), pf['root']))
                    if pf.get('dir_mtime') is not None:
                        cursor.execute("INSERT OR REPLACE INTO folder_mtimes (folder_path, dir_mtime, meta_mtime) VALUES (?, ?, ?)", (pf['root'], pf['dir_mtime'], pf['meta_mtime']))

                # 3. Commit ALL at once (Atomic Transaction)
                _commit_with_retry(conn, 'flush-pending')
                time.sleep(0.05)

                # 4. Append to JSONL log
                if pending_inserts or pending_updates:
                    with file_lock:
                        with open(scan_temp_file, 'a', encoding='utf-8') as f:
                            for item in pending_inserts:
                                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                            for item in pending_updates:
                                f.write(json.dumps(item, ensure_ascii=False) + '\n')

                pending_inserts.clear()
                pending_updates.clear()
                pending_folders.clear()
                print(
                    f"[Scanner-DB] Flush success (attempt {attempt}/{max_attempts}, is_final={is_final}) "
                    f"remaining_ins={len(pending_inserts)} remaining_upd={len(pending_updates)} remaining_folders={len(pending_folders)}"
                )
                return True
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if _is_db_locked_error(e) and attempt < max_attempts:
                    wait_sec = min(4.0, 0.25 * (2 ** (attempt - 1)))
                    print(
                        f"[Scanner-DB] Flush locked (attempt {attempt}/{max_attempts}, is_final={is_final}) "
                        f"ins={len(pending_inserts)} upd={len(pending_updates)} folders={len(pending_folders)} "
                        f"Retrying in {wait_sec:.2f}s..."
                    )
                    time.sleep(wait_sec)
                    continue
                print(
                    f"[Scanner ERROR] Flush failed after attempt {attempt}/{max_attempts}: {e} "
                    f"ins={len(pending_inserts)} upd={len(pending_updates)} folders={len(pending_folders)}"
                )
                return False
            finally:
                if gate_token:
                    try:
                        redis_release_lock(f"lock:db_write:{db_type}", gate_token)
                    except Exception:
                        pass

        return False

    def cleanup_jsonl_file():
        load_dotenv()
        if str(os.getenv('SCAN_JSONL_REMOVE', 'true')).strip().lower() == 'false':
            try:
                log_jsonl_dir = os.path.join(MEDIA_SERVER_DIR, 'logs', 'jsonl')
                os.makedirs(log_jsonl_dir, exist_ok=True)
                import shutil
                if os.path.exists(scan_temp_file):
                    shutil.move(scan_temp_file, os.path.join(log_jsonl_dir, os.path.basename(scan_temp_file)))
                    print(f"[Scanner] JSONL debug file saved to: {os.path.join(log_jsonl_dir, os.path.basename(scan_temp_file))}")
            except Exception as e:
                print(f"[Scanner ERROR] Failed to move JSONL file: {e}")
        else:
            try:
                if os.path.exists(scan_temp_file):
                    os.remove(scan_temp_file)
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=threads_to_use) as executor:
        futures = {
            executor.submit(process_folder_task, root, files, force, db_meta_full, db_offsets_cached, db_folder_mtimes, is_remote, library_id, db_files_cache, t_path): root
            for root, files, t_path in tasks
        }
        
        for fut in as_completed(futures):
            if stop_requested:
                print("[Scanner] ⚠️ 스캔 중단 요청(SIGTERM/SIGINT)이 감지되었습니다. 루프를 탈출하여 현재까지의 변경점만 DB에 쓰고 마감합니다.")
                break
            root_folder = futures[fut]
            try:
                res = fut.result()
                dir_mtime = None
                meta_mtime = None
                if res:
                    dir_mtime = res.get('dir_mtime')
                    meta_mtime = res.get('meta_mtime')
                    merged_meta = res['merged_meta']
                    if 'errors' in res and res['errors']:
                        library_errors.extend(res['errors'])
                    
                    batch_item_count = 0
                    for item in res['results']:
                        full_path = item['full_path']
                        if item['skip']:
                            continue

                        filename = item['filename']
                        file_format = item['file_format']
                        series_name = item['series_name']
                        title = item.get('title')
                        cover_image = item['cover_image']
                        offsets_data = item['offsets_data']
                        is_offset_only = item.get('offset_only', False)

                        if full_path in db_books:
                            pending_updates.append({
                                "action": "update", "is_offset_only": is_offset_only, "full_path": full_path, 
                                "cover_image": cover_image, "merged_meta": merged_meta, "offsets_data": offsets_data, 
                                "filename": filename, "series_name": series_name, "file_mtime": item.get('file_mtime', 0.0), "file_size": item.get('file_size', 0)
                            })
                        else:
                            pending_inserts.append({
                                "action": "insert", "library_id": library_id, "full_path": full_path, 
                                "filename": filename, "file_format": file_format, "series_name": series_name, 
                                "title": title,
                                "cover_image": cover_image, "merged_meta": merged_meta, "offsets_data": offsets_data,
                                "file_mtime": item.get('file_mtime', 0.0), "file_size": item.get('file_size', 0)
                            })
                            detected_new_books.append({
                                'title': title or os.path.splitext(filename)[0],
                                'file_path': full_path,
                                'series_name': series_name,
                                'author': (merged_meta.get('author') if isinstance(merged_meta, dict) else '') or '',
                                'publisher': (merged_meta.get('publisher') if isinstance(merged_meta, dict) else '') or '',
                                'format': file_format,
                            })
                            print(f"[Scanner-Process] Found new book: {filename} (Series: {series_name})")
                        batch_item_count += 1
                    
                    if batch_item_count > 0:
                        # ── [GIL Throttling] ──
                        time.sleep(0.01 * min(batch_item_count, 5))
                        
                    del res
                
                # 락 경쟁 최소화 최적화: 폴더의 수정 시간(mtime)이 DB 캐시와 완전히 일치하고,
                # 해당 폴더 내에서 새로 추가되거나 변경된 도서(ins/upd)가 전혀 없다면
                # 불필요한 folder_mtimes 갱신 및 scanner_progress DB 쓰기를 건너뜁니다.
                has_actual_changes = (batch_item_count > 0)
                cached_mtimes = db_folder_mtimes.get(root_folder)
                mtimes_match = False
                if cached_mtimes:
                    cached_dir_mtime, cached_meta_mtime = cached_mtimes
                    if cached_dir_mtime == dir_mtime and cached_meta_mtime == meta_mtime:
                        mtimes_match = True
                
                if has_actual_changes or not mtimes_match:
                    pending_folders.append({
                        'root': root_folder,
                        'dir_mtime': dir_mtime,
                        'meta_mtime': meta_mtime
                    })
                
                processed_folders_count += 1

            except Exception as e:
                print(f"[Scanner-DEBUG-Pool] ❌ Folder '{root_folder}' processing exception: {e}")
                continue

            if processed_folders_count % 20 == 0:
                log_pool_stats(f'progress-{processed_folders_count}')
            
            # Hybrid Flush Trigger
            if (len(pending_inserts) + len(pending_updates) >= 100) or len(pending_folders) >= 50:
                if not flush_pending_data():
                    raise RuntimeError('Scanner flush failed due to persistent DB contention.')

            if processed_folders_count % 50 == 0:
                gc.collect()

            # Detect manual cancel (abort) request and exit
            # [버그수정] 장기 conn은 WAL 스냅샷 격리로 인해 다른 세션의 COMMIT을 읽지 못함.
            # 취소 상태 확인만 독립 커넥션으로 조회하여 항상 최신 상태를 반영한다.
            # 대시보드 부하를 줄이기 위해 매 폴더가 아닌 주기적으로만 조회한다.
            if processed_folders_count % 10 == 0:
                status_row = None
                _cancel_conn = None
                try:
                    _cancel_conn = database.get_connection(db_type)
                    _cancel_cur = _cancel_conn.cursor()
                    _cancel_cur.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
                    status_row = _cancel_cur.fetchone()
                except Exception as _e:
                    print(f"[Scanner-Cancel] ⚠️ 취소 상태 확인 중 오류 (무시하고 계속 진행): {_e}")
                finally:
                    if _cancel_conn:
                        try:
                            _cancel_conn.close()
                        except Exception:
                            pass
                if status_row and status_row['scan_status'] == 'cancelling':
                    print(f"[Scanner-Cancel] 🛑 Safely aborting scan due to user request. (Completed folders: {processed_folders_count} folders)")
                    log_pool_stats('cancel-abort')
                    if not flush_pending_data():
                        raise RuntimeError('Scanner flush failed while processing cancel request.')
                    cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE id = ?", (library_id,))
                    _commit_with_retry(conn, 'cancel-status-update')
                    conn.close()
                    cleanup_jsonl_file()
                    return

            # Self-exit for real-time OOM prevention
            if check_memory_exceeded(db_type=db_type):
                print(f"[Scanner-Memory] 🛑 Emergency pause due to memory limit. (Progress: {processed_folders_count} folders applied)")
                log_pool_stats('memory-emergency')
                if not flush_pending_data():
                    raise RuntimeError('Scanner flush failed during memory emergency handling.')
                try:
                    conn.close()
                except Exception:
                    pass
                cleanup_jsonl_file()
                os._exit(0)

        # Final flush for any remaining data at the end of the loop
        print(
            f"[Scanner-DB] Final flush begin db={db_type} library_id={library_id} "
            f"pending_ins={len(pending_inserts)} pending_upd={len(pending_updates)} pending_folders={len(pending_folders)}"
        )
        if not flush_pending_data(is_final=True):
            raise RuntimeError('Scanner final flush failed due to persistent DB contention.')
        print(f"[Scanner-DB] Final flush done db={db_type} library_id={library_id}")
        log_pool_stats('scan-final-flush')
        cleanup_jsonl_file()


    # 3. Real-time deletion monitoring: Remove book info disappeared from file system
    print(f"[Scanner-DB] Deletion sync begin db={db_type} library_id={library_id}")
    if not handle_deleted_books(cursor, db_books, deleted_paths, target_paths, found_file_paths):
        print(f"[Scanner-DB] Deletion sync aborted db={db_type} library_id={library_id}")
        conn.close()
        return
    print(f"[Scanner-DB] Deletion sync done db={db_type} library_id={library_id}")

    # Initialize checkpoint of library upon successful completion
    print(f"[Scanner-DB] scan-end-cleanup commit begin db={db_type} library_id={library_id}")
    end_gate_token = None
    try:
        from utils.redis_helper import redis_acquire_lock, redis_release_lock

        end_gate_token = redis_acquire_lock(f"lock:db_write:{db_type}", ttl=90, wait_timeout=5.0)
        if not end_gate_token:
            raise RuntimeError(f"scan-end-cleanup db write gate busy for db_type={db_type}")
        cursor.execute("DELETE FROM scanner_progress WHERE library_id = ?", (str(library_id),))
        cursor.execute("""
            UPDATE libraries 
            SET scan_status = 'ready', 
                last_scanned_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (library_id,))
        _commit_with_retry(conn, 'scan-end-cleanup')
    finally:
        if end_gate_token:
            try:
                redis_release_lock(f"lock:db_write:{db_type}", end_gate_token)
            except Exception:
                pass
    print(f"[Scanner-DB] scan-end-cleanup commit done db={db_type} library_id={library_id}")
    conn.close()
    log_pool_stats('scan-end')
    gc.collect()

    # Save scan result error reports
    if library_errors:
        try:
            from utils.report_helper import save_scan_report
            save_scan_report(library_id, library_errors)
        except Exception as report_err:
            print(f"[Scanner ERROR] Scan report save failed: {report_err}")

    if detected_new_books:
        def _async_event_worker(books, target_db, lib_id, lib_name):
            try:
                sample = [b['title'] for b in books[:10]]
                event_payload = {
                    'db_type': target_db,
                    'library_id': lib_id,
                    'library_name': lib_name,
                    'new_books_count': len(books),
                    'sample_titles': sample,
                }
                try:
                    dispatch_webhook_event('scan.new_books_detected', event_payload)
                except Exception as hook_err:
                    print(f"[Scanner-Webhook] dispatch failed: {hook_err}")

                # 커뮤니티 표준 이벤트: book.new (신규 도서별 개별 발행)
                try:
                    for book in books:
                        metadata = {
                            'type': 'book',
                            'format': (book.get('format') or '').lower(),
                            'title': book.get('title') or '',
                            'author': book.get('author') or '',
                            'publisher': book.get('publisher') or '',
                            'series': book.get('series_name') or None,
                            'seriesIndex': None,
                            'progress': 0,
                            'totalPages': None,
                            'currentLocation': None,
                            'addedAt': int(time.time()),
                        }
                        payload = build_book_event_payload('book.new', metadata=metadata, user=False)
                        dispatch_standard_book_event(payload)
                except Exception as hook_err:
                    print(f"[Scanner-Webhook] standard book.new dispatch failed: {hook_err}")

                _dispatch_new_books_to_plugin_hooks(target_db, event_payload)
            except Exception as async_err:
                print(f"[Scanner-AsyncEvent ERROR] Failed to dispatch scan events: {async_err}")

        dispatch_thread = threading.Thread(
            target=_async_event_worker,
            args=(detected_new_books, db_type, library_id, library_name),
            daemon=True
        )
        dispatch_thread.start()


def _scan_library_covers_only_internal(conn, db_path, library_id, physical_path, target_paths, db_type):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_path, series_name
        FROM books WHERE library_id = ?
    """, (library_id,))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"[Scanner-Covers] No books to scan.")
        return

    is_remote = any(is_remote_path(p) for p in target_paths)

    # Group by folder (share first successful cover in folder as shared_cover_image)
    from collections import defaultdict
    from utils.sort_helper import natural_sort_key
    
    folder_groups = defaultdict(list)
    for row in rows:
        parent_dir = os.path.dirname(row['file_path'])
        folder_groups[parent_dir].append(row)
    
    # Sort files in each folder by title
    for parent_dir in folder_groups:
        folder_groups[parent_dir].sort(key=lambda r: natural_sort_key(r['file_path']))

    print(f"[Scanner-Covers] Folder-level cover extraction started (total {len(folder_groups)} folders, {len(rows)} books)")
    
    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_SCANNER_THREADS) as executor:
        futures = {
            executor.submit(process_folder_covers, parent_dir, folder_rows, is_remote, library_id): parent_dir
            for parent_dir, folder_rows in folder_groups.items()
        }
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                all_results.extend(res)
                
    print(f"[Scanner-Covers] Extraction completed. Bulk updating DB covers and timestamps...")
    processed_count = 0
    for book_id, cover_image in all_results:
        if cover_image:
            cursor.execute("""
                UPDATE books SET 
                    cover_image = ?,
                    cover_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (cover_image, book_id))
            processed_count += 1
            
    _commit_with_retry(conn, 'cover-only-scan')
    print(f"[Scanner-Covers] Cover-only scan finally completed! (total {processed_count} covers updated)")

