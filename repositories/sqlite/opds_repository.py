# -*- coding: utf-8 -*-
"""
opds_repository.py – OPDS 피드(navigation/acquisition) 데이터 조회를 위한 격리 데이터 액세스 레이어
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
                f"SELECT id, total_pages FROM books WHERE id IN ({','.join(['?'] * len(ids))})",
                tuple(ids)
            )
            rows = cursor.fetchall()
        return {int(r['id']): int(r['total_pages'] or 0) for r in rows}

    @staticmethod
    def get_library_list(db_type):
        """카테고리(도서관) 목록 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM libraries")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_series_entries(db_type, lib_id):
        """특정 카테고리 내 고유 시리즈 목록 및 대표 커버 이미지 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(series_name, '') AS series_name,
                       MAX(NULLIF(cover_image, '')) AS cover_image
                FROM books
                WHERE library_id = ? AND COALESCE(is_deleted, 0) = 0
                GROUP BY COALESCE(series_name, '')
                ORDER BY COALESCE(series_name, '')
                """,
                (lib_id,)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_book_entries_count(db_type, lib_id, series_name):
        """특정 라이브러리/시리즈 내 도서의 총 개수 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            is_all = not lib_id or str(lib_id).lower() in ('all', 'general', 'adult', '0')
            if is_all:
                if not series_name or series_name == '__empty_series__':
                    query = "SELECT COUNT(*) AS total FROM books WHERE (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = ()
                else:
                    query = "SELECT COUNT(*) AS total FROM books WHERE series_name=? AND COALESCE(is_deleted, 0) = 0"
                    params = (series_name,)
            else:
                if not series_name or series_name == '__empty_series__':
                    query = "SELECT COUNT(*) AS total FROM books WHERE library_id=? AND (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = (lib_id,)
                else:
                    query = "SELECT COUNT(*) AS total FROM books WHERE library_id=? AND series_name=? AND COALESCE(is_deleted, 0) = 0"
                    params = (lib_id, series_name)

            cursor.execute(query, params)
            row = cursor.fetchone()
        return row['total'] if row else 0

    @staticmethod
    def get_book_entries(db_type, lib_id, series_name, limit=None, offset=0):
        """특정 라이브러리/시리즈 내 도서 목록 페이징 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            is_all = not lib_id or str(lib_id).lower() in ('all', 'general', 'adult', '0')
            if is_all:
                if not series_name or series_name == '__empty_series__':
                    where_clause = "WHERE (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = []
                else:
                    where_clause = "WHERE series_name=? AND COALESCE(is_deleted, 0) = 0"
                    params = [series_name]
            else:
                if not series_name or series_name == '__empty_series__':
                    where_clause = "WHERE library_id=? AND (series_name = '' OR series_name IS NULL) AND COALESCE(is_deleted, 0) = 0"
                    params = [lib_id]
                else:
                    where_clause = "WHERE library_id=? AND series_name=? AND COALESCE(is_deleted, 0) = 0"
                    params = [lib_id, series_name]

            query = f"SELECT id, title, file_path, cover_image, summary FROM books {where_clause} ORDER BY title ASC, id ASC "
            if limit is not None:
                query += "LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_added_entries(db_type):
        """최근 추가된 도서 20권 조회"""
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
        """즐겨찾기 등록 도서 시리즈/단행본 대표 목록 조회 (시리즈 그룹핑)"""
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
                WHERE COALESCE(b.is_deleted, 0) = 0 AND uf.user_id = ?
                GROUP BY COALESCE(NULLIF(b.series_name, ''), b.title)
                ORDER BY series_group_name ASC
                LIMIT 200
                """
                ,
                (user_id,)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_read_entries_all(db_type, limit):
        """전체 사용자의 최근 읽은 책 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
                FROM user_progress AS p INDEXED BY idx_user_progress_last_read_book
                JOIN books b ON p.book_id = b.id
                WHERE b.title IS NOT NULL AND b.title != '' AND COALESCE(b.is_deleted, 0) = 0
                ORDER BY p.last_read_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_read_entries_by_user(db_type, user_id, limit):
        """특정 사용자의 최근 읽은 책 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
                FROM user_progress AS p INDEXED BY idx_user_progress_last_read
                JOIN books b ON p.book_id = b.id
                WHERE p.user_id = ?
                  AND b.title IS NOT NULL AND b.title != ''
                  AND COALESCE(b.is_deleted, 0) = 0
                ORDER BY p.last_read_at DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def search_books_like(db_type, query, limit, offset, user_id=None, role=None):
        """일반 테이블만 사용하는 다중 검색어 AND 검색."""
        terms = [term for term in str(query or '').split() if term][:10]
        if not terms:
            return [], 0

        where = ["COALESCE(b.is_deleted, 0) = 0"]
        params = []
        for term in terms:
            like_query = f"%{_escape_like(term)}%"
            where.append(
                "(COALESCE(b.title, '') LIKE ? ESCAPE '\\' "
                "OR COALESCE(b.series_name, '') LIKE ? ESCAPE '\\' "
                "OR COALESCE(b.author, '') LIKE ? ESCAPE '\\')"
            )
            params.extend([like_query, like_query, like_query])

        where_sql = ' AND '.join(where)
        conn = database.get_connection(db_type)
        try:
            cursor = conn.cursor()

            if role != 'admin' and user_id is not None:
                cursor.execute(
                    "SELECT library_id, has_access FROM user_category_permissions WHERE user_id = ?",
                    (int(user_id),)
                )
                perm_rows = cursor.fetchall()
                if perm_rows:
                    allowed_library_ids = [int(row['library_id']) for row in perm_rows if int(row['has_access'] or 0) == 1]
                    if not allowed_library_ids:
                        return [], 0
                    placeholders = ','.join(['?'] * len(allowed_library_ids))
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
                LIMIT ? OFFSET ?
                """,
                tuple(params + [limit, offset])
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows], total
        finally:
            conn.close()



    @staticmethod
    def get_supported_series_names(db_type, clean_names):
        """동화 호환성을 위한 특정 만화 포맷 존재 시리즈 리스트 필터링"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(clean_names))
            query = f"""
                SELECT DISTINCT series_name
                FROM books
                WHERE COALESCE(is_deleted, 0) = 0
                  AND lower(COALESCE(file_format, '')) IN ('zip', 'cbz')
                  AND series_name IN ({placeholders})
            """
            cursor.execute(query, tuple(clean_names))
            rows = cursor.fetchall()
        return {row['series_name'] for row in rows}
