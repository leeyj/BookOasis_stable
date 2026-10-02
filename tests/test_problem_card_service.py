"""문제 카드 상세 조회(services/problem_card_service.py) - 실제 SQLite 스키마, 메모리 DB."""
import sqlite3
from contextlib import contextmanager

import pytest

import database
from repositories.sqlite import problem_repository as sqlite_repository
from services import problem_card_service as pcs
from services import problem_service
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL
from services.problem_service import ProblemService, make_series_key


class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def db(monkeypatch):
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
    monkeypatch.setattr(pcs, '_library_roots', lambda _db, _lib: ['/lib/만화'])
    connection.execute("INSERT INTO libraries (id, name, physical_path) VALUES (80, '만화', '/lib/만화')")
    for i in range(1, 6):
        connection.execute("INSERT INTO books (id, library_id, title, series_name, file_path, file_format, total_pages) VALUES (?, 80, ?, '원피스', ?, 'zip', 0)",
                           (i, f'원피스 {i}권', f'/lib/만화/원피스/{i}.zip'))
    connection.execute("INSERT INTO books (id, library_id, title, series_name, file_path, file_format, total_pages) VALUES (9, 80, '단편', '단편', '/lib/만화/단편/a.zip', 'zip', 0)")
    connection.commit()
    yield connection
    connection.close()


def _missing(book_id, series, path):
    ProblemService.report('mass_missing', 'book', book_id, library_id=80, target_path=path,
                          series_key=make_series_key(80, series))


def test_relative_scan_path():
    assert pcs.relative_scan_path(['/lib/만화'], '/lib/만화/원피스') == '원피스'
    assert pcs.relative_scan_path(['/lib/만화/'], '/lib/만화') == ''
    assert pcs.relative_scan_path(['/lib/만화'], '/elsewhere/x') is None
    assert pcs.relative_scan_path([r'C:\lib'], r'C:\lib\a\b') == 'a/b'


def test_card_lines_and_items(db):
    for i in (1, 2, 3):
        _missing(i, '원피스', f'/lib/만화/원피스/{i}.zip')
    _missing(9, '단편', '/lib/만화/단편/a.zip')
    data = pcs.get_card('mass_missing|general|80')
    lines = {l['series_name']: l for l in data['lines']}
    assert lines['원피스']['open_count'] == 3 and lines['원피스']['series_total'] == 5
    assert lines['원피스']['scan_path'] == '원피스'
    assert lines['단편']['open_count'] == 1 and lines['단편']['series_total'] == 1
    assert lines['단편']['single_target_id'] == '9'

    page = pcs.get_card_items('mass_missing|general|80', series_key='80|원피스', limit=2)
    assert page['total'] == 3 and len(page['items']) == 2
    assert page['items'][0]['title'].startswith('원피스') and page['items'][0]['scan_path'] == '원피스'


def test_resolved_card_returns_none(db):
    assert pcs.get_card('mass_missing|general|80') is None
    assert pcs.get_card_items('mass_missing|general|80') is None
