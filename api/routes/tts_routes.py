# -*- coding: utf-8 -*-
"""
tts_routes.py - 브라우저 TTS("음성으로 듣기"): 플레이어 화면, 런타임/모델 자산, 듣기 위치 저장 /
읽기↔듣기 위치 동기화 API. 합성은 기본적으로 클라이언트가 하고, 관리자가 켜면 서버가 책을 미리 만들어
둘 수 있다(서버 미리 만들기 — services/tts_pregen_service.py).
"""
import os

from flask import Blueprint, request, jsonify, session, render_template, make_response, send_from_directory, Response

from api.auth import login_required, admin_required, check_adult_permission, check_book_rating_permission
from services import tts_asset_service as assets
from services import tts_pregen_service as pregen
from services.tts_progress_service import TTSProgressService
from utils.i18n import _t

tts_bp = Blueprint('tts', __name__)

# TTS 대상은 TXT/EPUB 도서뿐이라 도서 DB만 허용한다
_BOOK_DB_TYPES = ('general', 'adult')


def _check_access(db_type, book_id):
    if db_type not in _BOOK_DB_TYPES:
        return jsonify({'success': False, 'error': 'invalid db_type'}), 400
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    if not check_book_rating_permission(db_type, book_id):
        return jsonify({'success': False, 'error': _t('api.err_no_rating_access')}), 403
    return None


def _book_id(value):
    try:
        book_id = int(value)
    except (TypeError, ValueError):
        return None
    return book_id if book_id > 0 else None


@tts_bp.route('/api/media/tts/position', methods=['GET'])
@login_required
def get_tts_position():
    db_type = request.args.get('db_type', 'general')
    book_id = _book_id(request.args.get('book_id'))
    if book_id is None:
        return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400
    denied = _check_access(db_type, book_id)
    if denied:
        return denied
    state = TTSProgressService.get_sync_state(db_type, book_id, session.get('user_id'))
    return jsonify({'success': True, 'state': state})


@tts_bp.route('/api/media/tts/position', methods=['POST'])
@login_required
def save_tts_position():
    # 페이지를 떠날 때 sendBeacon으로도 오므로 Content-Type에 관계없이 JSON으로 읽는다
    payload = request.get_json(force=True, silent=True) or {}
    db_type = payload.get('db_type', 'general')
    book_id = _book_id(payload.get('book_id'))
    if book_id is None:
        return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400
    denied = _check_access(db_type, book_id)
    if denied:
        return denied
    try:
        updated_ms = TTSProgressService.save(db_type, book_id, session.get('user_id'), payload)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'success': True, 'updated_ms': updated_ms})


@tts_bp.route('/listen', methods=['GET'])
@login_required
def tts_player():
    """듣기 화면: 본문을 스크롤로 보여 주며 읽는 문장을 강조한다."""
    book_id = _book_id(request.args.get('book_id'))
    if book_id is not None:
        denied = _check_access(request.args.get('db_type', 'general'), book_id)
        if denied:
            return denied
    response = make_response(render_template('tts_player.html', tts_pregen_enabled=pregen.is_enabled()))
    response.headers['Cache-Control'] = 'no-store'
    return assets.cross_origin_isolate(response)


@tts_bp.route('/tts/ort/<name>', methods=['GET'])
@login_required
def tts_ort_file(name):
    """ORT 워커 스크립트도 COEP 헤더가 있어야 격리된 페이지에서 뜨므로 static 대신 여기서 내준다."""
    if name not in assets.ORT_FILES:
        return Response(status=404)
    # 모듈 스크립트/wasm은 MIME이 틀리면 브라우저가 거부하므로 OS mimetypes 설정에 맡기지 않는다
    mimetype = 'application/wasm' if name.endswith('.wasm') else 'text/javascript'
    response = send_from_directory(assets.ORT_DIR, name, mimetype=mimetype, max_age=86400 * 30)
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    return assets.cross_origin_isolate(response)


@tts_bp.route('/tts/model/onnx/<name>', methods=['GET'])
@login_required
def tts_model_file(name):
    """HF 직접 다운로드가 CORS로 막힌 브라우저용 모델 가중치. Range를 지원해 이어받기가 된다."""
    if name not in assets.MODEL_FILES:
        return Response(status=404)
    try:
        assets.ensure_model(name)
    except Exception as e:
        return jsonify({'success': False, 'error': f'model download failed: {e}'}), 502
    return send_from_directory(assets.MODEL_DIR, name, mimetype='application/octet-stream',
                               max_age=86400 * 30, conditional=True)


# ---- 서버 미리 만들기 (services/tts_pregen_service.py) ----
@tts_bp.route('/api/media/tts/pregen', methods=['POST'])
@login_required
def create_tts_pregen():
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('db_type', 'general')
    book_id = _book_id(payload.get('book_id'))
    if book_id is None:
        return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400
    denied = _check_access(db_type, book_id)
    if denied:
        return denied
    if not pregen.is_enabled():
        return jsonify({'success': False, 'error': 'server pre-generation is disabled'}), 403
    try:
        job, created = pregen.create_job(db_type, book_id, session.get('user_id'), payload)
    except PermissionError as e:
        return jsonify({'success': False, 'error': str(e)}), 429
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 409
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'success': True, 'created': created, 'job': pregen.job_view(job)})


@tts_bp.route('/api/media/tts/pregen/status', methods=['GET'])
@login_required
def get_tts_pregen_status():
    db_type = request.args.get('db_type', 'general')
    book_id = _book_id(request.args.get('book_id'))
    if book_id is None:
        return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400
    denied = _check_access(db_type, book_id)
    if denied:
        return denied
    return jsonify({'success': True, 'enabled': pregen.is_enabled(), 'job': pregen.latest_status(db_type, book_id)})


@tts_bp.route('/api/media/tts/pregen/admin-status', methods=['GET'])
@admin_required
def get_tts_pregen_admin_status():
    return jsonify({'success': True, **pregen.admin_status()})


@tts_bp.route('/api/media/tts/pregen/<int:job_id>', methods=['DELETE'])
@login_required
def cancel_tts_pregen(job_id):
    db_type = request.args.get('db_type', 'general')
    if db_type not in _BOOK_DB_TYPES:
        return jsonify({'success': False, 'error': 'invalid db_type'}), 400
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        cancelled = pregen.cancel_job(db_type, job_id, session.get('user_id'), session.get('role') == 'admin')
    except LookupError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'success': False, 'error': str(e)}), 403
    return jsonify({'success': True, 'cancelled': cancelled})


@tts_bp.route('/api/media/tts/audio/lookup', methods=['POST'])
@login_required
def lookup_tts_audio():
    """조각 키 목록 중 서버에 만들어 둔 것만 {key: 길이(초)}로 돌려준다. 기능이 꺼져 있어도 이미 만든 음성은 쓴다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('db_type', 'general')
    if db_type not in _BOOK_DB_TYPES:
        return jsonify({'success': False, 'error': 'invalid db_type'}), 400
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        found = pregen.lookup(db_type, payload.get('keys'))
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'success': True, 'audio': found})


@tts_bp.route('/api/media/tts/audio/<db_type>/<key>.m4a', methods=['GET'])
@login_required
def get_tts_audio(db_type, key):
    if db_type not in _BOOK_DB_TYPES or not pregen.KEY_RE.match(key):
        return Response(status=404)
    if not check_adult_permission(db_type):
        return Response(status=403)
    path = pregen.audio_path(db_type, key)
    if not os.path.isfile(path):
        return Response(status=404)
    # 키가 내용의 해시라 파일이 바뀌지 않는다 → 오래 캐시
    response = send_from_directory(os.path.dirname(path), os.path.basename(path), mimetype='audio/mp4',
                                   max_age=86400 * 365, conditional=True)
    response.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
    return response
