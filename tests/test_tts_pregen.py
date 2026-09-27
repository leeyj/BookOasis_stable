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
    assert 'piece_key' in dict(tables['tts_audio_cache'])
    assert 'CREATE TABLE IF NOT EXISTS tts_pregen_jobs' in MARIADB_CENTRAL_SCHEMA
    assert 'CREATE TABLE IF NOT EXISTS tts_audio_cache' in MARIADB_CENTRAL_SCHEMA


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


def test_audio_cache_roundtrip(sqlite_db):
    Repo.put_audio('general', 'a' * 64, 3.5, 1000, 1)
    Repo.put_audio('general', 'b' * 64, 2.0, 500, 2)
    assert Repo.get_audio('general', ['a' * 64, 'c' * 64]) == {'a' * 64: 3.5}
    assert Repo.total_audio_bytes('general') == 1500
    Repo.touch_audio('general', ['a' * 64], 10)
    assert Repo.oldest_audio('general', 1) == [('b' * 64, 500)]
    Repo.delete_audio('general', ['b' * 64])
    assert Repo.total_audio_bytes('general') == 1000


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


def test_lookup_returns_only_existing_files(sqlite_db, audio_root):
    present, missing = 'a' * 64, 'b' * 64
    Repo.put_audio('general', present, 3.0, 10, 1)
    Repo.put_audio('general', missing, 3.0, 10, 1)
    path = pregen.audio_path('general', present)
    os.makedirs(os.path.dirname(path))
    open(path, 'wb').close()
    assert pregen.lookup('general', [present, missing, 'not-a-key']) == {present: 3.0}


def test_disk_cap_removes_least_recently_used(sqlite_db, audio_root, monkeypatch):
    monkeypatch.setattr(pregen, 'disk_cap_bytes', lambda: 1500)
    for i, key in enumerate(('a' * 64, 'b' * 64, 'c' * 64)):
        Repo.put_audio('general', key, 1.0, 1000, i)
        path = pregen.audio_path('general', key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').close()
    pregen.enforce_disk_cap('general')
    assert set(Repo.get_audio('general', ['a' * 64, 'b' * 64, 'c' * 64])) == {'c' * 64}
    assert not os.path.exists(pregen.audio_path('general', 'a' * 64))


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


def _fake_encode(wav, sample_rate, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(b'm4a')
    return 3


def test_worker_makes_missing_pieces_and_skips_cached(sqlite_db, audio_root, monkeypatch):
    monkeypatch.setattr(pregen, 'is_enabled', lambda: True)
    monkeypatch.setattr(pregen.tts_engine, 'availability', lambda: (True, ''))
    monkeypatch.setattr(pregen.tts_engine, 'Engine', FakeEngine)
    monkeypatch.setattr(pregen.tts_engine, 'encode_m4a', _fake_encode)
    notified = []
    monkeypatch.setattr(pregen, '_notify_ready', lambda db_type, job: notified.append(job['id']))
    pieces = [_piece('하나.'), _piece('둘.'), _piece('셋.')]
    # 첫 조각은 이미 캐시에 있다
    _fake_encode(None, 10, pregen.audio_path('general', pieces[0]['key']))
    Repo.put_audio('general', pieces[0]['key'], 2.5, 3, 1)
    with patch.object(pregen, 'wake_worker'):
        job, _ = pregen.create_job('general', 1, 7, _payload(pieces))

    worker = pregen._Worker()
    assert worker._tick()
    assert worker._engine.calls == ['둘.', '셋.']
    done = Repo.get_job('general', job['id'])
    assert done['status'] == 'done' and done['done_pieces'] == 3
    assert notified == [job['id']]
    assert set(pregen.lookup('general', [p['key'] for p in pieces])) == {p['key'] for p in pieces}
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


def test_audio_route_rejects_bad_keys_and_adult_without_access(tmp_path, monkeypatch):
    monkeypatch.setattr(pregen, 'AUDIO_ROOT', str(tmp_path))
    client = _client(adult=0)
    assert client.get('/api/media/tts/audio/general/not-a-key.m4a').status_code == 404
    assert client.get(f"/api/media/tts/audio/video/{'a' * 64}.m4a").status_code == 404
    assert client.get(f"/api/media/tts/audio/adult/{'a' * 64}.m4a").status_code == 403
    assert client.get(f"/api/media/tts/audio/general/{'a' * 64}.m4a").status_code == 404
    path = pregen.audio_path('general', 'a' * 64)
    os.makedirs(os.path.dirname(path))
    with open(path, 'wb') as f:
        f.write(b'audio')
    response = client.get(f"/api/media/tts/audio/general/{'a' * 64}.m4a")
    assert response.status_code == 200 and response.data == b'audio'
    assert 'immutable' in response.headers['Cache-Control']


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
