# -*- coding: utf-8 -*-
"""
rclone_gdrive_copy.py – rclone.conf에 저장된 Google Drive 리모트를 감지하고,
해당 리모트의 OAuth 자격증명으로 Drive REST API 접근 토큰을 발급/검증한다.

공유받은 폴더를 서버가 대신 스트리밍하는 대신, 등록 시점에 사용자 자신의 드라이브로
서버사이드 복사(files.copy)를 해두기 위한 "2단계"(리모트 감지·선택·검증) 구현.
실제 폴더 전체 복사(3단계)는 아직 포함하지 않는다 — docs/plan_gdrive_server_side_copy.md 참조.

주의: refresh_token/access_token/client_secret 등 민감정보는 어떤 경우에도 로그로 출력하지 않는다.

rclone.conf 경로는 기본적으로 rclone 자신의 기본 탐색 규칙을 따르되, RCLONE_CONFIG_PATH
환경변수가 설정돼 있으면 모든 rclone CLI 호출에 `--config <path>`로 강제한다 — 인스턴스마다
rclone.conf를 다른 경로에 따로 두는 사용자를 위한 것(2026-08-24 커뮤니티 피드백).

도커 PUID/PGID 사용 시 이 코드는 media_user로 실행되지만(entrypoint.sh의 gosu), 사용자가
`docker exec`로 컨테이너에 들어가 rclone.conf를 설정할 때는 기본적으로 root 계정이라
$HOME이 서로 달라(/home/media_user vs /root) 같은 컨테이너인데도 앱이 그 설정을 못 찾는
사례가 실제로 보고됐다(2026-08-24, hamsuehun 커뮤니티: media_user 홈엔 rclone.conf가
아예 없고 root 홈에만 있음). 환경변수도 없고 현재 프로세스 기본 위치에도 파일이 없으면
root의 표준 위치를 마지막으로 한 번 더 확인해 이 흔한 사례를 사용자 설정 없이 구제한다.
"""
import json
import os
import subprocess
import time

import requests

RCLONE_CONFIG_DUMP_TIMEOUT = 10
OAUTH_TOKEN_TIMEOUT = 10
DRIVE_API_TIMEOUT = 15
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
DRIVE_API_BASE = 'https://www.googleapis.com/drive/v3'
RCLONE_COPY_TIMEOUT = 300
RCLONE_FOLDER_COPY_TIMEOUT = 1800

# remote_name -> {'access_token': str, 'expires_at': epoch_seconds}
_token_cache = {}


_ROOT_RCLONE_CONFIG_FALLBACK = '/root/.config/rclone/rclone.conf'


def _rclone_config_args():
    """RCLONE_CONFIG_PATH(우리 전용) 또는 RCLONE_CONFIG(rclone 자체가 이미 인식하는
    표준 환경변수명, 2026-08-24 커뮤니티 요청) 중 설정된 값으로 `--config <path>`
    인자를 반환한다 — 사용자가 rclone.conf를 기본 위치가 아닌 다른 경로에 여러 개
    두고 쓰는 경우 이 기능이 참조할 파일을 명시적으로 지정할 수 있게 한다.
    rclone 프로세스는 RCLONE_CONFIG를 환경변수 상속만으로도 스스로 읽지만, 여기서
    명시적으로 --config를 붙여 어떤 파일을 쓰는지 우리 로그에서도 확정적으로 알 수
    있게 한다. 둘 다 설정됐다면 RCLONE_CONFIG_PATH가 우선한다.

    둘 다 없으면 현재 프로세스의 기본 위치($HOME/.config/rclone/rclone.conf)를 그대로
    맡기되, 그 파일이 없고 root의 표준 위치(/root/.config/rclone/rclone.conf)에는
    있으면 그걸 대신 쓴다 — 도커에서 media_user로 앱이 돌지만 rclone.conf는
    root 계정으로 설정된 흔한 사례(2026-08-24 hamsuehun 커뮤니티 리포트)를 사용자가
    직접 RCLONE_CONFIG_PATH를 지정하지 않아도 구제한다."""
    config_path = (
        os.environ.get('RCLONE_CONFIG_PATH', '').strip()
        or os.environ.get('RCLONE_CONFIG', '').strip()
    )
    if config_path:
        return ['--config', config_path]

    own_default = os.path.expanduser('~/.config/rclone/rclone.conf')
    if not os.path.isfile(own_default) and os.path.isfile(_ROOT_RCLONE_CONFIG_FALLBACK):
        print(f"[RcloneGdriveCopy] 기본 위치 '{own_default}'에 rclone.conf가 없어 "
              f"'{_ROOT_RCLONE_CONFIG_FALLBACK}'을(를) 대신 사용합니다 "
              f"(RCLONE_CONFIG_PATH를 지정하면 이 자동 폴백보다 우선합니다).")
        return ['--config', _ROOT_RCLONE_CONFIG_FALLBACK]

    return []


def _rclone_config_dump():
    """`rclone config dump`를 실행해 파싱된 dict(리모트명 -> 설정)를 반환. 실패 시 None."""
    try:
        result = subprocess.run(
            ['rclone'] + _rclone_config_args() + ['config', 'dump'],
            capture_output=True, text=True, timeout=RCLONE_CONFIG_DUMP_TIMEOUT
        )
    except FileNotFoundError:
        print('[RcloneGdriveCopy] rclone 바이너리를 찾을 수 없습니다 (PATH 확인 필요)')
        return None
    except subprocess.TimeoutExpired:
        print('[RcloneGdriveCopy] rclone config dump 시간 초과')
        return None
    except Exception as e:
        print(f'[RcloneGdriveCopy] rclone config dump 실행 오류: {e}')
        return None

    if result.returncode != 0:
        print(f'[RcloneGdriveCopy] rclone config dump 실패 (code={result.returncode}): {result.stderr.strip()[:200]}')
        return None

    try:
        return json.loads(result.stdout)
    except Exception as e:
        print(f'[RcloneGdriveCopy] rclone config dump 출력 파싱 실패: {e}')
        return None


def list_writable_drive_remotes():
    """rclone.conf에 설정된 리모트 중 '내 드라이브(쓰기 가능)'로 쓸 수 있는 것만 추려 반환한다.
    민감정보(토큰/시크릿)는 반환값에 절대 포함하지 않는다.
    커스텀 client_id/client_secret이 없는(=rclone 기본 공유 OAuth 앱을 쓰는) 리모트는
    대리 API 호출에 부적합하다고 보고 제외한다 (사유를 함께 표기)."""
    dump = _rclone_config_dump()
    if not dump:
        return []

    remotes = []
    for name, cfg in dump.items():
        if not isinstance(cfg, dict):
            continue
        if cfg.get('type') != 'drive':
            continue
        scope = (cfg.get('scope') or '').strip()
        if scope and scope != 'drive':
            # drive.readonly / drive.file 등 쓰기 불가능하거나 제한적인 스코프는 제외
            continue
        if not cfg.get('token'):
            continue

        has_custom_app = bool(cfg.get('client_id')) and bool(cfg.get('client_secret'))
        remotes.append({
            'name': name,
            'usable': has_custom_app,
            'reason': None if has_custom_app else '커스텀 client_id/client_secret이 설정되지 않아(rclone 기본 앱 사용) 이번 단계에서는 지원 대상에서 제외됩니다.',
        })

    return remotes


def _extract_credentials(remote_cfg):
    token_raw = remote_cfg.get('token')
    if not token_raw:
        raise ValueError('리모트에 저장된 OAuth 토큰이 없습니다.')
    try:
        token_json = json.loads(token_raw)
    except Exception:
        raise ValueError('리모트 토큰 형식을 해석할 수 없습니다.')

    refresh_token = token_json.get('refresh_token')
    client_id = remote_cfg.get('client_id')
    client_secret = remote_cfg.get('client_secret')
    if not (refresh_token and client_id and client_secret):
        raise ValueError('리모트에 client_id/client_secret/refresh_token이 모두 설정되어 있어야 합니다.')

    return client_id, client_secret, refresh_token


def get_access_token(remote_name):
    """remote_name의 rclone OAuth 자격증명으로 새 access token을 발급받는다 (메모리 캐시)."""
    cached = _token_cache.get(remote_name)
    if cached and cached['expires_at'] > time.time() + 30:
        return cached['access_token']

    dump = _rclone_config_dump()
    if not dump or remote_name not in dump:
        raise ValueError(f"rclone 리모트 '{remote_name}'을(를) 찾을 수 없습니다.")

    client_id, client_secret, refresh_token = _extract_credentials(dump[remote_name])

    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        },
        timeout=OAUTH_TOKEN_TIMEOUT,
    )
    if resp.status_code != 200:
        raise ValueError(f'Google OAuth 토큰 갱신 실패 (HTTP {resp.status_code})')

    payload = resp.json()
    access_token = payload.get('access_token')
    expires_in = payload.get('expires_in', 3600)
    if not access_token:
        raise ValueError('Google OAuth 응답에 access_token이 없습니다.')

    _token_cache[remote_name] = {
        'access_token': access_token,
        'expires_at': time.time() + int(expires_in),
    }
    return access_token


def get_remote_root_folder_id(remote_name):
    """이 리모트가 rclone.conf에서 root_folder_id로 특정 서브폴더에 고정돼 있으면 그
    폴더 id를, 아니면 Drive API의 실제 최상위를 가리키는 'root' 별칭을 반환한다.

    'root' 별칭은 항상 내 드라이브의 진짜 최상위를 가리킨다 — rclone 리모트가
    root_folder_id로 특정 서브폴더(예: 공유 조직화용 'tempview' 폴더)에 고정된
    경우에도 마찬가지다. 이 함수 없이 무조건 'root'를 부모로 써서 폴더를 만들면,
    Drive API 상으로는 성공해도 그 폴더는 rclone이 마운트한 서브트리 바깥(진짜
    최상위)에 생기므로 로컬 마운트 경로에서는 영원히 보이지 않는다 — 복사 성공
    로그와 실제 파일 부재가 같이 나타나는 버그의 원인이었다(2026-08-23 실사용자 리포트)."""
    dump = _rclone_config_dump()
    cfg = (dump or {}).get(remote_name) or {}
    return cfg.get('root_folder_id') or 'root'


def resolve_effective_root_folder_id(access_token, remote_name):
    """이 리모트를 통해 파일/폴더를 만들 때 실제로 써야 하는 시작 폴더 id를 계산한다.
    두 가지 스코핑 방식을 모두 반영해야 한다:
    1) rclone.conf의 root_folder_id 설정(get_remote_root_folder_id) — 리모트 자체가
       특정 서브폴더에 고정된 경우.
    2) 'rclone mount remote:subpath ...'처럼 마운트 명령행 인자로만 준 서브경로
       (detect_mount_remote_subpath) — rclone.conf엔 흔적이 없어 1)만으로는 못 잡음.
    2)는 /proc/mounts에서만 읽을 수 있어(도커 등 마운트 네임스페이스가 다르면 못 읽고
    빈 문자열) 최선의 노력이다 — 이 경우 이전처럼 root_folder_id/실제 루트로만 계산되어
    같은 증상(로컬에서 안 보임)이 재발할 수 있으니, 감지 실패 시 로그를 남긴다."""
    from tools.scanner.vfs import detect_mount_remote_subpath

    folder_id = get_remote_root_folder_id(remote_name)
    subpath = detect_mount_remote_subpath(remote_name)
    if not subpath:
        print(f"[RcloneGdriveCopy] 리모트 '{remote_name}'의 마운트 서브경로를 감지하지 못함 (도커 등으로 /proc/mounts를 못 읽는 경우 정상) — root_folder_id 기준으로만 계산")
        return folder_id

    for part in [p for p in subpath.split('/') if p]:
        folder_id = find_or_create_folder(access_token, part, folder_id)
    return folder_id


def find_or_create_folder(access_token, name, parent_id):
    """parent_id 아래에서 name과 일치하는 폴더를 찾고, 없으면 생성해 폴더 id를 반환."""
    headers = {'Authorization': f'Bearer {access_token}'}
    safe_name = name.replace("'", "\\'")
    query = f"name = '{safe_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    resp = requests.get(
        f'{DRIVE_API_BASE}/files',
        headers=headers,
        params={'q': query, 'fields': 'files(id,name)'},
        timeout=DRIVE_API_TIMEOUT,
    )
    if resp.status_code != 200:
        raise ValueError(f'Drive 폴더 조회 실패 (HTTP {resp.status_code})')
    files = resp.json().get('files') or []
    if files:
        return files[0]['id']

    resp = requests.post(
        f'{DRIVE_API_BASE}/files',
        headers=headers,
        json={'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]},
        timeout=DRIVE_API_TIMEOUT,
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f'Drive 폴더 생성 실패 (HTTP {resp.status_code})')
    return resp.json()['id']


def copy_file(access_token, file_id, dest_folder_id, dest_name=None):
    """file_id로 지정된 파일을 dest_folder_id 아래로 서버사이드 복사한다 (files.copy). 1회 재시도."""
    headers = {'Authorization': f'Bearer {access_token}'}
    payload = {'parents': [dest_folder_id]}
    if dest_name:
        payload['name'] = dest_name

    last_error = None
    for attempt in range(2):
        try:
            resp = requests.post(
                f'{DRIVE_API_BASE}/files/{file_id}/copy',
                headers=headers,
                json=payload,
                timeout=DRIVE_API_TIMEOUT,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            last_error = f'HTTP {resp.status_code}: {resp.text[:200]}'
        except requests.RequestException as e:
            last_error = str(e)
        time.sleep(1.0)

    raise ValueError(f'파일 복사 실패 (file_id={file_id}): {last_error}')


def compute_relative_dest_path(physical_path, mount_root):
    """physical_path가 mount_root(이 리모트가 통째로 마운트된 로컬 경로) 아래에 있으면
    그 상대경로(Drive 쪽 dest_path로 그대로 쓸 수 있는 값)를 반환하고, 아니면 None.

    "카테고리 복사" 배치 플로우에서 admin이 물리 경로(로컬)와 dest_path(Drive쪽)를 각각
    손으로 입력하다 보니 둘이 겹치는 부분("share" 같은)을 착각해 어긋나는 게 실사용자
    혼란 포인트였다(2026-08-22). mount_root 하나만 알면 물리 경로에서 자동으로 뽑아낼 수
    있으므로, dest_path를 직접 입력받지 않고 이걸로 계산한다.

    문자열이 정확히 일치하지 않아도, 심볼릭 링크(realpath로 재해석)나 대소문자 차이(도커
    볼륨 매핑 등)만으로 어긋난 경우는 구제한다 — 둘 다 실사용자 케이스로 확인됨
    (2026-08-24 커뮤니티 피드백). 그래도 못 맞추면 여전히 None(호출부가 경고 로그를 남김)."""
    physical_path = (physical_path or '').strip()
    mount_root = (mount_root or '').strip()
    if not physical_path or not mount_root:
        return None
    norm_physical = physical_path.replace('\\', '/').rstrip('/')
    norm_mount = mount_root.replace('\\', '/').rstrip('/')
    if norm_physical == norm_mount:
        return ''
    prefix = norm_mount + '/'
    if norm_physical.startswith(prefix):
        return norm_physical[len(prefix):]

    try:
        real_physical = os.path.realpath(physical_path).replace('\\', '/').rstrip('/')
        real_mount = os.path.realpath(mount_root).replace('\\', '/').rstrip('/')
    except OSError:
        real_physical, real_mount = norm_physical, norm_mount
    if real_physical == real_mount:
        return ''
    real_prefix = real_mount + '/'
    if real_physical.startswith(real_prefix):
        return real_physical[len(real_prefix):]

    if norm_physical.lower() == norm_mount.lower():
        return ''
    if norm_physical.lower().startswith(prefix.lower()):
        return norm_physical[len(prefix):]

    return None


def resolve_dest_folder(access_token, dest_path, remote_name=None):
    """dest_path(리모트 내부 상대경로)의 폴더 체인을 없으면 생성하며 최종 폴더 id를 반환.
    remote_name을 주면 그 리모트의 실제 스코핑(root_folder_id + 마운트 서브경로)을
    시작점으로 쓴다 — resolve_effective_root_folder_id() 참조."""
    folder_id = resolve_effective_root_folder_id(access_token, remote_name) if remote_name else 'root'
    dest_path = (dest_path or '').strip().strip('/')
    if dest_path:
        for part in [p for p in dest_path.split('/') if p]:
            folder_id = find_or_create_folder(access_token, part, folder_id)
    return folder_id


def validate_remote_access(remote_name, dest_path):
    """선택한 리모트의 계정 정보를 확인하고, dest_path 경로의 폴더를 없으면 생성해
    실제로 쓰기 가능한지 검증한다. 성공 시 {'success': True, 'account_email', 'folder_id'} 반환."""
    try:
        access_token = get_access_token(remote_name)

        about_resp = requests.get(
            f'{DRIVE_API_BASE}/about',
            headers={'Authorization': f'Bearer {access_token}'},
            params={'fields': 'user'},
            timeout=DRIVE_API_TIMEOUT,
        )
        if about_resp.status_code != 200:
            return {'success': False, 'error': f'Drive 계정 정보 조회 실패 (HTTP {about_resp.status_code})'}
        account_email = (about_resp.json().get('user') or {}).get('emailAddress')

        folder_id = resolve_dest_folder(access_token, dest_path, remote_name)

        return {'success': True, 'account_email': account_email, 'folder_id': folder_id}
    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except requests.RequestException as e:
        return {'success': False, 'error': f'네트워크 오류: {e}'}
    except Exception as e:
        return {'success': False, 'error': f'알 수 없는 오류: {e}'}


# ==============================================================================
# rclone CLI 기반 서버사이드 복사 (2026-08-23 도입)
# ==============================================================================
# 위쪽 REST 기반 copy_file()/find_or_create_folder()는 파일 하나씩 Drive API를 직접
# 호출하는 방식이라, 이미지 낱장 폴더(zip으로 안 묶인 책)처럼 파일이 여러 개인 소스는
# 우리가 직접 순회하며 재귀 로직을 다시 구현해야 했다. rclone은 이미 이 문제(재귀 탐색,
# 동시성, 재시도, 이미 복사된 파일 스킵)를 내장하고 있고, 소스와 목적지가 둘 다 Drive
# 백엔드면 자동으로 서버사이드 복사를 쓴다 — 로컬 다운로드가 아니라 구글 데이터센터
# 내부에서 끝난다(2026-08-23 실 계정으로 검증: "Copied (server-side copy)" 로그 확인).
#
# 더 중요한 이점: 'remote:path' 문법이 로컬 마운트가 실제로 보여주는 경로 체계와
# 100% 동일하다 — root_folder_id 스코핑이나 'rclone mount remote:subpath ...'처럼
# 명령행으로만 스코핑된 마운트도 rclone 스스로 정확히 해석한다. 우리가 REST API로
# "이 리모트의 실제 루트 폴더 id가 뭔지" 직접 추론하려다 겪은 버그들
# (get_remote_root_folder_id/resolve_effective_root_folder_id로 땜질해야 했던 것)이
# 원천적으로 발생하지 않는다.


def _run_rclone(args, timeout=RCLONE_COPY_TIMEOUT, input_bytes=None):
    """rclone CLI를 서브프로세스로 실행하고 (returncode, stdout, stderr) bytes를 반환한다."""
    try:
        result = subprocess.run(
            ['rclone'] + _rclone_config_args() + list(args),
            capture_output=True, timeout=timeout, input=input_bytes,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        raise ValueError('rclone 바이너리를 찾을 수 없습니다 (PATH 확인 필요)')
    except subprocess.TimeoutExpired:
        raise ValueError('rclone 명령이 시간 초과됐습니다')


def rclone_copy_file_by_id(remote_name, file_id, dest_rclone_path):
    """단일 파일(file_id)을 remote_name 리모트의 dest_rclone_path로 서버사이드 복사한다
    (`rclone backend copyid`). dest_rclone_path에는 반드시 'remote:' 접두사를 포함해야
    한다 — 빠뜨리면 이 서버 로컬 디스크로 실제 다운로드돼버린다(2026-08-23 로컬 테스트로
    직접 확인한 실수 포인트). 목적지 상위 폴더가 없으면 rclone이 자동 생성한다."""
    if ':' not in dest_rclone_path:
        raise ValueError(f"dest_rclone_path에 'remote:' 접두사가 없습니다: {dest_rclone_path}")
    code, _, stderr = _run_rclone(['backend', 'copyid', f'{remote_name}:', file_id, dest_rclone_path])
    if code != 0:
        raise ValueError(f'rclone copyid 실패: {stderr.decode("utf-8", "replace")[:300]}')
    return True


def rclone_copy_folder_by_id(remote_name, folder_id, dest_rclone_path):
    """폴더(folder_id) 전체를 재귀적으로 remote_name 리모트의 dest_rclone_path 아래로
    서버사이드 복사한다(`rclone copy`, 인라인 root_folder_id 오버라이드로 임의의 공유
    폴더를 소스 리모트의 루트인 것처럼 취급). 이미지 낱장 폴더(imgdir) 책 복사에 쓴다.
    dest_rclone_path에는 반드시 'remote:' 접두사가 있어야 한다(위 copy_file_by_id 참고)."""
    if ':' not in dest_rclone_path:
        raise ValueError(f"dest_rclone_path에 'remote:' 접두사가 없습니다: {dest_rclone_path}")
    source = f'{remote_name},root_folder_id={folder_id}:'
    code, _, stderr = _run_rclone(
        ['copy', source, dest_rclone_path, '--drive-server-side-across-configs'],
        timeout=RCLONE_FOLDER_COPY_TIMEOUT,
    )
    if code != 0:
        raise ValueError(f'rclone copy(폴더) 실패: {stderr.decode("utf-8", "replace")[:300]}')
    return True


def rclone_ensure_ignore_marker(marker_rclone_path):
    """marker_rclone_path(예: 'sjva:_bookoasis_view_cache/.bookoasisignore')에
    '.bookoasisignore' 마커(내용 '*')가 없으면 만든다 — 로컬/레이지 스캐너가 뷰캐시
    폴더를 별개 소스로 잘못 재스캔해 중복 등록하지 않게 막는다. 존재 확인 후에만
    실제로 쓴다(멱등, 매 복사 시도마다 불러도 안전)."""
    check_code, check_out, _ = _run_rclone(['lsf', marker_rclone_path])
    if check_code == 0 and check_out.strip():
        return
    code, _, stderr = _run_rclone(['rcat', marker_rclone_path], input_bytes=b'*')
    if code != 0:
        # 마커 생성 실패는 치명적이지 않다 — 최악의 경우 다음 스캔에서 이 캐시 폴더가
        # 잘못 재스캔될 수 있을 뿐, 복사/열람 자체는 계속 진행해도 된다.
        print(f'[RcloneGdriveCopy] .bookoasisignore 마커 생성 실패 (무시하고 계속): {stderr.decode("utf-8", "replace")[:200]}')
