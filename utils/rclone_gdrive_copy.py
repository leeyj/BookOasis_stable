# -*- coding: utf-8 -*-
"""
rclone_gdrive_copy.py – rclone.conf에 저장된 Google Drive 리모트를 감지하고,
해당 리모트의 OAuth 자격증명으로 Drive REST API 접근 토큰을 발급/검증한다.

공유받은 폴더를 서버가 대신 스트리밍하는 대신, 등록 시점에 사용자 자신의 드라이브로
서버사이드 복사(files.copy)를 해두기 위한 "2단계"(리모트 감지·선택·검증) 구현.
실제 폴더 전체 복사(3단계)는 아직 포함하지 않는다 — docs/plan_gdrive_server_side_copy.md 참조.

주의: refresh_token/access_token/client_secret 등 민감정보는 어떤 경우에도 로그로 출력하지 않는다.
"""
import json
import subprocess
import time

import requests

RCLONE_CONFIG_DUMP_TIMEOUT = 10
OAUTH_TOKEN_TIMEOUT = 10
DRIVE_API_TIMEOUT = 15
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
DRIVE_API_BASE = 'https://www.googleapis.com/drive/v3'

# remote_name -> {'access_token': str, 'expires_at': epoch_seconds}
_token_cache = {}


def _rclone_config_dump():
    """`rclone config dump`를 실행해 파싱된 dict(리모트명 -> 설정)를 반환. 실패 시 None."""
    try:
        result = subprocess.run(
            ['rclone', 'config', 'dump'],
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


def ensure_ignore_marker(access_token, folder_id):
    """folder_id 아래에 .bookoasisignore 파일(내용 '*' — 이 폴더 전체를 무시)이 없으면 만든다.
    책 단위 사전복사 전용 캐시 폴더(_bookoasis_view_cache)를 일반/레이지 스캐너가 별개의
    로컬 소스로 잘못 다시 스캔해 중복 등록하는 것을 막기 위한 마커. 매번 호출해도 안전
    (존재하면 즉시 반환, 없을 때만 1회 생성)."""
    headers = {'Authorization': f'Bearer {access_token}'}
    query = f"name = '.bookoasisignore' and '{folder_id}' in parents and trashed = false"
    resp = requests.get(
        f'{DRIVE_API_BASE}/files',
        headers=headers,
        params={'q': query, 'fields': 'files(id)'},
        timeout=DRIVE_API_TIMEOUT,
    )
    if resp.status_code == 200 and (resp.json().get('files') or []):
        return

    boundary = 'bookoasis-ignore-marker'
    metadata = json.dumps({'name': '.bookoasisignore', 'parents': [folder_id], 'mimeType': 'text/plain'})
    body = (
        f'--{boundary}\r\n'
        f'Content-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n'
        f'--{boundary}\r\n'
        f'Content-Type: text/plain\r\n\r\n*\r\n'
        f'--{boundary}--'
    )
    upload_resp = requests.post(
        'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
        headers={**headers, 'Content-Type': f'multipart/related; boundary={boundary}'},
        data=body.encode('utf-8'),
        timeout=DRIVE_API_TIMEOUT,
    )
    if upload_resp.status_code not in (200, 201):
        # 마커 생성 실패는 치명적이지 않다 — 최악의 경우 다음 스캔에서 이 캐시 폴더가
        # 잘못 재스캔될 수 있을 뿐, 복사/열람 자체는 계속 진행해도 된다.
        print(f'[RcloneGdriveCopy] .bookoasisignore 마커 생성 실패 (HTTP {upload_resp.status_code}) — 무시하고 계속')


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


def resolve_dest_folder(access_token, dest_path):
    """dest_path(리모트 내부 상대경로)의 폴더 체인을 없으면 생성하며 최종 폴더 id를 반환."""
    folder_id = 'root'
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

        folder_id = resolve_dest_folder(access_token, dest_path)

        return {'success': True, 'account_email': account_email, 'folder_id': folder_id}
    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except requests.RequestException as e:
        return {'success': False, 'error': f'네트워크 오류: {e}'}
    except Exception as e:
        return {'success': False, 'error': f'알 수 없는 오류: {e}'}
