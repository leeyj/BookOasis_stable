# -*- coding: utf-8 -*-
import os
import sys
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import database
from tools.scanner.vfs import trigger_vfs_refresh
from utils.drive_helper import is_remote_path
from tools.scanner.memory_helper import check_memory_exceeded
from tools.scanner.db_writer import update_book_metadata, insert_new_book_v2, save_book_offsets, bulk_update_books, bulk_insert_books, bulk_save_book_offsets
from tools.scanner.tasks import process_folder_task, process_folder_covers, SUPPORTED_FORMATS, SUPPORTED_IMAGE_FORMATS, IMGDIR_VIRTUAL_FILENAME
from tools.scanner.sync_detector import detect_and_handle_book_movement, handle_deleted_books

MAX_SCANNER_THREADS = 4
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')

def _scan_library_internal(conn, db_path, library_id, physical_path, force, db_type, target_paths, is_remote, threads_to_use, library_errors):
    cursor = conn.cursor()

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
        db_books[row['file_path']] = row['id']
        db_files_cache[row['file_path']] = (row['file_mtime'] or 0.0, row['file_size'] or 0)
        if row['has_offsets'] == 1:
            db_offsets_cached.add(row['file_path'])
        if (row['cover_image'] and not row['cover_image'].startswith('series_') and
                row['author'] and row['publisher'] and row['summary']):
            db_meta_full.add(row['file_path'])

    cursor.execute("SELECT folder_path, dir_mtime, meta_mtime FROM folder_mtimes")
    db_folder_mtimes = {row['folder_path']: (row['dir_mtime'], row['meta_mtime']) for row in cursor.fetchall()}

    # 0. Load completely scanned folders from previous checkpoint
    cursor.execute("SELECT folder_path FROM scanner_progress WHERE library_id = ?", (str(library_id),))
    scanned_folders = set(row['folder_path'] for row in cursor.fetchall())
    if scanned_folders:
        print(f"[Scanner-Progress] 🔄 Previous scan progress detected ({len(scanned_folders)}folders completed). Resuming scan.")

    # 1. Traverse physical folder tree and pre-collect file list
    tasks = []
    found_file_paths = set()
    print(f"[Scanner] Scanning physical folder tree...")
    folder_count = 0
    for t_path in target_paths:
        if not os.path.exists(t_path):
            print(f"[Scanner] Warning: Path does not exist, skipping: {t_path}")
            continue
        for root, dirs, files in os.walk(t_path):
            media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
            image_files = [f for f in files if f.lower().endswith(SUPPORTED_IMAGE_FORMATS)]
            has_imgdir_candidate = bool(image_files) and not media_files
            if not media_files and not has_imgdir_candidate:
                continue
            for f in media_files:
                found_file_paths.add(os.path.join(root, f))
            if has_imgdir_candidate:
                found_file_paths.add(os.path.join(root, IMGDIR_VIRTUAL_FILENAME))
            
            if root in scanned_folders:
                continue
                
            tasks.append((root, files))

    # ── [Book movement detection and history preservation layer - pre-process before thread execution] ──
    deleted_paths = detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached)
    conn.commit()

    # 2. Run thread pool and streaming process (as_completed)
    print(f"[Scanner] Multithread scan pool created (threads: {threads_to_use})")
    
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
                    meta.get('author',''), meta.get('publisher',''), meta.get('link',''),
                    score, score, meta.get('summary',''), meta.get('release_date',''),
                    meta.get('genre',''), meta.get('tags',''),
                    d.get('file_mtime', 0.0), d.get('file_size', 0),
                    d['full_path']
                ))
            if update_data:
                bulk_update_books(cur, update_data)
            
        if ins_list:
            insert_data = []
            for d in ins_list:
                meta = d['merged_meta']
                title = d.get('title')
                if not title:
                    title, _ = os.path.splitext(d['filename'])
                insert_data.append((
                    d['library_id'], title, d['series_name'], meta.get('author',''),
                    d['full_path'], d['file_format'], 100 if d['file_format'] == 'epub' else 0,
                    d['cover_image'], meta.get('publisher',''), meta.get('link',''),
                    meta.get('score',0), meta.get('summary',''), meta.get('release_date',''),
                    meta.get('genre',''), meta.get('tags',''),
                    d.get('file_mtime', 0.0), d.get('file_size', 0)
                ))
            bulk_insert_books(cur, insert_data)

        all_paths = [d['full_path'] for d in ins_list] + [d['full_path'] for d in upd_list if d.get('offsets_data')]
        if all_paths:
            path_to_id = {}
            for i in range(0, len(all_paths), 900):
                chunk = all_paths[i:i+900]
                placeholders = ','.join(['?']*len(chunk))
                cur.execute(f"SELECT id, file_path FROM books WHERE file_path IN ({placeholders})", chunk)
                for row in cur.fetchall():
                    path_to_id[row['file_path']] = row['id']
            
            offsets_to_save = []
            for d in upd_list + ins_list:
                if d.get('offsets_data'):
                    bid = path_to_id.get(d['full_path'])
                    if bid:
                        for off in d['offsets_data']:
                            offsets_to_save.append((bid, *off))
                            
            if offsets_to_save:
                bulk_save_book_offsets(cur, offsets_to_save)

    pending_inserts = []
    pending_updates = []
    pending_folders = []

    def flush_pending_data():
        if not pending_inserts and not pending_updates and not pending_folders:
            return
        
        try:
            # 1. DB Bulk Update
            if pending_inserts or pending_updates:
                process_batch(cursor, pending_inserts, pending_updates)
            
            # 2. Scanner Progress Update
            for pf in pending_folders:
                cursor.execute("INSERT OR IGNORE INTO scanner_progress (library_id, folder_path) VALUES (?, ?)", (str(library_id), pf['root']))
                if pf.get('dir_mtime') is not None:
                    cursor.execute("INSERT OR REPLACE INTO folder_mtimes (folder_path, dir_mtime, meta_mtime) VALUES (?, ?, ?)", (pf['root'], pf['dir_mtime'], pf['meta_mtime']))
            
            # 3. Commit ALL at once (Atomic Transaction)
            conn.commit()
            import time
            time.sleep(0.05)  # 대시보드 측 DB 락 선점을 돕기 위해 미세 양보(micro-yield)

            # 4. Append to JSONL log
            if pending_inserts or pending_updates:
                with file_lock:
                    with open(scan_temp_file, 'a', encoding='utf-8') as f:
                        for item in pending_inserts:
                            f.write(json.dumps(item, ensure_ascii=False) + '\n')
                        for item in pending_updates:
                            f.write(json.dumps(item, ensure_ascii=False) + '\n')

        except Exception as e:
            print(f"[Scanner ERROR] Flush failed: {e}")
        finally:
            pending_inserts.clear()
            pending_updates.clear()
            pending_folders.clear()

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
            executor.submit(process_folder_task, root, files, force, db_meta_full, db_offsets_cached, db_folder_mtimes, is_remote, library_id, db_files_cache): root
            for root, files in tasks
        }
        
        for fut in as_completed(futures):
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
                            print(f"[Scanner-Process] Found new book: {filename} (Series: {series_name})")
                        batch_item_count += 1
                    
                    if batch_item_count > 0:
                        # ── [GIL Throttling] ──
                        import time
                        time.sleep(0.01 * min(batch_item_count, 5))
                        
                    del res
                
                pending_folders.append({
                    'root': root_folder,
                    'dir_mtime': dir_mtime,
                    'meta_mtime': meta_mtime
                })
                processed_folders_count += 1
                
                # Hybrid Flush Trigger
                if (len(pending_inserts) + len(pending_updates) >= 100) or len(pending_folders) >= 50:
                    flush_pending_data()

                if processed_folders_count % 50 == 0:
                    gc.collect()

                # Detect manual cancel (abort) request and exit
                # [버그수정] 장기 conn은 WAL 스냅샷 격리로 인해 다른 세션의 COMMIT을 읽지 못함.
                # 취소 상태 확인만 독립 커넥션으로 조회하여 항상 최신 상태를 반영한다.
                status_row = None
                try:
                    _cancel_conn = database.get_connection(db_type)
                    _cancel_cur = _cancel_conn.cursor()
                    _cancel_cur.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
                    status_row = _cancel_cur.fetchone()
                    _cancel_conn.close()
                except Exception as _e:
                    print(f"[Scanner-Cancel] ⚠️ 취소 상태 확인 중 오류 (무시하고 계속 진행): {_e}")
                if status_row and status_row['scan_status'] == 'cancelling':
                    print(f"[Scanner-Cancel] 🛑 Safely aborting scan due to user request. (Completed folders: {processed_folders_count} folders)")
                    flush_pending_data()
                    cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE id = ?", (library_id,))
                    conn.commit()
                    conn.close()
                    cleanup_jsonl_file()
                    return

                # Self-exit for real-time OOM prevention
                if check_memory_exceeded():
                    print(f"[Scanner-Memory] 🛑 Emergency pause due to memory limit. (Progress: {processed_folders_count} folders applied)")
                    flush_pending_data()
                    try:
                        conn.close()
                    except Exception:
                        pass
                    cleanup_jsonl_file()
                    os._exit(0)

            except Exception as e:
                print(f"[Scanner-DEBUG-Pool] ❌ Folder '{root_folder}' processing exception: {e}")

        # Final flush for any remaining data at the end of the loop
        flush_pending_data()
        cleanup_jsonl_file()


    # 3. Real-time deletion monitoring: Remove book info disappeared from file system
    if not handle_deleted_books(cursor, db_books, deleted_paths, target_paths, found_file_paths):
        conn.close()
        return
        
    # Initialize checkpoint of library upon successful completion
    cursor.execute("DELETE FROM scanner_progress WHERE library_id = ?", (str(library_id),))
    conn.commit()
    conn.close()
    gc.collect()

    # Save scan result error reports
    if library_errors:
        try:
            from utils.report_helper import save_scan_report
            save_scan_report(library_id, library_errors)
        except Exception as report_err:
            print(f"[Scanner ERROR] Scan report save failed: {report_err}")

    # Trigger database optimization tuning after scan
    import threading
    t = threading.Thread(target=database.optimize_database, args=(db_type,))
    t.daemon = True
    t.start()


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
            
    conn.commit()
    print(f"[Scanner-Covers] Cover-only scan finally completed! (total {processed_count} covers updated)")

