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
DB_AUDIOBOOK_PATH = os.path.join(DB_DIR, 'media_audiobook.db')
DB_VIDEO_PATH = os.path.join(DB_DIR, 'media_video.db')


def _is_hdd_aggressive_warmup_enabled(db_type):
    try:
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value(db_type, 'HDD_AGGRESSIVE_WARMUP')
        return bool(val and str(val).strip() == '1')
    except Exception as e:
        print(f"[Scanner-WakeUp] HDD 웜업 설정 조회 실패, 기본값(OFF) 사용: {e}")
        return False


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

def _run_db_self_recovery(db_type):
    import subprocess
    import sqlite3
    db_file_name = f"media_{db_type}.db"
    db_full_path = os.path.join(DB_DIR, db_file_name)
    recovery_script = os.path.join(MEDIA_SERVER_DIR, 'tools', 'db_recovery.py')
    print(f"[Scanner-SelfHealing] 🚨 Running db_recovery.py for {db_full_path}...")
    try:
        res = subprocess.run([sys.executable, recovery_script, '--db', db_full_path, '--yes'], capture_output=True, text=True, timeout=300)
        print(f"[Scanner-SelfHealing] Recovery exit code: {res.returncode}")
        if res.stdout:
            print(f"[Scanner-SelfHealing] Output:\n{res.stdout}")
    except Exception as rec_err:
        print(f"[Scanner-SelfHealing ERROR] Auto recovery failed: {rec_err}")

@scanner_print_control_decorator
def scan_library(db_path, library_id, physical_path, force=False, skip_vfs_refresh=False):
    """Scan library path and sync DB with file system (force full reindex if force=True)"""
    print(f"🚀🚀🚀 [ScannerEngine] Core scan_library EXECUTING! DB Path={db_path}, Library ID={library_id}, Path='{physical_path}', Force={force}")
    
    library_errors = []
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        raise ValueError("스캔 경로 정보가 입력되지 않았습니다.")

    db_type = (
        'audiobook' if 'audiobook' in os.path.basename(db_path) else
        'video' if 'video' in os.path.basename(db_path) else
        'adult' if 'adult' in os.path.basename(db_path) else
        'general'
    )
    is_remote = any(is_remote_path(p) for p in target_paths)
    hdd_aggressive_warmup = _is_hdd_aggressive_warmup_enabled(db_type)
    use_aggressive_warmup = bool(hdd_aggressive_warmup and not is_remote)
    max_attempts = 6 if use_aggressive_warmup else 3
    retry_delay_sec = 3.0 if use_aggressive_warmup else 1.0

    print(f"[Scanner-WakeUp] db_type={db_type}, mode={'aggressive' if use_aggressive_warmup else 'normal'} (remote={is_remote}, setting={hdd_aggressive_warmup})")

    # ── [HDD/NAS Wake-up & Path Validation] ──
    from utils.drive_helper import is_gdrive_url
    failed_paths = []
    
    for path in target_paths:
        if is_gdrive_url(path):
            print(f"[Scanner-WakeUp] 구글 드라이브 웹 공유 링크 감지: '{path}'. 로컬 디스크 Wake-up 검사를 우회합니다.")
            continue

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

    if db_type == 'audiobook':
        print(f"[Scanner-Audiobook] 🎧 Triggering audiobook dedicated scanner pipeline for library_id={library_id}...")
        from services.audiobook_scanner import scan_audiobook_library
        for target_p in target_paths:
            scan_audiobook_library(target_p, library_id=library_id, force=force)
        print(f"[Scanner-Audiobook] 🎧 Audiobook scan completed for library_id={library_id}")
        return

    if db_type == 'video':
        print(f"[Scanner-Video] 🎬 Triggering video dedicated scanner pipeline for library_id={library_id}...")
        from services.video_scanner import scan_video_library
        for target_p in target_paths:
            scan_video_library(target_p, library_id=library_id, force=force)
        print(f"[Scanner-Video] 🎬 Video scan completed for library_id={library_id}")
        return

    threads_to_use = 1 if is_remote else MAX_SCANNER_THREADS

    if is_remote:
        print(f"[Scanner-VFS] Remote mount path detected. Serializing scan threads({threads_to_use} folders), Skipping heavy archive I/O analysis.")

    # ── [Self-Healing: 사전 DB 무결성 점검 및 손상 감지 시 자동 복구] ──
    try:
        engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
        if engine not in ('mariadb', 'mysql'):
            check_conn = database.get_connection(db_type, wait_timeout=5.0)
            try:
                check_cur = check_conn.cursor()
                res = check_cur.execute("PRAGMA integrity_check;").fetchone()
                if not res or str(res[0]).lower() != 'ok':
                    print(f"[Scanner-SelfHealing] ⚠️ 무결성 이상 감지 ({res}). 자동 복구(db_recovery.py)를 가동합니다.")
                    check_conn.close()
                    _run_db_self_recovery(db_type)
                else:
                    check_conn.close()
            except Exception as db_malformed_err:
                print(f"[Scanner-SelfHealing] ⚠️ DB 손상 감지 ({db_malformed_err}). 자동 복구(db_recovery.py)를 가동합니다.")
                try:
                    check_conn.close()
                except Exception:
                    pass
                _run_db_self_recovery(db_type)
    except Exception as check_err:
        print(f"[Scanner-SelfHealing] 사전 무결성 점검 경고 (무시하고 계속): {check_err}")

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

@scanner_print_control_decorator
def scan_library_path(db_path, library_id, target_path, force=False, skip_vfs_refresh=False):
    """Scan a single book/series subfolder within a library and register just those books
    (used by the 'add one book/series then scan it in' API, as opposed to a full periodic scan)."""
    print(f"🎯 [ScannerEngine] Single-path scan EXECUTING! DB Path={db_path}, Library ID={library_id}, Target='{target_path}', Force={force}")

    library_errors = []
    target_path = str(target_path).strip()
    if not target_path:
        raise ValueError("스캔 경로가 입력되지 않았습니다.")

    db_type = (
        'audiobook' if 'audiobook' in os.path.basename(db_path) else
        'video' if 'video' in os.path.basename(db_path) else
        'adult' if 'adult' in os.path.basename(db_path) else
        'general'
    )

    from utils.drive_helper import is_gdrive_url
    is_gdrive = is_gdrive_url(target_path)
    is_remote = is_remote_path(target_path)

    if not is_gdrive and not os.path.exists(target_path):
        raise FileNotFoundError(f"스캔 대상 경로를 찾을 수 없습니다: {target_path}")

    if not skip_vfs_refresh:
        trigger_vfs_refresh(db_path, library_id, target_path)

    if db_type == 'audiobook':
        print(f"[Scanner-Audiobook] 🎧 Triggering audiobook single-path scan for library_id={library_id}, path='{target_path}'...")
        from services.audiobook_scanner import scan_audiobook_library
        scan_audiobook_library(target_path, library_id=library_id, force=force)
        print(f"[Scanner-Audiobook] 🎧 Audiobook single-path scan completed for library_id={library_id}")
        return

    if db_type == 'video':
        print(f"[Scanner-Video] 🎬 Triggering video single-path scan for library_id={library_id}, path='{target_path}'...")
        from services.video_scanner import scan_video_library
        scan_video_library(target_path, library_id=library_id, force=force)
        print(f"[Scanner-Video] 🎬 Video single-path scan completed for library_id={library_id}")
        return

    threads_to_use = 1 if is_remote else MAX_SCANNER_THREADS

    conn = database.get_connection(db_type)
    try:
        from tools.scanner.path_utils import canonical_path
        _scan_library_internal(
            conn, db_path, library_id, target_path, force, db_type,
            [target_path], is_remote, threads_to_use, library_errors,
            path_scope=canonical_path(target_path)
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass
        gc.collect()

    if library_errors:
        try:
            from utils.report_helper import save_scan_report
            save_scan_report(library_id, library_errors)
        except Exception as report_err:
            print(f"[Scanner ERROR] Scan report save failed: {report_err}")


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
    
    from repositories.category_repository import CategoryRepository
    if os.path.exists(DB_GENERAL_PATH):
        libs = CategoryRepository.get_all_libraries('general')
        for lib in libs:
            scan_library(DB_GENERAL_PATH, lib['id'], lib['physical_path'])
            
    if os.path.exists(DB_ADULT_PATH):
        libs = CategoryRepository.get_all_libraries('adult')
        for lib in libs:
            scan_library(DB_ADULT_PATH, lib['id'], lib['physical_path'])

    if os.path.exists(DB_AUDIOBOOK_PATH):
        libs = CategoryRepository.get_all_libraries('audiobook')
        for lib in libs:
            scan_library(DB_AUDIOBOOK_PATH, lib['id'], lib['physical_path'])

    if os.path.exists(DB_VIDEO_PATH):
        libs = CategoryRepository.get_all_libraries('video')
        for lib in libs:
            scan_library(DB_VIDEO_PATH, lib['id'], lib['physical_path'])
