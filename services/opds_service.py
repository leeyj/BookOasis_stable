# -*- coding: utf-8 -*-
import mimetypes
import os
import re
from urllib.parse import quote

from repositories.opds_repository import OpdsRepository


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
    return OpdsRepository.get_library_list(db_type)


def get_series_entries(db_type: str, lib_id: int, prefix: str, urn_prefix: str):
    rows = OpdsRepository.get_series_entries(db_type, lib_id)
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
    total = OpdsRepository.get_book_entries_count(db_type, lib_id, series_name)
    books = OpdsRepository.get_book_entries(db_type, lib_id, series_name, limit, offset)

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
    books = OpdsRepository.get_recently_added_entries(db_type)
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
    books = OpdsRepository.get_favorite_entries(db_type, user_id)
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
    # 표시 건수 설정 조회
    from repositories.reading_progress_repository import ReadingProgressRepository
    row_limit = ReadingProgressRepository.get_settings_value(db_type, 'RECENT_BOOKS_LIMIT')
    limit = 30
    if row_limit and str(row_limit).isdigit():
        limit = int(row_limit)

    if user_id is None:
        books = OpdsRepository.get_recently_read_entries_all(db_type, limit)
    else:
        books = OpdsRepository.get_recently_read_entries_by_user(db_type, user_id, limit)

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
    return ' AND '.join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)


def _search_books_entries_like(db_type: str, query: str, limit: int, offset: int):
    return OpdsRepository.search_books_like(db_type, query, limit, offset)


def _search_books_entries_fts(db_type: str, query: str, limit: int, offset: int):
    match_query = _build_fts_match_query(query)
    if not match_query:
        return [], 0
    return OpdsRepository.search_books_fts(db_type, query, match_query, limit, offset)


def search_books_entries(db_type: str, query: str, download_prefix: str, urn_prefix: str, limit: int = 100, offset: int = 0):
    try:
        books, total = _search_books_entries_fts(db_type, query, limit, offset)
        if total == 0:
            books, total = _search_books_entries_like(db_type, query, limit, offset)
    except Exception:
        books, total = _search_books_entries_like(db_type, query, limit, offset)
    
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
