# -*- coding: utf-8 -*-
import os
import urllib.request
import urllib.error
import urllib.parse
import json
import base64
import time
import database
from utils.drive_helper import is_remote_path, get_rclone_refresh_dirs


def _is_connection_refused_error(err):
    reason = getattr(err, 'reason', err)
    if isinstance(reason, ConnectionRefusedError):
        return True
    errno = getattr(reason, 'errno', None)
    if errno in (111, 10061):
        return True
    return 'Connection refused' in str(reason)


def _is_vfs_refresh_success_response(res_text, rel_path):
    text = str(res_text or '').strip()
    lowered = text.lower()
    if not text:
        return False, 'empty response'
    if 'file does not exist' in lowered:
        return False, 'file does not exist'

    try:
        payload = json.loads(text)
    except Exception:
        return True, 'non-json success response'

    if isinstance(payload, dict) and payload.get('error'):
        return False, str(payload.get('error'))

    result = payload.get('result') if isinstance(payload, dict) else None
    if isinstance(result, dict):
        entry = result.get(rel_path)
        if isinstance(entry, str) and 'file does not exist' in entry.lower():
            return False, entry
        if rel_path in result:
            return True, str(entry)

    return True, 'ok'

def trigger_vfs_refresh(db_path, library_id, physical_path):
    """Refresh rclone cache before starting scan if remote mount path (VFS)."""
    target_paths_raw = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    target_paths = list(dict.fromkeys(target_paths_raw))
    remote_paths = list(dict.fromkeys([p for p in target_paths if is_remote_path(p)]))
    
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

        # Deduplicate RC URLs while preserving order
        rc_urls = list(dict.fromkeys(rc_urls))
                
        for r_path in remote_paths:
            print(f"[Scanner-VFS] Starting VFS cache pre-refresh. Target: {r_path}")
            rel_paths = get_rclone_refresh_dirs(r_path)

            refreshed = False
            for rel_idx, rel_path in enumerate(rel_paths, start=1):
                print(f"[Scanner-VFS] VFS refresh candidate path attempt: '{rel_path}' ({rel_idx}/{len(rel_paths)})")
                for rc_url in rc_urls:
                    try:
                        parsed = urllib.parse.urlparse(rc_url)
                        headers = {'Content-Type': 'application/json'}
                        
                        if parsed.username and parsed.password:
                            auth_str = f"{parsed.username}:{parsed.password}"
                            auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
                            headers['Authorization'] = f"Basic {auth_b64}"
                            
                            # Remove user info from netloc to form clean URL
                            netloc = parsed.netloc.split('@')[-1]
                            clean_rc_url = f"{parsed.scheme}://{netloc}"
                        else:
                            clean_rc_url = rc_url
                        
                        full_url = f"{clean_rc_url.rstrip('/')}/vfs/refresh"
                        req_data = json.dumps({"dir": rel_path}).encode('utf-8')
                        req = urllib.request.Request(
                            full_url, 
                            data=req_data,
                            headers=headers
                        )

                        for attempt in range(1, 4):
                            try:
                                with urllib.request.urlopen(req, timeout=1200) as resp:
                                    res_text = resp.read().decode('utf-8')
                                    ok, reason = _is_vfs_refresh_success_response(res_text, rel_path)
                                    if ok:
                                        print(f"[Scanner-VFS] VFS cache refresh success - Server: '{clean_rc_url}', Target: '{rel_path}', Result: {res_text}")
                                        print(f"[Scanner-VFS] VFS refresh candidate selected: '{rel_path}' ({rel_idx}/{len(rel_paths)})")
                                        refreshed = True
                                        break
                                    print(f"[Scanner-VFS Warning] Non-success VFS refresh response ignored - Server: '{clean_rc_url}', Target: '{rel_path}', Reason: {reason}")
                                    break
                            except urllib.error.URLError as e:
                                if attempt < 3 and _is_connection_refused_error(e):
                                    print(f"[Scanner-VFS Warning] RC server not ready yet. Retrying shortly (server='{clean_rc_url}', path='{rel_path}', attempt={attempt}/3)")
                                    time.sleep(2.0)
                                    continue
                                raise

                        if refreshed:
                            break
                    except Exception as e:
                        # Obfuscate credentials in logs if present
                        safe_url = rc_url
                        if '@' in rc_url:
                            try:
                                p = urllib.parse.urlparse(rc_url)
                                safe_url = f"{p.scheme}://****:****@{p.netloc.split('@')[-1]}"
                            except Exception:
                                safe_url = "[Protected URL]"
                        print(f"[Scanner-VFS Warning] Server '{safe_url}' path '{rel_path}' refresh attempt ignored or failed: {e}")

                if refreshed:
                    break

            if refreshed:
                continue
    except Exception as e:
        print(f"[Scanner-VFS Warning] VFS cache refresh process failed: {e}")

    print("=== Scanner Task Complete ===")
