import inspect
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from flask import Flask

from api import api_bp
from repositories import trash_repository_shared
from repositories.mariadb import category_repository as mariadb_category
from repositories.mariadb import tts_progress_repository as mariadb_repository
from repositories.sqlite import category_repository as sqlite_category
from repositories.sqlite import tts_progress_repository as sqlite_repository
from services.db_migration_service import _SCHEMA_SQL, parse_schema_columns
from services.tts_progress_service import TTSProgressService
from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA
from tools.scanner import sync_detector


# ---- schema ----

def test_table_is_defined_for_both_engines():
    columns = dict(parse_schema_columns(_SCHEMA_SQL)['tts_progress'])
    for kind in ('listen', 'read'):
        for field in ('chapter', 'offset', 'text_len', 'anchor', 'updated_ms'):
            assert f'{kind}_{field}' in columns
    assert 'CREATE TABLE IF NOT EXISTS tts_progress' in MARIADB_CENTRAL_SCHEMA
    assert 'UNIQUE KEY uq_tts_progress_book_user (book_id, user_id)' in MARIADB_CENTRAL_SCHEMA


def test_book_deletion_paths_clean_up_tts_progress():
    # 스키마에 FK/CASCADE가 없어 삭제 경로마다 자식 테이블 목록을 들고 있다
    assert 'DELETE FROM tts_progress' in inspect.getsource(trash_repository_shared)
    assert 'DELETE FROM tts_progress' in inspect.getsource(sync_detector)
    for module in (sqlite_category, mariadb_category):
        source = inspect.getsource(module)
        assert 'DELETE FROM tts_progress WHERE book_id IN (SELECT id FROM books WHERE library_id' in source
        assert "_dynamic_insert(cursor_dst, 'tts_progress'" in source


# ---- sqlite repository (real schema, in-memory) ----

class NonClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def sqlite_db(monkeypatch):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    wrapper = NonClosingConnection(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(sqlite_repository.database, 'get_connection', lambda *_a, **_k: wrapper)
    monkeypatch.setattr(sqlite_repository.database, 'connection', fake_connection)
    yield connection
    connection.close()


def _pos(offset, ms, chapter=0, anchor='앵커 문구입니다'):
    return {'chapter': chapter, 'offset': offset, 'text_len': 10_000, 'anchor': anchor, 'updated_ms': ms}


def test_sqlite_listen_and_read_are_saved_independently(sqlite_db):
    repo = sqlite_repository.TTSProgressRepository
    assert repo.get('general', 5, 1) is None

    repo.save('general', 5, 1, 'listen', _pos(1200, 1000), {'voice': 'F1', 'steps': 8, 'speed': 1.05})
    repo.save('general', 5, 1, 'read', _pos(3400, 2000, chapter=2))
    row = repo.get('general', 5, 1)
    assert (row['listen_offset'], row['listen_updated_ms'], row['voice'], row['steps']) == (1200, 1000, 'F1', 8)
    assert (row['read_offset'], row['read_chapter'], row['read_updated_ms']) == (3400, 2, 2000)

    # 듣기 위치를 다시 저장해도 읽기 위치와 음성 설정은 그대로
    repo.save('general', 5, 1, 'listen', _pos(1500, 3000))
    row = repo.get('general', 5, 1)
    assert (row['listen_offset'], row['read_offset'], row['voice']) == (1500, 3400, 'F1')
    assert sqlite_db.execute('SELECT COUNT(*) FROM tts_progress').fetchone()[0] == 1


def test_sqlite_rows_are_per_user_and_book(sqlite_db):
    repo = sqlite_repository.TTSProgressRepository
    repo.save('general', 5, 1, 'listen', _pos(10, 1))
    repo.save('general', 5, 2, 'listen', _pos(20, 1))
    repo.save('general', 6, 1, 'listen', _pos(30, 1))
    assert repo.get('general', 5, 1)['listen_offset'] == 10
    assert repo.get('general', 5, 2)['listen_offset'] == 20
    assert repo.get('general', 6, 1)['listen_offset'] == 30


def test_repositories_reject_unknown_kind():
    for repo in (sqlite_repository.TTSProgressRepository, mariadb_repository.TTSProgressRepository):
        with pytest.raises(ValueError):
            repo.save('general', 1, 1, 'listen; DROP TABLE books', _pos(0, 0))


# ---- mariadb repository (fake cursor) ----

class FakeCursor:
    def __init__(self, row=None):
        self.calls = []
        self.row = row

    def execute(self, query, params):
        self.calls.append((query, params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row=None, fail=False):
        self.cursor_instance = FakeCursor(row)
        self.closed = False
        self.committed = False
        self.rolled_back = False
        self.fail = fail

    def cursor(self):
        if self.fail:
            def boom(*_a):
                raise RuntimeError('db down')
            self.cursor_instance.execute = boom
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_mariadb_upsert_only_updates_the_given_kind(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(mariadb_repository.database, 'get_connection', lambda _db_type, **_k: connection)
    mariadb_repository.TTSProgressRepository.save(
        'adult', 9, 3, 'read', _pos(77, 123, chapter=4, anchor='a'))
    query, params = connection.cursor_instance.calls[0]
    assert 'ON DUPLICATE KEY UPDATE' in query
    assert 'read_offset = VALUES(read_offset)' in query
    assert 'listen_' not in query and 'voice' not in query
    assert params == (9, 3, 4, 77, 10_000, 'a', 123)
    assert connection.committed and connection.closed


def test_mariadb_connection_is_released_on_failure(monkeypatch):
    connection = FakeConnection(fail=True)
    monkeypatch.setattr(mariadb_repository.database, 'get_connection', lambda _db_type, **_k: connection)
    with pytest.raises(RuntimeError):
        mariadb_repository.TTSProgressRepository.save('general', 1, 1, 'listen', _pos(0, 0))
    assert connection.rolled_back and connection.closed


# ---- service: validation + latest ----

@pytest.mark.parametrize('payload', [
    {'kind': 'watch'},
    {'kind': 'listen', 'char_offset': -1},
    {'kind': 'listen', 'char_offset': 'abc'},
    {'kind': 'listen', 'voice': 'X9'},
    {'kind': 'listen', 'steps': 3},
    {'kind': 'listen', 'speed': 9},
    {'kind': 'read', 'anchor': 123},
])
def test_invalid_payloads_are_rejected(payload):
    with pytest.raises(ValueError):
        TTSProgressService.validate(payload)


def test_long_anchor_is_truncated_and_settings_only_for_listen():
    kind, position, settings = TTSProgressService.validate(
        {'kind': 'read', 'anchor': '가' * 500, 'voice': 'F1', 'char_offset': '12'})
    assert kind == 'read' and len(position['anchor']) == 200 and position['offset'] == 12
    assert settings == {}


def _row(listen_ms=None, read_ms=None):
    row = {'voice': 'M2', 'steps': 4, 'speed': 1.2}
    for kind, ms in (('listen', listen_ms), ('read', read_ms)):
        row.update({f'{kind}_chapter': 1, f'{kind}_offset': 50, f'{kind}_text_len': 100,
                    f'{kind}_anchor': 'x', f'{kind}_updated_ms': ms})
    return row


@pytest.mark.parametrize('listen_ms, read_ms, legacy_state, expected', [
    (2000, 1000, None, 'listen'),
    (1000, 2000, None, 'read'),
    (1000, None, {'pages_read': 3, 'total_pages': 9, 'epub_session': {'index': None}}, 'listen'),
    (None, None, {'pages_read': 3, 'total_pages': 9, 'epub_session': {'index': None}}, 'legacy'),
    (None, None, {'pages_read': 0, 'total_pages': 9, 'epub_session': {'index': 2}}, 'legacy'),
    (None, None, {'pages_read': 0, 'total_pages': 9, 'epub_session': {'index': None}}, None),
    (None, None, None, None),
])
def test_latest_follows_the_more_recent_position(listen_ms, read_ms, legacy_state, expected):
    with patch('services.tts_progress_service.TTSProgressRepository.get', return_value=_row(listen_ms, read_ms)), \
            patch('services.tts_progress_service.ReadingProgressService.get_progress_state', return_value=legacy_state):
        state = TTSProgressService.get_sync_state('general', 1, 1)
    assert state['latest'] == expected
    assert (state['listen'] is None) == (listen_ms is None)
    if read_ms is not None:
        assert state['legacy'] is None  # 세밀한 읽기 위치가 있으면 거친 진도는 안 본다
    assert state['settings'] == {'voice': 'M2', 'steps': 4, 'speed': 1.2}


# ---- routes ----

def _client(role='user', adult=0):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-tts-progress')
    app.register_blueprint(api_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 7
        session['role'] = role
        session['is_default_password'] = 0
        session['has_adult_access'] = adult
    return client


@pytest.fixture
def allow_rating():
    with patch('api.routes.tts_routes.check_book_rating_permission', return_value=True):
        yield


def test_post_saves_for_the_session_user(allow_rating):
    with patch('services.tts_progress_service.TTSProgressRepository.save') as save:
        # sendBeacon은 text/plain으로 보낸다
        response = _client().post('/api/media/tts/position', data=(
            '{"db_type":"general","book_id":3,"kind":"listen","chapter_idx":0,'
            '"char_offset":120,"text_len":5000,"anchor":"abc","voice":"F1","steps":8,"speed":1.05}'
        ), content_type='text/plain')
    assert response.status_code == 200
    args = save.call_args.args
    assert args[:4] == ('general', 3, 7, 'listen')
    assert args[4]['offset'] == 120 and args[5] == {'voice': 'F1', 'steps': 8, 'speed': 1.05}


def test_post_rejects_bad_input(allow_rating):
    client = _client()
    assert client.post('/api/media/tts/position', json={'db_type': 'general', 'kind': 'listen'}).status_code == 400
    assert client.post('/api/media/tts/position', json={'db_type': 'video', 'book_id': 1, 'kind': 'listen'}).status_code == 400
    assert client.post('/api/media/tts/position', json={'db_type': 'general', 'book_id': 1, 'kind': 'x'}).status_code == 400


def test_adult_db_requires_adult_access(allow_rating):
    response = _client(adult=0).get('/api/media/tts/position?db_type=adult&book_id=1')
    assert response.status_code == 403
    with patch('services.tts_progress_service.TTSProgressService.get_sync_state', return_value={'latest': None}):
        assert _client(adult=1).get('/api/media/tts/position?db_type=adult&book_id=1').status_code == 200


def test_rating_restricted_book_is_denied():
    with patch('api.routes.tts_routes.check_book_rating_permission', return_value=False):
        response = _client().get('/api/media/tts/position?db_type=general&book_id=1')
    assert response.status_code == 403


def test_get_returns_sync_state(allow_rating):
    state = {'listen': None, 'read': None, 'legacy': None, 'latest': None, 'settings': None}
    with patch('services.tts_progress_service.TTSProgressService.get_sync_state', return_value=state) as get:
        response = _client().get('/api/media/tts/position?db_type=general&book_id=4')
    assert response.status_code == 200
    assert response.get_json() == {'success': True, 'state': state}
    assert get.call_args.args == ('general', 4, 7)


def test_requires_login():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='x')
    app.register_blueprint(api_bp)
    assert app.test_client().get('/api/media/tts/position?book_id=1').status_code == 401
