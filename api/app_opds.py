# -*- coding: utf-8 -*-
"""
app_opds.py – 타치요미(Tachiyomi/Mihon) 등 비표준 OPDS 클라이언트 전용 라우터

  기존 표준 OPDS(/opds/*)와 완전히 분리된 엔드포인트를 제공합니다.
  차이점: Basic Auth 결과를 TTL 캐시(5분)로 보관하여 페이지별 반복 인증 연산 방지.

  엔드포인트 목록:
  - /app-opds               : 일반 카탈로그 최상위 피드
  - /app-opds-adult         : 성인 전용 최상위 피드 (admin 권한 필요)
  - /app-opds/library/<id>  : 라이브러리 하위 시리즈 목록
  - /app-opds/series/…      : 시리즈 단행본 목록
  - /app-opds/download/…    : 개별 도서 파일 전송
  - /app-opds/recently-added: 신규 추가 도서
  - /app-opds/recently-read : 최근 읽은 도서
"""
import hashlib
import os
import re
import time
import urllib.parse

from flask import Blueprint, Response, jsonify, redirect, request, send_file, session
import database
from api.cache import LRUCache
from api.opds_common.auth import authenticate_basic_auth_user, unauthorized_response
from api.opds_common.xml import atom_response, get_page_params
from api.opds_common.xml_app_opds import build_app_opds_xml
from api.app_opds_handlers import AppOpdsHandlers
from services.opds_service import (
    EMPTY_SERIES_TOKEN,
)
from services.app_opds_viewer_service import (
    get_pdf_source as viewer_get_pdf_source,
    get_progress_state as viewer_get_progress_state,
    get_stream_page as viewer_get_stream_page,
    get_txt_content as viewer_get_txt_content,
    mark_unread as viewer_mark_unread,
    preload_next_book as viewer_preload_next_book,
    save_progress as viewer_save_progress,
)
from services.opds_compat_service import (
    enrich_books_for_app_opds,
    filter_supported_books_for_app_opds,
    filter_supported_series_for_app_opds,
)
from utils.safe_file_response import stream_file_safely
from utils.i18n import _t

app_opds_bp = Blueprint('media_app_opds', __name__)


import threading

# ─── Basic Auth + TTL 캐시 인증 ─────────────────────────────

# { sha256(username:password): (expires_at: float, user: dict) }
_auth_cache: dict = {}
_auth_lock = threading.Lock()
_CACHE_TTL = 300  # 5분 (초 단위)


def _session_user(is_adult: bool = False):
    if not session.get('user_id'):
        return None
    role = session.get('role')
    if is_adult and role != 'admin':
        return None
    return {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': role,
    }


def _get_authenticated_user_cached(is_adult: bool = False):
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return _session_user(is_adult=is_adult)

    key = hashlib.sha256(f"{auth.username}:{auth.password}".encode()).hexdigest()
    now = time.time()

    if key in _auth_cache:
        expires, user = _auth_cache[key]
        if now < expires:
            if is_adult and user.get('role') != 'admin':
                return None
            return user

    with _auth_lock:
        if key in _auth_cache:
            expires, user = _auth_cache[key]
            if now < expires:
                if is_adult and user.get('role') != 'admin':
                    return None
                return user
            _auth_cache.pop(key, None)

        user = authenticate_basic_auth_user(auth.username, auth.password, require_admin=False)
        if not user:
            return None

        user_meta = {
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
        }
        _auth_cache[key] = (time.time() + _CACHE_TTL, user_meta)

        if is_adult and user_meta['role'] != 'admin':
            _auth_cache.pop(key, None)
            return None

        return user_meta


def _check_auth_cached(is_adult: bool = False) -> bool:
    """
    Basic Auth 검증 결과를 TTL 캐시로 보관.
    Double-Checked Locking 패턴을 사용하여 타치요미 병렬 요청 시의 Thundering Herd 현상 방지.
    """
    return _get_authenticated_user_cached(is_adult=is_adult) is not None


def _unauthorized():
    return unauthorized_response('BookOasis App OPDS')


# ─── Atom XML 생성 ────────────────────────────────────────────

APP_OPDS_CACHE_TTL = 60
APP_OPDS_DEFAULT_PAGE_SIZE = 100
APP_OPDS_MAX_PAGE_SIZE = 200
app_opds_response_cache = LRUCache(capacity=50)


def _get_cached_response(key: str):
    cached = app_opds_response_cache.get(key)
    if cached is None:
        return None
    xml, timestamp = cached
    if time.time() - timestamp > APP_OPDS_CACHE_TTL:
        return None
    return xml


def _set_cached_response(key: str, xml: str):
    app_opds_response_cache.put(key, (xml, time.time()))


def _get_page_params():
    return get_page_params(request.args, APP_OPDS_DEFAULT_PAGE_SIZE, APP_OPDS_MAX_PAGE_SIZE)


def _opds_xml(db_type: str, title: str, entries: list,
              is_adult: bool = False, next_link: str = None) -> str:
    """Atom XML 규격의 OPDS 피드 생성 (start 링크는 is_adult 여부에 따라 설정)"""
    search_href = '/app-opds/search' if not is_adult else '/app-opds-adult/search'
    start_href = '/app-opds' if not is_adult else '/app-opds-adult'
    return build_app_opds_xml(
        request,
        title=title,
        entries=entries,
        start_path=start_href,
        search_path=search_href,
        next_link=next_link,
    )


def _atom_response(xml: str):
    return atom_response(xml)


def _parse_paging_args(default_limit: int = 30):
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', default_limit))
    except ValueError:
        page, limit = 1, default_limit
    return max(page, 1), max(limit, 1)

def _redirect_cover_compat(filename: str):
    encoded_filename = urllib.parse.quote(filename, safe='/')
    target_path = f"/covers/{encoded_filename}"
    query = request.query_string.decode('utf-8')
    if query:
        target_path = f"{target_path}?{query}"
    return redirect(target_path, code=307)


def _require_app_opds_auth(db_type: str = None):
    is_adult_prefix = request.path.startswith('/app-opds-adult/')
    if not _check_auth_cached(is_adult=is_adult_prefix):
        return _unauthorized()
    if db_type and str(db_type).strip().lower() == 'adult' and not _check_auth_cached(is_adult=True):
        return _unauthorized()
    return None


def _enrich_books_for_app_opds(books_list, db_type: str, is_adult_prefix: bool):
    return enrich_books_for_app_opds(books_list, db_type, is_adult_prefix)


def _filter_supported_series_for_app_opds(db_type: str, series_list):
    return filter_supported_series_for_app_opds(db_type, series_list)


def _filter_supported_books_for_app_opds(books_list):
    return filter_supported_books_for_app_opds(books_list)

_handlers = AppOpdsHandlers(
    check_auth_cached=_check_auth_cached,
    get_current_user=_get_authenticated_user_cached,
    unauthorized=_unauthorized,
    get_cached_response=_get_cached_response,
    set_cached_response=_set_cached_response,
    opds_xml=_opds_xml,
    atom_response=_atom_response,
    parse_paging_args=_parse_paging_args,
    get_page_params=_get_page_params,
    filter_supported_series=_filter_supported_series_for_app_opds,
    filter_supported_books=_filter_supported_books_for_app_opds,
    enrich_books=_enrich_books_for_app_opds,
)

# ─── 라우터 ──────────────────────────────────────────────────

@app_opds_bp.route('/app-opds', methods=['GET'])
def app_opds_root():
    return _handlers.handle_root_feed(is_adult=False)


@app_opds_bp.route('/app-opds/api/media/list', methods=['GET'])
@app_opds_bp.route('/app-opds/api/media/all-list', methods=['GET'])
def app_opds_media_api_compat():
    return _handlers.handle_media_api_compat(is_adult=False)


@app_opds_bp.route('/app-opds/api/media/libraries', methods=['GET'])
def app_opds_media_libraries_compat():
    return _handlers.handle_media_libraries_compat(is_adult=False)


@app_opds_bp.route('/app-opds/api/media/detail', methods=['GET'])
def app_opds_media_detail_compat():
    return _handlers.handle_media_detail_compat(is_adult=False)


@app_opds_bp.route('/app-opds/api/media/books/<int:book_id>/info', methods=['GET'])
def app_opds_book_info_compat(book_id: int):
    return _handlers.handle_book_info_compat(is_adult=False, book_id=book_id)


@app_opds_bp.route('/app-opds/api/media/stream', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/stream', methods=['GET'])
def app_opds_stream_compat():
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = request.args.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error
    current_user = _get_authenticated_user_cached(is_adult=default_db_type == 'adult' or db_type == 'adult') or {}

    book_id = request.args.get('book_id')
    try:
        page_idx = int(request.args.get('page_idx', 0))
    except (ValueError, TypeError):
        page_idx = 0
    user_id = current_user.get('id', 1)
    role = current_user.get('role')

    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400
    try:
        book_id = int(book_id)
    except (ValueError, TypeError):
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    result = viewer_get_stream_page(db_type, book_id, page_idx, user_id=user_id, role=role)
    if result['status'] == 'book_not_found':
        return jsonify({'error': _t('api.err_book_not_found')}), 404
    if result['status'] == 'extract_failed':
        return jsonify({'error': _t('api.err_extract_page')}), 400

    res = Response(result['img_data'], mimetype=result['mime_type'])
    res.headers['Cache-Control'] = 'public, max-age=31536000'
    return res


@app_opds_bp.route('/app-opds/api/media/txt', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/txt', methods=['GET'])
def app_opds_txt_compat():
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = request.args.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error
    current_user = _get_authenticated_user_cached(is_adult=default_db_type == 'adult' or db_type == 'adult') or {}
    user_id = current_user.get('id', 1)
    role = current_user.get('role')

    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    result = viewer_get_txt_content(db_type, book_id, user_id=user_id, role=role)
    if result['status'] == 'book_not_found':
        return jsonify({'error': _t('api.err_book_not_found')}), 404
    if result['status'] == 'file_not_found':
        return jsonify({'error': _t('api.err_file_not_found')}), 404
    if result['status'] == 'error':
        return jsonify({'error': result.get('error', 'Unknown error')}), 500
    return Response(result['content'], mimetype='text/plain; charset=utf-8')


@app_opds_bp.route('/app-opds/api/media/pdf', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/pdf', methods=['GET'])
def app_opds_pdf_compat():
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = request.args.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error
    current_user = _get_authenticated_user_cached(is_adult=default_db_type == 'adult' or db_type == 'adult') or {}
    user_id = current_user.get('id', 1)
    role = current_user.get('role')

    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    source = viewer_get_pdf_source(db_type, book_id, user_id=user_id, role=role)
    if source['status'] == 'book_not_found':
        return jsonify({'error': _t('api.err_book_not_found')}), 404
    if source['status'] == 'file_not_found':
        return jsonify({'error': _t('api.err_file_not_found')}), 404

    file_path = source['file_path']
    mime = source['mime']

    range_header = request.headers.get('Range')
    if not range_header:
        try:
            return stream_file_safely(file_path, mimetype=mime)
        except OSError as e:
            return jsonify({'error': str(e)}), 500

    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None
    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if m:
        byte1 = int(m.group(1))
        if m.group(2):
            byte2 = int(m.group(2))
    if byte2 is None:
        byte2 = size - 1
    length = byte2 - byte1 + 1

    try:
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
        rv = Response(data, 206, mimetype=mime, direct_passthrough=True)
        rv.headers['Content-Range'] = f'bytes {byte1}-{byte2}/{size}'
        rv.headers['Accept-Ranges'] = 'bytes'
        rv.headers['Content-Length'] = str(length)
        return rv
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/progress-state', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/progress-state', methods=['GET'])
def app_opds_progress_state_compat():
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = request.args.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error

    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400

    try:
        result = viewer_get_progress_state(db_type, book_id, user_id=1)
        if result['status'] != 'ok':
            return jsonify({'success': False, 'error': 'book not found'}), 404
        return jsonify({'success': True, 'state': result['state']})
    except Exception as e:
        print(f"[App-OPDS Progress State API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/progress', methods=['POST'])
@app_opds_bp.route('/app-opds-adult/api/media/progress', methods=['POST'])
def app_opds_progress_compat():
    data = request.json or {}
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = data.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error

    try:
        book_id = data.get('book_id')
        page_idx = data.get('page_idx')
        total_pages = data.get('total_pages')
        epub_session = data.get('epub_session') or None

        if book_id is None or page_idx is None:
            return jsonify({'success': False, 'error': _t('api.err_book_id_page_idx_required')}), 400

        viewer_save_progress(db_type, book_id, page_idx, total_pages, epub_session=epub_session, user_id=1)
        return jsonify({'success': True})
    except Exception as e:
        print(f"[App-OPDS Progress API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/unread', methods=['POST'])
@app_opds_bp.route('/app-opds-adult/api/media/unread', methods=['POST'])
def app_opds_unread_compat():
    data = request.json or {}
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = data.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error

    try:
        book_id = data.get('book_id')
        if book_id is None:
            return jsonify({'success': False, 'error': 'book_id가 누락되었습니다.'}), 400

        viewer_mark_unread(db_type, book_id, user_id=1)
        return jsonify({'success': True})
    except Exception as e:
        print(f"[App-OPDS Unread API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/preload-next-book', methods=['POST'])
@app_opds_bp.route('/app-opds-adult/api/media/preload-next-book', methods=['POST'])
def app_opds_preload_next_book_compat():
    data = request.json or {}
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = data.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error

    try:
        book_id = data.get('book_id')
        if not book_id:
            return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400

        result = viewer_preload_next_book(db_type, book_id, user_id=1)
        if result['status'] == 'no_next':
            return jsonify({'success': True, 'message': _t('api.msg_no_next_book')})
        if result['status'] == 'next_not_exist':
            return jsonify({'success': False, 'error': _t('api.err_next_book_not_exist')}), 404
        return jsonify({'success': True, 'preloaded_book_id': result['preloaded_book_id']})
    except Exception as e:
        print(f"[App-OPDS Preload API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/login', methods=['POST', 'GET'])
def app_opds_login_compat():
    return _handlers.handle_login_compat(is_adult=False)

@app_opds_bp.route('/app-opds/covers/<path:filename>', methods=['GET'])
def app_opds_cover_compat(filename: str):
    return _redirect_cover_compat(filename)

@app_opds_bp.route('/app-opds-adult', methods=['GET'])
def app_opds_adult_root():
    return _handlers.handle_root_feed(is_adult=True)


@app_opds_bp.route('/app-opds-adult/api/media/list', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/all-list', methods=['GET'])
def app_opds_adult_media_api_compat():
    return _handlers.handle_media_api_compat(is_adult=True)


@app_opds_bp.route('/app-opds-adult/api/media/libraries', methods=['GET'])
def app_opds_adult_media_libraries_compat():
    return _handlers.handle_media_libraries_compat(is_adult=True)


@app_opds_bp.route('/app-opds-adult/api/media/detail', methods=['GET'])
def app_opds_adult_media_detail_compat():
    return _handlers.handle_media_detail_compat(is_adult=True)


@app_opds_bp.route('/app-opds-adult/api/media/books/<int:book_id>/info', methods=['GET'])
def app_opds_adult_book_info_compat(book_id: int):
    return _handlers.handle_book_info_compat(is_adult=True, book_id=book_id)


@app_opds_bp.route('/app-opds-adult/login', methods=['POST', 'GET'])
def app_opds_adult_login_compat():
    return _handlers.handle_login_compat(is_adult=True)

@app_opds_bp.route('/app-opds-adult/covers/<path:filename>', methods=['GET'])
def app_opds_adult_cover_compat(filename: str):
    return _redirect_cover_compat(filename)

@app_opds_bp.route('/app-opds/library/<int:lib_id>', methods=['GET'])
def app_opds_library(lib_id: int):
    return _handlers.handle_library_feed(is_adult=False, lib_id=lib_id)


@app_opds_bp.route('/app-opds/adult/library/<int:lib_id>', methods=['GET'])
def app_opds_adult_library(lib_id: int):
    return _handlers.handle_library_feed(is_adult=True, lib_id=lib_id)


@app_opds_bp.route('/app-opds/series/<int:lib_id>/<path:series_name>', methods=['GET'])
def app_opds_series_books(lib_id: int, series_name: str):
    return _handlers.handle_series_feed(is_adult=False, lib_id=lib_id, series_name=series_name)


@app_opds_bp.route('/app-opds/adult/series/<int:lib_id>/<path:series_name>', methods=['GET'])
def app_opds_adult_series_books(lib_id: int, series_name: str):
    return _handlers.handle_series_feed(is_adult=True, lib_id=lib_id, series_name=series_name)


@app_opds_bp.route('/app-opds/recently-added', methods=['GET'])
def app_opds_recently_added():
    return _handlers.handle_recently_feed(is_adult=False, kind='added')


@app_opds_bp.route('/app-opds/recently-read', methods=['GET'])
def app_opds_recently_read():
    return _handlers.handle_recently_feed(is_adult=False, kind='read')


@app_opds_bp.route('/app-opds/favorite', methods=['GET'])
def app_opds_favorite():
    return _handlers.handle_recently_feed(is_adult=False, kind='favorite')


@app_opds_bp.route('/app-opds/adult/recently-added', methods=['GET'])
def app_opds_adult_recently_added():
    return _handlers.handle_recently_feed(is_adult=True, kind='added')


@app_opds_bp.route('/app-opds/adult/recently-read', methods=['GET'])
def app_opds_adult_recently_read():
    return _handlers.handle_recently_feed(is_adult=True, kind='read')


@app_opds_bp.route('/app-opds/adult/favorite', methods=['GET'])
def app_opds_adult_favorite():
    return _handlers.handle_recently_feed(is_adult=True, kind='favorite')


@app_opds_bp.route('/app-opds/download/<string:db_type>/<int:book_id>', methods=['GET'])
def app_opds_download_book(db_type: str, book_id: int):
    """타치요미/미혼이 파일을 직접 다운로드하는 엔드포인트"""
    is_adult = (db_type == 'adult')
    if not _check_auth_cached(is_adult=is_adult):
        return _unauthorized()

    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM books WHERE id=?", (book_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': _t('api.err_book_not_found')}), 404
    file_path = row['file_path']
    if not os.path.exists(file_path):
        return jsonify({'error': _t('api.err_file_not_found')}), 404

    return send_file(file_path, as_attachment=True)


@app_opds_bp.route('/app-opds/search', methods=['GET'])
def app_opds_search():
    return jsonify({'success': False, 'error': 'App-OPDS search is temporarily disabled'}), 503


@app_opds_bp.route('/app-opds-adult/search', methods=['GET'])
def app_opds_adult_search():
    return jsonify({'success': False, 'error': 'App-OPDS search is temporarily disabled'}), 503


