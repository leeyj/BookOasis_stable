import hashlib
import os
import threading
from unittest.mock import patch

import pytest
import requests
from flask import Flask

from api import api_bp
from services import tts_asset_service as assets

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _create_app():
    app = Flask(__name__, template_folder=os.path.join(REPO_ROOT, 'templates'))
    app.config.update(TESTING=True, SECRET_KEY='test-tts-player')
    app.register_blueprint(api_bp)

    @app.context_processor
    def _assets():
        return {'static_asset_url': lambda filename, **_k: f'/static/{filename}'}

    return app


@pytest.fixture
def client():
    return _create_app().test_client()


@pytest.fixture
def user_client(client):
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['role'] = 'user'
        session['is_default_password'] = 0
        session['has_adult_access'] = 0
    return client


# ---- 듣기 화면 ----

def test_player_page_is_cross_origin_isolated(user_client):
    with patch('api.routes.tts_routes.check_book_rating_permission', return_value=True):
        response = user_client.get('/listen?book_id=1&db_type=general')
    assert response.status_code == 200
    assert response.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert response.headers['Cross-Origin-Embedder-Policy'] == 'require-corp'
    assert response.headers['Cache-Control'] == 'no-store'
    body = response.get_data(as_text=True)
    assert '/static/js/tts/tts_player.js' in body
    assert 'js/i18n.js' in body


def test_player_page_requires_login(client):
    assert client.get('/listen').status_code == 302


def test_player_page_checks_book_permissions(user_client):
    with patch('api.routes.tts_routes.check_book_rating_permission', return_value=False):
        assert user_client.get('/listen?book_id=1&db_type=general').status_code == 403
    assert user_client.get('/listen?book_id=1&db_type=adult').status_code == 403
    assert user_client.get('/listen?book_id=1&db_type=video').status_code == 400


def test_old_experimental_player_url_redirects(user_client):
    response = user_client.get('/experimental/tts/player?book_id=5&db_type=general')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/listen?book_id=5&db_type=general')


# ---- ORT 런타임 ----

@pytest.mark.parametrize('prefix', ['/tts/ort', '/experimental/tts/ort'])
@pytest.mark.parametrize('name', sorted(assets.ORT_FILES))
def test_ort_files_are_served_with_isolation_headers(user_client, prefix, name):
    response = user_client.get(f'{prefix}/{name}')
    assert response.status_code == 200
    assert response.headers['Cross-Origin-Embedder-Policy'] == 'require-corp'
    assert response.headers['Cross-Origin-Resource-Policy'] == 'same-origin'
    assert response.mimetype == ('application/wasm' if name.endswith('.wasm') else 'text/javascript')
    assert len(response.get_data()) == os.path.getsize(os.path.join(assets.ORT_DIR, name))
    response.close()


@pytest.mark.parametrize('path', [
    '/tts/ort/LICENSE',
    '/tts/ort/ort-wasm-simd-threaded.wasm',
    '/tts/ort/..%2F..%2F..%2Fcore.py',
    '/tts/ort/%2E%2E%2Fsupertonic%2Fst_helper.js',
])
def test_other_files_are_not_served(user_client, path):
    assert user_client.get(path).status_code == 404


def test_ort_files_require_login(client):
    assert client.get('/tts/ort/ort.all.min.mjs').status_code == 302


def test_vendored_helper_imports_the_isolated_ort_route():
    with open(os.path.join(REPO_ROOT, 'static', 'lib', 'supertonic', 'st_helper.js'), encoding='utf-8') as f:
        source = f.read()
    assert "from '/tts/ort/ort.all.min.mjs'" in source
    assert "'onnxruntime-web'" not in source


# ---- 모델 가중치 대체 경로 (HF 직접 다운로드가 CORS로 막힐 때) ----

class _FakeHfResponse:
    def __init__(self, data, etag):
        self._data = data
        redirect = type('R', (), {'headers': {'X-Linked-ETag': f'"{etag}"'}})()
        self.history = [redirect]
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for i in range(0, len(self._data), chunk_size):
            yield self._data[i:i + chunk_size]


@pytest.fixture
def fake_hf(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, 'MODEL_DIR', str(tmp_path))
    state = {'data': bytes(range(256)) * 40, 'etag': None, 'calls': []}

    def fake_get(url, **kwargs):
        state['calls'].append(url)
        etag = state['etag'] or hashlib.sha256(state['data']).hexdigest()
        return _FakeHfResponse(state['data'], etag)

    monkeypatch.setattr(requests, 'get', fake_get)
    return state


def test_model_is_downloaded_once_and_served_with_range(user_client, fake_hf, tmp_path):
    first = user_client.get('/tts/model/onnx/vocoder.onnx')
    assert first.status_code == 200
    assert first.get_data() == fake_hf['data']
    first.close()

    ranged = user_client.get('/tts/model/onnx/vocoder.onnx', headers={'Range': 'bytes=1000-'})
    assert ranged.status_code == 206
    assert ranged.get_data() == fake_hf['data'][1000:]
    ranged.close()

    assert len(fake_hf['calls']) == 1
    assert fake_hf['calls'][0].endswith(f'/resolve/{assets.MODEL_REVISION}/onnx/vocoder.onnx')
    assert os.listdir(tmp_path) == ['vocoder.onnx']


def test_concurrent_requests_for_the_same_model_download_once(fake_hf):
    results = []
    threads = [threading.Thread(target=lambda: results.append(assets.ensure_model('text_encoder.onnx')))
               for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(results)) == 1
    assert len(fake_hf['calls']) == 1


def test_checksum_mismatch_is_not_cached(user_client, fake_hf, tmp_path):
    fake_hf['etag'] = '0' * 64
    assert user_client.get('/tts/model/onnx/vocoder.onnx').status_code == 502
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize('path', [
    '/tts/model/onnx/model.onnx',
    '/tts/model/onnx/tts.json',
    '/tts/model/onnx/..%2F..%2Fcore.py',
])
def test_only_known_model_files_are_proxied(user_client, fake_hf, path):
    assert user_client.get(path).status_code == 404
    assert fake_hf['calls'] == []


def test_model_route_requires_login(client, fake_hf):
    assert client.get('/tts/model/onnx/vocoder.onnx').status_code == 302
    assert fake_hf['calls'] == []


def test_model_file_list_matches_the_client():
    with open(os.path.join(REPO_ROOT, 'static', 'js', 'tts', 'tts_core.js'), encoding='utf-8') as f:
        source = f.read()
    assert f"MODEL_REVISION = '{assets.MODEL_REVISION}'" in source
    assert "MODEL_FALLBACK_BASE = '/tts/model'" in source
    for name in assets.MODEL_FILES:
        assert f"'{name[:-len('.onnx')]}'" in source
