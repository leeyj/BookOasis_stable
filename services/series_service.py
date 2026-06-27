# -*- coding: utf-8 -*-
import os
import database
from utils.cover_helper import get_cover_image_with_t, resolve_series_cover

class SeriesService:
    @staticmethod
    def get_books_list(db_type, library_id, page, limit, search_query, sort='asc'):
        try:
            if library_id is not None and library_id not in ('all', 'favorite', 'history', 'home'):
                library_id = int(library_id)
        except (ValueError, TypeError):
            pass

        offset = (page - 1) * limit
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()

        sort_dir = 'ASC' if sort.lower() == 'asc' else 'DESC'

        if library_id == 'favorite':
            if search_query:
                cursor.execute(f"""
                    SELECT b.series_name,
                           COUNT(b.id)         AS book_count,
                           (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                           (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                           MAX(b.is_favorite)  AS is_favorite,
                           MAX(b.created_at)   AS latest_added,
                           MIN(b.id)           AS representative_book_id,
                           b.library_id        AS library_id
                    FROM books b
                    WHERE b.is_favorite = 1 AND (b.series_name LIKE ? OR b.author LIKE ?)
                    GROUP BY b.series_name, b.library_id
                    ORDER BY b.series_name {sort_dir}
                    LIMIT ? OFFSET ?
                """, (f"%{search_query}%", f"%{search_query}%", limit + 1, offset))
            else:
                cursor.execute(f"""
                    SELECT b.series_name,
                           COUNT(b.id)         AS book_count,
                           (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                           (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                           MAX(b.is_favorite)  AS is_favorite,
                           MAX(b.created_at)   AS latest_added,
                           MIN(b.id)           AS representative_book_id,
                           b.library_id        AS library_id
                    FROM books b
                    WHERE b.is_favorite = 1
                    GROUP BY b.series_name, b.library_id
                    ORDER BY b.series_name {sort_dir}
                    LIMIT ? OFFSET ?
                """, (limit + 1, offset))
        elif library_id and library_id != 'all':
            if search_query:
                cursor.execute(f"""
                    SELECT b.series_name,
                           COUNT(b.id)         AS book_count,
                           (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                           (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                           MAX(b.is_favorite)  AS is_favorite,
                           MAX(b.created_at)   AS latest_added,
                           MIN(b.id)           AS representative_book_id,
                           b.library_id        AS library_id
                    FROM books b
                    WHERE b.library_id = ? AND (b.series_name LIKE ? OR b.author LIKE ?)
                    GROUP BY b.series_name, b.library_id
                    ORDER BY b.series_name {sort_dir}
                    LIMIT ? OFFSET ?
                """, (library_id, f"%{search_query}%", f"%{search_query}%", limit + 1, offset))
            else:
                cursor.execute(f"""
                    SELECT b.series_name,
                           COUNT(b.id)         AS book_count,
                           (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                           (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                           MAX(b.is_favorite)  AS is_favorite,
                           MAX(b.created_at)   AS latest_added,
                           MIN(b.id)           AS representative_book_id,
                           b.library_id        AS library_id
                    FROM books b
                    WHERE b.library_id = ?
                    GROUP BY b.series_name, b.library_id
                    ORDER BY b.series_name {sort_dir}
                    LIMIT ? OFFSET ?
                """, (library_id, limit + 1, offset))
        else:
            if search_query:
                cursor.execute(f"""
                    SELECT b.series_name,
                           COUNT(b.id)         AS book_count,
                           (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                           (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                           MAX(b.is_favorite)  AS is_favorite,
                           MAX(b.created_at)   AS latest_added,
                           MIN(b.id)           AS representative_book_id,
                           b.library_id        AS library_id
                    FROM books b
                    WHERE b.series_name LIKE ? OR b.author LIKE ?
                    GROUP BY b.series_name, b.library_id
                    ORDER BY b.series_name {sort_dir}
                    LIMIT ? OFFSET ?
                """, (f"%{search_query}%", f"%{search_query}%", limit + 1, offset))
            else:
                cursor.execute(f"""
                    SELECT b.series_name,
                           COUNT(b.id)         AS book_count,
                           (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                           (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                           MAX(b.is_favorite)  AS is_favorite,
                           MAX(b.created_at)   AS latest_added,
                           MIN(b.id)           AS representative_book_id,
                           b.library_id        AS library_id
                    FROM books b
                    GROUP BY b.series_name, b.library_id
                    ORDER BY b.series_name {sort_dir}
                    LIMIT ? OFFSET ?
                """, (limit + 1, offset))

        rows = cursor.fetchall()

        series_list = []
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        covers_dir = os.path.join(base_dir, 'covers')
        
        for r in rows:
            series_name = r['series_name'] or '기타 단행본'
            lib_id = r['library_id']
            db_cover = r['cover_image']
            
            final_cover = resolve_series_cover(
                series_name=series_name,
                lib_id=lib_id,
                db_cover=db_cover,
                covers_dir=covers_dir,
                conn=conn
            )
            
            series_list.append({
                'series_name' : series_name,
                'book_count'  : r['book_count'],
                'cover_image' : get_cover_image_with_t(final_cover, r['cover_updated_at']),
                'is_favorite' : r['is_favorite'] or 0,
                'latest_added': r['latest_added'],
                'representative_book_id': r['representative_book_id']
            })
        conn.close()
        return series_list

    @staticmethod
    def get_all_books_list(db_type, library_id):
        """Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회"""
        try:
            if library_id is not None and library_id not in ('all', 'favorite', 'history', 'home'):
                library_id = int(library_id)
        except (ValueError, TypeError):
            pass

        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()

        if library_id == 'favorite':
            cursor.execute("""
                SELECT b.series_name,
                       MAX(b.author)       AS author,
                       COUNT(b.id)         AS book_count,
                       (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                       (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                       MAX(b.is_favorite)  AS is_favorite,
                       MAX(b.created_at)   AS latest_added,
                       MIN(b.id)           AS representative_book_id,
                       b.library_id        AS library_id
                FROM books b
                WHERE b.is_favorite = 1
                GROUP BY b.series_name, b.library_id
                ORDER BY b.series_name ASC
            """)
        elif library_id and library_id != 'all':
            cursor.execute("""
                SELECT b.series_name,
                       MAX(b.author)       AS author,
                       COUNT(b.id)         AS book_count,
                       (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                       (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                       MAX(b.is_favorite)  AS is_favorite,
                       MAX(b.created_at)   AS latest_added,
                       MIN(b.id)           AS representative_book_id,
                       b.library_id        AS library_id
                FROM books b
                WHERE b.library_id = ?
                GROUP BY b.series_name, b.library_id
                ORDER BY b.series_name ASC
            """, (library_id,))
        else:
            cursor.execute("""
                SELECT b.series_name,
                       MAX(b.author)       AS author,
                       COUNT(b.id)         AS book_count,
                       (SELECT b2.cover_image FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_image,
                       (SELECT b2.cover_updated_at FROM books b2 WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id AND b2.cover_image IS NOT NULL AND b2.cover_image != '' ORDER BY b2.title ASC LIMIT 1) AS cover_updated_at,
                       MAX(b.is_favorite)  AS is_favorite,
                       MAX(b.created_at)   AS latest_added,
                       MIN(b.id)           AS representative_book_id,
                       b.library_id        AS library_id
                FROM books b
                GROUP BY b.series_name, b.library_id
                ORDER BY b.series_name ASC
            """)

        rows = cursor.fetchall()

        series_list = []
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        covers_dir = os.path.join(base_dir, 'covers')
        
        for r in rows:
            series_name = r['series_name'] or '기타 단행본'
            lib_id = r['library_id']
            db_cover = r['cover_image']
            
            final_cover = resolve_series_cover(
                series_name=series_name,
                lib_id=lib_id,
                db_cover=db_cover,
                covers_dir=covers_dir,
                conn=conn
            )
                
            series_list.append({
                'series_name' : series_name,
                'author'      : r['author'] or '',
                'book_count'  : r['book_count'],
                'cover_image' : get_cover_image_with_t(final_cover, r['cover_updated_at']),
                'is_favorite' : r['is_favorite'] or 0,
                'latest_added': r['latest_added'],
                'representative_book_id': r['representative_book_id']
            })
        conn.close()
        return series_list
