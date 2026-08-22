# -*- coding: utf-8 -*-
# BookOasis Engine (boe-core-a17f3c9) - VFS(rclone) 캐시 사전 갱신 로직
# Copyright (c) BookOasis contributors. Licensed under the GNU AGPLv3 (see LICENSE).
# 이 파일을 포함한 수정본을 네트워크 서비스로 운용하는 경우, AGPLv3 13조에 따라
# 이용자에게 대응 소스코드(Corresponding Source)를 제공해야 하며, 5조에 따라
# 위 저작권/라이선스 고지를 임의로 제거할 수 없습니다.
import os
import urllib.request
import urllib.error
import urllib.parse
import json
import base64
import time
import database
from utils.drive_helper import is_remote_path, is_gdrive_url, is_rclone_vfs_path, get_rclone_refresh_dirs
from utils.engine_signature import ENGINE_NAME, ENGINE_SIGNATURE


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
    remote_paths = list(dict.fromkeys([p for p in target_paths if is_rclone_vfs_path(p) and not is_gdrive_url(p)]))

    if not remote_paths:
        return

    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    print(f"[Scanner-VFS] Remote mount path detected: {remote_paths} - Checking cache status...")

    try:
        from repositories.category_repository import CategoryRepository
        row = CategoryRepository.get_library_by_id(db_type, library_id)

        if not row or row['is_remote'] != 1:
            print(f"[Scanner-VFS] VFS refresh skipped: remote drive flag is disabled for library {library_id}.")
            return

        if row['vfs_refresh_before_scan'] != 1:
            return

        rc_urls = resolve_rc_urls(db_type, row)
    except Exception as e:
        print(f"[Scanner-VFS Warning] VFS cache refresh process failed: {e}")
        return

    refresh_vfs_paths(remote_paths, rc_urls)


def resolve_rc_urls(db_type, row):
    """라이브러리 row의 rclone_rc_url 컬럼(콤마 구분)을 우선 쓰고, 비어있으면 전역
    설정(RCLONE_RC_URL) -> localhost 기본값 순으로 폴백해 RC 주소 목록을 만든다.
    trigger_vfs_refresh()와 책 단위 사전복사(gdrive_view_copy_service.py) 양쪽에서 공용."""
    rc_urls = ["http://localhost:5572"]
    if row and row.get('rclone_rc_url') and str(row['rclone_rc_url']).strip():
        rc_urls = [u.strip().rstrip('/') for u in str(row['rclone_rc_url']).split(',') if u.strip()]
    else:
        try:
            from repositories.settings_repository import SettingsRepository
            val = SettingsRepository.get_value(db_type, 'RCLONE_RC_URL')
            if val:
                rc_urls = [u.strip().rstrip('/') for u in str(val).split(',') if u.strip()]
        except Exception:
            pass
    return list(dict.fromkeys(rc_urls))


def refresh_vfs_paths(remote_paths, rc_urls):
    """remote_paths(로컬 마운트 경로들) 각각에 대해 rc_urls 중 응답하는 rclone RC 서버로
    vfs/refresh를 시도한다 (재시도/후보 경로 폴백 포함). 실패해도 예외를 던지지 않는다 —
    호출부는 이 갱신을 최선의 노력으로만 취급해야 한다(성공 안 해도 다음 접근 때 자연
    캐시 만료로 결국 보이긴 하므로, 뷰어 흐름을 막을 만큼 치명적이지 않음)."""
    try:
        for r_path in remote_paths:
            print(f"[Scanner-VFS] Starting VFS cache pre-refresh. Target: {r_path}")
            rel_paths = get_rclone_refresh_dirs(r_path)

            refreshed = False
            for rel_idx, rel_path in enumerate(rel_paths, start=1):
                print(f"[Scanner-VFS] VFS refresh candidate path attempt: '{rel_path}' ({rel_idx}/{len(rel_paths)})")
                for rc_url in rc_urls:
                    try:
                        parsed = urllib.parse.urlparse(rc_url)
                        # User-Agent에 엔진 시그니처를 남겨, 이 VFS 사전 갱신 로직이 그대로
                        # 복제/재사용된 경우 네트워크 트래픽에서도 출처를 식별할 수 있게 한다.
                        headers = {
                            'Content-Type': 'application/json',
                            'User-Agent': f'{ENGINE_NAME}/{ENGINE_SIGNATURE}',
                        }

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

    print("=== VFS Refresh Complete ===")
