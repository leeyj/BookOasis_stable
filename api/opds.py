# -*- coding: utf-8 -*-
"""
opds.py – OPDS (외부 뷰어 앱 연동) 라우터
  - /opds               : 일반 OPDS 최상위 피드 (Basic Auth 필수)
  - /opds-adult         : 성인 전용 OPDS 피드 (Basic Auth 필수, admin 권한 검사)
  - /opds/library/<id>  : 라이브러리 하위 시리즈 목록
  - /opds/series/…      : 시리즈 단행본 다운로드 링크
  - /opds/download/…    : 개별 도서 파일 전송
"""
import html
import mimetypes
import os
import time
from datetime import datetime

from flask import Blueprint, Response, jsonify, request, send_file  # type: ignore[reportMissingImports]
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
from werkzeug.security import check_password_hash  # type: ignore[reportMissingImports]

opds_bp = Blueprint('media_opds', __name__)


# ─── 인증 헬퍼 ───────────────────────────────────────────────

def _check_auth(is_adult: bool = False) -> bool:
    """OPDS용 DB 기반 Basic Auth 인증 검사"""
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return False
        
    conn = database.get_connection('general')
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, role FROM users WHERE username = ?", (auth.username,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return False
        
    if not check_password_hash(row['password_hash'], auth.password):
        return False
        
    # 성인 OPDS의 경우 admin 역할 권한만 허용
    if is_adult and row['role'] != 'admin':
        return False
        
    return True


def _unauthorized():
    return Response(
        "Unauthorized", status=401,
        headers={'WWW-Authenticate': 'Basic realm="BookOasis OPDS Catalog"'}
    )


# ─── Atom XML 생성 ────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    return html.escape(str(text), quote=True)


OPDS_CACHE_TTL = 60  # seconds
OPDS_DEFAULT_PAGE_SIZE = 100
OPDS_MAX_PAGE_SIZE = 200
opds_response_cache = LRUCache(capacity=50)


def _get_cached_opds_response(key: str):
    cached = opds_response_cache.get(key)
    if cached is None:
        return None
    xml, timestamp = cached
    if time.time() - timestamp > OPDS_CACHE_TTL:
        return None
    return xml


def _set_cached_opds_response(key: str, xml: str):
    opds_response_cache.put(key, (xml, time.time()))


def _get_page_params():
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get('page_size', str(OPDS_DEFAULT_PAGE_SIZE)))
    except ValueError:
        page_size = OPDS_DEFAULT_PAGE_SIZE

    page = max(page, 1)
    page_size = min(max(page_size, 1), OPDS_MAX_PAGE_SIZE)
    offset = (page - 1) * page_size
    return page, page_size, offset


def _opds_xml(db_type: str, title: str, entries: list, is_adult: bool = False, next_link: str = None) -> str:
    """Atom XML 규격의 OPDS 피드 문자열 생성"""
    base_url   = request.url_root.rstrip('/')
    now        = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">',
        f'  <id>{_escape_xml(request.url)}</id>',
        f'  <title>{_escape_xml(title)}</title>',
        f'  <updated>{now}</updated>',
        f'  <link rel="self" href="{_escape_xml(request.url)}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
        f'  <link rel="start" href="{_escape_xml(base_url + "/opds")}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
    ]
    search_href = "/opds/search" if not is_adult else "/opds-adult/search"
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
                f'href="{_escape_xml(href)}" type="{_escape_xml(e["mime"]) }"/>'
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

@opds_bp.route('/opds', methods=['GET'])
def opds_root():
    """일반 OPDS 최상위 피드"""
    if not _check_auth(is_adult=False):
        return _unauthorized()

    cache_key = 'opds_root:general'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    libs = get_library_list('general')
    entries = [
        {'id': f"urn:library:{l['id']}", 'title': l['name'],
         'type': 'navigation', 'href': f"/opds/library/{l['id']}"}
        for l in libs
    ]
    # 신규 추가, 최근 읽은 섹션 추가
    entries.extend([
        {'id': 'urn:recently-added', 'title': '신규 추가',
         'type': 'navigation', 'href': '/opds/recently-added'},
        {'id': 'urn:recently-read', 'title': '최근 읽은 도서',
         'type': 'navigation', 'href': '/opds/recently-read'},
    ])
    xml = _opds_xml('general', "My Supporter OPDS Catalog", entries)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds-adult', methods=['GET'])
def opds_adult_root():
    """성인 전용 OPDS 최상위 피드"""
    if not _check_auth(is_adult=True):
        return _unauthorized()

    cache_key = 'opds_root:adult'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    libs = get_library_list('adult')
    entries = [
        {'id': f"urn:adult:library:{l['id']}", 'title': l['name'],
         'type': 'navigation', 'href': f"/opds/adult/library/{l['id']}"}
        for l in libs
    ]
    # 신규 추가, 최근 읽은 섹션 추가
    entries.extend([
        {'id': 'urn:adult:recently-added', 'title': '신규 추가',
         'type': 'navigation', 'href': '/opds/adult/recently-added'},
        {'id': 'urn:adult:recently-read', 'title': '최근 읽은 도서',
         'type': 'navigation', 'href': '/opds/adult/recently-read'},
    ])
    xml = _opds_xml('adult', "My Supporter Adult OPDS Catalog", entries, is_adult=True)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/library/<int:lib_id>', methods=['GET'])
def opds_library(lib_id: int):
    if not _check_auth(is_adult=False):
        return _unauthorized()
    cache_key = f'opds_library:general:{lib_id}'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_series_entries('general', lib_id, '/opds/series', 'general')
    xml = _opds_xml('general', "Library Series", entries)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/adult/library/<int:lib_id>', methods=['GET'])
def opds_adult_library(lib_id: int):
    if not _check_auth(is_adult=True):
        return _unauthorized()
    cache_key = f'opds_library:adult:{lib_id}'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_series_entries('adult', lib_id, '/opds/adult/series', 'adult')
    xml = _opds_xml('adult', "Adult Library Series", entries, is_adult=True)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/series/<int:lib_id>/<string:series_name>', methods=['GET'])
def opds_series_books(lib_id: int, series_name: str):
    if not _check_auth(is_adult=False):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    cache_key = f'opds_series:general:{lib_id}:{series_name}:{page}:{page_size}'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries, total = get_book_entries('general', lib_id, series_name, '/opds/download/general', 'general', limit=page_size, offset=offset)
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?page={page+1}&page_size={page_size}"
    xml = _opds_xml('general', f"Series: {series_name}", entries, next_link=next_link)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/adult/series/<int:lib_id>/<string:series_name>', methods=['GET'])
def opds_adult_series_books(lib_id: int, series_name: str):
    if not _check_auth(is_adult=True):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    cache_key = f'opds_series:adult:{lib_id}:{series_name}:{page}:{page_size}'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries, total = get_book_entries('adult', lib_id, series_name, '/opds/download/adult', 'adult', limit=page_size, offset=offset)
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?page={page+1}&page_size={page_size}"
    xml = _opds_xml('adult', f"Adult Series: {series_name}", entries, is_adult=True, next_link=next_link)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/recently-added', methods=['GET'])
def opds_recently_added():
    """신규 추가 도서 목록 (일반)"""
    if not _check_auth(is_adult=False):
        return _unauthorized()
    cache_key = 'opds_recently_added:general'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_added_entries('general', '/opds/download/general', 'general')
    xml = _opds_xml('general', "신규 추가", entries)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/recently-read', methods=['GET'])
def opds_recently_read():
    """최근 읽은 도서 목록 (일반)"""
    if not _check_auth(is_adult=False):
        return _unauthorized()
    cache_key = 'opds_recently_read:general'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_read_entries('general', '/opds/download/general', 'general')
    xml = _opds_xml('general', "최근 읽은 도서", entries)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/adult/recently-added', methods=['GET'])
def opds_adult_recently_added():
    """신규 추가 도서 목록 (성인)"""
    if not _check_auth(is_adult=True):
        return _unauthorized()
    cache_key = 'opds_recently_added:adult'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_added_entries('adult', '/opds/download/adult', 'adult')
    xml = _opds_xml('adult', "신규 추가", entries, is_adult=True)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/adult/recently-read', methods=['GET'])
def opds_adult_recently_read():
    """최근 읽은 도서 목록 (성인)"""
    if not _check_auth(is_adult=True):
        return _unauthorized()
    cache_key = 'opds_recently_read:adult'
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_read_entries('adult', '/opds/download/adult', 'adult')
    xml = _opds_xml('adult', "최근 읽은 도서", entries, is_adult=True)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/download/<string:db_type>/<int:book_id>', methods=['GET'])
def opds_download_book(db_type: str, book_id: int):
    """외부 뷰어 앱이 직접 파일을 다운로드하는 엔드포인트"""
    is_adult = (db_type == 'adult')
    if not _check_auth(is_adult=is_adult):
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


@opds_bp.route('/opds/search', methods=['GET'])
def opds_search():
    if not _check_auth(is_adult=False):
        return _unauthorized()
    
    query = request.args.get('q') or request.args.get('query') or ''
    if not query:
        base_url = request.url_root.rstrip('/')
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>BookOasis</ShortName>
  <Description>Search BookOasis Catalog</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type="application/atom+xml" template="{base_url}/opds/search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')
        
    page, page_size, offset = _get_page_params()
    entries, total = search_books_entries('general', query, '/opds/download/general', 'general', limit=page_size, offset=offset)
    
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?q={query}&page={page+1}&page_size={page_size}"
        
    xml = _opds_xml('general', f"검색 결과: {query}", entries, next_link=next_link)
    return _atom_response(xml)


@opds_bp.route('/opds-adult/search', methods=['GET'])
def opds_adult_search():
    if not _check_auth(is_adult=True):
        return _unauthorized()
        
    query = request.args.get('q') or request.args.get('query') or ''
    if not query:
        base_url = request.url_root.rstrip('/')
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>BookOasis Adult</ShortName>
  <Description>Search BookOasis Adult Catalog</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type="application/atom+xml" template="{base_url}/opds-adult/search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')
        
    page, page_size, offset = _get_page_params()
    entries, total = search_books_entries('adult', query, '/opds/download/adult', 'adult', limit=page_size, offset=offset)
    
    next_link = None
    if offset + page_size < total:
        next_link = f"{request.base_url}?q={query}&page={page+1}&page_size={page_size}"
        
    xml = _opds_xml('adult', f"성인 검색 결과: {query}", entries, is_adult=True, next_link=next_link)
    return _atom_response(xml)

