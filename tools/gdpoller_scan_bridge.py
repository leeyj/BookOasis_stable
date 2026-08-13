# -*- coding: utf-8 -*-
"""
gdpoller_scan_bridge.py - gd-poller(Google Drive 변경 감지 폴러)의 CommandDispatcher가
호출하는 브릿지 스크립트.

gd-poller CommandDispatcher는 설정된 command 뒤에 [action, file|directory, path, removed_path?]를
그대로 argv로 append해서 실행하므로, curl을 직접 command로 쓸 수 없다 (경로가 쿼리스트링이 아닌
위치 인자로 붙어버림). 이 스크립트가 그 argv를 받아 실제 변경된 파일의 "부모 폴더(시리즈 단위)"를
라이브러리 physical_path 기준 상대경로로 변환하고, 짧은 시간 내 동일 폴더 중복 호출을 디바운스한 뒤
BookOasis의 /api/webhook/scan 에 path 파라미터를 실어 호출한다.

사용 예 (gd-poller config.yaml):

    - class: CommandDispatcher
      command: >-
        python3 /path/to/tools/gdpoller_scan_bridge.py
        --base-url http://your-bookoasis-ip:5930
        --token oasis_secure_api_token_1234
        --library-id 25
        --type general
        --root /path/that/gd-poller/sees/as/the/library/root
"""
import argparse
import os
import sys
import time
import hashlib
import tempfile
import urllib.parse
import urllib.request


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='BookOasis 서버 URL (예: http://ip:5930)')
    parser.add_argument('--token', required=True, help='.env의 WEBHOOK_TOKEN 값')
    parser.add_argument('--library-id', required=True, type=int)
    parser.add_argument('--type', default='general', choices=['general', 'adult'])
    parser.add_argument('--root', required=True, help='gd-poller 관점에서의 라이브러리 물리 루트 경로')
    parser.add_argument('--debounce', type=int, default=20, help='동일 폴더 중복 호출 억제 시간(초)')
    parser.add_argument('--timeout', type=int, default=30, help='웹훅 요청 타임아웃(초)')
    parser.add_argument('action')
    parser.add_argument('kind', choices=['file', 'directory'])
    parser.add_argument('path')
    parser.add_argument('removed_path', nargs='?', default=None)
    return parser.parse_args(argv)


def resolve_target_dir(kind, path):
    if kind == 'directory':
        return path
    return os.path.dirname(path)


def to_relative_path(root, target_dir):
    root_norm = os.path.normpath(root)
    target_norm = os.path.normpath(target_dir)
    if target_norm == root_norm:
        return ''
    if not target_norm.startswith(root_norm + os.sep):
        return None
    return os.path.relpath(target_norm, root_norm)


def is_debounced(rel_path, debounce_seconds):
    if debounce_seconds <= 0:
        return False
    state_dir = os.path.join(tempfile.gettempdir(), 'bookoasis_gdpoller_bridge')
    os.makedirs(state_dir, exist_ok=True)
    key = hashlib.sha1(rel_path.encode('utf-8')).hexdigest()
    marker = os.path.join(state_dir, key)
    now = time.time()
    if os.path.exists(marker) and (now - os.path.getmtime(marker)) < debounce_seconds:
        return True
    with open(marker, 'w', encoding='utf-8') as f:
        f.write(rel_path)
    os.utime(marker, (now, now))
    return False


def trigger_scan(base_url, token, library_id, db_type, rel_path, timeout):
    query = urllib.parse.urlencode({
        'token': token,
        'library_id': library_id,
        'type': db_type,
        'path': rel_path,
    })
    url = f"{base_url.rstrip('/')}/api/webhook/scan?{query}"
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode('utf-8', errors='replace')


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    target_dir = resolve_target_dir(args.kind, args.path)
    rel_path = to_relative_path(args.root, target_dir)
    if rel_path is None:
        print(f"[gdpoller_scan_bridge] skip: '{target_dir}' is outside root '{args.root}'")
        return 0

    if is_debounced(rel_path, args.debounce):
        print(f"[gdpoller_scan_bridge] skip (debounced): '{rel_path}'")
        return 0

    try:
        status, body = trigger_scan(args.base_url, args.token, args.library_id, args.type, rel_path, args.timeout)
        print(f"[gdpoller_scan_bridge] scan requested path='{rel_path}' status={status} body={body}")
        return 0 if 200 <= status < 300 else 1
    except Exception as exc:
        print(f"[gdpoller_scan_bridge] request failed for '{rel_path}': {exc}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
