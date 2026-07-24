# -*- coding: utf-8 -*-
import os
import hashlib
from utils.cover_helper import get_cover_image_with_t, resolve_series_cover
from repositories.series_repository import SeriesRepository

def _comparison_dir_for_book(file_path, file_format):
    normalized = str(file_path or '').replace('\\', '/')
    if not normalized:
        return ''
    if str(file_format or '').lower() == 'imgdir' and normalized.endswith('/__folder__.imgdir'):
        return os.path.dirname(os.path.dirname(file_path))
    return os.path.dirname(file_path)


def _normalize_library_id(library_id):
    if isinstance(library_id, str):
        library_id = library_id.strip()
        token = library_id.lower()
        if token in ('all', 'favorite', 'history', 'home'):
            return token
    try:
        if library_id is not None and library_id not in ('all', 'favorite', 'history', 'home'):
            return int(library_id)
    except (ValueError, TypeError):
        pass
    return library_id


def _build_series_entries(db_type, rows):
    groups = {}
    order = []

    for row in rows:
        series_name = row['series_name'] or '기타 단행본'
        comp_dir = _comparison_dir_for_book(row['file_path'], row['file_format'])
        key = (row['library_id'], series_name, comp_dir)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    covers_dir = os.path.join(base_dir, 'covers')

    entries = []
    for key in order:
        lib_id, series_name, comp_dir = key
        books = groups[key]
        representative = min(books, key=lambda r: r['id'])

        first_with_cover = next((b for b in books if b['cover_image']), None)
        db_cover = first_with_cover['cover_image'] if first_with_cover else None
        updated_at = first_with_cover['cover_updated_at'] if first_with_cover else None

        final_cover = resolve_series_cover(
            series_name=series_name,
            lib_id=lib_id,
            db_cover=db_cover,
            covers_dir=covers_dir,
            conn=None,
            candidates_rows=books,
            allow_series_cover=False,
            db_type=db_type
        )



        latest_added = max((b['created_at'] for b in books if b['created_at']), default='')
        any_favorite = 1 if any((b['is_favorite'] or 0) == 1 for b in books) else 0
        any_locked = 1 if any((b.get('metadata_locked') or 0) == 1 for b in books) else 0
        author = next((b['author'] for b in books if b['author']), '')
        genre = next((b['genre'] for b in books if b['genre']), '')
        tags = next((b['tags'] for b in books if b['tags']), '')
        series_key = hashlib.md5(f"{lib_id}|{series_name}|{comp_dir}".encode('utf-8')).hexdigest()[:16]

        entries.append({
            'series_key': f"{lib_id}:{series_key}",
            'series_name': series_name,
            'representative_title': representative['title'] or '',
            'author': author,
            'book_count': len(books),
            'cover_image': get_cover_image_with_t(final_cover, updated_at),
            'is_favorite': any_favorite,
            'metadata_locked': any_locked,
            'latest_added': latest_added,
            'representative_book_id': representative['id'],
            'library_id': lib_id,
            'genre': genre,
            'tags': tags,
            'anchor_dir': comp_dir,
        })

    return entries


def _sort_entries(entries, sort='asc'):
    sort_key = (sort or 'asc').lower()
    if sort_key in ('asc', 'desc'):
        reverse = (sort_key == 'desc')
        entries.sort(key=lambda x: (str(x.get('series_name') or ''), str(x.get('representative_title') or '')), reverse=reverse)
        return

    if sort_key == 'date_asc':
        entries.sort(key=lambda x: str(x.get('latest_added') or ''))
        return

    # default: latest first
    entries.sort(key=lambda x: str(x.get('latest_added') or ''), reverse=True)


class SeriesService:
    @staticmethod
    def get_books_list(db_type, library_id, page, limit, search_query, sort='asc', user_id=None, role=None):
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        if library_id in ('all', 'favorite', 'history', 'home'):
            library_filter = None
        else:
            library_filter = library_id

        rows = SeriesRepository.fetch_books_for_grouping(
            db_type,
            library_filter,
            search_query=search_query or '',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role
        )

        entries = _build_series_entries(db_type, rows)
        _sort_entries(entries, sort=sort)

        offset = max(0, (page - 1) * limit)
        paged = entries[offset:offset + limit + 1]
        return paged

    @staticmethod
    def get_all_books_list(db_type, library_id, user_id=None, role=None):
        """Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회"""
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        if library_id in ('all', 'favorite', 'history', 'home'):
            library_filter = None
        else:
            library_filter = library_id

        rows = SeriesRepository.fetch_books_for_grouping(
            db_type,
            library_filter,
            search_query='',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role
        )
        entries = _build_series_entries(db_type, rows)
        _sort_entries(entries, sort='asc')

        return entries
