"""SystemHealthService: 계속 실패 중인 백그라운드 작업 경고 기록/해제 테스트 (저장소 = problem_occurrences)."""
import json
import sqlite3
from contextlib import contextmanager

import pytest

from repositories.sqlite import problem_repository as sqlite_repository
from services import problem_service, system_health_service
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL, _migrate_system_health_settings
from services.system_health_service import SystemHealthService, series_summary_health_key


class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def health_db(monkeypatch):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    connection.executescript(_INDEXES_SQL)
    wrapper = NonClosingConnection(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(sqlite_repository.database, 'get_connection', lambda *_a, **_k: wrapper)
    monkeypatch.setattr(sqlite_repository.database, 'connection', fake_connection)
    monkeypatch.setattr(problem_service, 'ProblemRepository', sqlite_repository.ProblemRepository)
    system_health_service._active_cache['at'] = 0.0
    yield connection
    system_health_service._active_cache['at'] = 0.0
    connection.close()


KEY, LABEL = series_summary_health_key('general')


def _fail(message='boom'):
    with pytest.raises(RuntimeError):
        with SystemHealthService.track(KEY, LABEL):
            raise RuntimeError(message)


def _row_count(conn):
    return conn.execute("SELECT COUNT(*) FROM problem_occurrences").fetchone()[0]


def test_success_without_history_writes_nothing(health_db):
    with SystemHealthService.track(KEY, LABEL):
        pass
    assert _row_count(health_db) == 0
    assert SystemHealthService.get_active_warnings() == []


def test_repeated_failures_accumulate_then_clear_on_success(health_db):
    _fail('first')
    _fail("(1048, \"Column 'latest_added' cannot be null\")")

    warnings = SystemHealthService.get_active_warnings()
    assert len(warnings) == 1
    assert warnings[0]['key'] == 'series_summary:general'
    assert warnings[0]['label'] == LABEL
    assert warnings[0]['fail_count'] == 2
    assert 'latest_added' in warnings[0]['message']
    assert warnings[0]['first_failed_at']

    with SystemHealthService.track(KEY, LABEL):
        pass
    assert SystemHealthService.get_active_warnings() == []


def test_failure_after_success_keeps_last_ok_at(health_db):
    _fail()
    with SystemHealthService.track(KEY, LABEL):
        pass
    _fail()
    warning = SystemHealthService.get_active_warnings()[0]
    assert warning['last_ok_at']
    assert warning['fail_count'] == 1


def test_warning_is_a_system_problem_card(health_db):
    _fail()
    cards = problem_service.ProblemService.list_cards()
    assert [c['group_key'] for c in cards] == ['system_task_failed|general|-']
    assert cards[0]['severity'] == 'action_required'


def test_storage_error_never_breaks_caller(health_db, monkeypatch):
    class Broken:
        def __getattr__(self, _name):
            raise OSError('db down')

    monkeypatch.setattr(problem_service, 'ProblemRepository', Broken())
    with SystemHealthService.track(KEY, LABEL):
        pass
    with pytest.raises(RuntimeError):
        with SystemHealthService.track(KEY, LABEL):
            raise RuntimeError('still propagates')
    assert SystemHealthService.get_active_warnings() == []


def test_legacy_settings_rows_are_migrated_and_removed(health_db):
    failed = {'status': 'failed', 'label': LABEL, 'message': 'old failure', 'fail_count': 4}
    ok = {'status': 'ok', 'label': '다른 작업', 'last_ok_at': '2026-09-29T13:00:00+00:00'}
    health_db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('SYSTEM_HEALTH_' + KEY, json.dumps(failed)))
    health_db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('SYSTEM_HEALTH_other', json.dumps(ok)))
    health_db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('SYSTEM_LANG', 'ko'))
    health_db.commit()

    _migrate_system_health_settings(health_db, health_db.cursor(), 'general')

    warnings = SystemHealthService.get_active_warnings()
    assert [(w['key'], w['message']) for w in warnings] == [(KEY, 'old failure')]
    keys = [r[0] for r in health_db.execute("SELECT key FROM settings").fetchall()]
    assert keys == ['SYSTEM_LANG']


def test_legacy_migration_keeps_settings_when_problem_table_unwritable(health_db, monkeypatch):
    failed = {'status': 'failed', 'label': LABEL, 'message': 'old failure'}
    health_db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('SYSTEM_HEALTH_' + KEY, json.dumps(failed)))
    health_db.commit()

    class Broken:
        def __getattr__(self, _name):
            raise OSError('no table')

    monkeypatch.setattr(problem_service, 'ProblemRepository', Broken())
    _migrate_system_health_settings(health_db, health_db.cursor(), 'general')
    assert health_db.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 1
