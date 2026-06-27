# -*- coding: utf-8 -*-
import os
import urllib.request
import json
import database
from utils.drive_helper import is_remote_path, get_rclone_relative_path

def trigger_vfs_refresh(db_path, library_id, physical_path):
    """원격 마운트 경로(VFS)인 경우 스캔 시작 전 rclone 캐시를 갱신합니다."""
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    remote_paths = [p for p in target_paths if is_remote_path(p)]
    
    if not remote_paths:
        return
        
    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    print(f"[Scanner-VFS] 원격 마운트 경로 감지: {remote_paths} - 캐시 상태 확인 중...")
    
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT vfs_refresh_before_scan FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row or row['vfs_refresh_before_scan'] != 1:
            return
            
        rc_url = "http://localhost:5572"
        try:
            conn_s = database.get_connection(db_type)
            cursor_s = conn_s.cursor()
            cursor_s.execute("SELECT value FROM settings WHERE key = 'RCLONE_RC_URL'")
            row_s = cursor_s.fetchone()
            if row_s:
                rc_url = row_s['value'].rstrip('/')
            conn_s.close()
        except Exception:
            pass
            
        for r_path in remote_paths:
            print(f"[Scanner-VFS] VFS 캐시 사전 새로고침을 시작합니다. 대상: {r_path}")
            rel_path = get_rclone_relative_path(r_path)
            full_url = f"{rc_url}/vfs/refresh"
            req_data = json.dumps({"dir": rel_path}).encode('utf-8')
            req = urllib.request.Request(
                full_url, 
                data=req_data,
                headers={'Content-Type': 'application/json'}
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    print(f"[Scanner-VFS] VFS 캐시 갱신 성공 - 대상: '{rel_path}', 결과: {resp.read().decode('utf-8')}")
            except Exception as e:
                print(f"[Scanner-VFS Warning] 경로 '{rel_path}' 갱신 실패: {e}")
    except Exception as e:
        print(f"[Scanner-VFS Warning] VFS 캐시 새로고침 실패 (rclone 오프라인 등): {e}")

    print("=== 스캐너 작업 완료 ===")
