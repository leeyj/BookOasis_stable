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


def _docker_localhost_rc_hint(rc_url):
    """rc_url의 호스트가 localhost/127.0.0.1이면, 도커 컨테이너 안에서는 그 주소가
    컨테이너 자기 자신을 가리켜 호스트(또는 다른 컨테이너)의 rclone RC 서버에 연결이
    거의 항상 실패한다는 힌트를 반환한다 — 도커 사용자 대부분이 RC 연결에 실패한다는
    커뮤니티 피드백(2026-08-24)의 원인. 로컬(비도커) 설치에서는 정상 동작이라 빈
    문자열을 반환한다."""
    try:
        host = (urllib.parse.urlparse(rc_url).hostname or '').lower()
    except Exception:
        return ''
    if host not in ('localhost', '127.0.0.1'):
        return ''
    return (
        " — 도커 환경이라면 'localhost'는 이 컨테이너 자신을 가리켜 호스트의 rclone RC 서버에"
        " 닿지 못합니다. 설정 > 라이브러리의 'RC 주소'를 Linux는 host.docker.internal"
        "(docker-compose에 extra_hosts: host.docker.internal:host-gateway 추가 필요),"
        " Mac/Windows(Docker Desktop)는 host.docker.internal로, rclone이 별도 컨테이너면"
        " 그 서비스명으로 바꿔 보세요."
    )


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
    설정(RCLONE_RC_URL) -> localhost/host.docker.internal 기본값 순으로 폴백해 RC 주소
    목록을 만든다. trigger_vfs_refresh()와 책 단위 사전복사(gdrive_view_copy_service.py)
    양쪽에서 공용. host.docker.internal을 기본 후보에 포함하는 이유: 도커 사용자가
    실사용자 다수인데(2026-08-24 커뮤니티 피드백) 'localhost' 단독으로는 컨테이너 안에서
    호스트의 rclone RC 서버에 거의 항상 닿지 못한다 — Docker Desktop(Mac/Windows)은 이
    호스트명을 기본 지원해 설정 없이도 바로 연결되고, Linux는 여전히 compose에
    extra_hosts 매핑이 필요하다(도달 불가 시 자연히 다음 후보로 폴백하므로 무해)."""
    rc_urls = ["http://localhost:5572", "http://host.docker.internal:5572"]
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


def _rc_request_headers(rc_url):
    """rc_url의 userinfo(basic auth)를 헤더로 옮기고, 인증정보가 빠진 깨끗한 URL을 함께 반환."""
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': f'{ENGINE_NAME}/{ENGINE_SIGNATURE}',
    }
    parsed = urllib.parse.urlparse(rc_url)
    if parsed.username and parsed.password:
        auth_str = f"{parsed.username}:{parsed.password}"
        auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        headers['Authorization'] = f"Basic {auth_b64}"
        clean_rc_url = f"{parsed.scheme}://{parsed.netloc.split('@')[-1]}"
    else:
        clean_rc_url = rc_url
    return headers, clean_rc_url


def _unescape_proc_mounts_field(value):
    """/proc/mounts는 공백/탭/개행/백슬래시를 8진 이스케이프(\\040 등)로 인코딩한다."""
    return (
        value.replace('\\040', ' ')
             .replace('\\011', '\t')
             .replace('\\012', '\n')
             .replace('\\134', '\\')
    )


def detect_mount_root_from_proc_mounts(remote_name, physical_path=None):
    """리눅스 /proc/mounts에서 이 rclone 리모트(remote_name, 콜론 없이)가 마운트된 로컬
    경로를 찾는다. rclone RC의 mount/listmounts는 CLI(`rclone mount ...`)로 시작한
    마운트를 추적하지 못하는 경우가 실제로 확인됐다(2026-08-22, `--rc`가 걸려 있어도
    listmounts가 빈 배열을 반환) — OS 마운트 테이블을 직접 읽는 이 방법이 rclone 버전/RC
    등록 방식과 무관하게 항상 정확하다. BookOasis 프로세스가 rclone과 같은 마운트
    네임스페이스에 있을 때만 동작(도커라면 호스트 /proc 마운트가 없는 한 안 보일 수 있음)
    — 그 경우 detect_mount_root_via_rc()로 폴백."""
    remote_name = (remote_name or '').strip().rstrip(':')
    if not remote_name:
        print("[Vfs-MountDetect] remote_name이 비어 있어 /proc/mounts 조회를 건너뜀")
        return None

    try:
        with open('/proc/mounts', 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError as e:
        print(f"[Vfs-MountDetect] /proc/mounts 읽기 실패(도커 등 마운트 네임스페이스가 다르면 정상): {e}")
        return None

    physical_path_norm = (physical_path or '').strip().replace('\\', '/').rstrip('/') or None
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        source, mountpoint_raw, fstype = parts[0], parts[1], parts[2]
        if 'fuse.rclone' not in fstype and fstype != 'rclone':
            continue
        source_remote = source.split(':', 1)[0]
        if source_remote != remote_name:
            continue
        mountpoint = _unescape_proc_mounts_field(mountpoint_raw).rstrip('/')
        print(f"[Vfs-MountDetect] /proc/mounts에서 발견: remote='{remote_name}' -> mountpoint='{mountpoint}'")
        if physical_path_norm and not (physical_path_norm == mountpoint or physical_path_norm.startswith(mountpoint + '/')):
            print(f"[Vfs-MountDetect] 경고: physical_path='{physical_path_norm}'가 이 마운트 하위 경로가 아님 — 물리 경로를 다시 확인하세요")
            continue
        return mountpoint

    print(f"[Vfs-MountDetect] /proc/mounts에 remote='{remote_name}' 마운트 없음")
    return None


def detect_mount_remote_subpath(remote_name):
    """/proc/mounts의 source 필드(예: 'sjva:tempview')에서 리모트 이름 뒤의 서브경로
    ('tempview')를 반환한다. 관리자가 'rclone mount sjva:tempview /path'처럼 특정
    서브폴더를 대상으로 마운트한 경우, 로컬 마운트 루트는 그 서브폴더에 대응하지만
    rclone.conf의 root_folder_id는 비어있을 수 있다(명령행 인자로만 스코핑된 경우
    설정 파일엔 아무 흔적이 없음) — Drive API 호출 시 이 서브경로를 시작점에 반영하지
    않으면 파일이 실제 Drive 루트(마운트 범위 밖)에 생겨 로컬에서 영원히 안 보이는
    문제로 이어진다(2026-08-23 실사용자 리포트, get_remote_root_folder_id()의
    root_folder_id 처리만으로는 이 케이스를 못 잡아냄). 못 찾으면 빈 문자열."""
    remote_name = (remote_name or '').strip().rstrip(':')
    if not remote_name:
        return ''
    try:
        with open('/proc/mounts', 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return ''
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        source, _mountpoint, fstype = parts[0], parts[1], parts[2]
        if 'fuse.rclone' not in fstype and fstype != 'rclone':
            continue
        if ':' not in source:
            continue
        prefix, _, subpath = source.partition(':')
        if prefix != remote_name:
            continue
        return subpath.strip('/')
    return ''


def detect_mount_root_via_rc(rc_urls, physical_path):
    """rclone RC의 mount/listmounts로 현재 활성 마운트 목록을 조회해, physical_path를
    포함하는(그 경로가 하위에 있는) 마운트의 MountPoint를 반환한다 — 관리자가 "이 리모트가
    로컬 어디에 마운트돼 있는지"를 직접 타이핑하지 않아도, rclone 자신이 이미 아는 정보를
    그대로 읽어오는 것이다. 여러 rc_urls 후보를 순서대로 시도, 실패/불일치 시 None.
    가장 길게(구체적으로) 일치하는 MountPoint를 우선한다."""
    physical_path = (physical_path or '').strip().replace('\\', '/').rstrip('/')
    if not physical_path:
        print("[Vfs-MountDetect] physical_path가 비어 있어 감지를 건너뜀")
        return None

    print(f"[Vfs-MountDetect] 감지 시작: physical_path='{physical_path}', rc_urls={rc_urls}")

    for rc_url in rc_urls:
        try:
            headers, clean_rc_url = _rc_request_headers(rc_url)
            full_url = f"{clean_rc_url.rstrip('/')}/mount/listmounts"
            req = urllib.request.Request(full_url, data=b'{}', headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_body = resp.read().decode('utf-8')
                payload = json.loads(raw_body)
        except Exception as e:
            print(f"[Vfs-MountDetect] RC 서버 '{rc_url}' 조회 실패(다음 후보로 계속): {e}{_docker_localhost_rc_hint(rc_url)}")
            continue

        print(f"[Vfs-MountDetect] RC 서버 '{rc_url}' 응답: {raw_body}")

        mount_points = payload.get('mountPoints') if isinstance(payload, dict) else None
        if not isinstance(mount_points, list):
            print(f"[Vfs-MountDetect] RC 서버 '{rc_url}' 응답에 mountPoints 배열이 없음 (payload keys: {list(payload.keys()) if isinstance(payload, dict) else type(payload)})")
            continue
        if not mount_points:
            print(f"[Vfs-MountDetect] RC 서버 '{rc_url}': 현재 활성 마운트가 0개 (rclone mount로 마운트된 게 아니라 rclone.conf 상의 원격 자체를 다른 방식(fstab 등)으로 마운트했을 가능성)")

        best_match = None
        for entry in mount_points:
            mp = str(entry.get('MountPoint') or '').replace('\\', '/').rstrip('/')
            print(f"[Vfs-MountDetect]   후보 마운트: Fs='{entry.get('Fs')}', MountPoint='{mp}' -> {'일치' if (physical_path == mp or physical_path.startswith(mp + '/')) else '불일치'}")
            if not mp:
                continue
            if physical_path == mp or physical_path.startswith(mp + '/'):
                if best_match is None or len(mp) > len(best_match):
                    best_match = mp
        if best_match:
            print(f"[Vfs-MountDetect] 감지 성공: '{best_match}'")
            return best_match

    print(f"[Vfs-MountDetect] 감지 실패: physical_path='{physical_path}'를 포함하는 마운트를 못 찾음")
    return None


def detect_mount_root(remote_name, physical_path, rc_urls):
    """마운트 루트 자동 감지 진입점. /proc/mounts(OS 마운트 테이블, 항상 정확하지만
    BookOasis와 rclone이 같은 마운트 네임스페이스에 있어야 함)를 먼저 시도하고, 실패하면
    RC의 mount/listmounts(그 마운트가 RC로 등록됐을 때만 보임)로 폴백한다."""
    mount_root = detect_mount_root_from_proc_mounts(remote_name, physical_path)
    if mount_root:
        return mount_root
    return detect_mount_root_via_rc(rc_urls, physical_path)


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
                        print(f"[Scanner-VFS Warning] Server '{safe_url}' path '{rel_path}' refresh attempt ignored or failed: {e}{_docker_localhost_rc_hint(rc_url)}")

                if refreshed:
                    break

            if refreshed:
                continue
    except Exception as e:
        print(f"[Scanner-VFS Warning] VFS cache refresh process failed: {e}")

    print("=== VFS Refresh Complete ===")
