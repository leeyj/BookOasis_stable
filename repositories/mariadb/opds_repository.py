# -*- coding: utf-8 -*-
"""
opds_repository.py – MariaDB 전용 OPDS 피드 데이터 액세스 레이어
"""
import database

def _escape_like(term):
    return str(term).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

class OpdsRepository:
    @staticmethod
    def get_total_pages(db_type, book_ids):
        """book_id -> total_pages (OPDS-PSE 페이지 스트리밍 링크의 pse:count 용, 한 번의 쿼리)."""
        ids = [int(i) for i in book_ids or [] if i is not None]
        if not ids:
            return {}
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT id, total_pages FROM books WHERE id IN ({','.join(['%s'] * len(ids))})",
                tuple(ids)
            )
            rows = cursor.fetchall()
        return {int(r['id']): int(r['total_pages'] or 0) for r in rows}

    @staticmethod
    def get_library_list(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM libraries")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_series_entries(db_type, lib_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(series_name, '') AS series_name,
                       MAX(NULLIF(cover_image, '')) AS cover_image
                FROM books
                WHERE library_id = %s AND COALESCE(is_deleted, 0) = 0
                GROUP BY COALESCE(series_name, '')
                ORDER BY COALESCE(series_name, '')
                """,
                (lib_id,)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_book_entries_count(db_type, lib_id, series_name):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            is_all = not lib_id or str(lib_id).lower() in ('all', 'general', 'adult', '0')
            if is_all:
                if not series_name or series_name == '__empty_series__':
                    query = "SELECT COUNT(*) AS total FROM books WHERE (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = ()
                else:
                    query = "SELECT COUNT(*) AS total FROM books WHERE series_name=%s AND COALESCE(is_deleted, 0) = 0"
                    params = (series_name,)
            else:
                if not series_name or series_name == '__empty_series__':
                    query = "SELECT COUNT(*) AS total FROM books WHERE library_id=%s AND (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = (lib_id,)
                else:
                    query = "SELECT COUNT(*) AS total FROM books WHERE library_id=%s AND series_name=%s AND COALESCE(is_deleted, 0) = 0"
                    params = (lib_id, series_name)

            cursor.execute(query, params)
            row = cursor.fetchone()
        return row['total'] if row else 0

    @staticmethod
    def get_book_entries(db_type, lib_id, series_name, limit=None, offset=0):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            is_all = not lib_id or str(lib_id).lower() in ('all', 'general', 'adult', '0')
            if is_all:
                if not series_name or series_name == '__empty_series__':
                    where_clause = "WHERE (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = []
                else:
                    where_clause = "WHERE series_name=%s AND COALESCE(is_deleted, 0) = 0"
                    params = [series_name]
            else:
                if not series_name or series_name == '__empty_series__':
                    where_clause = "WHERE library_id=%s AND (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = [lib_id]
                else:
                    where_clause = "WHERE library_id=%s AND series_name=%s AND COALESCE(is_deleted, 0) = 0"
                    params = [lib_id, series_name]

            query = f"SELECT id, title, file_path, cover_image, summary FROM books {where_clause} ORDER BY title ASC, id ASC "
            if limit is not None:
                query += "LIMIT %s OFFSET %s"
                params.extend([int(limit), int(offset)])

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_added_entries(db_type):
        with database.connection(db_type) as conn:
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
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_favorite_entries(db_type, user_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COALESCE(NULLIF(b.series_name, ''), b.title) AS series_group_name,
                    COALESCE(MIN(CASE WHEN b.cover_image IS NOT NULL AND b.cover_image != '' THEN b.id END), MIN(b.id)) AS id,
                    COALESCE(NULLIF(b.series_name, ''), b.title) AS title,
                    COUNT(b.id) AS book_count,
                    MIN(b.file_path) AS file_path,
                    MAX(b.cover_image) AS cover_image
                FROM books b
                JOIN user_favorites uf ON uf.book_id = b.id
                WHERE COALESCE(b.is_deleted, 0) = 0 AND uf.user_id = %s
                GROUP BY COALESCE(NULLIF(b.series_name, ''), b.title)
                ORDER BY series_group_name ASC
                LIMIT 200
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_read_entries_all(db_type, limit):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
                FROM user_progress AS p
                JOIN books b ON p.book_id = b.id
                WHERE b.title IS NOT NULL AND b.title != '' AND COALESCE(b.is_deleted, 0) = 0
                ORDER BY p.last_read_at DESC
                LIMIT %s
                """,
                (int(limit),)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_read_entries_by_user(db_type, user_id, limit):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
                FROM user_progress AS p
                JOIN books b ON p.book_id = b.id
                WHERE p.user_id = %s
                  AND b.title IS NOT NULL AND b.title != ''
                  AND COALESCE(b.is_deleted, 0) = 0
                ORDER BY p.last_read_at DESC
                LIMIT %s
                """,
                (user_id, int(limit))
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def search_books_like(db_type, query, limit, offset, user_id=None, role=None):
        terms = [term for term in str(query or '').split() if term][:10]
        if not terms:
            return [], 0

        where = ["COALESCE(b.is_deleted, 0) = 0"]
        params = []
        for term in terms:
            like_query = f"%{_escape_like(term)}%"
            where.append(
                "(COALESCE(b.title, '') LIKE %s "
                "OR COALESCE(b.series_name, '') LIKE %s "
                "OR COALESCE(b.author, '') LIKE %s)"
            )
            params.extend([like_query, like_query, like_query])

        where_sql = ' AND '.join(where)
        conn = database.get_connection(db_type)
        try:
            cursor = conn.cursor()

            if role != 'admin' and user_id is not None:
                # library_id에 상관관계를 건 EXISTS는 series_repository의 _fetch_summary_rows에서
                # 확인된 것과 동일하게 옵티마이저가 ORDER BY 인덱스 기반 조기 LIMIT을 못 쓰게 만들
                # 수 있다 - 권한 행을 먼저 조회해 정적 IN 목록으로 바꾼다. 권한 테이블에 해당
                # 사용자 행이 아예 없으면(과거 NOT EXISTS 분기와 동일하게) 제한 없이 전체 허용.
                cursor.execute(
                    "SELECT library_id, has_access FROM user_category_permissions WHERE user_id = %s",
                    (int(user_id),)
                )
                perm_rows = cursor.fetchall()
                if perm_rows:
                    allowed_library_ids = [int(row['library_id']) for row in perm_rows if int(row['has_access'] or 0) == 1]
                    if not allowed_library_ids:
                        return [], 0
                    placeholders = ','.join(['%s'] * len(allowed_library_ids))
                    where_sql += f" AND b.library_id IN ({placeholders})"
                    params.extend(allowed_library_ids)

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM books b WHERE {where_sql}",
                tuple(params)
            )
            total = cursor.fetchone()['total']

            cursor.execute(
                f"""
                SELECT b.id, b.title, b.series_name, b.author, b.file_path, b.file_format,
                       b.cover_image, b.summary
                FROM books b
                WHERE {where_sql}
                ORDER BY b.title ASC, b.id ASC
                LIMIT %s OFFSET %s
                """,
                tuple(params + [int(limit), int(offset)])
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows], total
        finally:
            conn.close()

    @staticmethod
    def get_supported_series_names(db_type, clean_names):
        if not clean_names:
            return set()
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['%s'] * len(clean_names))
            query = f"""
                SELECT DISTINCT series_name
                FROM books
                WHERE COALESCE(is_deleted, 0) = 0
                  AND LOWER(COALESCE(file_format, '')) IN ('zip', 'cbz')
                  AND series_name IN ({placeholders})
            """
            cursor.execute(query, tuple(clean_names))
            rows = cursor.fetchall()
        return {row['series_name'] for row in rows}
