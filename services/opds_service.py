# -*- coding: utf-8 -*-
import mimetypes
import os
import re
from urllib.parse import quote

import database


def _guess_mime_type(file_path: str) -> str:
    return mimetypes.guess_type(file_path)[0] or 'application/octet-stream'


def _encode_url_segment(value: str) -> str:
    return quote(str(value), safe='/')


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
        WHERE library_id = ?
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
            'href': f"{prefix}/{lib_id}/{_encode_url_segment(s['series_name'] or '기타')}",
            'cover': s['cover_image'],
        }
        for i, s in enumerate(rows)
    ]


def get_book_entries(db_type: str, lib_id: int, series_name: str, download_prefix: str, urn_prefix: str, limit: int = None, offset: int = 0):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM books WHERE library_id=? AND series_name=?", (lib_id, series_name))
    total = cursor.fetchone()['total']

    query = (
        "SELECT id, title, file_path, cover_image, summary FROM books "
        "WHERE library_id=? AND series_name=? "
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
        entries.append({
            'id': f"urn:{urn_prefix}:book:{b['id']}",
            'title': b['title'],
            'summary': b['summary'],
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
        })
    return entries, total


def get_recently_added_entries(db_type: str, download_prefix: str, urn_prefix: str):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, file_path, cover_image
        FROM books
        ORDER BY created_at DESC, id DESC
        LIMIT 20
        """
    )
    books = cursor.fetchall()
    conn.close()

    entries = []
    for i, b in enumerate(books):
        entries.append({
            'id': f"urn:{urn_prefix}:new:{i}",
            'title': b['title'],
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
        })
    return entries


def get_recently_read_entries(db_type: str, download_prefix: str, urn_prefix: str):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM settings WHERE key = 'RECENT_BOOKS_LIMIT'")
    row_limit = cursor.fetchone()
    limit = 30
    if row_limit and row_limit['value'] and str(row_limit['value']).isdigit():
        limit = int(row_limit['value'])

    cursor.execute(
        """
        SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
        FROM user_progress p
        JOIN books b ON p.book_id = b.id
        WHERE b.title IS NOT NULL AND b.title != ''
        ORDER BY p.last_read_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    books = cursor.fetchall()
    conn.close()

    entries = []
    for i, b in enumerate(books):
        title = b['title']
        if _is_corrupted_title(title):
            title = _extract_title_from_path(b['file_path'])
        entries.append({
            'id': f"urn:{urn_prefix}:read:{i}",
            'title': title,
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
        })
    return entries

def search_books_entries(db_type: str, query: str, download_prefix: str, urn_prefix: str, limit: int = 100, offset: int = 0):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    
    like_query = f"%{query}%"
    cursor.execute(
        """
        SELECT COUNT(*) AS total FROM books
        WHERE title LIKE ? OR series_name LIKE ? OR author LIKE ?
        """,
        (like_query, like_query, like_query)
    )
    total = cursor.fetchone()['total']
    
    cursor.execute(
        """
        SELECT id, title, series_name, author, file_path, cover_image, summary
        FROM books
        WHERE title LIKE ? OR series_name LIKE ? OR author LIKE ?
        ORDER BY title ASC, id ASC
        LIMIT ? OFFSET ?
        """,
        (like_query, like_query, like_query, limit, offset)
    )
    books = cursor.fetchall()
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
            
        entries.append({
            'id': f"urn:{urn_prefix}:search:{b['id']}",
            'title': b['title'],
            'summary': desc,
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
        })
    return entries, total

