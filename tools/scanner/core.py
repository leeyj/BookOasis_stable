# -*- coding: utf-8 -*-
import os
import sys
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root path to sys.path to prevent package import errors
MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import database
from tools.scanner.parser import parse_info_xml, parse_kavita_yaml, parse_series_json, parse_comicinfo_from_cbz, is_consonant_folder
from tools.scanner.cover import get_series_cover_fallback, extract_cover_from_b64, download_cover_from_url
from tools.scanner.offset import collect_zip_offsets_data
from tools.scanner.vfs import trigger_vfs_refresh
from utils.drive_helper import is_remote_path

import builtins
from contextlib import contextmanager

@contextmanager
def scanner_print_control(db_path):
    original_print = builtins.print
    write_log = True
    conn = None
    try:
        db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'SCANNER_WRITE_LOG'")
        row = cursor.fetchone()
        if row:
            value = str(row['value']).strip()
            if value == '0':
                write_log = False
    except Exception:
        pass
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    if not write_log:
        builtins.print = lambda *args, **kwargs: None
    else:
        import datetime
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'scanner.log')
        
        def custom_print(*args, **kwargs):
            try:
                sep = kwargs.get('sep', ' ')
                end = kwargs.get('end', '\n')
                message = sep.join(map(str, args)) + end
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                formatted_message = f"[{timestamp}] {message}"
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(formatted_message)
            except Exception:
                pass
        builtins.print = custom_print
        
    try:
        yield
    finally:
        builtins.print = original_print

def scanner_print_control_decorator(func):
    def wrapper(db_path, *args, **kwargs):
        ctx = scanner_print_control(db_path)
        ctx.__enter__()
        try:
            return func(db_path, *args, **kwargs)
        finally:
            ctx.__exit__(None, None, None)
    return wrapper

# Path configuration
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')
DB_GENERAL_PATH = os.path.join(DB_DIR, 'media_general.db')
DB_ADULT_PATH = os.path.join(DB_DIR, 'media_adult.db')

SUPPORTED_FORMATS = ('.zip', '.cbz', '.epub', '.pdf', '.txt')
MAX_SCANNER_THREADS = 4

from tools.scanner.memory_helper import check_memory_exceeded
from tools.scanner.db_writer import update_book_metadata, insert_new_book_v2, save_book_offsets
from tools.scanner.sync_detector import detect_and_handle_book_movement, handle_deleted_books

def process_folder_task(root, files, force, db_meta_full, db_offsets_cached, is_remote=False, library_id=None):
    """Independent I/O scan task per folder (DB independent, pure FS/I/O scaling)"""
    print(f"[Scanner-DEBUG-Task] 📂 entering process_folder_task - folder: '{root}'")
    
    media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
    if not media_files:
        print(f"[Scanner-DEBUG-Task] 📁 Unsupported folder (skip) - folder: '{root}'")
        return None

    # 1. Pre-check if metadata file exists
    has_yaml = any(f.lower() == 'kavita.yaml' for f in files)
    has_xml = any(f.lower() == 'info.xml' for f in files)
    
    # 2. Early skip if fully cached and no metadata file exists (non-force scan)
    if not force and not has_yaml and not has_xml:
        all_cached = True
        for filename in media_files:
            full_path = os.path.join(root, filename)
            if full_path not in db_meta_full or full_path not in db_offsets_cached:
                all_cached = False
                break
        if all_cached:
            print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files cached and metadata irrelevant - folder: '{root}'")
            return None

    path_parts = os.path.normpath(root).split(os.sep)
    series_name = ""
    for i in range(len(path_parts) - 1):
        if is_consonant_folder(path_parts[i]):
            series_name = path_parts[i+1]
            break
    if not series_name and len(path_parts) > 0:
        series_name = path_parts[-1]

    print(f"[Scanner-DEBUG-Task]   - Metadata YAML/XML/JSON load started")
    yaml_meta = parse_kavita_yaml(root, files=files)
    xml_meta = parse_info_xml(root, files=files)
    json_meta = parse_series_json(root, files=files)
    print(f"[Scanner-DEBUG-Task]   - Metadata load completed")

    merged_meta = {
        'author': xml_meta['author'] or yaml_meta['author'] or json_meta['author'] or '',
        'publisher': xml_meta['publisher'] or yaml_meta['publisher'] or '',
        'summary': xml_meta['summary'] or yaml_meta['summary'] or json_meta['summary'] or '',
        'link': yaml_meta['link'] or '',
        'score': yaml_meta['score'] or 0,
        'release_date': xml_meta['release_date'] or '',
        'genre': xml_meta.get('genre', '') or yaml_meta.get('genre', '') or '',
        'tags': xml_meta.get('tags', '') or yaml_meta.get('tags', '') or '',
        'cover_b64_map': yaml_meta['cover_b64_map'] or {}
    }

    meta_has_data = bool(
        merged_meta['author'] or merged_meta['publisher'] or
        merged_meta['summary'] or merged_meta['release_date'] or
        merged_meta['cover_b64_map']
    )

    is_series_folder = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    is_json_only_webtoon = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    series_cover_url = json_meta.get('cover_image_url', '') if is_json_only_webtoon else ''
    shared_cover_image = None

    import zipfile
    results = []
    errors = []
    for filename in media_files:
        full_path = os.path.join(root, filename)
        _, ext = os.path.splitext(filename)
        file_format = ext.replace('.', '').lower()

        skip = False
        if not force and not meta_has_data and full_path in db_meta_full and full_path in db_offsets_cached:
            skip = True

        cover_image = None
        offsets_data = []
        offset_only = False  # Cover/meta complete, offset-only fast path flag

        if skip:
            pass  # Fully cached book — skip all processing

        elif (
            not force and
            not meta_has_data and
            full_path in db_meta_full and
            full_path not in db_offsets_cached and
            file_format in ('zip', 'cbz') and
            not is_remote
        ):
            # ── [Offset-only Fast Path] ──
            # If existing book has cover/meta but no offset:
            # Completely skip ComicInfo parsing and cover extraction pipeline
            # Only read ZIP central directory (collect offsets) - Minimize I/O
            offset_only = True
            try:
                offsets_data = collect_zip_offsets_data(full_path)
                if offsets_data:
                    print(f"[Scanner-DEBUG-Task] ⚡ [Offset-only] '{filename}' ({len(offsets_data)}p)")
                else:
                    print(f"[Scanner-DEBUG-Task] ⚡ [Offset-only] Skip ZIP without images: '{filename}'")
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ Offset-only collection failed: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'OffsetError',
                    'message': f"Offset-only collection failed: {str(e)}"
                })

        else:
            # ── [General Path] Cover extraction + Offset collection ──
            print(f"[Scanner-DEBUG-Task]   - File processing started: '{filename}'")
            try:
                # [ComicInfo.xml parsing] If local file and CBZ format, extract metadata internally
                # Skip remote paths due to high I/O cost -> delegated to Lazy Scanner
                if not is_remote and file_format in ('cbz', 'zip') and (
                    not merged_meta['author'] or not merged_meta['summary'] or not merged_meta.get('genre') or not merged_meta.get('tags')
                ):
                    try:
                        comicinfo = parse_comicinfo_from_cbz(full_path)
                        if comicinfo['author'] and not merged_meta['author']:
                            merged_meta['author'] = comicinfo['author']
                            print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml author fallback: {comicinfo['author']}")
                        if comicinfo['publisher'] and not merged_meta['publisher']:
                            merged_meta['publisher'] = comicinfo['publisher']
                        if comicinfo['summary'] and not merged_meta['summary']:
                            merged_meta['summary'] = comicinfo['summary']
                        if comicinfo['release_date'] and not merged_meta['release_date']:
                            merged_meta['release_date'] = comicinfo['release_date']
                        if comicinfo.get('genre') and not merged_meta.get('genre'):
                            merged_meta['genre'] = comicinfo['genre']
                        if comicinfo.get('tags') and not merged_meta.get('tags'):
                            merged_meta['tags'] = comicinfo['tags']
                    except Exception as ce:
                        print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml parsing skipped: {ce}")

                # Convert keys to lowercase to prevent case issues in Linux
                filename_lower = filename.lower()
                b64_keys_lower = {k.lower(): v for k, v in merged_meta['cover_b64_map'].items()}
                
                if filename_lower in b64_keys_lower:
                    print(f"[Scanner-DEBUG-Task]     - YAML b64 cover decoding started")
                    cover_image = extract_cover_from_b64(full_path, b64_keys_lower[filename_lower], force=force, library_id=library_id)
                
                if not cover_image:
                    if (is_series_folder or is_json_only_webtoon) and shared_cover_image:
                        print(f"[Scanner-DEBUG-Task]     - Series cover (thumbnail) cloned")
                        cover_image = shared_cover_image
                    elif is_json_only_webtoon and series_cover_url:
                        print(f"[Scanner-DEBUG-Task]     - series.json URL cover download started")
                        cover_image = download_cover_from_url(full_path, series_cover_url, force=force, library_id=library_id)
                    else:
                        print(f"[Scanner-DEBUG-Task]     - Fallback cover extraction started")
                        cover_image = get_series_cover_fallback(series_name, root, force=force, is_remote=is_remote, filename=filename, file_path=full_path, library_id=library_id)
                
                # Save first successful cover as shared thumbnail for series folder regardless of source
                if (is_series_folder or is_json_only_webtoon) and cover_image and not shared_cover_image:
                    shared_cover_image = cover_image

                # Real-time check if extracted cover is 0 bytes
                if cover_image:
                    cover_filepath = os.path.join(MEDIA_SERVER_DIR, 'covers', cover_image)
                    if os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) == 0:
                        print(f"[Scanner-DEBUG-Task] ⚠️ Extracted cover file is 0 bytes: {cover_filepath}")
                        try:
                            os.remove(cover_filepath)
                        except Exception:
                            pass
                        cover_image = None  # Invalidate to include in error report collection
                
                # Log to error list if Zip/EPUB format but no cover acquired
                if not cover_image and file_format in ('zip', 'cbz', 'epub'):
                    errors.append({
                        'file_path': full_path,
                        'filename': filename,
                        'error_type': 'NoCover',
                        'message': 'ERR_NO_COVER'
                    })
            except zipfile.BadZipFile as bzf:
                print(f"[Scanner-DEBUG-Task] ❌ BadZipFile detected: '{filename}' - {bzf}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'BadZipFile',
                    'message': str(bzf)
                })
            except ValueError as ve:
                print(f"[Scanner-DEBUG-Task] ❌ ValueError detected: '{filename}' - {ve}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'NoCover',
                    'message': str(ve)
                })
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ General exception detected: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'Exception',
                    'message': str(e)
                })

            try:
                if file_format in ('zip', 'cbz') and (force or full_path not in db_offsets_cached):
                    if is_remote:
                        offsets_data = []
                    else:
                        print(f"[Scanner-DEBUG-Task]     - Offset analysis started: '{filename}'")
                        offsets_data = collect_zip_offsets_data(full_path)
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ Offset analysis failed: '{filename}' - {e}")
                if not any(err['file_path'] == full_path for err in errors):
                    errors.append({
                        'file_path': full_path,
                        'filename': filename,
                        'error_type': 'OffsetAnalysis',
                        'message': f"ERR_OFFSET_FAIL: {str(e)}"
                    })
            print(f"[Scanner-DEBUG-Task]   - File processing completed: '{filename}'")

        results.append({
            'full_path': full_path,
            'filename': filename,
            'file_format': file_format,
            'series_name': series_name,
            'cover_image': cover_image,
            'offsets_data': offsets_data,
            'skip': skip,
            'offset_only': offset_only,  # Whether it's offset-only fast path
        })

    # Clear references to large base64 maps used to free memory
    merged_meta.pop('cover_b64_map', None)

    gc.collect()
    print(f"[Scanner-DEBUG-Task] 📁 process_folder_task completed - folder: '{root}'")
    return {
        'root': root,
        'merged_meta': merged_meta,
        'results': results,
        'errors': errors
    }

@scanner_print_control_decorator
def scan_library(db_path, library_id, physical_path, force=False):
    """Scan library path and sync DB with file system (force full reindex if force=True)"""
    print(f"[Scanner] Scan started: Library ID={library_id}, Path='{physical_path}', Force={force}")
    
    library_errors = []
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        print(f"[Scanner] Warning: Scan path does not exist: {physical_path}")
        return

    trigger_vfs_refresh(db_path, library_id, physical_path)
    
    is_remote = any(is_remote_path(p) for p in target_paths)
    threads_to_use = 1 if is_remote else MAX_SCANNER_THREADS

    if is_remote:
        print(f"[Scanner-VFS] Remote mount path detected. Serializing scan threads({threads_to_use} folders), Skipping heavy archive I/O analysis.")

    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    conn = database.get_connection(db_type)
    try:
        _scan_library_internal(conn, db_path, library_id, physical_path, force, db_type, target_paths, is_remote, threads_to_use, library_errors)
    finally:
        try:
            conn.close()
        except Exception:
            pass
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

def _scan_library_internal(conn, db_path, library_id, physical_path, force, db_type, target_paths, is_remote, threads_to_use, library_errors):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_path, has_offsets,
               cover_image, author, publisher, summary
        FROM books WHERE library_id = ?
    """, (library_id,))
    all_rows = cursor.fetchall()
    db_books = {}          
    db_meta_full = set()   
    db_offsets_cached = set() 
    for row in all_rows:
        db_books[row['file_path']] = row['id']
        if row['has_offsets'] == 1:
            db_offsets_cached.add(row['file_path'])
        if (row['cover_image'] and not row['cover_image'].startswith('series_') and
                row['author'] and row['publisher'] and row['summary']):
            db_meta_full.add(row['file_path'])

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
            if not media_files:
                continue
            for f in media_files:
                found_file_paths.add(os.path.join(root, f))
            
            if root in scanned_folders:
                continue
                
            tasks.append((root, files))

    # ── [Book movement detection and history preservation layer - pre-process before thread execution] ──
    deleted_paths = detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached)
    conn.commit()

    # 2. Run thread pool and streaming process (as_completed)
    print(f"[Scanner] Multithread scan pool created (threads: {threads_to_use})")
    
    processed_folders_count = 0
    uncommitted_count = 0
    processed_books_count = 0

    with ThreadPoolExecutor(max_workers=threads_to_use) as executor:
        futures = {
            executor.submit(process_folder_task, root, files, force, db_meta_full, db_offsets_cached, is_remote, library_id): root
            for root, files in tasks
        }
        
        for fut in as_completed(futures):
            root_folder = futures[fut]
            try:
                res = fut.result()
                if res:
                    merged_meta = res['merged_meta']
                    if 'errors' in res and res['errors']:
                        library_errors.extend(res['errors'])
                    for item in res['results']:
                        full_path = item['full_path']
                        if item['skip']:
                            continue

                        filename = item['filename']
                        file_format = item['file_format']
                        series_name = item['series_name']
                        cover_image = item['cover_image']
                        offsets_data = item['offsets_data']
                        is_offset_only = item.get('offset_only', False)

                        db_action_taken = False
                        if full_path in db_books:
                            book_id = db_books[full_path]
                            if is_offset_only:
                                # Offset-only path: Save offset without touching cover/meta
                                if offsets_data:
                                    save_book_offsets(cursor, book_id, filename, offsets_data)
                                    db_action_taken = True
                            else:
                                # General path: Update cover/meta + Save offset
                                print(f"[Scanner-Process] Book check progress: {filename} (Force={force})")
                                update_book_metadata(cursor, full_path, cover_image, merged_meta)
                                db_action_taken = True
                                if offsets_data:
                                    save_book_offsets(cursor, book_id, filename, offsets_data)
                        else:
                            # Register new book (cannot be offset_only case)
                            book_id = insert_new_book_v2(cursor, library_id, full_path, filename, file_format, series_name, cover_image, merged_meta)
                            print(f"[Scanner] New book registered: {filename} (Series: {series_name})")
                            db_action_taken = True
                            if offsets_data:
                                save_book_offsets(cursor, book_id, filename, offsets_data)

                        if db_action_taken:
                            uncommitted_count += 1
                            processed_books_count += 1
                            
                            # Intermediate commit per 30 books (Prevent SQLite memory bloat and long lock holds)
                            if uncommitted_count >= 30:
                                conn.commit()
                                uncommitted_count = 0

                            # Provide gap for web load bottleneck during scan (Throttling) (Throttling)
                            import time
                            time.sleep(0.05)

                            # Force memory release per 50 books
                            if processed_books_count % 50 == 0:
                                gc.collect()

                    # Release memory and save checkpoint immediately
                    del res
                
                cursor.execute("INSERT OR IGNORE INTO scanner_progress (library_id, folder_path) VALUES (?, ?)", (str(library_id), root_folder))
                conn.commit()
                uncommitted_count = 0
                
                processed_folders_count += 1
                if processed_folders_count % 10 == 0:
                    gc.collect()

                # Detect manual cancel (abort) request and exit
                cursor.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
                status_row = cursor.fetchone()
                if status_row and status_row['scan_status'] == 'cancelling':
                    print(f"[Scanner-Cancel] 🛑 Safely aborting scan due to user request. (Completed folders: {processed_folders_count} folders)")
                    cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE id = ?", (library_id,))
                    conn.commit()
                    conn.close()
                    return

                # Self-exit for real-time OOM prevention
                if check_memory_exceeded():
                    print(f"[Scanner-Memory] 🛑 Emergency pause due to memory limit. (Progress: {processed_folders_count} folders applied)")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    os._exit(0)

            except Exception as e:
                print(f"[Scanner-DEBUG-Pool] ❌ Folder '{root_folder}' processing exception: {e}")

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

@scanner_print_control_decorator
def scan_library_covers_only(db_path, library_id, physical_path):
    """Force re-extract/regenerate only covers of existing books in library path and sync (skip offset/meta)"""
    print(f"[Scanner-Covers] Cover-only Scan started: Library ID={library_id}, Path='{physical_path}'")
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        print(f"[Scanner-Covers] Warning: Scan path does not exist: {physical_path}")
        return

    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    conn = database.get_connection(db_type)
    try:
        _scan_library_covers_only_internal(conn, db_path, library_id, physical_path, target_paths, db_type)
    finally:
        try:
            conn.close()
        except Exception:
            pass

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

    def process_folder_covers(parent_dir, folder_rows):
        """Extract covers by folder. Share to rest if first book succeeds."""
        yaml_meta = parse_kavita_yaml(parent_dir)
        json_meta = parse_series_json(parent_dir)
        
        is_series = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
        is_json_only = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
        series_cover_url = json_meta.get('cover_image_url', '') if is_json_only else ''
        b64_keys_lower = {k.lower(): v for k, v in yaml_meta.get('cover_b64_map', {}).items()}
        
        shared_cover = None
        results = []
        
        for row in folder_rows:
            book_id = row['id']
            file_path = row['file_path']
            filename = os.path.basename(file_path)
            series_name = row['series_name']
            
            file_exists = os.path.exists(file_path)
            
            cover_image = None
            filename_lower = filename.lower()
            
            # 1) kavita.yaml Base64 cover - no actual file access needed, remote files supported
            if filename_lower in b64_keys_lower:
                cover_image = extract_cover_from_b64(file_path, b64_keys_lower[filename_lower], force=True, library_id=library_id)
            
            # 2) Reuse already shared cover (if series folder) - no file access needed
            if not cover_image and (is_series or is_json_only) and shared_cover:
                print(f"[Scanner-Covers] Series cover cloned: '{filename}'")
                cover_image = shared_cover
            
            # 3) series.json URL download - no actual file access needed, remote files supported
            if not cover_image and is_json_only and series_cover_url:
                cover_image = download_cover_from_url(file_path, series_cover_url, force=True, library_id=library_id)
            
            # 4) Fallback: first image in archive - requires file access, skip if none -> delegate to Lazy Scanner
            if not cover_image:
                if not file_exists:
                    print(f"[Scanner-Covers] Remote file unreachable -> Delegated to Lazy scanner: '{filename}'")
                else:
                    cover_image = get_series_cover_fallback(
                        series_name, parent_dir, force=True, is_remote=is_remote,
                        filename=filename, file_path=file_path, library_id=library_id
                    )

            
            # Cache upon first successful shared cover
            if (is_series or is_json_only) and cover_image and not shared_cover:
                shared_cover = cover_image
            
            if cover_image:
                results.append((book_id, cover_image))
        
        return results

    print(f"[Scanner-Covers] Folder-level cover extraction started (total {len(folder_groups)} folders, {len(rows)} books)")
    
    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_SCANNER_THREADS) as executor:
        futures = {
            executor.submit(process_folder_covers, parent_dir, folder_rows): parent_dir
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

def run_sync_scanner():
    """Iterate all databases (general, adult) libraries and execute scan"""
    print("=== File System Sync Scanner Started ===")
    
    if os.path.exists(DB_GENERAL_PATH):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path FROM libraries")
        libs = cursor.fetchall()
        conn.close()
        for lib in libs:
            scan_library(DB_GENERAL_PATH, lib['id'], lib['physical_path'])
            
    if os.path.exists(DB_ADULT_PATH):
        conn = database.get_connection('adult')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path FROM libraries")
        libs = cursor.fetchall()
        conn.close()
        for lib in libs:
            scan_library(DB_ADULT_PATH, lib['id'], lib['physical_path'])
