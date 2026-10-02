"""도서 [진단](services/book_diagnosis_service.py) + [관리자에게 알리기](services/user_problem_report_service.py)
+ 카드 [해결됨] - 알림센터 5단계. 실제 SQLite 스키마(메모리 DB) + 임시 폴더의 실제 파일."""
import sqlite3
import threading
import zipfile
from contextlib import contextmanager

import pytest

import database
from repositories.sqlite import problem_repository as sqlite_repository
from services import book_diagnosis_service as bds
from services import problem_service
from services import user_problem_report_service as ups
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL
from services.problem_service import ProblemService


class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def env(monkeypatch, tmp_path):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    connection.executescript(_INDEXES_SQL)
    wrapper = NonClosingConnection(connection)

    @contextmanager
    def fake_connection(*_a, **_k):
        yield wrapper

    monkeypatch.setattr(database, 'get_connection', lambda *_a, **_k: wrapper)
    monkeypatch.setattr(database, 'connection', fake_connection)
    monkeypatch.setattr(problem_service, 'ProblemRepository', sqlite_repository.ProblemRepository)
    import repositories.problem_repository as facade
    monkeypatch.setattr(facade, 'ProblemRepository', sqlite_repository.ProblemRepository)

    root = tmp_path / 'lib'
    series = root / '원피스'
    series.mkdir(parents=True)
    with zipfile.ZipFile(series / 'good.zip', 'w') as z:
        z.writestr('001.jpg', b'x')
    with zipfile.ZipFile(series / 'back.zip', 'w') as z:
        z.writestr('001.jpg', b'x')
    (series / 'broken.zip').write_bytes(b'not a zip at all')
    (series / 'empty.zip').write_bytes(b'')
    lib = {'id': 80, 'name': '만화', 'physical_path': str(root)}
    monkeypatch.setattr(bds, '_library', lambda _db, lib_id: lib if lib_id == 80 else None)

    connection.execute("INSERT INTO libraries (id, name, physical_path) VALUES (80, '만화', ?)", (str(root),))
    rows = [
        (1, 'good', series / 'good.zip', 0, None),
        (2, 'broken', series / 'broken.zip', 0, None),
        (3, 'gone', series / 'gone.zip', 0, None),
        (4, 'empty', series / 'empty.zip', 0, None),
        (5, 'trashed gone', series / 'old.zip', 1, '2026-09-01 10:00:00'),
        (6, 'trashed back', series / 'back.zip', 1, '2026-09-30 10:00:00'),
    ]
    for book_id, title, path, deleted, at in rows:
        connection.execute(
            "INSERT INTO books (id, library_id, title, series_name, file_path, file_format, total_pages, is_deleted, deleted_at) "
            "VALUES (?, 80, ?, '원피스', ?, 'zip', 0, ?, ?)", (book_id, title, str(path), deleted, at))
    connection.commit()
    ups._recent.clear()
    yield {'conn': connection, 'root': root}
    connection.close()


def _statuses(result):
    return {c['id']: c['status'] for c in result['checks']}


def test_healthy_book(env):
    r = bds.diagnose_book('general', 1)
    assert _statuses(r) == {'db': 'ok', 'remote': 'ok', 'file': 'ok', 'format': 'ok'}
    assert r['conclusion']['key'] == 'diagnose.result.healthy' and r['actions'] == []
    assert r['book']['library'] == '만화'


def test_corrupt_and_empty_files_suggest_rescanning_the_book(env):
    broken = bds.diagnose_book('general', 2)
    assert _statuses(broken)['format'] == 'fail'
    assert broken['conclusion']['key'] == 'diagnose.result.file_corrupt'
    assert broken['actions'] == [{'id': 'rescan_book', 'book_id': 2}]
    empty = bds.diagnose_book('general', 4)
    assert _statuses(empty)['file'] == 'fail' and empty['conclusion']['key'] == 'diagnose.result.file_corrupt'


def test_missing_file_suggests_folder_rescan(env):
    r = bds.diagnose_book('general', 3)
    assert _statuses(r)['file'] == 'fail'
    assert r['conclusion']['key'] == 'diagnose.result.file_moved'
    assert r['actions'] == [{'id': 'rescan_path', 'library_id': 80, 'scan_path': '원피스'}]


def test_trashed_books(env):
    gone = bds.diagnose_book('general', 5)
    assert _statuses(gone)['db'] == 'warn'
    assert gone['checks'][0]['vars'] == {'purge': '2026-09-08'}
    assert gone['conclusion']['key'] == 'diagnose.result.trashed_missing'
    back = bds.diagnose_book('general', 6)
    assert back['conclusion']['key'] == 'diagnose.result.trashed_but_present'
    assert back['actions'][0]['id'] == 'rescan_path'


def test_unreachable_root_stops_before_file_checks(env):
    # 마운트가 끊기면 빈 폴더로 보인다
    for p in sorted(env['root'].rglob('*'), reverse=True):
        if p.is_file():
            p.unlink()
        else:
            p.rmdir()
    r = bds.diagnose_book('general', 1)
    assert _statuses(r) == {'db': 'ok', 'remote': 'fail'}
    assert r['conclusion']['key'] == 'diagnose.result.remote_unavailable' and r['actions'] == []


def test_slow_drive_times_out_instead_of_hanging(env, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(bds, 'FS_TIMEOUT_SECONDS', 0.2)
    monkeypatch.setattr('services.scan_problem_service.check_roots', lambda _p: gate.wait(5))
    try:
        r = bds.diagnose_book('general', 1)
    finally:
        gate.set()
    assert r['checks'][-1]['key'] == 'diagnose.check.remote.timeout'
    assert r['conclusion']['key'] == 'diagnose.result.remote_slow'


def test_unknown_book_and_unsupported_type(env):
    r = bds.diagnose_book('general', 999)
    assert r['book'] is None and r['conclusion']['key'] == 'diagnose.result.no_record'
    with pytest.raises(ValueError):
        bds.diagnose_book('video', 1)


def test_open_problems_are_listed(env):
    ProblemService.report('cover_missing', 'book', 1, library_id=80, target_path='x')
    r = bds.diagnose_book('general', 1)
    assert [p['code'] for p in r['problems']] == ['cover_missing']
    assert r['conclusion']['key'] == 'diagnose.result.healthy_with_problems'


# ---- [관리자에게 알리기] ----

def _report(user_id=7, role='user', book_id=1, db_type='general'):
    return ups.report_book_problem(user_id=user_id, username='kid', role=role, db_type=db_type,
                                   book_id=book_id, message='Failed to load image')


def _user_report_rows(env):
    return env['conn'].execute("SELECT * FROM problem_occurrences WHERE code = 'user_report'").fetchall()


def test_user_report_needs_category_permission(env):
    with pytest.raises(ups.ReportRejected) as e:
        _report()
    assert e.value.status == 404 and _user_report_rows(env) == []
    env['conn'].execute("INSERT INTO user_category_permissions (user_id, library_id, has_access) VALUES (7, 80, 1)")
    assert _report()['title'] == 'good'
    row = _user_report_rows(env)[0]
    assert (row['source'], row['severity'], row['group_key'], row['series_key']) == \
        ('viewer', 'notice', 'user_report|general|80', '80|원피스')
    assert row['message'] == 'Failed to load image' and '"reporter": "kid"' in row['context']


def test_repeat_report_only_counts_and_card_resolves(env):
    _report(role='admin')
    _report(role='admin')
    rows = _user_report_rows(env)
    assert len(rows) == 1 and rows[0]['occurrence_count'] == 2
    cards = {c['group_key']: c for c in ProblemService.list_cards()}
    assert cards['user_report|general|80']['actions'] == ['resolve']
    assert ProblemService.resolve_card('user_report|general|80') == 1
    assert 'user_report|general|80' not in {c['group_key'] for c in ProblemService.list_cards()}


def test_scanner_cards_cannot_be_resolved_by_hand(env):
    with pytest.raises(ValueError):
        ProblemService.resolve_card('file_missing|general|80')


def test_report_throttle_and_validation(env, monkeypatch):
    monkeypatch.setattr(ups, 'REPORTS_PER_HOUR', 2)
    _report(role='admin')
    _report(role='admin')
    with pytest.raises(ups.ReportRejected) as e:
        _report(role='admin')
    assert e.value.status == 429
    with pytest.raises(ups.ReportRejected):
        _report(role='admin', db_type='video')
    with pytest.raises(ups.ReportRejected):
        _report(role='admin', book_id='abc')
