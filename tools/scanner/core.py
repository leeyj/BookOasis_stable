# -*- coding: utf-8 -*-
import os
import sys
import time

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import gc
import database
from tools.scanner.logger import scanner_print_control_decorator
from tools.scanner.engine import _scan_library_internal, _scan_library_covers_only_internal, MAX_SCANNER_THREADS
from tools.scanner.sync_detector import detect_and_handle_book_movement, handle_deleted_books
from tools.scanner.vfs import trigger_vfs_refresh
from utils.drive_helper import is_remote_path

DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')
DB_GENERAL_PATH = os.path.join(DB_DIR, 'media_general.db')
DB_ADULT_PATH = os.path.join(DB_DIR, 'media_adult.db')


def _is_hdd_aggressive_warmup_enabled(db_type):
    conn = None
    try:
        conn = database.get_connection(db_type, wait_timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'HDD_AGGRESSIVE_WARMUP'")
        row = cursor.fetchone()
        return bool(row and str(row['value']).strip() == '1')
    except Exception as e:
        print(f"[Scanner-WakeUp] HDD 웜업 설정 조회 실패, 기본값(OFF) 사용: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _aggressive_warmup_path(path):
    start_ts = time.perf_counter()
    warmed_entries = 0
    try:
        first_dir = None
        with os.scandir(path) as it:
            for idx, entry in enumerate(it):
                try:
                    entry.stat(follow_symlinks=False)
                    warmed_entries += 1
                except Exception:
                    pass
                if first_dir is None:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            first_dir = entry.path
                    except Exception:
                        pass
                if idx >= 19:
                    break

        if first_dir and os.path.exists(first_dir):
            with os.scandir(first_dir) as child_it:
                for j, child in enumerate(child_it):
                    try:
                        child.stat(follow_symlinks=False)
                        warmed_entries += 1
                    except Exception:
                        pass
                    if j >= 9:
                        break

        elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
        print(f"[Scanner-WakeUp] 적극 웜업 완료: path='{path}', touched={warmed_entries}, elapsed={elapsed_ms:.1f}ms")
    except Exception as e:
        print(f"[Scanner-WakeUp] 적극 웜업 중 예외(무시): {e}")

@scanner_print_control_decorator
def scan_library(db_path, library_id, physical_path, force=False, skip_vfs_refresh=False):
    """Scan library path and sync DB with file system (force full reindex if force=True)"""
    print(f"[Scanner] Scan started: Library ID={library_id}, Path='{physical_path}', Force={force}")
    
    library_errors = []
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        raise ValueError("스캔 경로 정보가 입력되지 않았습니다.")

    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    is_remote = any(is_remote_path(p) for p in target_paths)
    hdd_aggressive_warmup = _is_hdd_aggressive_warmup_enabled(db_type)
    use_aggressive_warmup = bool(hdd_aggressive_warmup and not is_remote)
    max_attempts = 6 if use_aggressive_warmup else 3
    retry_delay_sec = 3.0 if use_aggressive_warmup else 1.0

    print(f"[Scanner-WakeUp] mode={'aggressive' if use_aggressive_warmup else 'normal'} (remote={is_remote}, setting={hdd_aggressive_warmup})")

    # ── [HDD/NAS Wake-up & Path Validation] ──
    failed_paths = []
    
    for path in target_paths:
        path_accessible = False
        last_error_msg = ""
        for attempt in range(1, max_attempts + 1):
            try:
                # os.path.exists()를 트리거하여 하드디스크 스핀업(Spin-up) 및 네트워크 세션 연결 유도
                if os.path.exists(path):
                    path_accessible = True
                    if use_aggressive_warmup:
                        _aggressive_warmup_path(path)
                    break
                else:
                    last_error_msg = "경로를 찾을 수 없거나 마운트 해제 상태입니다."
            except Exception as e:
                last_error_msg = str(e)
            
            print(f"[Scanner-WakeUp] '{path}' 접근 준비 지연 (시도 {attempt}/{max_attempts}). {retry_delay_sec:.1f}초 후 재시도... 사유: {last_error_msg}")
            time.sleep(retry_delay_sec)
            
        if not path_accessible:
            failed_paths.append((path, last_error_msg))

    if failed_paths:
        err_details = [f"'{p}' (사유: {msg})" for p, msg in failed_paths]
        err_msg = f"스캔 대상 경로 접근 실패 (HDD/NAS Wake-up 실패): " + ", ".join(err_details)
        print(f"[Scanner-WakeUp ERROR] {err_msg}")
        raise FileNotFoundError(err_msg)

    if not skip_vfs_refresh:
        trigger_vfs_refresh(db_path, library_id, physical_path)

    threads_to_use = 1 if is_remote else MAX_SCANNER_THREADS

    if is_remote:
        print(f"[Scanner-VFS] Remote mount path detected. Serializing scan threads({threads_to_use} folders), Skipping heavy archive I/O analysis.")

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

def run_sync_scanner():
    """Iterate all databases (general, adult) libraries and execute scan"""
    print("=== File System Sync Scanner Started ===")
    
    if os.path.exists(DB_GENERAL_PATH):
        conn = None
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, physical_path FROM libraries")
            libs = cursor.fetchall()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        for lib in libs:
            scan_library(DB_GENERAL_PATH, lib['id'], lib['physical_path'])
            
    if os.path.exists(DB_ADULT_PATH):
        conn = None
        try:
            conn = database.get_connection('adult')
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, physical_path FROM libraries")
            libs = cursor.fetchall()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        for lib in libs:
            scan_library(DB_ADULT_PATH, lib['id'], lib['physical_path'])
