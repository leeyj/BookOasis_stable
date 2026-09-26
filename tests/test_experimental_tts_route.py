import os

import pytest
from flask import Flask

from api import api_bp

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISOLATION_HEADERS = ('Cross-Origin-Opener-Policy', 'Cross-Origin-Embedder-Policy')


def _create_app():
    app = Flask(__name__, template_folder=os.path.join(REPO_ROOT, 'templates'))
    app.config.update(TESTING=True, SECRET_KEY='test-experimental-tts')
    app.register_blueprint(api_bp)
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
    return client


def test_tts_page_is_cross_origin_isolated(user_client):
    response = user_client.get('/experimental/tts?book_id=1&db_type=general')
    assert response.status_code == 200
    assert response.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert response.headers['Cross-Origin-Embedder-Policy'] == 'require-corp'
    assert response.headers['Cache-Control'] == 'no-store'
    body = response.get_data(as_text=True)
    assert '/static/lib/supertonic/st_helper.js' in body
    assert '/static/js/tts/tts_core.js' in body


def test_tts_page_requires_login(client):
    response = client.get('/experimental/tts')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_isolation_headers_do_not_leak_to_other_pages(user_client):
    response = user_client.get('/experimental/page-turn')
    assert response.status_code == 200
    for header in ISOLATION_HEADERS:
        assert header not in response.headers


# ---- 짧은 문장 재현 러너 (tools/tts_repro) ----

import io
import json

import api.routes.experimental_routes as experimental_routes


@pytest.fixture
def admin_client(client, tmp_path, monkeypatch):
    monkeypatch.setattr(experimental_routes, '_REPRO_OUT', str(tmp_path))
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['role'] = 'admin'
        session['is_default_password'] = 0
    return client


def test_repro_runner_is_admin_only(user_client):
    assert user_client.get('/experimental/tts/repro').status_code == 403
    assert user_client.post('/experimental/tts/repro/save', data={}).status_code == 403


def test_repro_save_appends_results_and_done_lists_jobs(admin_client, tmp_path):
    meta = {'job': 's003_webgpu_F1_s8_x1.05_r0', 'pred_dur': 1.5}
    response = admin_client.post('/experimental/tts/repro/save', data={
        'run': 'desktop-webgpu', 'meta': json.dumps(meta),
        'wav': (io.BytesIO(b'RIFF....'), 'x.wav'),
    }, content_type='multipart/form-data')
    assert response.status_code == 200
    assert (tmp_path / 'desktop-webgpu' / 'wav' / 's003_webgpu_F1_s8_x1.05_r0.wav').read_bytes() == b'RIFF....'
    done = admin_client.get('/experimental/tts/repro/done?run=desktop-webgpu').get_json()
    assert done['done'] == ['s003_webgpu_F1_s8_x1.05_r0']


@pytest.mark.parametrize('run,job', [('../x', 'ok'), ('ok', '../../core'), ('a/b', 'ok'), ('', 'ok')])
def test_repro_save_rejects_unsafe_names(admin_client, tmp_path, run, job):
    response = admin_client.post('/experimental/tts/repro/save', data={
        'run': run, 'meta': json.dumps({'job': job}), 'wav': (io.BytesIO(b'x'), 'x.wav'),
    }, content_type='multipart/form-data')
    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(not os.path.isfile(os.path.join(REPO_ROOT, 'templates', 'experimental_tts_repro.html')),
                    reason='공개판에는 재현 러너 화면이 없다')
def test_repro_page_is_cross_origin_isolated(admin_client):
    response = admin_client.get('/experimental/tts/repro')
    assert response.status_code == 200
    assert response.headers['Cross-Origin-Embedder-Policy'] == 'require-corp'
