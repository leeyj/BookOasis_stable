# -*- coding: utf-8 -*-
import os
import sys

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

@scanner_print_control_decorator
def scan_library(db_path, library_id, physical_path, force=False, skip_vfs_refresh=False):
    """Scan library path and sync DB with file system (force full reindex if force=True)"""
    print(f"[Scanner] Scan started: Library ID={library_id}, Path='{physical_path}', Force={force}")
    
    library_errors = []
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        print(f"[Scanner] Warning: Scan path does not exist: {physical_path}")
        return

    if not skip_vfs_refresh:
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
