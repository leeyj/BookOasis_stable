# -*- coding: utf-8 -*-
"""
opds.py – OPDS (외부 뷰어 앱 연동) 라우터
  - /opds               : 일반 OPDS 최상위 피드 (Basic Auth 필수)
  - /opds-adult         : 성인 전용 OPDS 피드 (Basic Auth 필수, admin 권한 검사)
  - /opds/library/<id>  : 라이브러리 하위 시리즈 목록
  - /opds/series/…      : 시리즈 단행본 다운로드 링크
  - /opds/download/…    : 개별 도서 파일 전송
"""
import mimetypes
import os
import threading
import time
import hashlib

from flask import Blueprint, Response, jsonify, request, send_file  # type: ignore[reportMissingImports]
import database
from api.cache import LRUCache
from api.opds_common.auth import authenticate_basic_auth_user, unauthorized_response
from api.opds_common.xml import atom_response, build_external_request_url, build_opds_xml, get_external_base_url, get_page_params
from services.opds_service import (
    get_book_entries,
    get_favorite_entries,
    get_library_list,
    get_recently_added_entries,
    get_recently_read_entries,
    get_series_entries,
    search_books_entries,
)
from utils.i18n import _t

opds_bp = Blueprint('media_opds', __name__)


# ─── 인증 헬퍼 ───────────────────────────────────────────────

_auth_cache: dict = {}
_auth_lock = threading.Lock()
_AUTH_CACHE_TTL = 300

def _get_authenticated_user(is_adult: bool = False):
    """OPDS용 DB 기반 Basic Auth 인증 검사 및 사용자 정보 반환"""
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return None

    key = hashlib.sha256(f"{auth.username}:{auth.password}".encode()).hexdigest()
    now = time.time()

    cached = _auth_cache.get(key)
    if cached is not None:
        expires, user = cached
        if now < expires:
            if is_adult and user.get('role') != 'admin':
                return None
            return user

    with _auth_lock:
        cached = _auth_cache.get(key)
        if cached is not None:
            expires, user = cached
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
        _auth_cache[key] = (time.time() + _AUTH_CACHE_TTL, user_meta)

        if is_adult and user_meta['role'] != 'admin':
            _auth_cache.pop(key, None)
            return None
        return user_meta


def _check_auth(is_adult: bool = False) -> bool:
    return _get_authenticated_user(is_adult=is_adult) is not None


def _unauthorized():
    return unauthorized_response('BookOasis OPDS Catalog')


# ─── Atom XML 생성 ────────────────────────────────────────────

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
    return get_page_params(request.args, OPDS_DEFAULT_PAGE_SIZE, OPDS_MAX_PAGE_SIZE)


def _opds_xml(db_type: str, title: str, entries: list, is_adult: bool = False, next_link: str = None) -> str:
    search_href = '/opds/search' if not is_adult else '/opds-adult/search'
    return build_opds_xml(
        request,
        title=title,
        entries=entries,
        start_path='/opds',
        search_path=search_href,
        next_link=next_link,
    )


def _atom_response(xml: str):
    return atom_response(xml)


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
           {'id': 'urn:favorite', 'title': '즐겨찾기',
            'type': 'navigation', 'href': '/opds/favorite'},
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
           {'id': 'urn:adult:favorite', 'title': '즐겨찾기',
            'type': 'navigation', 'href': '/opds/adult/favorite'},
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
        next_link = build_external_request_url(request, {'page': page + 1, 'page_size': page_size})
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
        next_link = build_external_request_url(request, {'page': page + 1, 'page_size': page_size})
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
    user = _get_authenticated_user(is_adult=False)
    if not user:
        return _unauthorized()
    cache_key = f"opds_recently_read:general:{user['id']}"
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_read_entries('general', '/opds/download/general', 'general', user_id=user['id'])
    xml = _opds_xml('general', "최근 읽은 도서", entries)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/favorite', methods=['GET'])
def opds_favorite():
    """즐겨찾기 도서 목록 (일반)"""
    user = _get_authenticated_user(is_adult=False)
    if not user:
        return _unauthorized()
    cache_key = f"opds_favorite:general:{user['id']}"
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_favorite_entries('general', '/opds/download/general', 'general', user_id=user['id'])
    xml = _opds_xml('general', "즐겨찾기", entries)
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
    user = _get_authenticated_user(is_adult=True)
    if not user:
        return _unauthorized()
    cache_key = f"opds_recently_read:adult:{user['id']}"
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_recently_read_entries('adult', '/opds/download/adult', 'adult', user_id=user['id'])
    xml = _opds_xml('adult', "최근 읽은 도서", entries, is_adult=True)
    _set_cached_opds_response(cache_key, xml)
    return _atom_response(xml)


@opds_bp.route('/opds/adult/favorite', methods=['GET'])
def opds_adult_favorite():
    """즐겨찾기 도서 목록 (성인)"""
    user = _get_authenticated_user(is_adult=True)
    if not user:
        return _unauthorized()
    cache_key = f"opds_favorite:adult:{user['id']}"
    cached_xml = _get_cached_opds_response(cache_key)
    if cached_xml is not None:
        return _atom_response(cached_xml)

    entries = get_favorite_entries('adult', '/opds/download/adult', 'adult', user_id=user['id'])
    xml = _opds_xml('adult', "즐겨찾기", entries, is_adult=True)
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

    from services.opds_service import _guess_mime_type
    mime_type = _guess_mime_type(file_path)
    filename = os.path.basename(file_path)

    response = send_file(file_path, as_attachment=True, download_name=filename, mimetype=mime_type)
    response.headers['Content-Type'] = f"{mime_type}; charset=utf-8" if mime_type.startswith('text/') else mime_type
    return response


@opds_bp.route('/opds/search', methods=['GET'])
def opds_search():
    query = request.args.get('q') or request.args.get('query') or ''

    if not query:
        # OpenSearch Description 문서: 인증 없이 허용
        # (OPDS 앱들은 스펙 탐색 단계에서 인증 전에 description을 먼저 요청하는 것이 표준 동작)
        base_url = get_external_base_url(request)
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>BookOasis</ShortName>
  <Description>Search BookOasis Catalog</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type="application/atom+xml;profile=opds-catalog" template="{base_url}/opds/search?q={{searchTerms}}"/>
  <Url type="application/atom+xml" template="{base_url}/opds/search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')

    # 실제 검색 요청: 인증 필요
    if not _check_auth(is_adult=False):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    entries, total = search_books_entries('general', query, '/opds/download/general', 'general', limit=page_size, offset=offset)
    
    next_link = None
    if offset + page_size < total:
        next_link = build_external_request_url(request, {'q': query, 'page': page + 1, 'page_size': page_size})
        
    xml = _opds_xml('general', f"검색 결과: {query}", entries, next_link=next_link)
    return _atom_response(xml)


@opds_bp.route('/opds-adult/search', methods=['GET'])
def opds_adult_search():
    query = request.args.get('q') or request.args.get('query') or ''

    if not query:
        # OpenSearch Description 문서: 인증 없이 허용
        base_url = get_external_base_url(request)
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>BookOasis Adult</ShortName>
  <Description>Search BookOasis Adult Catalog</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type="application/atom+xml;profile=opds-catalog" template="{base_url}/opds-adult/search?q={{searchTerms}}"/>
  <Url type="application/atom+xml" template="{base_url}/opds-adult/search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')

    # 실제 검색 요청: 인증 필요 (성인 admin 권한)
    if not _check_auth(is_adult=True):
        return _unauthorized()

    page, page_size, offset = _get_page_params()
    entries, total = search_books_entries('adult', query, '/opds/download/adult', 'adult', limit=page_size, offset=offset)
    
    next_link = None
    if offset + page_size < total:
        next_link = build_external_request_url(request, {'q': query, 'page': page + 1, 'page_size': page_size})
        
    xml = _opds_xml('adult', f"성인 검색 결과: {query}", entries, is_adult=True, next_link=next_link)
    return _atom_response(xml)

