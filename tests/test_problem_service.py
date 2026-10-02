"""문제 기록(problem_occurrences/problem_groups) 리포지토리·서비스 테스트 - 실제 SQLite 스키마, 메모리 DB."""
import sqlite3
from contextlib import contextmanager

import pytest

from repositories.sqlite import problem_repository as sqlite_repository
from services import problem_service
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL, parse_schema_columns
from services.problem_service import ProblemService, make_group_key, make_series_key
from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA


T0 = 1_790_000_000_000  # 2026-09 무렵 epoch ms


class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def problem_db(monkeypatch):
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
    clock = {'ms': T0}
    monkeypatch.setattr(problem_service, 'now_ms', lambda: clock['ms'])
    yield connection, clock
    connection.close()


def _missing(book_id, library_id=80, series='원피스', db_type='general'):
    return ProblemService.report(
        'file_missing', 'book', book_id, db_type=db_type, library_id=library_id,
        target_path=f'/books/{series}/{book_id}.zip', series_key=make_series_key(library_id, series),
    )


# ---- schema ----

def test_tables_are_defined_for_both_engines():
    tables = parse_schema_columns(_SCHEMA_SQL)
    cols = dict(tables['problem_occurrences'])
    for col in ('code', 'severity', 'source', 'db_type', 'library_id', 'target_type', 'target_id', 'target_path',
                'series_key', 'group_key', 'title', 'detail', 'message', 'context', 'occurrence_count',
                'first_seen_ms', 'last_seen_ms', 'status', 'resolved_ms'):
        assert col in cols
    assert 'muted_count' in dict(tables['problem_groups'])
    for table in ('problem_occurrences', 'problem_groups'):
        assert f'CREATE TABLE IF NOT EXISTS {table}' in MARIADB_CENTRAL_SCHEMA


# ---- 기록 / 재발 / 해결 ----

def test_repeat_report_upserts_one_row(problem_db):
    _conn, clock = problem_db
    assert _missing(1)
    clock['ms'] += 5000
    assert _missing(1)
    rows = ProblemService.list_open()
    assert len(rows) == 1
    row = rows[0]
    assert row['occurrence_count'] == 2
    assert row['first_seen_ms'] == T0 and row['last_seen_ms'] == T0 + 5000
    assert row['group_key'] == 'file_missing|general|80'
    assert row['severity'] == 'notice'  # 카탈로그 기본값 (이미 휴지통으로 옮긴 도서라 참고)
    assert row['series_key'] == '80|원피스'


def test_resolved_then_recurring_starts_fresh_and_keeps_last_ok(problem_db):
    _conn, clock = problem_db
    _missing(1)
    _missing(1)
    clock['ms'] += 1000
    assert ProblemService.resolve('file_missing', 'book', 1)
    assert ProblemService.list_open() == []
    assert not ProblemService.resolve('file_missing', 'book', 1)  # 이미 해결됨 → 변화 없음
    clock['ms'] += 1000
    _missing(1)
    row = ProblemService.list_open()[0]
    assert row['occurrence_count'] == 1
    assert row['first_seen_ms'] == T0 + 2000
    assert row['resolved_ms'] == T0 + 1000


def test_same_target_different_db_type_is_separate(problem_db):
    _missing(1, db_type='general')
    _missing(1, db_type='adult')
    assert len(ProblemService.list_open()) == 2
    ProblemService.resolve('file_missing', 'book', 1, db_type='adult')
    assert [r['db_type'] for r in ProblemService.list_open()] == ['general']


def test_track_reports_on_error_and_resolves_on_success(problem_db):
    with pytest.raises(RuntimeError):
        with ProblemService.track('file_corrupt', 'book', 7, db_type='general', library_id=80):
            raise RuntimeError('bad zip header')
    row = ProblemService.list_open()[0]
    assert row['code'] == 'file_corrupt' and row['severity'] == 'notice'
    assert 'bad zip' in row['message']
    with ProblemService.track('file_corrupt', 'book', 7, db_type='general', library_id=80):
        pass
    assert ProblemService.list_open() == []


def test_resolve_targets_bulk_and_by_code(problem_db):
    for book_id in range(1, 6):
        _missing(book_id)
    ProblemService.report('file_corrupt', 'book', 3, library_id=80)
    assert ProblemService.resolve_targets('general', 'book', [1, 2, 3], code='file_missing') == 3
    open_rows = {(r['code'], r['target_id']) for r in ProblemService.list_open()}
    assert open_rows == {('file_missing', '4'), ('file_missing', '5'), ('file_corrupt', '3')}
    assert ProblemService.on_books_deleted('general', [3, 4, 5]) == 3
    assert ProblemService.list_open() == []


def test_report_never_raises(problem_db, monkeypatch):
    assert not ProblemService.report('file_missing', 'nonsense', 1)

    class Broken:
        def __getattr__(self, _name):
            raise OSError('db down')

    monkeypatch.setattr(problem_service, 'ProblemRepository', Broken())
    assert not _missing(1)
    assert not ProblemService.resolve('file_missing', 'book', 1)
    assert ProblemService.resolve_targets('general', 'book', [1]) == 0
    assert ProblemService.list_cards() == []


# ---- 카드 / 시리즈 접기 / 페이지네이션 ----

def test_cards_group_by_code_and_library_and_fold_series(problem_db):
    for book_id in range(1, 4):
        _missing(book_id, series='원피스')
    _missing(10, series='나루토')
    _missing(20, library_id=81, series='기타')
    ProblemService.report('file_corrupt', 'book', 99, library_id=80)

    cards = {c['group_key']: c for c in ProblemService.list_cards()}
    assert set(cards) == {'file_missing|general|80', 'file_missing|general|81', 'file_corrupt|general|80'}
    card = cards['file_missing|general|80']
    assert card['open_count'] == 4
    assert card['severity'] == 'notice'
    assert card['title_key'] == 'problems.code.file_missing.title'
    assert 'rescan' in card['actions']
    assert card['last_seen_at'].count(':') >= 2 and ('+' in card['last_seen_at'] or 'Z' in card['last_seen_at'])
    # 조치 필요 카드가 참고 카드보다 앞 (나중에 기록돼도)
    ProblemService.report('mass_missing', 'book', 500, library_id=82)
    keys = [c['group_key'] for c in ProblemService.list_cards()]
    assert keys[0] == 'mass_missing|general|82'

    lines = ProblemService.list_card_series('file_missing|general|80')
    assert [(l['series_key'], l['open_count']) for l in lines] == [('80|원피스', 3), ('80|나루토', 1)]

    items, total = ProblemService.list_card_items('file_missing|general|80', series_key='80|원피스', limit=2)
    assert total == 3 and len(items) == 2
    items2, _ = ProblemService.list_card_items('file_missing|general|80', series_key='80|원피스', limit=2, offset=2)
    assert len(items2) == 1
    assert {i['target_id'] for i in items + items2} == {'1', '2', '3'}


def test_library_and_system_rows_are_their_own_lines(problem_db):
    ProblemService.report('remote_unavailable', 'library', 80, library_id=80, source='scanner')
    lines = ProblemService.list_card_series(make_group_key('remote_unavailable', 'general', 80))
    assert len(lines) == 1 and lines[0]['series_key'] is None and lines[0]['line_key'] == 'target:library:80'


def test_mute_hides_until_count_grows_and_clears_when_empty(problem_db):
    _missing(1)
    _missing(2)
    key = 'file_missing|general|80'
    assert ProblemService.mute_card(key)
    assert ProblemService.list_cards() == []
    assert ProblemService.list_cards(include_muted=True)[0]['muted'] is True
    _missing(1)  # 재발만 - 대상 수는 그대로
    assert ProblemService.list_cards() == []
    _missing(3)  # 새 대상 추가 → 다시 보인다
    assert ProblemService.list_cards()[0]['open_count'] == 3

    ProblemService.mute_card(key)
    ProblemService.resolve_targets('general', 'book', [1, 2, 3])
    conn, _clock = problem_db
    assert conn.execute("SELECT COUNT(*) FROM problem_groups").fetchone()[0] == 0
    _missing(5)  # 카드가 비었다가 새로 생기면 예전 음소거에 가려지지 않는다
    assert len(ProblemService.list_cards()) == 1


def test_mute_unknown_card_returns_false(problem_db):
    assert not ProblemService.mute_card('file_missing|general|404')


# ---- 수명 관리 / 삭제 연동 ----

def test_purge_resolved_after_retention(problem_db):
    conn, clock = problem_db
    _missing(1)
    _missing(2)
    ProblemService.resolve('file_missing', 'book', 1)
    clock['ms'] += 31 * 86400 * 1000
    assert ProblemService.purge_resolved() == 1
    assert conn.execute("SELECT COUNT(*) FROM problem_occurrences").fetchone()[0] == 1  # 열린 행은 그대로


def test_library_deletion_removes_rows_and_group_state(problem_db):
    conn, _clock = problem_db
    _missing(1, library_id=80)
    _missing(2, library_id=81)
    ProblemService.mute_card('file_missing|general|80')
    _missing(1, library_id=80, db_type='adult')
    assert ProblemService.on_library_deleted('general', 80) == 1
    remaining = {(r['db_type'], r['library_id']) for r in ProblemService.list_open()}
    assert remaining == {('general', 81), ('adult', 80)}
    assert conn.execute("SELECT COUNT(*) FROM problem_groups").fetchone()[0] == 0


def test_mass_missing_thresholds_are_fixed_for_now():
    assert problem_service.get_mass_missing_thresholds('general', 80) == {'ratio': 0.2, 'min_count': 20}


def test_unknown_code_uses_fallback_catalog():
    entry = problem_service.catalog_entry('something_new')
    assert entry['title_key'] == 'problems.code.unknown.title'
    assert entry['severity'] == 'notice'


# ---- 순단 유예 (remote_unavailable) ----

def _remote(library_id=80, db_type='general'):
    return ProblemService.report('remote_unavailable', 'library', library_id, db_type=db_type, library_id=library_id,
                                 target_path='/mnt/gdrive/books', message='/mnt/gdrive/books (not found)')


def _codes():
    return [c['code'] for c in ProblemService.list_cards()]


def test_remote_unavailable_card_waits_out_the_grace_period(problem_db):
    _, clock = problem_db
    grace_ms = problem_service.CATALOG['remote_unavailable']['grace_sec'] * 1000
    _remote()
    assert 'remote_unavailable' not in _codes()            # 막 끊김: 아직 순단일 수 있다
    clock['ms'] += grace_ms - 1
    _remote()                                               # 그 사이 스캔이 또 실패해도 최초 시각 기준
    assert 'remote_unavailable' not in _codes()
    clock['ms'] += 1
    assert 'remote_unavailable' in _codes()                 # 유예가 지나도록 해제되지 않음 → 카드


def test_a_blip_that_recovers_within_the_grace_period_never_shows_a_card(problem_db):
    _, clock = problem_db
    grace_ms = problem_service.CATALOG['remote_unavailable']['grace_sec'] * 1000
    _remote()
    clock['ms'] += 30_000
    ProblemService.resolve('remote_unavailable', 'library', 80, db_type='general')
    clock['ms'] += grace_ms * 2
    assert 'remote_unavailable' not in _codes()
    _remote()                                               # 다시 끊기면 유예를 새로 센다
    assert 'remote_unavailable' not in _codes()


def test_other_codes_show_immediately(problem_db):
    _missing(1)
    assert 'file_missing' in _codes()
