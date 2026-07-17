# -*- coding: utf-8 -*-
import os
import hashlib
import database
from utils.cover_helper import get_cover_image_with_t, resolve_series_cover


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


def _fetch_books_for_grouping(cursor, library_id, search_query='', favorite_only=False, user_id=None, role=None):
    if favorite_only and user_id is None:
        return []

    safe_user_id = int(user_id) if user_id is not None else 0
    where = ["COALESCE(b.is_deleted, 0) = 0"]
    params = [safe_user_id]

    if favorite_only:
        where.append("uf.book_id IS NOT NULL")

    if library_id and library_id != 'all':
        where.append("b.library_id = ?")
        params.append(library_id)

    if search_query:
        like = f"%{search_query}%"
        where.append("(b.series_name LIKE ? OR b.author LIKE ?)")
        params.extend([like, like])

    # 일반 사용자는 user_category_permissions에 허용된 카테고리만 조회
    if role != 'admin' and user_id:
        where.append(
            "EXISTS ("
            "SELECT 1 FROM user_category_permissions p "
            "WHERE p.library_id = b.library_id AND p.user_id = ? AND p.has_access = 1"
            ")"
        )
        params.append(user_id)

    sql = f"""
        SELECT b.id, b.series_name, b.title, b.author, b.file_path, b.file_format,
               b.cover_image, b.cover_updated_at,
               CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
               b.created_at,
               b.genre, b.tags, b.library_id
        FROM books b
        LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = ?
        WHERE {' AND '.join(where)}
        ORDER BY b.library_id ASC, b.series_name ASC, b.id ASC
    """
    cursor.execute(sql, tuple(params))
    return cursor.fetchall()


def _build_series_entries(rows, conn):
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
            conn=conn,
            candidates_rows=books,
            allow_series_cover=False
        )

        latest_added = max((b['created_at'] for b in books if b['created_at']), default='')
        any_favorite = 1 if any((b['is_favorite'] or 0) == 1 for b in books) else 0
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

        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()

        rows = _fetch_books_for_grouping(
            cursor,
            library_filter,
            search_query=search_query or '',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role
        )

        entries = _build_series_entries(rows, conn)
        _sort_entries(entries, sort=sort)

        offset = max(0, (page - 1) * limit)
        paged = entries[offset:offset + limit + 1]
        conn.close()
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

        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()

        rows = _fetch_books_for_grouping(
            cursor,
            library_filter,
            search_query='',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role
        )
        entries = _build_series_entries(rows, conn)
        _sort_entries(entries, sort='asc')

        conn.close()
        return entries
