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
import re
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request, send_file
import database
from werkzeug.security import check_password_hash

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


def _encode_url_segment(value: str) -> str:
    # cover_image는 라이브러리별 서브디렉터리 경로를 포함할 수 있으므로
    # 슬래시는 유지하면서 나머지 특수 문자를 인코딩합니다.
    return quote(str(value), safe='/')


def _extract_title_from_path(file_path: str) -> str:
    """파일 경로에서 제목 추출 (잘못된 제목용 fallback)"""
    if not file_path:
        return ''
    filename = os.path.basename(file_path)
    filename = os.path.splitext(filename)[0]  # 확장자 제거
    filename = re.sub(r'#\d+$', '', filename)  # "#숫자" 제거
    return filename.strip()


def _is_corrupted_title(title: str) -> bool:
    """제목이 손상되었는지 확인 (예: '1 - 0', '2 - 0')"""
    if not title:
        return False
    # 숫자 - 숫자 패턴 (예: "1 - 0", "12 - 5")
    return bool(re.match(r'^\d+\s*-\s*\d+$', title.strip()))


def _opds_xml(db_type: str, title: str, entries: list, is_adult: bool = False) -> str:
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
                cover_url = f"{base_url}/covers/{_encode_url_segment(e['cover'])}"
                cover_mime = mimetypes.guess_type(e['cover'])[0] or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
        elif e['type'] == 'acquisition':
            lines.append(
                f'    <link rel="http://opds-spec.org/acquisition" '
                f'href="{_escape_xml(href)}" type="{_escape_xml(e["mime"]) }"/>'
            )
            if e.get('cover'):
                cover_url = f"{base_url}/covers/{_encode_url_segment(e['cover'])}"
                cover_mime = mimetypes.guess_type(e['cover'])[0] or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{_escape_xml(cover_url)}" type="{_escape_xml(cover_mime)}"/>')
        lines.append('  </entry>')

    lines.append('</feed>')
    return '\n'.join(lines)


def _atom_response(xml: str):
    return Response(xml, mimetype='application/atom+xml; charset=utf-8')


def _series_entries(db_type: str, lib_id: int, prefix: str, urn_prefix: str):
    """라이브러리의 시리즈 목록을 OPDS 엔트리 리스트로 반환"""
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT series_name,
            (SELECT cover_image FROM books b2
             WHERE b2.library_id = b1.library_id
               AND COALESCE(b2.series_name, '') = COALESCE(b1.series_name, '')
               AND b2.cover_image IS NOT NULL
               AND b2.cover_image != ''
             ORDER BY b2.title ASC
             LIMIT 1) AS cover_image
        FROM books b1
        WHERE library_id = ?
        ORDER BY COALESCE(series_name, '')
        """,
        (lib_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'id'   : f"urn:{urn_prefix}:series:{lib_id}:{i}",
            'title': s['series_name'] or '기타',
            'type' : 'navigation',
            'href' : f"{prefix}/{lib_id}/{_encode_url_segment(s['series_name'] or '기타')}",
            'cover': s['cover_image'],
        }
        for i, s in enumerate(rows)
    ]


def _book_entries(db_type: str, lib_id: int, series_name: str, download_prefix: str, urn_prefix: str):
    """시리즈 단행본 목록을 OPDS acquisition 엔트리 리스트로 반환"""
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, file_path, cover_image, summary FROM books "
        "WHERE library_id=? AND series_name=?",
        (lib_id, series_name)
    )
    books = cursor.fetchall()
    conn.close()
    entries = []
    for b in books:
        mime = mimetypes.guess_type(b['file_path'])[0] or 'application/octet-stream'
        entries.append({
            'id'     : f"urn:{urn_prefix}:book:{b['id']}",
            'title'  : b['title'],
            'summary': b['summary'],
            'type'   : 'acquisition',
            'href'   : f"{download_prefix}/{b['id']}",
            'mime'   : mime,
            'cover'  : b['cover_image'],
        })
    return entries


def _recently_added_entries(db_type: str, download_prefix: str, urn_prefix: str):
    """신규 추가 도서 목록을 OPDS acquisition 엔트리 리스트로 반환"""
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, file_path, cover_image
        FROM books
        ORDER BY created_at DESC, id DESC
        LIMIT 20
    """)
    books = cursor.fetchall()
    conn.close()
    entries = []
    for i, b in enumerate(books):
        mime = mimetypes.guess_type(b['file_path'])[0] or 'application/octet-stream'
        entries.append({
            'id'     : f"urn:{urn_prefix}:new:{i}",
            'title'  : b['title'],
            'summary': '',
            'type'   : 'acquisition',
            'href'   : f"{download_prefix}/{b['id']}",
            'mime'   : mime,
            'cover'  : b['cover_image'],
        })
    return entries


def _recently_read_entries(db_type: str, download_prefix: str, urn_prefix: str):
    """최근 읽은 도서 목록을 OPDS acquisition 엔트리 리스트로 반환"""
    conn = database.get_connection(db_type)
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM settings WHERE key = 'RECENT_BOOKS_LIMIT'")
    row_limit = cursor.fetchone()
    limit = 30
    if row_limit and row_limit['value'] and str(row_limit['value']).isdigit():
        limit = int(row_limit['value'])

    cursor.execute("""
        SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
        FROM user_progress p
        JOIN books b ON p.book_id = b.id
        WHERE b.title IS NOT NULL AND b.title != ''
        ORDER BY p.last_read_at DESC
        LIMIT ?
    """, (limit,))
    books = cursor.fetchall()
    conn.close()
    entries = []
    for i, b in enumerate(books):
        mime = mimetypes.guess_type(b['file_path'])[0] or 'application/octet-stream'
        # 제목이 손상된 경우 파일명에서 추출
        title = b['title']
        if _is_corrupted_title(title):
            title = _extract_title_from_path(b['file_path'])
        entries.append({
            'id'     : f"urn:{urn_prefix}:read:{i}",
            'title'  : title,
            'summary': '',
            'type'   : 'acquisition',
            'href'   : f"{download_prefix}/{b['id']}",
            'mime'   : mime,
            'cover'  : b['cover_image'],
        })
    return entries


# ─── 라우터 ──────────────────────────────────────────────────

@opds_bp.route('/opds', methods=['GET'])
def opds_root():
    """일반 OPDS 최상위 피드"""
    if not _check_auth(is_adult=False):
        return _unauthorized()
    conn = database.get_connection('general')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM libraries")
    libs = cursor.fetchall()
    conn.close()
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
    return _atom_response(_opds_xml('general', "My Supporter OPDS Catalog", entries))


@opds_bp.route('/opds-adult', methods=['GET'])
def opds_adult_root():
    """성인 전용 OPDS 최상위 피드"""
    if not _check_auth(is_adult=True):
        return _unauthorized()
    conn = database.get_connection('adult')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM libraries")
    libs = cursor.fetchall()
    conn.close()
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
    return _atom_response(_opds_xml('adult', "My Supporter Adult OPDS Catalog", entries, is_adult=True))


@opds_bp.route('/opds/library/<int:lib_id>', methods=['GET'])
def opds_library(lib_id: int):
    if not _check_auth(is_adult=False):
        return _unauthorized()
    entries = _series_entries('general', lib_id, '/opds/series', 'general')
    return _atom_response(_opds_xml('general', "Library Series", entries))


@opds_bp.route('/opds/adult/library/<int:lib_id>', methods=['GET'])
def opds_adult_library(lib_id: int):
    if not _check_auth(is_adult=True):
        return _unauthorized()
    entries = _series_entries('adult', lib_id, '/opds/adult/series', 'adult')
    return _atom_response(_opds_xml('adult', "Adult Library Series", entries, is_adult=True))


@opds_bp.route('/opds/series/<int:lib_id>/<string:series_name>', methods=['GET'])
def opds_series_books(lib_id: int, series_name: str):
    if not _check_auth(is_adult=False):
        return _unauthorized()
    entries = _book_entries('general', lib_id, series_name, '/opds/download/general', 'general')
    return _atom_response(_opds_xml('general', f"Series: {series_name}", entries))


@opds_bp.route('/opds/adult/series/<int:lib_id>/<string:series_name>', methods=['GET'])
def opds_adult_series_books(lib_id: int, series_name: str):
    if not _check_auth(is_adult=True):
        return _unauthorized()
    entries = _book_entries('adult', lib_id, series_name, '/opds/download/adult', 'adult')
    return _atom_response(_opds_xml('adult', f"Adult Series: {series_name}", entries, is_adult=True))


@opds_bp.route('/opds/recently-added', methods=['GET'])
def opds_recently_added():
    """신규 추가 도서 목록 (일반)"""
    if not _check_auth(is_adult=False):
        return _unauthorized()
    entries = _recently_added_entries('general', '/opds/download/general', 'general')
    return _atom_response(_opds_xml('general', "신규 추가", entries))


@opds_bp.route('/opds/recently-read', methods=['GET'])
def opds_recently_read():
    """최근 읽은 도서 목록 (일반)"""
    if not _check_auth(is_adult=False):
        return _unauthorized()
    entries = _recently_read_entries('general', '/opds/download/general', 'general')
    return _atom_response(_opds_xml('general', "최근 읽은 도서", entries))


@opds_bp.route('/opds/adult/recently-added', methods=['GET'])
def opds_adult_recently_added():
    """신규 추가 도서 목록 (성인)"""
    if not _check_auth(is_adult=True):
        return _unauthorized()
    entries = _recently_added_entries('adult', '/opds/download/adult', 'adult')
    return _atom_response(_opds_xml('adult', "신규 추가", entries, is_adult=True))


@opds_bp.route('/opds/adult/recently-read', methods=['GET'])
def opds_adult_recently_read():
    """최근 읽은 도서 목록 (성인)"""
    if not _check_auth(is_adult=True):
        return _unauthorized()
    entries = _recently_read_entries('adult', '/opds/download/adult', 'adult')
    return _atom_response(_opds_xml('adult', "최근 읽은 도서", entries, is_adult=True))


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
        return jsonify({'error': 'Book not found'}), 404
    file_path = row['file_path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(file_path, as_attachment=True)
