"""스캐너 워커 기동 정책 (core.should_enable_embedded_scanner_worker / ensure_scanner_worker_running).

전용 워커 운영(Docker entrypoint, manage.sh, systemd)에서 작업 등록이 웹 쪽 워커를 하나 더 띄워
같은 작업을 두 번 처리하던 문제(2026-10 이슈)의 회귀 테스트.
"""
import importlib
import os
import sys

import pytest


@pytest.fixture
def core(monkeypatch):
    # core는 import만 해도 웹 앱을 만든다 - 워커 모드로 불러와 앱 생성을 건너뛴다.
    if 'core' not in sys.modules:
        monkeypatch.setenv('BOOKOASIS_IS_WORKER', 'true')
        importlib.import_module('core')
    module = sys.modules['core']
    monkeypatch.setattr(module, 'IS_WORKER', False)
    monkeypatch.setattr(sys, 'argv', ['gunicorn'])
    monkeypatch.setattr(module, '_worker_process', None)
    module._dedicated_check_state.update(pending=False, last_at=0.0)
    module._real_schedule = module.schedule_dedicated_worker_check
    calls = {'spawn': 0, 'scan': 0, 'check': 0}
    monkeypatch.setattr(module, 'start_scanner_worker_process', lambda: calls.__setitem__('spawn', calls['spawn'] + 1))

    def fake_presence():
        calls['scan'] += 1
        return False
    monkeypatch.setattr(module, '_scanner_worker_presence', fake_presence)
    monkeypatch.setattr(module, 'schedule_dedicated_worker_check',
                        lambda: calls.__setitem__('check', calls['check'] + 1))
    module._test_calls = calls
    return module


@pytest.mark.parametrize('env, in_docker, expected', [
    ({}, True, False),                                              # Docker 기본: 끔 (entrypoint가 전용 워커)
    ({}, False, True),                                              # 비 Docker 기본: 켬 (기존 동작)
    ({'BOOKOASIS_ENABLE_EMBEDDED_WORKER': 'true'}, True, True),     # 명시값 우선
    ({'BOOKOASIS_ENABLE_EMBEDDED_WORKER': 'false'}, False, False),
    ({'BOOKOASIS_ENABLE_EMBEDDED_WORKER': ' OFF '}, False, False),
    ({'BOOKOASIS_ENABLE_EMBEDDED_WORKER': 'maybe'}, True, False),   # 알 수 없는 값은 미지정과 같다
])
def test_embedded_worker_policy(core, env, in_docker, expected):
    assert core.should_enable_embedded_scanner_worker(environ=env, in_docker=in_docker) is expected


def test_disabled_policy_never_searches_or_spawns(core, monkeypatch):
    monkeypatch.setenv('BOOKOASIS_ENABLE_EMBEDDED_WORKER', 'false')
    core.ensure_scanner_worker_running()
    assert core._test_calls == {'spawn': 0, 'scan': 0, 'check': 1}  # 잠시 뒤 생존 확인만 예약


def test_enabled_policy_keeps_auto_restart(core, monkeypatch):
    monkeypatch.setenv('BOOKOASIS_ENABLE_EMBEDDED_WORKER', 'true')
    core.ensure_scanner_worker_running()
    assert core._test_calls['spawn'] == 1 and core._test_calls['check'] == 0


def test_enabled_policy_does_not_spawn_when_worker_exists(core, monkeypatch):
    monkeypatch.setenv('BOOKOASIS_ENABLE_EMBEDDED_WORKER', 'true')
    monkeypatch.setattr(core, '_scanner_worker_presence', lambda: True)
    core.ensure_scanner_worker_running()
    assert core._test_calls['spawn'] == 0


def test_enqueue_inside_worker_process_does_nothing(core, monkeypatch):
    monkeypatch.setenv('BOOKOASIS_ENABLE_EMBEDDED_WORKER', 'true')
    monkeypatch.setattr(sys, 'argv', ['/app/tools/scanner_worker.py'])
    core.ensure_scanner_worker_running()
    assert core._test_calls == {'spawn': 0, 'scan': 0, 'check': 0}


class _FakeHealth:
    events = []

    @classmethod
    def record_success(cls, key):
        cls.events.append(('ok', key))

    @classmethod
    def record_failure(cls, key, label, error):
        cls.events.append(('fail', key))


@pytest.mark.parametrize('presence, expected', [(True, [('ok', 'scanner_worker:dedicated')]),
                                                 (False, [('fail', 'scanner_worker:dedicated')]),
                                                 (None, [])])  # 확인 불가(psutil 없음)면 경고하지 않는다
def test_dedicated_worker_check_reports_to_health(core, monkeypatch, presence, expected):
    import services.system_health_service as health
    _FakeHealth.events = []
    monkeypatch.setattr(health, 'SystemHealthService', _FakeHealth)
    monkeypatch.setattr(core, '_scanner_worker_presence', lambda: presence)
    core._check_dedicated_worker_alive()
    assert _FakeHealth.events == expected


def test_dedicated_check_is_deduplicated_not_rate_limited(core, monkeypatch):
    import threading
    import time
    started = []

    class FakeTimer:
        def __init__(self, delay, fn):
            started.append(delay)
            self.daemon = False

        def start(self):
            pass

    monkeypatch.setattr(threading, 'Timer', FakeTimer)
    schedule = core._real_schedule
    schedule()
    schedule()                       # 이미 예약됨 → 무시
    assert started == [core._DEDICATED_WORKER_CHECK_DELAY]
    # 확인이 막 끝난 직후라도(워커가 그 사이 죽었을 수 있다) 다음 등록은 다시 확인한다
    core._dedicated_check_state.update(pending=False, last_at=time.time())
    schedule()
    assert len(started) == 2
