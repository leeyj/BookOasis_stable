# -*- coding: utf-8 -*-
import database
from services.book_service import get_cover_image_with_t

class ReadingHistoryService:
    @staticmethod
    def get_history(db_type, user_id=1):
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM settings WHERE key = 'RECENT_BOOKS_LIMIT'")
        row_limit = cursor.fetchone()
        limit = 30
        if row_limit and row_limit['value'] and str(row_limit['value']).isdigit():
            limit = int(row_limit['value'])

        cursor.execute("""
            SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format,
                   p.pages_read, b.total_pages, p.last_read_at, b.is_favorite
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            WHERE p.user_id = ?
            ORDER BY p.last_read_at DESC
            LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'id'          : r['id'],
                'library_id'  : r['library_id'],
                'title'       : r['title'],
                'series_name' : r['series_name'] or '기타 단행본',
                'cover_image' : get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_format' : r['file_format'],
                'pages_read'  : r['pages_read']  or 0,
                'total_pages' : r['total_pages'] or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'last_read_at': r['last_read_at'],
            }
            for r in rows
        ]

    @staticmethod
    def get_recently_added(db_type):
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at, b.is_favorite
            FROM books b
            INNER JOIN (
                SELECT MAX(id) as max_id
                FROM books
                GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CAST(id AS TEXT) END
            ) g ON b.id = g.max_id
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'id'          : r['id'],
                'library_id'  : r['library_id'],
                'title'       : r['title'],
                'series_name' : r['series_name'] or '기타 단행본',
                'cover_image' : get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_format' : r['file_format'],
                'total_pages' : r['total_pages'] or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'created_at'  : r['created_at'],
            }
            for r in rows
        ]

