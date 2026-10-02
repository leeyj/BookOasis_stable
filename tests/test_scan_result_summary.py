"""스캔 결과 요약(scan_history.result_summary) + 트리거 출처 기록 테스트 (알림센터 2단계)."""
import json
import sqlite3
import types
from unittest.mock import Mock, patch

import pytest

from repositories.sqlite import scanner_queue_repository as sqlite_queue_module
from services import scanner_queue as scanner_queue_module
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL, parse_schema_columns
from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA
from test_scanner_stale_update_recovery import _ScanFixture

Repo = sqlite_queue_module.ScannerQueueRepository


class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def queue_db(monkeypatch):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    connection.executescript(_INDEXES_SQL)
    wrapper = NonClosingConnection(connection)
    monkeypatch.setattr(sqlite_queue_module.database, 'get_connection', lambda *_a, **_k: wrapper)
    yield connection
    connection.close()


def _insert_task(conn, task_type='library_scan', kwargs=None):
    kwargs = kwargs or {'db_type': 'general', 'library_id': 80, 'trigger_type': 'manual', 'is_cron': False}
    cur = conn.execute(
        "INSERT INTO scanner_tasks (task_type, task_key, status, kwargs, enqueue_at, started_at) "
        "VALUES (?, ?, 'running', ?, '2026-10-02 10:00:00', '2026-10-02 10:00:01')",
        (task_type, f'{task_type}_general_80', json.dumps(kwargs)),
    )
    conn.commit()
    return cur.lastrowid


# ---- 스키마 ----

def test_result_summary_column_exists_for_both_engines():
    assert 'result_summary' in dict(parse_schema_columns(_SCHEMA_SQL)['scan_history'])
    ddl = MARIADB_CENTRAL_SCHEMA.split('CREATE TABLE IF NOT EXISTS scan_history', 1)[1].split(';', 1)[0]
    assert 'result_summary' in ddl


# ---- 리포지토리 ----

def test_update_task_result_records_summary_in_history(queue_db):
    task_id = _insert_task(queue_db)
    summary = {'new_books': 3, 'errors': 1, 'report_file': '80_20261002100000.json'}
    assert Repo.update_task_result(task_id, '2026-10-02 10:05:00', None, result_summary=summary)
    row = queue_db.execute("SELECT status, result_summary FROM scan_history").fetchone()
    assert row['status'] == 'completed'
    assert json.loads(row['result_summary']) == summary
    assert queue_db.execute("SELECT COUNT(*) FROM scanner_tasks").fetchone()[0] == 0

    history = Repo.get_scan_history()
    assert history[0]['result_summary'] == summary
    assert history[0]['trigger_type'] == 'manual'


def test_history_without_summary_stays_null(queue_db):
    task_id = _insert_task(queue_db)
    Repo.update_task_result(task_id, '2026-10-02 10:05:00', 'boom')
    row = queue_db.execute("SELECT status, result_summary FROM scan_history").fetchone()
    assert row['status'] == 'failed' and row['result_summary'] is None
    assert Repo.get_scan_history()[0]['result_summary'] is None


def test_purge_scan_history_keeps_recent_rows(queue_db):
    queue_db.execute("INSERT INTO scan_history (task_type, status, created_at) VALUES ('library_scan', 'completed', datetime('now', '-91 days'))")
    queue_db.execute("INSERT INTO scan_history (task_type, status, created_at) VALUES ('library_scan', 'completed', datetime('now', '-89 days'))")
    queue_db.commit()
    assert Repo.purge_scan_history(90) == 1
    assert queue_db.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0] == 1


# ---- 엔진 → 요약 ----

class EngineSummaryTests(_ScanFixture):
    def test_new_book_is_counted_in_summary(self):
        summary = {}
        conn = self._connect()
        self.addCleanup(conn.close)
        from tools.scanner import engine
        with patch.object(engine, 'process_folder_task', side_effect=self._fake_task()):
            engine._scan_library_internal(
                conn, self.db_path, 1, self.lib_root, False, 'general',
                [self.lib_root], False, 1, [], result_summary=summary,
            )
        self.assertEqual(summary, {'new_books': 1, 'errors': 0, 'report_file': None})

    def test_rescan_of_existing_book_reports_no_new_books(self):
        self._insert_existing()
        summary = {}
        conn = self._connect()
        self.addCleanup(conn.close)
        from tools.scanner import engine
        with patch.object(engine, 'process_folder_task', side_effect=self._fake_task()):
            engine._scan_library_internal(
                conn, self.db_path, 1, self.lib_root, True, 'general',
                [self.lib_root], False, 1, [], result_summary=summary,
            )
        self.assertEqual(summary['new_books'], 0)


def test_core_saves_report_only_when_engine_did_not():
    from tools.scanner import core
    with patch('utils.report_helper.save_scan_report', return_value='80_x.json') as save:
        done = {'new_books': 0, 'errors': 2, 'report_file': '80_engine.json'}
        core._save_report_unless_saved(80, [{'e': 1}, {'e': 2}], done)
        save.assert_not_called()
        aborted = {'new_books': 4}
        core._save_report_unless_saved(80, [{'e': 1}], aborted)
        save.assert_called_once()
        assert aborted == {'new_books': 4, 'report_file': '80_x.json', 'errors': 1}


# ---- 선택 도서 스캔 요약 ----

def _batch_modules(scan):
    book_repository_module = types.ModuleType('repositories.book_scan_repository')
    book_repository_module.BookScanRepository = types.SimpleNamespace(
        get_book_basic_info_raw=lambda _db, book_id: {'title': f'책 {book_id}'}
    )
    book_scan_module = types.ModuleType('services.book_scan_service')
    book_scan_module.BookScanService = types.SimpleNamespace(scan_single_book=scan)
    queue_repository_module = types.ModuleType('repositories.scanner_queue_repository')
    queue_repository_module.ScannerQueueRepository = types.SimpleNamespace(update_task_stage=Mock())
    return {
        'repositories.book_scan_repository': book_repository_module,
        'services.book_scan_service': book_scan_module,
        'repositories.scanner_queue_repository': queue_repository_module,
    }


def test_batch_scan_returns_summary():
    scan = Mock(return_value=(True, '완료', None))
    with patch.dict('sys.modules', _batch_modules(scan)):
        summary = scanner_queue_module._process_batch_book_scan(Mock(), 1, db_type='general', book_ids=[1, 2], trigger_type='manual')
    assert summary == {'books': 2, 'succeeded': 2, 'errors': 0}


def test_batch_scan_failure_carries_summary_on_exception():
    scan = Mock(side_effect=[(True, '완료', None), (False, '파일 없음', None)])
    with patch.dict('sys.modules', _batch_modules(scan)):
        with pytest.raises(RuntimeError) as info:
            scanner_queue_module._process_batch_book_scan(Mock(), 1, db_type='general', book_ids=[1, 2])
    assert info.value.result_summary == {'books': 2, 'succeeded': 1, 'errors': 1}


# ---- 트리거 출처 ----

def test_cover_and_gdrive_runners_ignore_trigger_kwarg():
    cover = types.ModuleType('services.cover_scan_service')
    cover.CoverScanService = types.SimpleNamespace(run_cover_scan_job=Mock())
    gdrive = types.ModuleType('services.gdrive_copy_service')
    gdrive.GdriveCopyService = types.SimpleNamespace(run_gdrive_copy_job=Mock())
    with patch.dict('sys.modules', {'services.cover_scan_service': cover, 'services.gdrive_copy_service': gdrive}):
        scanner_queue_module._process_cover_scan(Mock(), db_type='general', db_path='x', library_id=1,
                                                 physical_path='/p', trigger_type='manual')
        scanner_queue_module._process_gdrive_copy(Mock(), 5, db_type='general', trigger_type='manual')
    assert 'trigger_type' not in cover.CoverScanService.run_cover_scan_job.call_args.kwargs
    assert 'trigger_type' not in gdrive.GdriveCopyService.run_gdrive_copy_job.call_args.kwargs


def test_scheduled_lazy_scan_is_marked_lazy():
    from services import scheduler_service
    with patch.object(scanner_queue_module.scanner_queue, 'enqueue') as enqueue:
        scheduler_service.run_lazy_scanner_job()
    enqueue.assert_called_once_with('lazy_scan', trigger_type='lazy')
