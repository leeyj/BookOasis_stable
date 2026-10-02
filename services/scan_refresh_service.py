# -*- coding: utf-8 -*-
"""
scan_refresh_service.py – 큐를 거치지 않는 즉시(동기) 스캔 뒤의 목록 반영

큐 스캔은 끝날 때 scanner_queue가 시리즈 요약 테이블(series_summary) 재생성 + 목록 캐시 무효화를 한다.
그런데 경로 지정 즉시 스캔(/libraries/<id>/scan-path, 시스템 API의 path 스캔, 플러그인 웹뷰 다운로드 등록)은
큐를 거치지 않아 이 처리가 빠져 있었다. 일반 목록(그리드)은 요약 테이블을 먼저 읽고, 요약 테이블은
시간이 지난다고 저절로 갱신되지 않으므로, 새 도서가 검색에는 나오는데 그리드에는 다음 큐 스캔 전까지
보이지 않았다(커뮤니티 제보: Mate의 scan-path 등록).

- 최근 추가/기록 캐시는 즉시 지운다(가볍다).
- 요약 재생성(DB 전체 재집계, 수십만 권이면 1초 이상)과 목록 캐시 무효화는 짧게 모아(DEBOUNCE_SEC)
  백그라운드에서 한 번 한다 - 여러 권을 연달아 등록해도 매번 다시 만들지 않고, API 응답을 늦추지 않는다.
"""
import threading
import time

DEBOUNCE_SEC = 1.0

_lock = threading.Lock()
_timers = {}


def _clear_recent_caches(db_type):
    try:
        from utils.redis_helper import redis_delete_pattern
        redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
        redis_delete_pattern(f"cache:history*:{db_type}:*")
    except Exception as e:
        print(f"[ScanRefresh] recent cache clear failed ({db_type}): {e}")


def rebuild_series_views(db_type):
    """요약 테이블 재생성 + 목록 캐시 무효화 (웹/워커 프로세스 모두 공유 epoch로 감지)."""
    from repositories.series_repository import SeriesRepository
    from services.series_service import SeriesService
    from services.system_health_service import SystemHealthService, series_summary_health_key
    try:
        if db_type in ('general', 'adult'):
            started = time.perf_counter()
            with SystemHealthService.track(*series_summary_health_key(db_type)):
                SeriesRepository.rebuild_summary(db_type)
            print(f"[ScanRefresh] series summary rebuilt after direct scan: db={db_type}, "
                  f"elapsed_ms={(time.perf_counter() - started) * 1000:.1f}")
    except Exception as e:
        print(f"[ScanRefresh] series summary rebuild failed ({db_type}): {e}")
    finally:
        SeriesService.invalidate_all_books_cache(db_type=db_type)


def _run(db_type):
    with _lock:
        _timers.pop(db_type, None)
    rebuild_series_views(db_type)


def refresh_after_direct_scan(db_type):
    """즉시 스캔이 끝난 뒤 부른다. 같은 db_type 요청이 DEBOUNCE_SEC 안에 또 오면 한 번으로 모은다."""
    db_type = str(db_type or 'general')
    _clear_recent_caches(db_type)
    with _lock:
        timer = _timers.get(db_type)
        if timer is not None:
            timer.cancel()
        timer = threading.Timer(DEBOUNCE_SEC, _run, args=(db_type,))
        timer.daemon = True
        _timers[db_type] = timer
        timer.start()
