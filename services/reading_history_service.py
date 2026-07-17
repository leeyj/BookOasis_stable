# -*- coding: utf-8 -*-
import database
from services.book_service import get_cover_image_with_t

class ReadingHistoryService:
    @staticmethod
    def get_history(db_type, user_id=1):
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()

        # 표시 건수 설정
        cursor.execute("SELECT value FROM settings WHERE key = 'RECENT_BOOKS_LIMIT'")
        row_limit = cursor.fetchone()
        limit = 30
        if row_limit and row_limit['value'] and str(row_limit['value']).isdigit():
            limit = int(row_limit['value'])

        # [버그수정] 완독 도서 숨김 설정을 서버사이드에서 직접 처리
        # 기존 방식(프론트 state 필터)은 두 가지 문제가 있었음:
        #   1) is_completed 필드를 API 응답에 미포함 → b.is_completed === 1 항상 false
        #   2) state.hideCompletedInHistory 세팅 전에 대시보드 렌더링(race condition)
        # → DB 설정을 직접 읽어 SQL WHERE 조건으로 필터링하여 두 문제를 동시에 해결
        cursor.execute("SELECT value FROM settings WHERE key = 'HIDE_COMPLETED_IN_HISTORY'")
        row_hide = cursor.fetchone()
        hide_completed = (row_hide and row_hide['value'] == '1')


        base_select = """
            SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format,
                   p.pages_read, b.total_pages, p.last_read_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                   p.is_completed
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = p.user_id
            WHERE COALESCE(b.is_deleted, 0) = 0 AND p.user_id = ?
        """
        if hide_completed:
            # is_completed = 1 이거나 pages_read >= total_pages(100% 완독) 인 도서 제외
            base_select += """
              AND COALESCE(p.is_completed, 0) = 0
              AND NOT (b.total_pages > 0 AND p.pages_read >= b.total_pages)
            """
        base_select += """
            ORDER BY p.last_read_at DESC
            LIMIT ?
        """
        cursor.execute(base_select, (user_id, limit))
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
                'is_completed': r['is_completed'] or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'last_read_at': r['last_read_at'],
            }
            for r in rows
        ]


    @staticmethod
    def get_recently_added(db_type, user_id=None, role=None):
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()
        if user_id and role != 'admin':
            # 권한이 설정된 카테고리(libraries)의 도서만 필터링
            cursor.execute("""
                SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at,
                       CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite
                FROM books b
                INNER JOIN (
                    SELECT MAX(id) as max_id
                    FROM books
                    WHERE COALESCE(is_deleted, 0) = 0
                    GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CAST(id AS TEXT) END
                ) g ON b.id = g.max_id
                JOIN user_category_permissions p ON b.library_id = p.library_id
                LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = ?
                WHERE COALESCE(b.is_deleted, 0) = 0 AND p.user_id = ? AND p.has_access = 1
                ORDER BY b.created_at DESC, b.id DESC
                LIMIT 20
            """, (user_id, user_id))
        else:
            cursor.execute("""
                SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at,
                       CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite
                FROM books b
                INNER JOIN (
                    SELECT MAX(id) as max_id
                    FROM books
                    WHERE COALESCE(is_deleted, 0) = 0
                    GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CAST(id AS TEXT) END
                ) g ON b.id = g.max_id
                LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = ?
                WHERE COALESCE(b.is_deleted, 0) = 0
                ORDER BY b.created_at DESC, b.id DESC
                LIMIT 20
            """, (int(user_id) if user_id is not None else 0,))
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

