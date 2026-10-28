# -*- coding: utf-8 -*-
"""
scan_refresh_service.py – 큐를 거치지 않는 즉시(동기) 스캔 뒤의 목록 반영

큐 스캔은 끝날 때 scanner_queue가 시리즈 요약 테이블(series_summary) 재생성 + 목록 캐시 무효화를 한다.
그런데 경로 지정 즉시 스캔(/libraries/<id>/scan-path, 시스템 API의 path 스캔, 플러그인 웹뷰 다운로드 등록)은
큐를 거치지 않아 이 처리가 빠져 있었다. 일반 목록(그리드)은 요약 테이블을 먼저 읽고, 요약 테이블은
시간이 지난다고 저절로 갱신되지 않으므로, 새 도서가 검색에는 나오는데 그리드에는 다음 큐 스캔 전까지
보이지 않았다(커뮤니티 제보: Mate의 scan-path 등록).

- 최근 추가/기록 캐시는 즉시 지운다(가볍다).
- 요약 반영과 목록 캐시 무효화는 짧게 모아(DEBOUNCE_SEC) 백그라운드에서 한다 - API 응답을 늦추지 않는다.
- track_direct_scan으로 감싼 스캔은 스캔 전후 스냅샷을 비교해 바뀐 시리즈 줄만 다시 계산한다.
  예전엔 등록마다 전체 재생성(DB 전체 재집계)을 돌려, 웹툰 회차를 연달아 등록하면 재생성이 끊이지 않고
  잠금 대기자까지 쌓여 MariaDB CPU를 계속 썼다(2026-10 커뮤니티 제보). 스냅샷을 못 뜬 경우만 전체 재생성.
- 같은 db_type의 반영은 프로세스 안에서 한 번에 하나만 돈다. 도는 동안 쌓인 요청은 끝난 뒤 한 번에 처리한다.
"""
import os
import threading
import time
from contextlib import contextmanager

DEBOUNCE_SEC = 1.0
# 바뀐 시리즈가 이보다 많으면 줄 단위보다 전체 재생성이 낫다
MAX_INCREMENTAL_KEYS = 500
SUMMARY_DB_TYPES = ('general', 'adult')

_lock = threading.Lock()
_timers = {}
_pending = {}     # db_type -> {'keys': set((library_id, series_key)), 'full': bool}
_running = set()


def _clear_recent_caches(db_type):
    try:
        from utils.redis_helper import redis_delete_pattern
        redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
        redis_delete_pattern(f"cache:history*:{db_type}:*")
    except Exception as e:
        print(f"[ScanRefresh] recent cache clear failed ({db_type}): {e}")


def rebuild_series_views(db_type, keys=None):
    """요약 반영 + 목록 캐시 무효화 (웹/워커 프로세스 모두 공유 epoch로 감지).
    keys가 주어지면 그 시리즈 줄만, None이면(또는 줄 단위 갱신이 거절되면) 전체 재생성."""
    from repositories.series_repository import SeriesRepository
    from services.series_service import SeriesService
    from services.system_health_service import SystemHealthService, series_summary_health_key
    try:
        if db_type in SUMMARY_DB_TYPES:
            started = time.perf_counter()
            with SystemHealthService.track(*series_summary_health_key(db_type)):
                refreshed = None
                if keys is not None and not keys:
                    refreshed = 0  # 시리즈에 영향 없는 스캔(같은 파일 재스캔 등) - 캐시만 무효화
                elif keys is not None and len(keys) <= MAX_INCREMENTAL_KEYS:
                    refreshed = SeriesRepository.refresh_summary_keys(db_type, sorted(keys))
                if refreshed is not None:
                    print(f"[ScanRefresh] series summary keys refreshed after direct scan: db={db_type}, "
                          f"keys={refreshed}, elapsed_ms={(time.perf_counter() - started) * 1000:.1f}")
                else:
                    rebuilt = SeriesRepository.rebuild_summary(db_type)
                    print(f"[ScanRefresh] series summary {'rebuilt' if rebuilt else 'rebuild skipped (already fresh)'} "
                          f"after direct scan: db={db_type}, elapsed_ms={(time.perf_counter() - started) * 1000:.1f}")
    except Exception as e:
        print(f"[ScanRefresh] series summary refresh failed ({db_type}): {e}")
    finally:
        SeriesService.invalidate_all_books_cache(db_type=db_type)


def _run(db_type):
    with _lock:
        _timers.pop(db_type, None)
        if db_type in _running:
            return  # 도는 쪽이 끝난 뒤 쌓인 요청을 이어서 처리한다
        _running.add(db_type)
    try:
        while True:
            with _lock:
                job = _pending.pop(db_type, None)
                if job is None:
                    _running.discard(db_type)
                    return
            rebuild_series_views(db_type, None if job['full'] else job['keys'])
    except BaseException:
        with _lock:
            _running.discard(db_type)
        raise


def refresh_after_direct_scan(db_type, keys=None):
    """즉시 스캔이 끝난 뒤 부른다. 같은 db_type 요청이 DEBOUNCE_SEC 안에 또 오면 한 번으로 모은다.
    keys: 바뀐 (library_id, series_key) 집합. None이면 전체 재생성."""
    db_type = str(db_type or 'general')
    _clear_recent_caches(db_type)
    with _lock:
        job = _pending.setdefault(db_type, {'keys': set(), 'full': False})
        if keys is None:
            job['full'] = True
        else:
            job['keys'].update(keys)
        timer = _timers.get(db_type)
        if timer is not None:
            timer.cancel()
        timer = threading.Timer(DEBOUNCE_SEC, _run, args=(db_type,))
        timer.daemon = True
        _timers[db_type] = timer
        timer.start()


def _scope_prefix(target_path):
    # scan_library_path와 같은 범위: 파일이면 그 폴더를 스캔한다
    from tools.scanner.path_utils import canonical_path
    path = str(target_path or '').strip()
    if os.path.isfile(path):
        path = os.path.dirname(path)
    return canonical_path(path)


def _snapshot(db_type, library_id, prefix):
    try:
        from repositories.series_repository import SeriesRepository
        return SeriesRepository.fetch_series_snapshot(db_type, library_id, prefix)
    except Exception as e:
        print(f"[ScanRefresh] series snapshot failed ({db_type}, library={library_id}): {e}")
        return None


def changed_series_keys(library_id, before, after):
    """스냅샷 두 개에서 값이 달라진 도서의 옛/새 시리즈 키."""
    keys = set()
    for book_id in set(before) | set(after):
        old, new = before.get(book_id), after.get(book_id)
        if old != new:
            if old:
                keys.add((library_id, old[0]))
            if new:
                keys.add((library_id, new[0]))
    return keys


@contextmanager
def track_direct_scan(db_type, library_id, target_path):
    """즉시 스캔을 감싼다: 스캔 전후 스냅샷으로 바뀐 시리즈만 골라 목록 반영을 예약한다.
    스캔이 예외로 끝나면 반영하지 않는다(기존 동작과 같음)."""
    from utils.drive_helper import is_gdrive_url
    db_type = str(db_type or 'general')
    before = prefix = None
    if db_type in SUMMARY_DB_TYPES and not is_gdrive_url(str(target_path or '')):
        prefix = _scope_prefix(target_path)
        before = _snapshot(db_type, library_id, prefix)
    yield
    keys = None
    if before is not None:
        after = _snapshot(db_type, library_id, prefix)
        if after is not None:
            keys = changed_series_keys(library_id, before, after)
    refresh_after_direct_scan(db_type, keys=keys)
