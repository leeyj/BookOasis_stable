# -*- coding: utf-8 -*-
import os
import urllib.request
import json
import database
from utils.drive_helper import is_remote_path, get_rclone_relative_path

def trigger_vfs_refresh(db_path, library_id, physical_path):
    """Refresh rclone cache before starting scan if remote mount path (VFS)."""
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    remote_paths = [p for p in target_paths if is_remote_path(p)]
    
    if not remote_paths:
        return
        
    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    print(f"[Scanner-VFS] Remote mount path detected: {remote_paths} - Checking cache status...")
    
    try:
        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT vfs_refresh_before_scan, rclone_rc_url FROM libraries WHERE id = ?", (library_id,))
            row = cursor.fetchone()
        except Exception as e:
            print(f"[Scanner-VFS Warning] Failed to fetch library info: {e}")
            return
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            
        if not row or row['vfs_refresh_before_scan'] != 1:
            return
            
        rc_urls = ["http://localhost:5572"]
        if row['rclone_rc_url'] and row['rclone_rc_url'].strip():
            rc_urls = [u.strip().rstrip('/') for u in str(row['rclone_rc_url']).split(',') if u.strip()]
        else:
            conn_s = None
            try:
                conn_s = database.get_connection(db_type)
                cursor_s = conn_s.cursor()
                cursor_s.execute("SELECT value FROM settings WHERE key = 'RCLONE_RC_URL'")
                row_s = cursor_s.fetchone()
                if row_s and row_s['value']:
                    rc_urls = [u.strip().rstrip('/') for u in str(row_s['value']).split(',') if u.strip()]
            except Exception:
                pass
            finally:
                if conn_s:
                    try:
                        conn_s.close()
                    except Exception:
                        pass
                
        for r_path in remote_paths:
            print(f"[Scanner-VFS] Starting VFS cache pre-refresh. Target: {r_path}")
            rel_path = get_rclone_relative_path(r_path)
            
            for rc_url in rc_urls:
                full_url = f"{rc_url}/vfs/refresh"
                req_data = json.dumps({"dir": rel_path}).encode('utf-8')
                req = urllib.request.Request(
                    full_url, 
                    data=req_data,
                    headers={'Content-Type': 'application/json'}
                )
                try:
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        print(f"[Scanner-VFS] VFS cache refresh success - Server: '{rc_url}', Target: '{rel_path}', Result: {resp.read().decode('utf-8')}")
                except Exception as e:
                    print(f"[Scanner-VFS Warning] Server '{rc_url}' path '{rel_path}' refresh attempt ignored or failed: {e}")
    except Exception as e:
        print(f"[Scanner-VFS Warning] VFS cache refresh process failed: {e}")

    print("=== Scanner Task Complete ===")
