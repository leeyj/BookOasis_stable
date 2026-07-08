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
import html
import mimetypes
import os
import re
import time
import urllib.parse
from datetime import datetime

from flask import Blueprint, Response, jsonify, redirect, request, send_file, session
import database
from api.cache import LRUCache
from services.opds_service import (
    EMPTY_SERIES_TOKEN,
    get_book_entries,
    get_library_list,
    get_recently_added_entries,
    get_recently_read_entries,
    get_series_entries,
    search_books_entries,
)
from services.book_detail_service import BookDetailService
from services.book_info_service import BookInfoService
from services.category_service import CategoryService
from services.series_service import SeriesService
from services.stream_service import StreamService
from utils.i18n import _t
from werkzeug.security import check_password_hash

app_opds_bp = Blueprint('media_app_opds', __name__)


import threading

# ─── Basic Auth + TTL 캐시 인증 ─────────────────────────────

# { sha256(username:password): (expires_at: float, user: dict) }
_auth_cache: dict = {}
_auth_lock = threading.Lock()
_CACHE_TTL = 300  # 5분 (초 단위)


def _check_auth_cached(is_adult: bool = False) -> bool:
    """
    Basic Auth 검증 결과를 TTL 캐시로 보관.
    Double-Checked Locking 패턴을 사용하여 타치요미 병렬 요청 시의 Thundering Herd 현상 방지.
    """
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        # Browser-based compat clients may rely on existing web session auth instead of Basic Auth.
        if session.get('user_id'):
            if is_adult and session.get('role') != 'admin':
                return False
            return True
        return False

    key = hashlib.sha256(f"{auth.username}:{auth.password}".encode()).hexdigest()
    now = time.time()

    # 1. 락 없는 빠른 읽기 (Fast Path)
    if key in _auth_cache:
        expires, user = _auth_cache[key]
        if now < expires:
            if is_adult and user.get('role') != 'admin':
                return False
            return True

    # 2. 캐시 미스 또는 만료된 경우 락 획득 (Slow Path)
    with _auth_lock:
        # 락 획득 후 이미 갱신되었는지 다시 한 번 확인 (Double Check)
        if key in _auth_cache:
            expires, user = _auth_cache[key]
            if now < expires:
                if is_adult and user.get('role') != 'admin':
                    return False
                return True
            # 만료된 경우 쓰레드 안전하게 삭제 (pop 사용으로 KeyError 예방)
            _auth_cache.pop(key, None)

        # 3. 무거운 작업 (DB 접근 및 bcrypt 검증) 수행 (오직 하나의 스레드만 진입)
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash, role FROM users WHERE username = ?",
            (auth.username,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False
        if not check_password_hash(row['password_hash'], auth.password):
            return False
            
        # 4. 검증이 완료되면 캐시에 업데이트
        _auth_cache[key] = (time.time() + _CACHE_TTL, dict(row))
        
        if is_adult and row['role'] != 'admin':
            return False
            
        return True


def _unauthorized():
    return Response(
        "Unauthorized", status=401,
        headers={'WWW-Authenticate': 'Basic realm="BookOasis App OPDS"'}
    )


# ─── Atom XML 생성 ────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    return html.escape(str(text), quote=True)


APP_OPDS_CACHE_TTL = 60
APP_OPDS_DEFAULT_PAGE_SIZE = 100
APP_OPDS_MAX_PAGE_SIZE = 200
app_opds_response_cache = LRUCache(capacity=50)
APP_OPDS_SUPPORTED_FORMATS = {'zip', 'cbz'}


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
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get('page_size', str(APP_OPDS_DEFAULT_PAGE_SIZE)))
    except ValueError:
        page_size = APP_OPDS_DEFAULT_PAGE_SIZE

    page = max(page, 1)
    page_size = min(max(page_size, 1), APP_OPDS_MAX_PAGE_SIZE)
    offset = (page - 1) * page_size
    return page, page_size, offset


def _opds_xml(db_type: str, title: str, entries: list,
              is_adult: bool = False, next_link: str = None) -> str:
    """Atom XML 규격의 OPDS 피드 생성 (start 링크는 /app-opds 기준)"""
    base_url = request.url_root.rstrip('/')
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">',
        f'  <id>{_escape_xml(request.url)}</id>',
        f'  <title>{_escape_xml(title)}</title>',
        f'  <updated>{now}</updated>',
        f'  <link rel="self" href="{_escape_xml(request.url)}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
        f'  <link rel="start" href="{_escape_xml(base_url + "/app-opds")}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
    ]
    search_href = "/app-opds/search" if not is_adult else "/app-opds-adult/search"
    lines.append(
        f'  <link rel="search" href="{_escape_xml(base_url + search_href)}" type="application/opensearchdescription+xml" title="Search Books"/>'
    )
    if next_link:
        lines.append(
            f'  <link rel="next" href="{_escape_xml(next_link)}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>'
        )

    for e in entries:
        lines += [
            '  <entry>',
            f'    <title>{_escape_xml(e["title"])}</title>',
            f'    <id>{_escape_xml(e["id"])}</id>',
            f'    <updated>{now}</updated>',
        ]
        if e.get('summary'):
            lines.append(f'    <summary>{_escape_xml(e["summary"])}</summary>')

        href = f"{base_url}{e['href']}"
        if e['type'] == 'navigation':
            lines.append(
                f'    <link rel="subsection" href="{_escape_xml(href)}" '
                f'type="application/atom+xml;profile=opds-catalog;kind=navigation"/>'
            )
            if e.get('cover'):
                cover_url = f"{base_url}/covers/{_escape_xml(e['cover'])}"
                cover_mime = mimetypes.guess_type(e['cover'])[0] or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
        elif e['type'] == 'acquisition':
            lines.append(
                f'    <link rel="http://opds-spec.org/acquisition" '
                f'href="{_escape_xml(href)}" type="{_escape_xml(e["mime"])}"/>'
            )
            if e.get('cover'):
                cover_url = f"{base_url}/covers/{_escape_xml(e['cover'])}"
                cover_mime = mimetypes.guess_type(e['cover'])[0] or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
        lines.append('  </entry>')

    lines.append('</feed>')
    return '\n'.join(lines)


def _atom_response(xml: str):
    return Response(xml, mimetype='application/atom+xml; charset=utf-8')


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
    prefix = '/app-opds-adult' if is_adult_prefix else '/app-opds'
    enriched = []
    for b in books_list or []:
        item = dict(b)
        fmt = (item.get('file_format') or '').lower()
        item['file_format'] = fmt
        item['format'] = fmt

        book_id = item.get('id')
        if fmt in ('zip', 'cbz', 'imgdir'):
            item['read_url'] = f"{prefix}/api/media/stream?db_type={db_type}&book_id={book_id}&page_idx=0"
            item['reader_type'] = 'comic'
        elif fmt == 'txt':
            item['read_url'] = f"{prefix}/api/media/txt?db_type={db_type}&book_id={book_id}"
            item['reader_type'] = 'txt'
        elif fmt in ('epub', 'pdf'):
            item['read_url'] = f"{prefix}/api/media/pdf?db_type={db_type}&book_id={book_id}"
            item['reader_type'] = fmt
        else:
            item['read_url'] = ''
            item['reader_type'] = fmt or 'unknown'

        enriched.append(item)
    return enriched


def _get_supported_series_names(db_type: str, series_names):
    clean_names = [s for s in (series_names or []) if s]
    if not clean_names:
        return set()

    conn = database.get_connection(db_type)
    try:
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(clean_names))
        query = f"""
            SELECT DISTINCT series_name
            FROM books
            WHERE COALESCE(is_deleted, 0) = 0
              AND lower(COALESCE(file_format, '')) IN ('zip', 'cbz')
              AND series_name IN ({placeholders})
        """
        cursor.execute(query, tuple(clean_names))
        return {row['series_name'] for row in cursor.fetchall()}
    finally:
        conn.close()


def _filter_supported_series_for_app_opds(db_type: str, series_list):
    names = [s.get('series_name', '') for s in (series_list or []) if isinstance(s, dict)]
    allowed_names = _get_supported_series_names(db_type, names)
    return [s for s in (series_list or []) if s.get('series_name', '') in allowed_names]


def _filter_supported_books_for_app_opds(books_list):
    filtered = []
    for b in books_list or []:
        fmt = str((b or {}).get('file_format') or '').lower()
        if fmt in APP_OPDS_SUPPORTED_FORMATS:
            filtered.append(b)
    return filtered

# ─── 라우터 ──────────────────────────────────────────────────

@app_opds_bp.route('/app-opds', methods=['GET'])
def app_opds_root():
    """타치요미용 일반 OPDS 최상위 피드"""
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    cache_key = 'app_opds_root:general'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    libs = get_library_list('general')
    entries = [
        {'id': f"urn:app:library:{l['id']}", 'title': l['name'],
         'type': 'navigation', 'href': f"/app-opds/library/{l['id']}"}
        for l in libs
    ]
    entries.extend([
        {'id': 'urn:app:recently-added', 'title': '신규 추가',
         'type': 'navigation', 'href': '/app-opds/recently-added'},
        {'id': 'urn:app:recently-read', 'title': '최근 읽은 도서',
         'type': 'navigation', 'href': '/app-opds/recently-read'},
    ])
    xml = _opds_xml('general', "BookOasis App OPDS Catalog", entries)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/api/media/list', methods=['GET'])
@app_opds_bp.route('/app-opds/api/media/all-list', methods=['GET'])
def app_opds_media_api_compat():
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    db_type = request.args.get('type', 'general')
    library_id = request.args.get('library_id', 'all')
    search_query = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'asc').strip().lower()

    try:
        if request.path.endswith('/all-list'):
            series_list = SeriesService.get_all_books_list(db_type, library_id)
            series_list = _filter_supported_series_for_app_opds(db_type, series_list)
            return jsonify({'success': True, 'series': series_list})

        page, limit = _parse_paging_args(default_limit=30)
        series_list = SeriesService.get_books_list(db_type, library_id, page, limit, search_query, sort)
        series_list = _filter_supported_series_for_app_opds(db_type, series_list)
        has_more = len(series_list) > limit
        if has_more:
            series_list = series_list[:limit]
        return jsonify({'success': True, 'series': series_list, 'has_more': has_more})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/libraries', methods=['GET'])
def app_opds_media_libraries_compat():
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    db_type = request.args.get('type', 'general')
    if db_type == 'adult' and not _check_auth_cached(is_adult=True):
        return _unauthorized()

    try:
        libraries = CategoryService.get_libraries(db_type, user_id=None, role='admin')
        return jsonify({'success': True, 'libraries': libraries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/detail', methods=['GET'])
def app_opds_media_detail_compat():
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    db_type = request.args.get('type', 'general')
    if db_type == 'adult' and not _check_auth_cached(is_adult=True):
        return _unauthorized()

    series_name = request.args.get('series', '')
    library_id = request.args.get('library_id', 'all')

    try:
        meta, books_list = BookDetailService.get_media_detail(
            db_type,
            series_name,
            library_id,
            user_id=1,
            restrict_same_directory=False,
        )
        books_list = _filter_supported_books_for_app_opds(books_list)
        books_list = _enrich_books_for_app_opds(books_list, db_type, is_adult_prefix=False)
        return jsonify({'success': True, 'meta': meta, 'books': books_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/books/<int:book_id>/info', methods=['GET'])
def app_opds_book_info_compat(book_id: int):
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    db_type = request.args.get('type', 'general')
    if db_type == 'adult' and not _check_auth_cached(is_adult=True):
        return _unauthorized()

    try:
        info = BookInfoService.get_viewer_info(db_type, book_id)
        if info is None:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        return jsonify({
            'success': True,
            'total_pages': info.get('total_pages', 0),
            'cover_image': info.get('cover_image')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/api/media/stream', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/stream', methods=['GET'])
def app_opds_stream_compat():
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = request.args.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error

    book_id = request.args.get('book_id')
    try:
        page_idx = int(request.args.get('page_idx', 0))
    except (ValueError, TypeError):
        page_idx = 0
    user_id = 1

    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400
    try:
        book_id = int(book_id)
    except (ValueError, TypeError):
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path, file_format = StreamService.get_book_file_info(db_type, book_id)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    result = StreamService.extract_page(file_path, page_idx, db_type=db_type, book_id=book_id)
    if result is None:
        return jsonify({'error': _t('api.err_extract_page')}), 400

    img_data, mime_type = result
    try:
        total_pages = StreamService.get_total_pages_for_book(
            db_type,
            book_id,
            file_path=file_path,
            file_format=file_format
        )
        if total_pages > 0:
            StreamService.record_progress(db_type, book_id, page_idx, total_pages, user_id=user_id)
    except Exception as e:
        print(f"[App-OPDS Progress Recorder] Fail: {e}")

    res = Response(img_data, mimetype=mime_type)
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

    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    content, error = StreamService.get_txt_content(file_path)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500
    return Response(content, mimetype='text/plain; charset=utf-8')


@app_opds_bp.route('/app-opds/api/media/pdf', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/pdf', methods=['GET'])
def app_opds_pdf_compat():
    default_db_type = 'adult' if request.path.startswith('/app-opds-adult/') else 'general'
    db_type = request.args.get('db_type', default_db_type)
    auth_error = _require_app_opds_auth(db_type)
    if auth_error:
        return auth_error

    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404
    if not os.path.exists(file_path):
        return jsonify({'error': _t('api.err_file_not_found')}), 404

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext == '.epub':
        mime = 'application/epub+zip'
    elif ext == '.pdf':
        mime = 'application/pdf'
    elif ext == '.txt':
        mime = 'text/plain'
    else:
        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or 'application/octet-stream'

    range_header = request.headers.get('Range')
    if not range_header:
        return send_file(file_path, mimetype=mime)

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
        state = StreamService.get_progress_state(db_type, book_id, user_id=1)
        if not state:
            return jsonify({'success': False, 'error': 'book not found'}), 404
        return jsonify({'success': True, 'state': state})
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

        if total_pages is None:
            total_pages = 1

        StreamService.record_progress(
            db_type,
            book_id,
            page_idx,
            total_pages,
            user_id=1,
            epub_session=epub_session
        )
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

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, 1))
        cursor.execute("DELETE FROM user_reading_log WHERE book_id = ? AND user_id = ?", (book_id, 1))
        conn.commit()
        conn.close()
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

        from services.book_service import BookService
        from utils.cache_helper import start_background_copy

        next_book = BookService.get_next_book(db_type, book_id, user_id=1)
        if not next_book or not next_book.get('file_path'):
            return jsonify({'success': True, 'message': _t('api.msg_no_next_book')})

        next_file_path = next_book['file_path']
        if os.path.exists(next_file_path):
            start_background_copy(next_file_path)
            print(f"[App-OPDS Viewer-Preload] Preloading next book successfully: {next_book['title']}")
            return jsonify({'success': True, 'preloaded_book_id': next_book['id']})
        return jsonify({'success': False, 'error': _t('api.err_next_book_not_exist')}), 404
    except Exception as e:
        print(f"[App-OPDS Preload API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds/login', methods=['POST', 'GET'])
def app_opds_login_compat():
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()
    return jsonify({'success': True})

@app_opds_bp.route('/app-opds/covers/<path:filename>', methods=['GET'])
def app_opds_cover_compat(filename: str):
    return _redirect_cover_compat(filename)

@app_opds_bp.route('/app-opds-adult', methods=['GET'])
def app_opds_adult_root():
    """타치요미용 성인 전용 OPDS 최상위 피드"""
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    cache_key = 'app_opds_root:adult'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    libs = get_library_list('adult')
    entries = [
        {'id': f"urn:app:adult:library:{l['id']}", 'title': l['name'],
         'type': 'navigation', 'href': f"/app-opds/adult/library/{l['id']}"}
        for l in libs
    ]
    entries.extend([
        {'id': 'urn:app:adult:recently-added', 'title': '신규 추가',
         'type': 'navigation', 'href': '/app-opds/adult/recently-added'},
        {'id': 'urn:app:adult:recently-read', 'title': '최근 읽은 도서',
         'type': 'navigation', 'href': '/app-opds/adult/recently-read'},
    ])
    xml = _opds_xml('adult', "BookOasis App Adult OPDS Catalog", entries, is_adult=True)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds-adult/api/media/list', methods=['GET'])
@app_opds_bp.route('/app-opds-adult/api/media/all-list', methods=['GET'])
def app_opds_adult_media_api_compat():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    db_type = request.args.get('type', 'adult')
    library_id = request.args.get('library_id', 'all')
    search_query = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'asc').strip().lower()

    try:
        if request.path.endswith('/all-list'):
            series_list = SeriesService.get_all_books_list(db_type, library_id)
            series_list = _filter_supported_series_for_app_opds(db_type, series_list)
            return jsonify({'success': True, 'series': series_list})

        page, limit = _parse_paging_args(default_limit=30)
        series_list = SeriesService.get_books_list(db_type, library_id, page, limit, search_query, sort)
        series_list = _filter_supported_series_for_app_opds(db_type, series_list)
        has_more = len(series_list) > limit
        if has_more:
            series_list = series_list[:limit]
        return jsonify({'success': True, 'series': series_list, 'has_more': has_more})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds-adult/api/media/libraries', methods=['GET'])
def app_opds_adult_media_libraries_compat():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    db_type = request.args.get('type', 'adult')
    try:
        libraries = CategoryService.get_libraries(db_type, user_id=None, role='admin')
        return jsonify({'success': True, 'libraries': libraries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds-adult/api/media/detail', methods=['GET'])
def app_opds_adult_media_detail_compat():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    db_type = request.args.get('type', 'adult')
    series_name = request.args.get('series', '')
    library_id = request.args.get('library_id', 'all')

    try:
        meta, books_list = BookDetailService.get_media_detail(
            db_type,
            series_name,
            library_id,
            user_id=1,
            restrict_same_directory=False,
        )
        books_list = _filter_supported_books_for_app_opds(books_list)
        books_list = _enrich_books_for_app_opds(books_list, db_type, is_adult_prefix=True)
        return jsonify({'success': True, 'meta': meta, 'books': books_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds-adult/api/media/books/<int:book_id>/info', methods=['GET'])
def app_opds_adult_book_info_compat(book_id: int):
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    db_type = request.args.get('type', 'adult')
    try:
        info = BookInfoService.get_viewer_info(db_type, book_id)
        if info is None:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        return jsonify({
            'success': True,
            'total_pages': info.get('total_pages', 0),
            'cover_image': info.get('cover_image')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app_opds_bp.route('/app-opds-adult/login', methods=['POST', 'GET'])
def app_opds_adult_login_compat():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()
    return jsonify({'success': True})

@app_opds_bp.route('/app-opds-adult/covers/<path:filename>', methods=['GET'])
def app_opds_adult_cover_compat(filename: str):
    return _redirect_cover_compat(filename)

@app_opds_bp.route('/app-opds/library/<int:lib_id>', methods=['GET'])
def app_opds_library(lib_id: int):
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()
    cache_key = f'app_opds_library:general:{lib_id}'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_series_entries('general', lib_id, '/app-opds/series', 'app:general')
    xml = _opds_xml('general', "Library Series", entries)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/adult/library/<int:lib_id>', methods=['GET'])
def app_opds_adult_library(lib_id: int):
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()
    cache_key = f'app_opds_library:adult:{lib_id}'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_series_entries('adult', lib_id, '/app-opds/adult/series', 'app:adult')
    xml = _opds_xml('adult', "Adult Library Series", entries, is_adult=True)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/series/<int:lib_id>/<path:series_name>', methods=['GET'])
def app_opds_series_books(lib_id: int, series_name: str):
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    cache_key = f'app_opds_series:general:{lib_id}:{series_name}:{page}:{page_size}'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    series_name = '' if series_name == EMPTY_SERIES_TOKEN else series_name

    entries, total = get_book_entries(
        'general', lib_id, series_name,
        '/app-opds/download/general', 'app:general',
        limit=page_size, offset=offset
    )
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?page={page + 1}&page_size={page_size}"
    xml = _opds_xml('general', f"Series: {series_name}", entries, next_link=next_link)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/adult/series/<int:lib_id>/<path:series_name>', methods=['GET'])
def app_opds_adult_series_books(lib_id: int, series_name: str):
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    cache_key = f'app_opds_series:adult:{lib_id}:{series_name}:{page}:{page_size}'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    series_name = '' if series_name == EMPTY_SERIES_TOKEN else series_name

    entries, total = get_book_entries(
        'adult', lib_id, series_name,
        '/app-opds/download/adult', 'app:adult',
        limit=page_size, offset=offset
    )
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?page={page + 1}&page_size={page_size}"
    xml = _opds_xml('adult', f"Adult Series: {series_name}", entries,
                    is_adult=True, next_link=next_link)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/recently-added', methods=['GET'])
def app_opds_recently_added():
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()
    cache_key = 'app_opds_recently_added:general'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_added_entries('general', '/app-opds/download/general', 'app:general')
    xml = _opds_xml('general', "신규 추가", entries)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/recently-read', methods=['GET'])
def app_opds_recently_read():
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()
    cache_key = 'app_opds_recently_read:general'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_read_entries('general', '/app-opds/download/general', 'app:general')
    xml = _opds_xml('general', "최근 읽은 도서", entries)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/adult/recently-added', methods=['GET'])
def app_opds_adult_recently_added():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()
    cache_key = 'app_opds_recently_added:adult'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_added_entries('adult', '/app-opds/download/adult', 'app:adult')
    xml = _opds_xml('adult', "신규 추가", entries, is_adult=True)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds/adult/recently-read', methods=['GET'])
def app_opds_adult_recently_read():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()
    cache_key = 'app_opds_recently_read:adult'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_read_entries('adult', '/app-opds/download/adult', 'app:adult')
    xml = _opds_xml('adult', "최근 읽은 도서", entries, is_adult=True)
    _set_cached_response(cache_key, xml)
    return _atom_response(xml)


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
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()
    
    query = request.args.get('q') or request.args.get('query') or ''
    if not query:
        base_url = request.url_root.rstrip('/')
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>BookOasis App</ShortName>
  <Description>Search BookOasis App Catalog</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type="application/atom+xml" template="{base_url}/app-opds/search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')
        
    page, page_size, offset = _get_page_params()
    entries, total = search_books_entries('general', query, '/app-opds/download/general', 'app:general', limit=page_size, offset=offset)
    
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?q={query}&page={page+1}&page_size={page_size}"
        
    xml = _opds_xml('general', f"검색 결과: {query}", entries, next_link=next_link)
    return _atom_response(xml)


@app_opds_bp.route('/app-opds-adult/search', methods=['GET'])
def app_opds_adult_search():
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()
        
    query = request.args.get('q') or request.args.get('query') or ''
    if not query:
        base_url = request.url_root.rstrip('/')
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>BookOasis App Adult</ShortName>
  <Description>Search BookOasis App Adult Catalog</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type="application/atom+xml" template="{base_url}/app-opds-adult/search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')
        
    page, page_size, offset = _get_page_params()
    entries, total = search_books_entries('adult', query, '/app-opds/download/adult', 'app:adult', limit=page_size, offset=offset)
    
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?q={query}&page={page+1}&page_size={page_size}"
        
    xml = _opds_xml('adult', f"성인 검색 결과: {query}", entries, is_adult=True, next_link=next_link)
    return _atom_response(xml)


