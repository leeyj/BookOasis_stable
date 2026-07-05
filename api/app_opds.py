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
import time
from datetime import datetime

from flask import Blueprint, Response, jsonify, request, send_file
import database
from api.cache import LRUCache
from services.opds_service import (
    get_book_entries,
    get_library_list,
    get_recently_added_entries,
    get_recently_read_entries,
    get_series_entries,
    search_books_entries,
)
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


@app_opds_bp.route('/app-opds/series/<int:lib_id>/<string:series_name>', methods=['GET'])
def app_opds_series_books(lib_id: int, series_name: str):
    if not _check_auth_cached(is_adult=False):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    cache_key = f'app_opds_series:general:{lib_id}:{series_name}:{page}:{page_size}'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

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


@app_opds_bp.route('/app-opds/adult/series/<int:lib_id>/<string:series_name>', methods=['GET'])
def app_opds_adult_series_books(lib_id: int, series_name: str):
    if not _check_auth_cached(is_adult=True):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    cache_key = f'app_opds_series:adult:{lib_id}:{series_name}:{page}:{page_size}'
    cached_xml = _get_cached_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

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


