"""플러그인 문제 카드 계약(plugins/metadata/base.py report_problem/resolve_problem,
services/plugin_problem_service.py) - 알림센터 6단계. 실제 SQLite 스키마(메모리 DB)."""
import sqlite3
from contextlib import contextmanager

import pytest

import database
from plugins.metadata.base import BaseMetadataProvider
from repositories.sqlite import problem_repository as sqlite_repository
from services import notification_service as ns
from services import plugin_problem_service as pps
from services import problem_card_service as pcs
from services import problem_service
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL
from services.problem_service import ProblemService


class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


class SamplePlugin(BaseMetadataProvider):
    id = 'sample_mood'
    name = '샘플 무드'

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return True, ''


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
    import repositories.problem_repository as facade
    monkeypatch.setattr(facade, 'ProblemRepository', sqlite_repository.ProblemRepository)
    monkeypatch.setattr(pcs, '_library_roots', lambda _db, _lib: ['/lib/만화'])
    connection.execute("INSERT INTO libraries (id, name, physical_path) VALUES (80, '만화', '/lib/만화')")
    connection.execute("INSERT INTO books (id, library_id, title, series_name, file_path, file_format, total_pages) "
                       "VALUES (5, 80, '원피스 5권', '원피스', '/lib/만화/원피스/5.zip', 'zip', 0)")
    connection.commit()
    yield connection
    connection.close()


def _rows(db):
    return [dict(r) for r in db.execute("SELECT * FROM problem_occurrences ORDER BY id")]


def _card(group_key):
    return next((c for c in ProblemService.list_cards() if c['group_key'] == group_key), None)


def test_report_namespaces_code_and_source_and_counts_repeats(db):
    plugin = SamplePlugin()
    assert hasattr(plugin, 'report_problem')  # 플러그인 쪽 기능 감지 방법
    for _ in range(2):
        assert plugin.report_problem('token_expired', title='토큰 만료', detail='다시 연결하세요.',
                                     severity='action_required', action_id='reauth', action_label='다시 연결')
    rows = _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert (row['code'], row['source'], row['target_type'], row['target_id'], row['group_key']) == \
        ('sample_mood:token_expired', 'plugin:sample_mood', 'system', '-', 'plugin:sample_mood|token_expired|-')
    assert row['occurrence_count'] == 2 and row['title'] == '토큰 만료'

    card = _card('plugin:sample_mood|token_expired|-')
    assert card['severity'] == 'action_required' and card['actions'] == ['plugin_action']
    assert card['plugin'] == {'id': 'sample_mood', 'name': '샘플 무드', 'code': 'token_expired', 'title': '토큰 만료',
                              'detail': '다시 연결하세요.', 'action_id': 'reauth', 'action_label': '다시 연결'}

    assert plugin.resolve_problem('token_expired') is True
    assert plugin.resolve_problem('token_expired') is False  # 성공할 때마다 불러도 된다
    assert _card('plugin:sample_mood|token_expired|-') is None


def test_notification_item_always_shows_plugin_name(db):
    SamplePlugin().report_problem('quota', title='API 한도 초과', detail='내일 다시 시도합니다.')
    items = ns.problem_card_items(ProblemService.list_cards(), lambda *_a: '만화')
    item = items[0]
    assert item['title'] == '샘플 무드 · API 한도 초과'
    assert item['source'] == 'plugin' and item['tone'] == 'notice' and item['raw_detail'] == '내일 다시 시도합니다.'
    assert item['card']['plugin']['id'] == 'sample_mood' and item['actions'] == []


def test_book_target_gets_series_and_item_action(db):
    plugin = SamplePlugin()
    plugin.report_problem('lyrics_missing', title='가사 없음', target_type='book', target_id=5,
                          action_id='retry', action_label='다시 찾기')
    row = _rows(db)[0]
    assert (row['library_id'], row['series_key'], row['target_path']) == (80, '80|원피스', '/lib/만화/원피스/5.zip')
    data = pcs.get_card_items('plugin:sample_mood|lyrics_missing|-', series_key='80|원피스')
    item = data['items'][0]
    assert item['book_id'] == 5 and item['title'] == '원피스 5권'
    assert item['plugin_action'] == {'plugin_id': 'sample_mood', 'action_id': 'retry', 'label': '다시 찾기'}


@pytest.mark.parametrize('kwargs', [
    {'code': 'bad code!', 'title': 't'},
    {'code': 'x' * 65, 'title': 't'},
    {'code': 'ok', 'title': 't', 'severity': 'auto_fixed'},
    {'code': 'ok', 'title': 't', 'target_type': 'galaxy'},
    {'code': 'ok', 'title': 't', 'target_type': 'book'},  # target_id 없음
    {'code': 'ok', 'title': 't', 'action_id': 'has space'},
])
def test_invalid_arguments_return_false_without_raising(db, kwargs):
    code = kwargs.pop('code')
    assert SamplePlugin().report_problem(code, **kwargs) is False
    assert _rows(db) == []


def test_open_limit_trims_oldest(db, monkeypatch):
    monkeypatch.setattr(pps, 'PLUGIN_OPEN_LIMIT', 3)
    plugin = SamplePlugin()
    for i in range(5):
        plugin.report_problem('item_failed', title=f'#{i}', target_type='series', target_id=f'80|S{i}', library_id=80)
    open_ids = [r['target_id'] for r in _rows(db) if r['status'] == 'open']
    assert open_ids == ['80|S2', '80|S3', '80|S4']


def test_disable_and_boot_cleanup(db):
    SamplePlugin().report_problem('a', title='A')
    other = SamplePlugin()
    other.id = 'other_plugin'
    other.report_problem('b', title='B')
    assert pps.on_plugin_disabled('sample_mood') == 1
    assert [c['group_key'] for c in ProblemService.list_cards()] == ['plugin:other_plugin|b|-']
    # 서버 시작: other_plugin이 꺼졌거나 지워졌다
    assert pps.cleanup_inactive_plugins(['sample_mood']) == 1
    assert ProblemService.list_cards() == []


def test_plugins_cannot_collide_with_core_codes(db):
    SamplePlugin().report_problem('file_missing', title='플러그인 자체 코드')
    assert _rows(db)[0]['code'] == 'sample_mood:file_missing'
    with pytest.raises(ValueError):
        ProblemService.resolve_card('plugin:sample_mood|file_missing|-')  # [해결됨]은 사용자 신고 카드 전용
