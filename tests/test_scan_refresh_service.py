"""큐를 거치지 않는 즉시 스캔(scan-path 등) 뒤에도 그리드(시리즈 요약 테이블)에 새 도서가 반영되는가.

커뮤니티 제보: Mate가 scan-path로 등록한 도서가 검색에는 나오는데 그리드에는 1시간이 지나도 안 보였다.
요약 테이블 재생성/목록 캐시 무효화가 큐 완료 처리에만 있었기 때문.
"""
import time
from unittest.mock import patch

from flask import Flask

from api.routes.scan_routes import scan_bp
from services import scan_refresh_service as refresh


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_direct_scan_clears_recent_caches_now_and_rebuilds_the_summary_shortly_after(monkeypatch):
    monkeypatch.setattr(refresh, 'DEBOUNCE_SEC', 0.05)
    deleted, rebuilt = [], []
    monkeypatch.setattr('utils.redis_helper.redis_delete_pattern', deleted.append)
    monkeypatch.setattr(refresh, 'rebuild_series_views', rebuilt.append)

    refresh.refresh_after_direct_scan('general')

    assert deleted == ['cache:recent_added*:general:*', 'cache:history*:general:*']
    assert _wait_until(lambda: rebuilt == ['general'])


def test_back_to_back_direct_scans_rebuild_once(monkeypatch):
    monkeypatch.setattr(refresh, 'DEBOUNCE_SEC', 0.1)
    monkeypatch.setattr('utils.redis_helper.redis_delete_pattern', lambda _p: None)
    rebuilt = []
    monkeypatch.setattr(refresh, 'rebuild_series_views', rebuilt.append)

    for _ in range(5):
        refresh.refresh_after_direct_scan('general')
    refresh.refresh_after_direct_scan('adult')

    assert _wait_until(lambda: sorted(rebuilt) == ['adult', 'general'])
    time.sleep(0.2)
    assert sorted(rebuilt) == ['adult', 'general']


def test_rebuild_series_views_rebuilds_book_sessions_and_always_invalidates(monkeypatch):
    calls = []
    monkeypatch.setattr('repositories.series_repository.SeriesRepository.rebuild_summary',
                        lambda db_type, **_k: calls.append(('rebuild', db_type)))
    monkeypatch.setattr('services.series_service.SeriesService.invalidate_all_books_cache',
                        lambda db_type=None: calls.append(('invalidate', db_type)))
    monkeypatch.setattr('services.system_health_service.SystemHealthService.record_success', lambda *a, **k: None)

    refresh.rebuild_series_views('general')
    refresh.rebuild_series_views('video')

    assert calls == [('rebuild', 'general'), ('invalidate', 'general'), ('invalidate', 'video')]


def test_scan_path_route_refreshes_the_grid():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-scan-refresh')
    app.register_blueprint(scan_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['role'] = 'admin'
        session['is_default_password'] = 0

    with patch('repositories.category_repository.CategoryRepository.get_library_by_id',
               return_value={'id': 3, 'physical_path': '/books'}), \
            patch('api.routes.scan_routes._resolve_library_scoped_path', return_value='/books/New Series'), \
            patch('tools.scanner.core.scan_library_path') as scan, \
            patch('services.scan_refresh_service.refresh_after_direct_scan') as refresh_call:
        response = client.post('/api/media/libraries/3/scan-path', data={'type': 'general', 'path': 'New Series'})

    assert response.status_code == 200 and response.get_json()['success'] is True
    scan.assert_called_once()
    refresh_call.assert_called_once_with('general')
