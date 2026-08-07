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
        series_alias = next((b['series_alias'] for b in books if b.get('series_alias')), '')
        total_tracks = 0
        if db_type == 'audiobook':
            total_tracks = max((int(b.get('total_tracks') or 0) for b in books), default=0)
        series_key = hashlib.md5(f"{lib_id}|{series_name}|{comp_dir}".encode('utf-8')).hexdigest()[:16]

        book_count = sum(int(b.get('series_book_count') or b.get('book_count') or 1) for b in books)

        entries.append({
            'series_key': f"{lib_id}:{series_key}",
            'series_name': series_name,
            'series_alias': series_alias,
            'display_name': series_alias if series_alias else series_name,
            'representative_title': representative.get('title_alias') or representative['title'] or '',
            'author': author,
            'book_count': book_count,
            'total_tracks': total_tracks,
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


_ALL_BOOKS_CACHE = {}
_ALL_BOOKS_CACHE_TTL = 60.0  # 60초 인메모리 캐싱

class SeriesService:
    @staticmethod
    def invalidate_all_books_cache():
        global _ALL_BOOKS_CACHE
        _ALL_BOOKS_CACHE.clear()

    @staticmethod
    def get_books_list(db_type, library_id, page, limit, search_query, sort='asc', user_id=None, role=None):
        import time
        t0 = time.perf_counter()
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'

        offset = max(0, (page - 1) * limit)
        sql_limit = (limit + 1) if (not search_query and sort in ('asc', 'desc')) else None
        sql_offset = offset if (not search_query and sort in ('asc', 'desc')) else None

        t1 = time.perf_counter()
        rows = SeriesRepository.fetch_books_for_grouping(
            db_type,
            library_id,
            search_query=search_query or '',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role,
            limit=sql_limit,
            offset=sql_offset
        )
        t2 = time.perf_counter()

        entries = _build_series_entries(db_type, rows)
        t3 = time.perf_counter()

        _sort_entries(entries, sort=sort)
        t4 = time.perf_counter()

        paged = entries if sql_limit is not None else entries[offset:offset + limit + 1]
        
        print(f"[PERF-PROFILE] get_books_list(lib={library_id}, page={page}) TOTAL: {(t4-t0)*1000:.1f}ms | SQL-Fetch({len(rows)}rows): {(t2-t1)*1000:.1f}ms | BuildSeries({len(entries)}entries): {(t3-t2)*1000:.1f}ms | Sort: {(t4-t3)*1000:.1f}ms")
        return paged

    @staticmethod
    def get_all_books_list(db_type, library_id, user_id=None, role=None):
        """Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회"""
        import time
        t0 = time.perf_counter()
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        
        now = time.time()
        # 글로벌 인메모리 통캐시 (5분 간 전역 공유 - 0.0001초 응답)
        cache_key = f"global:{db_type}:{library_id}"
        if cache_key in _ALL_BOOKS_CACHE:
            cache_ts, cached_entries = _ALL_BOOKS_CACHE[cache_key]
            if now - cache_ts < 300.0:
                print(f"[PERF-PROFILE] get_all_books_list(lib={library_id}) GLOBAL IN-MEMORY CACHE HIT! ({len(cached_entries)} entries) - {(time.perf_counter()-t0)*1000:.1f}ms")
                return cached_entries

        t1 = time.perf_counter()
        rows = SeriesRepository.fetch_books_for_grouping(
            db_type,
            library_id,
            search_query='',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role
        )
        t2 = time.perf_counter()

        entries = _build_series_entries(db_type, rows)
        t3 = time.perf_counter()

        _sort_entries(entries, sort='asc')
        t4 = time.perf_counter()

        _ALL_BOOKS_CACHE[cache_key] = (now, entries)
        print(f"[PERF-PROFILE] get_all_books_list(lib={library_id}) TOTAL: {(t4-t0)*1000:.1f}ms | SQL-Fetch({len(rows)}rows): {(t2-t1)*1000:.1f}ms | BuildSeries({len(entries)}entries): {(t3-t2)*1000:.1f}ms | Sort: {(t4-t3)*1000:.1f}ms")
        return entries
