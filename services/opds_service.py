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
        '.cbz': 'application/vnd.comicbook+zip',    # Moon+ Reader 직접 열기 지원
        '.cbr': 'application/x-cbr',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        # .zip → CBZ와 동일 포맷이므로 comicbook+zip 사용
        # application/zip은 Moon+ Reader가 "다운로드 팝업"으로 처리함
        '.zip': 'application/vnd.comicbook+zip',
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


def _get_search_format_info(file_path: str, file_format: str = ''):
    raw_format = str(file_format or '').strip().lower()
    if not raw_format:
        raw_format = os.path.splitext(file_path or '')[1].lower().lstrip('.')

    if raw_format in ('zip', 'cbz', 'cbr', 'imgdir'):
        return '만화', raw_format.upper()
    if raw_format == 'epub':
        return 'EPUB', 'EPUB'
    if raw_format == 'pdf':
        return 'PDF', 'PDF'
    if raw_format in ('txt', 'text'):
        return '텍스트', 'TXT'
    if raw_format in ('audiobook', 'mp3', 'm4a', 'm4b', 'flac', 'ogg', 'opus'):
        return '오디오북', raw_format.upper()
    return (raw_format.upper() or '파일'), (raw_format.upper() or 'FILE')


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


def _build_stream_href(file_path: str, db_type: str, book_id: int, is_app_opds: bool = False) -> str:
    if not is_app_opds:
        return None
    ext = os.path.splitext(file_path or '')[1].lower()
    prefix = '/app-opds'
    if ext in ('.zip', '.cbz', '.imgdir') or file_path.lower().endswith('.imgdir'):
        return f"{prefix}/api/media/stream?db_type={db_type}&book_id={book_id}&page_idx=0"
    elif ext == '.txt':
        return f"{prefix}/api/media/txt?db_type={db_type}&book_id={book_id}"
    elif ext in ('.epub', '.pdf'):
        return f"{prefix}/api/media/pdf?db_type={db_type}&book_id={book_id}"
    return None


def get_book_entries(db_type: str, lib_id: int, series_name: str, download_prefix: str, urn_prefix: str, limit: int = None, offset: int = 0):
    total = OpdsRepository.get_book_entries_count(db_type, lib_id, series_name)
    books = OpdsRepository.get_book_entries(db_type, lib_id, series_name, limit, offset)
    is_app_opds = 'app' in urn_prefix

    entries = []
    for b in books:
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        mime = _guess_mime_type(b['file_path'])
        stream_href = _build_stream_href(b['file_path'], db_type, b['id'], is_app_opds)
        entries.append({
            'id': f"urn:{urn_prefix}:book:{b['id']}",
            'title': b['title'],
            'summary': b['summary'],
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'stream_href': stream_href,
            'mime': mime,
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries, total


def get_recently_added_entries(db_type: str, download_prefix: str, urn_prefix: str):
    books = OpdsRepository.get_recently_added_entries(db_type)
    is_app_opds = 'app' in urn_prefix
    entries = []
    for i, b in enumerate(books):
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        stream_href = _build_stream_href(b['file_path'], db_type, b['id'], is_app_opds)
        entries.append({
            'id': f"urn:{urn_prefix}:new:{i}",
            'title': b['title'],
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'stream_href': stream_href,
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries


def get_favorite_entries(db_type: str, download_prefix: str, urn_prefix: str, user_id: int):
    books = OpdsRepository.get_favorite_entries(db_type, user_id)
    is_app_opds = 'app' in urn_prefix
    entries = []
    for i, b in enumerate(books):
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        stream_href = _build_stream_href(b['file_path'], db_type, b['id'], is_app_opds)
        cnt = int(b.get('book_count', 1) or 1)
        if cnt > 1:
            series_name = b['title']
            if '/download/general' in download_prefix:
                feed_prefix = download_prefix.replace('/download/general', '/series')
            elif '/download/adult' in download_prefix:
                feed_prefix = download_prefix.replace('/download/adult', '/adult/series')
            else:
                feed_prefix = download_prefix.replace('/download', '/series')
            entries.append({
                'id': f"urn:{urn_prefix}:favorite:series:{i}",
                'title': f"{series_name} ({cnt}권)",
                'summary': f"총 {cnt}권 포함",
                'type': 'navigation',
                'href': f"{feed_prefix}/all/{_encode_url_segment(series_name)}",
                'cover': b['cover_image'],
                'cover_url': None if b['cover_image'] else _build_fallback_cover_href(series_name, 'text'),
                'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
            })
        else:
            entries.append({
                'id': f"urn:{urn_prefix}:favorite:{i}",
                'title': b['title'],
                'summary': '',
                'type': 'acquisition',
                'href': f"{download_prefix}/{b['id']}",
                'stream_href': stream_href,
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

    is_app_opds = 'app' in urn_prefix
    entries = []
    for i, b in enumerate(books):
        title = b['title']
        if _is_corrupted_title(title):
            title = _extract_title_from_path(b['file_path'])
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        stream_href = _build_stream_href(b['file_path'], db_type, b['id'], is_app_opds)
        entries.append({
            'id': f"urn:{urn_prefix}:read:{i}",
            'title': title,
            'summary': '',
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'stream_href': stream_href,
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(title, ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries


def search_books_entries(db_type: str, query: str, download_prefix: str, urn_prefix: str,
                         limit: int = 100, offset: int = 0, user_id=None, role=None):
    books, total = OpdsRepository.search_books_like(
        db_type, query, limit, offset, user_id=user_id, role=role
    )
    is_app_opds = 'app' in urn_prefix
    
    entries = []
    for b in books:
        format_label, format_term = _get_search_format_info(b['file_path'], b.get('file_format', ''))
        desc = b['summary'] or ""
        if not desc:
            meta = []
            if b['series_name']:
                meta.append(f"시리즈: {b['series_name']}")
            if b['author']:
                meta.append(f"저자: {b['author']}")
            desc = " / ".join(meta) if meta else "상세 설명 없음"
        desc = f"형식: {format_label} · {desc}"
        ext = os.path.splitext(b['file_path'] or '')[1].lower().replace('.', '') or 'text'
        stream_href = _build_stream_href(b['file_path'], db_type, b['id'], is_app_opds)
            
        entries.append({
            'id': f"urn:{urn_prefix}:search:{b['id']}",
            'title': f"[{format_label}] {b['title']}",
            'summary': desc,
            'format_label': format_label,
            'format_term': format_term,
            'type': 'acquisition',
            'href': f"{download_prefix}/{b['id']}",
            'stream_href': stream_href,
            'mime': _guess_mime_type(b['file_path']),
            'cover': b['cover_image'],
            'cover_url': None if b['cover_image'] else _build_fallback_cover_href(b['title'], ext),
            'cover_mime': 'image/svg+xml' if not b['cover_image'] else None,
        })
    return entries, total
