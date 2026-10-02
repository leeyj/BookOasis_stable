"""KOReader 진행 동기화 (kosync 호환 API)."""
import hashlib
import os
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from flask import Flask

from api.routes.kosync_routes import kosync_bp
from repositories.sqlite import kosync_repository as repo_module
from services import kosync_service
from services.db_migration_service import _SCHEMA_SQL


# ---- 문서 id: KOReader util.partialMD5와 같은 위치를 읽는다 ----

def test_partial_md5_reads_1kb_at_koreader_offsets_and_stops_past_the_end(tmp_path):
    data = os.urandom(5 * 1024 * 1024)                     # 5MB: 16MB 지점부터는 파일 밖
    path = tmp_path / 'book.cbz'
    path.write_bytes(data)
    expected = hashlib.md5()
    for offset in (0, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304):
        expected.update(data[offset:offset + 1024])
    assert kosync_service.partial_md5(str(path)) == expected.hexdigest()


def test_partial_md5_of_a_tiny_file(tmp_path):
    path = tmp_path / 'tiny.epub'
    path.write_bytes(b'abc')
    assert kosync_service.partial_md5(str(path)) == hashlib.md5(b'abc').hexdigest()


# ---- API ----

class _NonClosing:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def kosync_db(monkeypatch):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    wrapper = _NonClosing(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(repo_module.database, 'connection', fake_connection)
    monkeypatch.setattr('repositories.kosync_repository.KosyncRepository', repo_module.KosyncRepository)
    users = {'reader': {'id': 7, 'username': 'reader', 'role': 'user'}}
    monkeypatch.setattr('repositories.user_repository.UserRepository.find_by_username',
                        lambda _db, name: users.get(name))
    return connection


def _client(session_user=None):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='t')
    app.register_blueprint(kosync_bp)
    client = app.test_client()
    if session_user:
        with client.session_transaction() as s:
            s['user_id'], s['username'] = session_user
    return client


def _auth(password='sync-pass', user='reader'):
    return {'x-auth-user': user, 'x-auth-key': hashlib.md5(password.encode()).hexdigest(),
            'Accept': 'application/vnd.koreader.v1+json'}


def test_login_needs_the_separate_sync_password(kosync_db):
    client = _client()
    assert client.get('/kosync/users/auth', headers=_auth()).status_code == 401      # 아직 설정 안 함
    kosync_service.set_sync_password(7, 'sync-pass')
    assert client.get('/kosync/users/auth', headers=_auth()).get_json() == {'authorized': 'OK'}
    assert client.get('/kosync/users/auth', headers=_auth('wrong')).status_code == 401
    assert client.get('/kosync/users/auth', headers=_auth(user='nobody')).status_code == 401
    assert client.post('/kosync/users/create', json={'username': 'x', 'password': 'y'}).status_code == 402


def test_push_then_pull_round_trips_between_koreader_devices(kosync_db):
    kosync_service.set_sync_password(7, 'sync-pass')
    client = _client()
    body = {'document': 'a' * 32, 'progress': '/body/DocFragment[12]/body/p[3]/text().0', 'percentage': 0.42,
            'device': 'Kobo', 'device_id': 'kobo-1'}
    pushed = client.put('/kosync/syncs/progress', json=body, headers=_auth())
    assert pushed.status_code == 200 and pushed.get_json()['document'] == 'a' * 32

    pulled = client.get('/kosync/syncs/progress/' + 'a' * 32, headers=_auth()).get_json()
    assert {k: pulled[k] for k in ('progress', 'percentage', 'device', 'device_id')} == {
        'progress': body['progress'], 'percentage': 0.42, 'device': 'Kobo', 'device_id': 'kobo-1'}
    assert client.get('/kosync/syncs/progress/' + 'b' * 32, headers=_auth()).get_json() == {}
    assert client.put('/kosync/syncs/progress', json=body).status_code == 401


def _map_book(fmt, total_pages=180):
    repo_module.KosyncRepository.save_document('c' * 32, 'general', 42)
    return patch('repositories.reading_progress_repository.ReadingProgressRepository.get_book_for_progress',
                 return_value={'file_format': fmt, 'total_pages': total_pages})


def test_comic_progress_from_koreader_is_mirrored_into_bookoasis(kosync_db):
    kosync_service.set_sync_password(7, 'sync-pass')
    with _map_book('zip'), patch('services.reading_progress_service.ReadingProgressService.record_progress') as record:
        _client().put('/kosync/syncs/progress', json={'document': 'c' * 32, 'progress': '12', 'percentage': 0.0667,
                                                      'device': 'Kobo', 'device_id': 'k'}, headers=_auth())
    record.assert_called_once_with('general', 42, 11, 180, user_id=7)   # KOReader 12쪽 = 0부터 11


def test_epub_progress_is_not_written_over_the_web_viewer_position(kosync_db):
    kosync_service.set_sync_password(7, 'sync-pass')
    with _map_book('epub'), patch('services.reading_progress_service.ReadingProgressService.record_progress') as record:
        _client().put('/kosync/syncs/progress', json={'document': 'c' * 32, 'progress': '/body/x', 'percentage': 0.5},
                      headers=_auth())
    record.assert_not_called()


def test_pull_returns_the_web_page_when_the_web_read_later(kosync_db):
    kosync_service.set_sync_password(7, 'sync-pass')
    repo_module.KosyncRepository.save_progress(7, 'c' * 32, '12', 0.0667, 'Kobo', 'k', 1_000)
    web = {'pages_read': 30, 'total_pages': 180, 'last_read_at': '2026-10-02 12:00:00'}
    with _map_book('cbz'), patch('services.reading_progress_service.ReadingProgressService.get_progress_state',
                                 return_value=web):
        pulled = _client().get('/kosync/syncs/progress/' + 'c' * 32, headers=_auth()).get_json()
    assert (pulled['progress'], pulled['device'], pulled['percentage']) == ('30', 'BookOasis', round(30 / 180, 4))


def test_pull_keeps_the_koreader_record_when_it_is_newer(kosync_db):
    kosync_service.set_sync_password(7, 'sync-pass')
    repo_module.KosyncRepository.save_progress(7, 'c' * 32, '50', 0.27, 'Kobo', 'k', 4_000_000_000)
    web = {'pages_read': 30, 'total_pages': 180, 'last_read_at': '2026-10-02 12:00:00'}
    with _map_book('cbz'), patch('services.reading_progress_service.ReadingProgressService.get_progress_state',
                                 return_value=web):
        pulled = _client().get('/kosync/syncs/progress/' + 'c' * 32, headers=_auth()).get_json()
    assert (pulled['progress'], pulled['device']) == ('50', 'Kobo')


def test_account_settings_set_status_and_clear(kosync_db):
    client = _client(session_user=(7, 'reader'))
    assert client.get('/api/kosync/settings').get_json()['enabled'] is False
    assert client.post('/api/kosync/settings', json={'password': 'abc'}).status_code == 400   # 너무 짧음
    assert client.post('/api/kosync/settings', json={'password': 'sync-pass'}).get_json()['enabled'] is True
    state = client.get('/api/kosync/settings').get_json()
    assert state['enabled'] is True and state['username'] == 'reader' and state['server_url'].endswith('/kosync')
    assert client.delete('/api/kosync/settings').get_json()['enabled'] is False
    assert _client().get('/api/kosync/settings').status_code == 401


def test_opds_download_remembers_the_document_for_this_book(kosync_db, tmp_path):
    path = tmp_path / 'b.cbz'
    path.write_bytes(os.urandom(3000))
    kosync_service.remember_document('general', 42, str(path))
    assert repo_module.KosyncRepository.get_document(kosync_service.partial_md5(str(path))) == {'db_type': 'general', 'book_id': 42}
