# -*- coding: utf-8 -*-
"""
cover_storage_service.py – 커버 이미지 저장 루트 경로의 단일 진실 공급원(SSOT).

예전에는 `COVERS_DIR`가 tools/scanner/cover.py, api/stream.py, utils/cover_helper.py 등
15곳 이상에서 각자 `os.path.join(MEDIA_SERVER_DIR, 'covers')`로 독립적으로 재계산되고
있었다. 관리자가 커버 저장 위치를 다른 마운트 경로로 바꿀 수 있게 하려면 그 계산을 한
곳으로 모아야 한다 - 이 모듈이 그 자리다.

설정을 건드리지 않은 사용자는 기존과 완전히 동일한 기본 경로(`<프로젝트 루트>/covers`)를
그대로 쓴다. `SettingsService.get()`은 매 호출마다 DB를 조회하므로(캐시 없음), 스캔 중
파일 단위로 호출되는 `get_covers_dir()`는 반드시 프로세스 내 캐시를 둔다 - 설정을
저장한 직후 `invalidate_cache()`를 호출해 재시작 없이 즉시 반영한다.
"""
import os
import shutil
import threading

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_COVERS_DIR = os.path.join(MEDIA_SERVER_DIR, 'covers')

_dir_cache = None
_ensured_paths = set()
_warned_broken_paths = set()

_migration_lock = threading.Lock()
_migration_status = {'status': 'idle', 'moved': 0, 'total': 0, 'error': None, 'source': None, 'dest': None}


def _resolve():
    try:
        from services.settings_service import SettingsService
        override = str(SettingsService.get('COVER_STORAGE_ROOT', '') or '').strip()
    except Exception as e:
        print(f"[CoverStorageService] COVER_STORAGE_ROOT 설정 조회 실패, 기본 경로 사용: {e}")
        override = ''
    return override if override else DEFAULT_COVERS_DIR


def get_covers_dir():
    """현재 유효한 커버 저장 루트의 절대경로를 반환한다 (없으면 생성).

    설정된 경로가 연결이 끊긴 외장/네트워크 드라이브 등이라 생성이 불가능하면,
    커버 관련 요청 전체가 죽는 것을 막기 위해 이번 호출에 한해 기본 경로로
    안전하게 폴백한다 (설정값 자체는 그대로 둬 드라이브가 다시 연결되면 다음
    호출에서 자동으로 복구된다)."""
    global _dir_cache
    if _dir_cache is None:
        _dir_cache = _resolve()
    if _dir_cache not in _ensured_paths:
        try:
            os.makedirs(_dir_cache, exist_ok=True)
            _ensured_paths.add(_dir_cache)
        except Exception as e:
            if _dir_cache not in _warned_broken_paths:
                print(f"[CoverStorageService] 커버 저장 경로 접근 불가({_dir_cache}), 이번 요청은 기본 경로로 폴백: {e}")
                _warned_broken_paths.add(_dir_cache)
            if DEFAULT_COVERS_DIR not in _ensured_paths:
                os.makedirs(DEFAULT_COVERS_DIR, exist_ok=True)
                _ensured_paths.add(DEFAULT_COVERS_DIR)
            return DEFAULT_COVERS_DIR
    return _dir_cache


def invalidate_cache():
    """COVER_STORAGE_ROOT 설정이 저장된 직후 호출 - 다음 get_covers_dir() 호출부터 새 경로 반영."""
    global _dir_cache
    _dir_cache = None


def get_migration_status():
    with _migration_lock:
        return dict(_migration_status)


def _run_migration(source, dest):
    global _migration_status
    moved = 0
    try:
        for root, dirs, files in os.walk(source):
            rel = os.path.relpath(root, source)
            target_root = dest if rel == '.' else os.path.join(dest, rel)
            os.makedirs(target_root, exist_ok=True)
            for fname in files:
                src_path = os.path.join(root, fname)
                dst_path = os.path.join(target_root, fname)
                if os.path.abspath(src_path) == os.path.abspath(dst_path):
                    continue
                try:
                    shutil.move(src_path, dst_path)
                    moved += 1
                    with _migration_lock:
                        _migration_status['moved'] = moved
                except Exception as move_err:
                    print(f"[CoverStorageService] 이관 실패({src_path} -> {dst_path}): {move_err}")
        with _migration_lock:
            _migration_status['status'] = 'done'
    except Exception as e:
        print(f"[CoverStorageService] 커버 이관 중 오류: {e}")
        with _migration_lock:
            _migration_status['status'] = 'error'
            _migration_status['error'] = str(e)


def start_migration():
    """기존 기본 경로(DEFAULT_COVERS_DIR)에 남아있는 커버 파일을 현재 설정된 커버 저장
    루트로 이관한다. DB의 cover_image 값은 루트 기준 상대경로라 이동만으로 충분하며
    DB 갱신은 필요 없다. 백그라운드 스레드에서 실행되고, get_migration_status()로
    진행상황을 폴링한다. 이미 진행 중이면 (False, 사유)를 반환한다."""
    global _migration_status
    dest = get_covers_dir()
    source = DEFAULT_COVERS_DIR

    if os.path.abspath(source) == os.path.abspath(dest):
        return False, '커버 저장 경로가 기본값과 동일합니다 (이관할 대상이 없습니다). 먼저 다른 경로를 설정하세요.'

    with _migration_lock:
        if _migration_status['status'] == 'running':
            return False, '이미 이관이 진행 중입니다.'
        if not os.path.isdir(source):
            return False, '기본 커버 디렉토리가 존재하지 않습니다 (이관할 파일이 없습니다).'
        total = sum(len(files) for _, _, files in os.walk(source))
        _migration_status = {
            'status': 'running', 'moved': 0, 'total': total,
            'error': None, 'source': source, 'dest': dest,
        }

    thread = threading.Thread(target=_run_migration, args=(source, dest), daemon=True)
    thread.start()
    return True, None
