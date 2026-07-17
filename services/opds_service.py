# -*- coding: utf-8 -*-
import mimetypes
import os
import re
from urllib.parse import quote

import database


EMPTY_SERIES_TOKEN = '__empty_series__'


def _guess_mime_type(file_path: str) -> str:
    if not file_path:
        return 'application/octet-stream'
    ext = os.path.splitext(file_path)[1].lower()
    custom_mimes = {
        '.epub': 'application/epub+zip',
        '.cbz': 'application/x-cbz',
        '.cbr': 'application/x-cbr',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.zip': 'application/zip',
    }
    if ext in custom_mimes:
        return custom_mimes[ext]
    return mimetypes.guess_type(file_path)[0] or 'application/octet-stream'


def _encode_url_segment(value: str) -> str:
    return quote(str(value), safe='')


def _build_fallback_cover_href(title: str, file_format: str = 'text') -> str:
    safe_title = _encode_url_segment(title or 'Untitled')
    safe_format = _encode_url_segment(file_format or 'text')
    return f"/covers/fallback?title={safe_title}&format={safe_format}"


def _extract_title_from_path(file_path: str) -> str:
    if not file_path:
        return ''
    filename = os.path.basename(file_path)
    filename = os.path.splitext(filename)[0]
    filename = re.sub(r'#\d+$', '', filename)
    return filename.strip()


def _is_corrupted_title(title: str) -> bool:
    if not title:
        return False
    return bool(re.match(r'^\d+\s*-\s*\d+$', title.strip()))


def get_library_list(db_type: str):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM libraries")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_series_entries(db_type: str, lib_id: int, prefix: str, urn_prefix: str):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(series_name, '') AS series_name,
               MAX(NULLIF(cover_image, '')) AS cover_image
        FROM books
        WHERE library_id = ? AND COALESCE(is_deleted, 0) = 0
        GROUP BY COALESCE(series_name, '')
        ORDER BY COALESCE(series_name, '')
        """,
        (lib_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': f"urn:{urn_prefix}:series:{lib_id}:{i}",
            'title': s['series_name'] or '기타',
            'type': 'navigation',
            'href': f"{prefix}/{lib_id}/{_encode_url_segment(s['series_name'] if s['series_name'] else EMPTY_SERIES_TOKEN)}",
            'cover': s['cover_image'],
            'cover_url': None if s['cover_image'] else _build_fallback_cover_href(s['series_name'] or '기타', 'text'),
            'cover_mime': 'image/svg+xml' if not s['cover_image'] else None,
        }
        for i, s in enumerate(rows)
    ]


def get_book_entries(db_type: str, lib_id: int, series_name: str, download_prefix: str, urn_prefix: str, limit: int = None, offset: int = 0):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM books WHERE library_id=? AND series_name=? AND COALESCE(is_deleted, 0) = 0", (lib_id, series_name))
    total = cursor.fetchone()['total']

    query = (
        "SELECT id, title, file_path, cover_image, summary FROM books "
        "WHERE library_id=? AND series_name=? AND COALESCE(is_deleted, 0) = 0 "
        "ORDER BY title ASC, id ASC "
    )
    params = [lib_id, series_name]
    if limit is not None:
        query += "LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    books = cursor.fetchall()
    conn.close()

    entries = []
    for b in books:
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        entries.append({
            'id': f"urn:{urn_prefix}:book:{b['id']}",
            'title': b['title'],
            'summary': b['summary'],
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries, total


def get_recently_added_entries(db_type: str, download_prefix: str, urn_prefix: str):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, file_path, cover_image
        FROM books
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY created_at DESC, id DESC
        LIMIT 20
        """
    )
    books = cursor.fetchall()
    conn.close()

    entries = []
    for i, b in enumerate(books):
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        entries.append({
            'id': f"urn:{urn_prefix}:new:{i}",
            'title': b['title'],
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries


def get_favorite_entries(db_type: str, download_prefix: str, urn_prefix: str, user_id: int):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.id, b.title, b.file_path, b.cover_image
        FROM books b
        JOIN user_favorites uf ON uf.book_id = b.id
        WHERE COALESCE(b.is_deleted, 0) = 0 AND uf.user_id = ?
        ORDER BY b.title ASC, b.id ASC
        LIMIT 200
        """
        ,
        (user_id,)
    )
    books = cursor.fetchall()
    conn.close()

    entries = []
    for i, b in enumerate(books):
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        entries.append({
            'id': f"urn:{urn_prefix}:favorite:{i}",
            'title': b['title'],
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries


def get_recently_read_entries(db_type: str, download_prefix: str, urn_prefix: str, user_id: int = None):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM settings WHERE key = 'RECENT_BOOKS_LIMIT'")
    row_limit = cursor.fetchone()
    limit = 30
    if row_limit and row_limit['value'] and str(row_limit['value']).isdigit():
        limit = int(row_limit['value'])

    if user_id is None:
        cursor.execute(
            """
            SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
            FROM user_progress AS p INDEXED BY idx_user_progress_last_read_book
            JOIN books b ON p.book_id = b.id
            WHERE b.title IS NOT NULL AND b.title != '' AND COALESCE(b.is_deleted, 0) = 0
            ORDER BY p.last_read_at DESC
            LIMIT ?
            """,
            (limit,)
        )
    else:
        cursor.execute(
            """
            SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
            FROM user_progress AS p INDEXED BY idx_user_progress_last_read
            JOIN books b ON p.book_id = b.id
            WHERE p.user_id = ?
              AND b.title IS NOT NULL AND b.title != ''
              AND COALESCE(b.is_deleted, 0) = 0
            ORDER BY p.last_read_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
    books = cursor.fetchall()
    conn.close()

    entries = []
    for i, b in enumerate(books):
        title = b['title']
        if _is_corrupted_title(title):
            title = _extract_title_from_path(b['file_path'])
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        entries.append({
            'id': f"urn:{urn_prefix}:read:{i}",
            'title': title,
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(title, ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries

def _build_fts_match_query(query: str) -> str:
    terms = [term.strip() for term in re.split(r'\s+', str(query or '').strip()) if term.strip()]
    if not terms:
        return ''
    # FTS5 prefix 매칭(*): "동기"* → 동기, 동기짱, 동기화 등 접두어 일치
    # LIKE 검색의 %동기% 와 유사한 부분 검색 경험 제공
    return ' AND '.join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)


def _search_books_entries_like(cursor, query: str, limit: int, offset: int):
    like_query = f"%{query}%"
    cursor.execute(
        """
        SELECT COUNT(*) AS total FROM books
        WHERE (title LIKE ? OR series_name LIKE ? OR author LIKE ?) AND COALESCE(is_deleted, 0) = 0
        """,
        (like_query, like_query, like_query)
    )
    total = cursor.fetchone()['total']

    cursor.execute(
        """
        SELECT id, title, series_name, author, file_path, cover_image, summary
        FROM books
        WHERE (title LIKE ? OR series_name LIKE ? OR author LIKE ?) AND COALESCE(is_deleted, 0) = 0
        ORDER BY title ASC, id ASC
        LIMIT ? OFFSET ?
        """,
        (like_query, like_query, like_query, limit, offset)
    )
    return cursor.fetchall(), total


def _search_books_entries_fts(cursor, query: str, limit: int, offset: int):
    match_query = _build_fts_match_query(query)
    if not match_query:
        return [], 0

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM books_search
        JOIN books b ON b.id = books_search.rowid
        WHERE books_search MATCH ? AND COALESCE(b.is_deleted, 0) = 0
        """,
        (match_query,)
    )
    total = cursor.fetchone()['total']

    cursor.execute(
        """
        SELECT b.id, b.title, b.series_name, b.author, b.file_path, b.cover_image, b.summary
        FROM books_search
        JOIN books b ON b.id = books_search.rowid
        WHERE books_search MATCH ? AND COALESCE(b.is_deleted, 0) = 0
        ORDER BY bm25(books_search), b.title ASC, b.id ASC
        LIMIT ? OFFSET ?
        """,
        (match_query, limit, offset)
    )
    return cursor.fetchall(), total


def search_books_entries(db_type: str, query: str, download_prefix: str, urn_prefix: str, limit: int = 100, offset: int = 0):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    try:
        books, total = _search_books_entries_fts(cursor, query, limit, offset)
        # FTS가 예외 없이 0건을 반환하는 경우(토크나이저/질의 형태 이슈), LIKE로 보완한다.
        if total == 0:
            books, total = _search_books_entries_like(cursor, query, limit, offset)
    except Exception:
        books, total = _search_books_entries_like(cursor, query, limit, offset)
    conn.close()
    
    entries = []
    for b in books:
        desc = b['summary'] or ""
        if not desc:
            meta = []
            if b['series_name']:
                meta.append(f"시리즈: {b['series_name']}")
            if b['author']:
                meta.append(f"저자: {b['author']}")
            desc = " / ".join(meta) if meta else "상세 설명 없음"
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
            
        entries.append({
            'id': f"urn:{urn_prefix}:search:{b['id']}",
            'title': b['title'],
            'summary': desc,
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries, total

