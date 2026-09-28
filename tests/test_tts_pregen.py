import json
import os
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from flask import Flask

from api import api_bp
from repositories.sqlite import tts_pregen_repository as sqlite_repository
from services import tts_engine
from services import tts_pregen_service as pregen
from services.db_migration_service import _SCHEMA_SQL, _INDEXES_SQL, parse_schema_columns
from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA

Repo = sqlite_repository.TTSPregenRepository


# ---- schema ----

def test_tables_are_defined_for_both_engines():
    tables = parse_schema_columns(_SCHEMA_SQL)
    jobs = dict(tables['tts_pregen_jobs'])
    for col in ('book_id', 'user_id', 'voice', 'steps', 'speed', 'status', 'total_pieces', 'done_pieces', 'heartbeat_ms'):
        assert col in jobs
    assert 'quality' in jobs
    for col in ('book_id', 'voice', 'steps', 'speed', 'quality', 'rel_dir', 'bytes', 'created_by', 'last_used_ms'):
        assert col in dict(tables['tts_audio_books'])
    for col in ('audio_book_id', 'piece_key', 'chapter', 'part', 'byte_offset', 'byte_length', 'duration_sec'):
        assert col in dict(tables['tts_audio_pieces'])
    for table in ('tts_pregen_jobs', 'tts_audio_books', 'tts_audio_pieces'):
        assert f'CREATE TABLE IF NOT EXISTS {table}' in MARIADB_CENTRAL_SCHEMA


# ---- piece key (tests/test_tts_core.mjs에 같은 벡터가 있다) ----

def test_piece_key_matches_browser_vector():
    assert tts_engine.piece_key('F1', 4, 1.05, '안녕하세요.') == 'abd1f0295b1523c4a5e0d0dbc82b4b8a2ac8f6ab394e1b2f759886a674845258'
    assert tts_engine.piece_key('M3', 8, 1.0, '運命 → 운명 "따옴표"') == '0b24e05b350dde0bb801597c7a91e0f7f7079eb54fb156479fe70d22d657d189'


def test_js_number_formatting():
    assert tts_engine._js_number(1.0) == '1'
    assert tts_engine._js_number(1.05) == '1.05'
    assert tts_engine._js_number(0.9) == '0.9'


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
    connection.executescript(_INDEXES_SQL)
    wrapper = NonClosingConnection(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(sqlite_repository.database, 'get_connection', lambda *_a, **_k: wrapper)
    monkeypatch.setattr(sqlite_repository.database, 'connection', fake_connection)
    monkeypatch.setattr(pregen, 'TTSPregenRepository', Repo)
    yield connection
    connection.close()


def test_claim_is_exclusive_and_reclaims_stale_jobs(sqlite_db):
    job_id = Repo.create_job('general', 1, 7, 'F1', 4, 1.05, 10, 1000)
    claimed = Repo.claim_next('general', 2000, 2000 - pregen.STALE_MS)
    assert claimed['id'] == job_id and claimed['status'] == 'running'
    # 살아 있는 running 작업은 다시 가져가지 않는다
    assert Repo.claim_next('general', 3000, 3000 - pregen.STALE_MS) is None
    # heartbeat가 끊기면 다시 가져간다 (재시작 후 이어서 하기)
    later = 2000 + pregen.STALE_MS + 1
    assert Repo.claim_next('general', later, later - pregen.STALE_MS)['id'] == job_id


def test_progress_stops_after_cancel(sqlite_db):
    job_id = Repo.create_job('general', 1, 7, 'F1', 4, 1.05, 10, 1000)
    Repo.claim_next('general', 2000, 0)
    assert Repo.update_progress('general', job_id, 3, 2500)
    assert Repo.cancel('general', job_id, 2600)
    assert not Repo.update_progress('general', job_id, 4, 2700)
    assert Repo.get_job('general', job_id)['status'] == 'cancelled'


def test_active_job_lookup_and_counts(sqlite_db):
    Repo.create_job('general', 1, 7, 'F1', 4, 1.05, 10, 1000)
    assert Repo.find_active_job('general', 1, 'F1', 4, 1.05)
    assert Repo.find_active_job('general', 1, 'F1', 8, 1.05) is None
    assert Repo.count_active_by_user('general', 7) == 1
    assert Repo.count_by_status('general') == {'queued': 1}


def test_audio_book_index_roundtrip(sqlite_db):
    book = Repo.get_or_create_audio_book('general', 5, 'F1', 4, 1.05, 'standard', 'books/5/F1_4_1.05_standard', 7, 100)
    assert Repo.get_or_create_audio_book('general', 5, 'F1', 4, 1.05, 'standard', 'x', 8, 200)['id'] == book['id']
    other = Repo.get_or_create_audio_book('general', 6, 'F1', 4, 1.05, 'standard', 'books/6/F1_4_1.05_standard', 7, 300)
    Repo.add_piece('general', book['id'], 'a' * 64, 0, 0, 0, 100, 3.5)
    Repo.add_piece('general', book['id'], 'b' * 64, 1, 0, 0, 50, 2.0)
    Repo.add_piece('general', other['id'], 'a' * 64, 0, 0, 0, 80, 3.5)
    row = Repo.get_audio_book('general', book['id'])
    assert (row['pieces'], row['bytes'], row['duration_sec']) == (2, 150, 5.5)
    assert Repo.total_audio_bytes('general') == 230
    # 같은 키가 두 책에 있으면 최근에 들은 책 것
    Repo.touch_audio_books('general', [other['id']], 999)
    assert Repo.find_pieces('general', ['a' * 64])['a' * 64]['audio_book_id'] == other['id']
    assert [b['id'] for b in Repo.oldest_audio_books('general', 5)] == [book['id'], other['id']]
    Repo.remove_pieces('general', book['id'], ['b' * 64])
    assert Repo.get_audio_book('general', book['id'])['bytes'] == 100
    Repo.delete_audio_book('general', other['id'])
    assert Repo.find_pieces('general', ['a' * 64])['a' * 64]['audio_book_id'] == book['id']
    assert [b['id'] for b in Repo.list_audio_books('general')] == [book['id']]


# ---- service ----

def _piece(text, chapter=0, conf=('F1', 4, 1.05)):
    return {'chapter': chapter, 'text': text, 'key': tts_engine.piece_key(*conf, text)}


def _payload(pieces, conf=('F1', 4, 1.05)):
    return {'voice': conf[0], 'steps': conf[1], 'speed': conf[2], 'pieces': pieces}


@pytest.fixture
def audio_root(tmp_path, monkeypatch):
    monkeypatch.setattr(pregen, 'AUDIO_ROOT', str(tmp_path))
    return tmp_path


def test_create_job_validates_keys_and_dedupes(sqlite_db, audio_root):
    with patch.object(pregen, 'wake_worker'):
        job, created = pregen.create_job('general', 1, 7, _payload([_piece('첫 문장.'), _piece('첫 문장.'), _piece('둘째 문장.', 1)]))
    assert created and job['total_pieces'] == 2
    manifest = json.loads((audio_root / 'general' / 'jobs' / f"{job['id']}.json").read_text(encoding='utf-8'))
    assert [p['c'] for p in manifest['pieces']] == [0, 1]
    # 같은 책·설정의 진행 중 작업이 있으면 그걸 돌려준다
    again, created = pregen.create_job('general', 1, 7, _payload([_piece('다른 문장.')]))
    assert not created and again['id'] == job['id']


def test_create_job_rejects_bad_input(sqlite_db, audio_root):
    bad_key = _piece('문장.')
    bad_key['key'] = 'f' * 64
    for payload in (
        _payload([bad_key]),
        _payload([]),
        _payload([_piece('x' * (pregen.MAX_PIECE_CHARS + 1))]),
        {**_payload([_piece('문장.')]), 'voice': 'Z9'},
        {**_payload([_piece('문장.')]), 'steps': 2},
    ):
        with pytest.raises(ValueError):
            pregen.create_job('general', 1, 7, payload)


def test_create_job_limits_active_jobs_per_user(sqlite_db, audio_root):
    with patch.object(pregen, 'wake_worker'):
        for book_id in range(1, pregen.MAX_ACTIVE_PER_USER + 1):
            pregen.create_job('general', book_id, 7, _payload([_piece('문장.')]))
        with pytest.raises(PermissionError):
            pregen.create_job('general', 99, 7, _payload([_piece('문장.')]))


def _stored_book(book_id, pieces, chapter=0, quality='standard', user_id=7):
    """pack 파일에 조각(내용 = 키 앞 8자)을 실제로 써 둔 책 하나"""
    rel = pregen.book_rel_dir(book_id, 'F1', 4, 1.05, quality)
    book = Repo.get_or_create_audio_book('general', book_id, 'F1', 4, 1.05, quality, rel, user_id, 1)
    packs = pregen._BookPacks('general', book)
    for key in pieces:
        packs.append(key, chapter, key[:8].encode(), 2.0)
    return Repo.get_audio_book('general', book['id'])


def test_lookup_and_read_come_from_the_book_pack(sqlite_db, audio_root):
    present, other = 'a' * 64, 'b' * 64
    _stored_book(1, [present, other])
    assert pregen.lookup('general', [present, 'c' * 64, 'not-a-key']) == {present: 2.0}
    assert pregen.read_piece('general', other) == b'bbbbbbbb'
    # 조각들은 챕터 pack 하나에 이어 붙어 있다 (조각마다 파일이 생기지 않는다)
    folder = audio_root / 'general' / 'books' / '1' / 'F1_4_1.05_standard'
    assert [f.name for f in folder.iterdir()] == ['ch0000_00.pack']
    assert (folder / 'ch0000_00.pack').read_bytes() == b'aaaaaaaabbbbbbbb'
    # pack이 잘려 나갔으면 없는 조각이다
    (folder / 'ch0000_00.pack').write_bytes(b'aaaaaaaa')
    assert pregen.lookup('general', [present, other]) == {present: 2.0}
    assert pregen.read_piece('general', other) is None


def test_truncated_pieces_are_dropped_when_the_book_is_reopened(sqlite_db, audio_root):
    book = _stored_book(1, ['a' * 64, 'b' * 64])
    pack = audio_root / 'general' / 'books' / '1' / 'F1_4_1.05_standard' / 'ch0000_00.pack'
    pack.write_bytes(b'aaaaaaaab')  # 둘째 조각을 쓰다 죽음
    packs = pregen._BookPacks('general', book)
    assert packs.keys == {'a' * 64}
    assert Repo.get_audio_book('general', book['id'])['pieces'] == 1
    packs.append('c' * 64, 0, b'cccc', 1.0)  # 쓰레기 바이트 뒤에 이어 쓴다
    assert pregen.read_piece('general', 'c' * 64) == b'cccc'


def test_pack_rotates_to_next_part_when_full(sqlite_db, audio_root, monkeypatch):
    monkeypatch.setattr(pregen, 'PACK_MAX_BYTES', 16)
    _stored_book(1, ['a' * 64, 'b' * 64, 'c' * 64])
    folder = audio_root / 'general' / 'books' / '1' / 'F1_4_1.05_standard'
    assert sorted(f.name for f in folder.iterdir()) == ['ch0000_00.pack', 'ch0000_01.pack']
    assert pregen.read_piece('general', 'c' * 64) == b'cccccccc'


def test_disk_cap_removes_whole_books_least_recently_used(sqlite_db, audio_root, monkeypatch):
    monkeypatch.setattr(pregen, 'disk_cap_bytes', lambda: 20)
    old = _stored_book(1, ['a' * 64])
    mid = _stored_book(2, ['b' * 64])
    new = _stored_book(3, ['c' * 64])
    Repo.touch_audio_books('general', [mid['id']], 50)
    Repo.touch_audio_books('general', [new['id']], 60)
    pregen.enforce_disk_cap('general')
    assert {b['id'] for b in Repo.list_audio_books('general')} == {mid['id'], new['id']}
    assert not (audio_root / 'general' / 'books' / '1').exists()
    # 지금 만드는 책은 가장 오래됐어도 지우지 않는다
    monkeypatch.setattr(pregen, 'disk_cap_bytes', lambda: 1)
    pregen.enforce_disk_cap('general', keep_id=mid['id'])
    assert [b['id'] for b in Repo.list_audio_books('general')] == [mid['id']]


def test_delete_audio_book_permissions(sqlite_db, audio_root):
    book = _stored_book(1, ['a' * 64], user_id=7)
    with pytest.raises(PermissionError):
        pregen.delete_audio_book('general', book['id'], 8, False)
    with pytest.raises(LookupError):
        pregen.delete_audio_book('general', 999, 7, False)
    # 만드는 중이면 거절
    job_id = Repo.create_job('general', 1, 7, 'F1', 4, 1.05, 1, 1)
    with pytest.raises(RuntimeError):
        pregen.delete_audio_book('general', book['id'], 7, False)
    Repo.cancel('general', job_id, 2)
    assert pregen.delete_audio_book('general', book['id'], 8, True)
    assert not (audio_root / 'general' / 'books' / '1').exists()
    assert pregen.lookup('general', ['a' * 64]) == {}


def test_list_ready_books_joins_book_info(sqlite_db, audio_root):
    sqlite_db.execute("INSERT INTO books (id, library_id, title, file_path, file_format, total_pages) VALUES (1, 3, '책 하나', '/b/1.epub', 'epub', 10)")
    sqlite_db.execute("INSERT INTO books (id, library_id, title, file_path, file_format, total_pages, is_deleted) VALUES (2, 3, '지운 책', '/b/2.epub', 'epub', 10, 1)")
    _stored_book(1, ['a' * 64], user_id=7)
    _stored_book(2, ['b' * 64], user_id=7)
    books = pregen.list_ready_books('general', 8, False)
    assert [b['title'] for b in books] == ['책 하나']
    assert books[0]['tts']['bytes'] == 8 and books[0]['tts']['can_delete'] is False
    assert pregen.list_ready_books('general', 7, False)[0]['tts']['can_delete'] is True


def test_legacy_piece_files_are_purged_but_other_files_are_kept(sqlite_db, audio_root):
    legacy = audio_root / 'general' / 'ab'
    legacy.mkdir(parents=True)
    (legacy / f"{'ab' * 32}.m4a").write_bytes(b'x')
    keep_dir = audio_root / 'general' / 'cd'
    keep_dir.mkdir()
    (keep_dir / 'notes.txt').write_text('mine')
    (audio_root / 'general' / 'music').mkdir()
    jobs = audio_root / 'general' / 'jobs'
    jobs.mkdir()
    done_id = Repo.create_job('general', 1, 7, 'F1', 4, 1.05, 1, 1)
    Repo.claim_next('general', 2, 0)
    Repo.finish('general', done_id, 'done', 3)
    active_id = Repo.create_job('general', 2, 7, 'F1', 4, 1.05, 1, 1)
    (jobs / f'{done_id}.json').write_text('{}')
    (jobs / f'{active_id}.json').write_text('{}')
    assert pregen.purge_legacy_cache() == 1
    assert not legacy.exists()
    assert (keep_dir / 'notes.txt').exists() and (audio_root / 'general' / 'music').exists()
    assert not (jobs / f'{done_id}.json').exists() and (jobs / f'{active_id}.json').exists()


def test_near_silent_detection():
    np = pytest.importorskip('numpy')
    sr = 44100
    t = np.arange(sr) / sr
    voiced = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert not tts_engine.is_near_silent(voiced, sr, 1.0)
    assert tts_engine.is_near_silent(np.zeros(sr, dtype=np.float32), sr, 1.0)


# ---- worker (fake engine) ----

class FakeEngine:
    sample_rate = 10

    def __init__(self, threads=2):
        self.calls = []

    def synthesize(self, text, voice, steps, speed):
        self.calls.append(text)
        return [0.0] * 25


def _fake_encode(wav, sample_rate, quality='standard', tmp_dir=None):
    return f'm4a-{quality}'.encode()


def test_worker_makes_missing_pieces_and_skips_cached(sqlite_db, audio_root, monkeypatch):
    monkeypatch.setattr(pregen, 'is_enabled', lambda: True)
    monkeypatch.setattr(pregen.tts_engine, 'availability', lambda: (True, ''))
    monkeypatch.setattr(pregen.tts_engine, 'Engine', FakeEngine)
    monkeypatch.setattr(pregen.tts_engine, 'encode_m4a_bytes', _fake_encode)
    monkeypatch.setattr(pregen, 'quality_setting', lambda: 'compact')
    notified = []
    monkeypatch.setattr(pregen, '_notify_ready', lambda db_type, job: notified.append(job['id']))
    pieces = [_piece('하나.'), _piece('둘.', 1), _piece('셋.', 1)]
    # 첫 조각은 이 책 폴더에 이미 있다 (중단됐다 다시 시작한 경우)
    rel = pregen.book_rel_dir(1, 'F1', 4, 1.05, 'compact')
    book = Repo.get_or_create_audio_book('general', 1, 'F1', 4, 1.05, 'compact', rel, 7, 1)
    pregen._BookPacks('general', book).append(pieces[0]['key'], 0, b'old', 2.5)
    with patch.object(pregen, 'wake_worker'):
        job, _ = pregen.create_job('general', 1, 7, _payload(pieces))
    assert Repo.get_job('general', job['id'])['quality'] == 'compact'

    worker = pregen._Worker()
    assert worker._tick()
    assert worker._engine.calls == ['둘.', '셋.']
    done = Repo.get_job('general', job['id'])
    assert done['status'] == 'done' and done['done_pieces'] == 3
    assert notified == [job['id']]
    assert set(pregen.lookup('general', [p['key'] for p in pieces])) == {p['key'] for p in pieces}
    assert pregen.read_piece('general', pieces[1]['key']) == b'm4a-compact'
    folder = audio_root / 'general' / 'books' / '1' / 'F1_4_1.05_compact'
    assert sorted(f.name for f in folder.iterdir()) == ['ch0000_00.pack', 'ch0001_00.pack']
    # 끝난 작업의 조각 목록 파일은 지운다
    assert not (audio_root / 'general' / 'jobs' / f"{job['id']}.json").exists()
    assert not worker._tick()  # 더 할 일 없음


def test_worker_fails_job_after_repeated_errors(sqlite_db, audio_root, monkeypatch):
    class BrokenEngine(FakeEngine):
        def synthesize(self, *a):
            raise RuntimeError('boom')

    monkeypatch.setattr(pregen, 'is_enabled', lambda: True)
    monkeypatch.setattr(pregen.tts_engine, 'availability', lambda: (True, ''))
    monkeypatch.setattr(pregen.tts_engine, 'Engine', BrokenEngine)
    pieces = [_piece(f'문장 {i}.') for i in range(pregen.MAX_CONSECUTIVE_FAILURES + 2)]
    with patch.object(pregen, 'wake_worker'):
        job, _ = pregen.create_job('general', 1, 7, _payload(pieces))
    pregen._Worker()._tick()
    failed = Repo.get_job('general', job['id'])
    assert failed['status'] == 'failed' and 'boom' in failed['error']


def test_worker_idles_when_disabled(monkeypatch):
    monkeypatch.setattr(pregen, 'is_enabled', lambda: False)
    assert pregen._Worker()._tick() is False


# ---- routes ----

def _client(role='user', adult=0):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-tts-pregen')
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


def test_create_is_rejected_when_disabled(allow_rating):
    with patch.object(pregen, 'is_enabled', return_value=False):
        response = _client().post('/api/media/tts/pregen', json={'db_type': 'general', 'book_id': 1, **_payload([_piece('문장.')])})
    assert response.status_code == 403


def test_create_passes_session_user(allow_rating):
    job = {'id': 5, 'status': 'queued', 'voice': 'F1', 'steps': 4, 'speed': 1.05, 'total_pieces': 1, 'done_pieces': 0}
    with patch.object(pregen, 'is_enabled', return_value=True), \
            patch.object(pregen, 'create_job', return_value=(job, True)) as create:
        response = _client().post('/api/media/tts/pregen', json={'db_type': 'general', 'book_id': 3, **_payload([_piece('문장.')])})
    assert response.status_code == 200 and response.get_json()['job']['id'] == 5
    assert create.call_args.args[:3] == ('general', 3, 7)


def test_audio_route_serves_pack_slices_with_ranges(sqlite_db, audio_root):
    client = _client(adult=0)
    assert client.get('/api/media/tts/audio/general/not-a-key.m4a').status_code == 404
    assert client.get(f"/api/media/tts/audio/video/{'a' * 64}.m4a").status_code == 404
    assert client.get(f"/api/media/tts/audio/adult/{'a' * 64}.m4a").status_code == 403
    assert client.get(f"/api/media/tts/audio/general/{'a' * 64}.m4a").status_code == 404
    _stored_book(1, ['b' * 64, 'a' * 64])
    url = f"/api/media/tts/audio/general/{'a' * 64}.m4a"
    response = client.get(url)
    assert response.status_code == 200 and response.data == b'aaaaaaaa'
    assert response.mimetype == 'audio/mp4' and 'immutable' in response.headers['Cache-Control']
    assert response.headers['Accept-Ranges'] == 'bytes'
    ranged = client.get(url, headers={'Range': 'bytes=2-4'})
    assert ranged.status_code == 206 and ranged.data == b'aaa'
    assert ranged.headers['Content-Range'] == 'bytes 2-4/8'
    assert client.get(url, headers={'Range': 'bytes=-3'}).data == b'aaa'
    assert client.get(url, headers={'Range': 'bytes=20-'}).status_code == 416
    assert client.get(url, headers={'If-None-Match': f'"{"a" * 64}"'}).status_code == 304


def test_audio_books_routes(sqlite_db, audio_root, allow_rating):
    sqlite_db.execute("INSERT INTO books (id, library_id, title, file_path, file_format, total_pages) VALUES (1, 3, '책 하나', '/b/1.epub', 'epub', 10)")
    book = _stored_book(1, ['a' * 64], user_id=7)
    listed = _client().get('/api/media/tts/audio/books?type=general').get_json()
    assert [b['id'] for b in listed['books']] == [1]
    assert _client().get('/api/media/tts/audio/books?type=audiobook').get_json()['books'] == []
    assert _client(adult=0).get('/api/media/tts/audio/books?type=adult').status_code == 403
    assert _client().delete(f"/api/media/tts/audio/books/{book['id']}?db_type=general").status_code == 200
    assert _client().delete(f"/api/media/tts/audio/books/{book['id']}?db_type=general").status_code == 404


def test_admin_status_requires_admin():
    assert _client(role='user').get('/api/media/tts/pregen/admin-status').status_code == 403
    with patch.object(pregen, 'admin_status', return_value={'enabled': False, 'available': True, 'reason': '', 'queued': 0, 'running': 0, 'cache_mb': 0}):
        response = _client(role='admin').get('/api/media/tts/pregen/admin-status')
    assert response.status_code == 200 and response.get_json()['available'] is True


def test_job_with_every_piece_failing_is_failed_not_done(sqlite_db, audio_root, monkeypatch):
    # 조각 수가 연속 실패 한도보다 적어도 "완료"로 보고하면 안 된다 (테스트 서버에서 실제로 난 버그)
    class BrokenEngine(FakeEngine):
        def synthesize(self, *a):
            raise RuntimeError('model file broken')

    monkeypatch.setattr(pregen, 'is_enabled', lambda: True)
    monkeypatch.setattr(pregen.tts_engine, 'availability', lambda: (True, ''))
    monkeypatch.setattr(pregen.tts_engine, 'Engine', BrokenEngine)
    with patch.object(pregen, 'wake_worker'):
        job, _ = pregen.create_job('general', 1, 7, _payload([_piece('하나.'), _piece('둘.')]))
    pregen._Worker()._tick()
    row = Repo.get_job('general', job['id'])
    assert row['status'] == 'failed' and 'all 2 pieces failed' in row['error']


# ---- 저장 경로 (TTS_AUDIO_ROOT) ----

@pytest.fixture
def root_setting(monkeypatch):
    values = {}
    monkeypatch.setattr(pregen, 'AUDIO_ROOT', None)
    monkeypatch.setattr(pregen.SettingsService, 'get', lambda key, default='': values.get(key, default))
    pregen.invalidate_root_cache()
    yield values
    pregen.invalidate_root_cache()


def test_native_default_root_is_outside_cache(root_setting, monkeypatch):
    monkeypatch.setattr(pregen, '_in_docker', lambda: False)
    root, reason = pregen.audio_root()
    assert reason == '' and root == pregen.DEFAULT_AUDIO_ROOT and 'cache' not in root.split(os.sep)


def test_docker_requires_a_path_on_a_mounted_volume(root_setting, monkeypatch):
    monkeypatch.setattr(pregen, '_in_docker', lambda: True)
    mounted = set()
    monkeypatch.setattr(pregen, '_on_mounted_volume', lambda path: path in mounted)
    # 볼륨이 없는 옛 compose: 기본 경로도 거절
    assert 'not on a mounted volume' in pregen.audio_root()[1]
    # 새 compose(./tts_audio:/app/tts_audio): 설정 없이 기본 경로로 동작
    mounted.add(pregen.DEFAULT_AUDIO_ROOT)
    assert pregen.audio_root() == (pregen.DEFAULT_AUDIO_ROOT, '')
    # 지정 경로는 그 경로가 볼륨이어야 한다
    root_setting['TTS_AUDIO_ROOT'] = '/data/tts'
    pregen.invalidate_root_cache()
    assert pregen.audio_root()[1]
    mounted.add('/data/tts')
    assert pregen.audio_root() == ('/data/tts', '')


def test_relative_root_is_rejected(root_setting, monkeypatch):
    monkeypatch.setattr(pregen, '_in_docker', lambda: False)
    root_setting['TTS_AUDIO_ROOT'] = 'tts_audio'
    pregen.invalidate_root_cache()
    assert pregen.audio_root()[1] == 'audio path must be absolute'


def test_create_job_refuses_unsafe_root(sqlite_db, root_setting, monkeypatch):
    monkeypatch.setattr(pregen, '_in_docker', lambda: True)
    with pytest.raises(RuntimeError):
        pregen.create_job('general', 1, 7, _payload([_piece('문장.')]))


# ---- 알림 영역(스캔 활동) ----

def test_activity_shows_only_visible_jobs(monkeypatch):
    now = pregen._now_ms()
    mine = {'id': 1, 'db_type': 'general', 'book_id': 1, 'user_id': 7, 'title': '내 책', 'status': 'running', 'percent': 40, 'finished_ms': None}
    other = {'id': 2, 'db_type': 'general', 'book_id': 2, 'user_id': 8, 'title': '남의 책', 'status': 'queued', 'percent': 0, 'finished_ms': None}
    adult = {'id': 3, 'db_type': 'adult', 'book_id': 3, 'user_id': 7, 'title': '성인 책', 'status': 'done', 'percent': 100, 'finished_ms': now}
    old = {'id': 4, 'db_type': 'general', 'book_id': 4, 'user_id': 7, 'title': '오래전', 'status': 'done', 'percent': 100, 'finished_ms': now - pregen.RECENT_KEEP_MS - 1}
    monkeypatch.setattr(pregen, '_running_info', dict(mine))
    monkeypatch.setattr(pregen, '_recent_infos', [dict(adult), dict(old)])
    monkeypatch.setattr(pregen, '_queued_rows', lambda: [dict(other)])
    titles = lambda items: [i['title'] for i in items]
    assert titles(pregen.activity_for(7, False, False)) == ['내 책']
    assert titles(pregen.activity_for(7, False, True)) == ['내 책', '성인 책']
    assert titles(pregen.activity_for(99, True, True)) == ['내 책', '남의 책', '성인 책']
    assert 'user_id' not in pregen.activity_for(7, False, False)[0]


def test_worker_thread_runs_at_lowest_priority(monkeypatch):
    calls = []
    monkeypatch.setattr(pregen.os, 'setpriority', lambda which, who, value: calls.append((which, who, value)), raising=False)
    monkeypatch.setattr(pregen.os, 'getpriority', lambda which, who: 19, raising=False)
    monkeypatch.setattr(pregen.os, 'PRIO_PROCESS', 0, raising=False)
    pregen._lower_thread_priority()
    assert calls == [(0, pregen.threading.get_native_id(), pregen.WORKER_NICE)] and pregen.WORKER_NICE == 19


def test_lower_priority_is_ignored_where_unsupported(monkeypatch):
    monkeypatch.delattr(pregen.os, 'setpriority', raising=False)
    pregen._lower_thread_priority()  # Windows 등: 예외 없이 넘어간다
