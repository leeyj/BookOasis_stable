# -*- coding: utf-8 -*-
"""
opds_repository.py – OPDS 피드(navigation/acquisition) 데이터 조회를 위한 격리 데이터 액세스 레이어
"""
import database

class OpdsRepository:
    @staticmethod
    def get_library_list(db_type):
        """카테고리(도서관) 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM libraries")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_series_entries(db_type, lib_id):
        """특정 카테고리 내 고유 시리즈 목록 및 대표 커버 이미지 조회"""
        conn = database.get_connection(db_type)
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
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_book_entries_count(db_type, lib_id, series_name):
        """특정 라이브러리/시리즈 내 도서의 총 개수 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS total FROM books WHERE library_id=? AND series_name=? AND COALESCE(is_deleted, 0) = 0",
            (lib_id, series_name)
        )
        row = cursor.fetchone()
        conn.close()
        return row['total'] if row else 0

    @staticmethod
    def get_book_entries(db_type, lib_id, series_name, limit=None, offset=0):
        """특정 라이브러리/시리즈 내 도서 목록 페이징 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = (
            "SELECT id, title, file_path, cover_image, summary FROM books "
            "WHERE library_id=? AND series_name=? AND COALESCE(is_deleted, 0) = 0 "
            "ORDER BY title ASC, id ASC "
        )
        params = [lib_id, series_name]
        if limit is not None:
            query += "LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_added_entries(db_type):
        """최근 추가된 도서 20권 조회"""
        conn = database.get_connection(db_type)
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
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_favorite_entries(db_type, user_id):
        """즐겨찾기 등록 도서 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.id, b.title, b.file_path, b.cover_image
            FROM books b
            JOIN user_favorites uf ON uf.book_id = b.id
            WHERE COALESCE(b.is_deleted, 0) = 0 AND uf.user_id = ?
            ORDER BY b.title ASC, b.id ASC
            LIMIT 200
            """
            ,
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_read_entries_all(db_type, limit):
        """전체 사용자의 최근 읽은 책 조회"""
        conn = database.get_connection(db_type)
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
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_recently_read_entries_by_user(db_type, user_id, limit):
        """특정 사용자의 최근 읽은 책 조회"""
        conn = database.get_connection(db_type)
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
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def search_books_like(db_type, query, limit, offset):
        """LIKE 기반 도서 통합 검색"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        like_query = f"%{query}%"
        cursor.execute(
            """
            SELECT COUNT(*) AS total FROM books
            WHERE (title LIKE ? OR series_name LIKE ? OR author LIKE ?) AND COALESCE(is_deleted, 0) = 0
            """,
            (like_query, like_query, like_query)
        )
        total = cursor.fetchone()['total']

        cursor.execute(
            """
            SELECT id, title, series_name, author, file_path, cover_image, summary
            FROM books
            WHERE (title LIKE ? OR series_name LIKE ? OR author LIKE ?) AND COALESCE(is_deleted, 0) = 0
            ORDER BY title ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (like_query, like_query, like_query, limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows], total

    @staticmethod
    def search_books_fts(db_type, query, match_query, limit, offset):
        """FTS5 형태소 매칭 기반 도서 통합 검색"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM books_search
            JOIN books b ON b.id = books_search.rowid
            WHERE books_search MATCH ? AND COALESCE(b.is_deleted, 0) = 0
            """,
            (match_query,)
        )
        total = cursor.fetchone()['total']

        cursor.execute(
            """
            SELECT b.id, b.title, b.series_name, b.author, b.file_path, b.cover_image, b.summary
            FROM books_search
            JOIN books b ON b.id = books_search.rowid
            WHERE books_search MATCH ? AND COALESCE(b.is_deleted, 0) = 0
            ORDER BY bm25(books_search), b.title ASC, b.id ASC
            LIMIT ? OFFSET ?
            """,
            (match_query, limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_supported_series_names(db_type, clean_names):
        """동화 호환성을 위한 특정 만화 포맷 존재 시리즈 리스트 필터링"""
        conn = database.get_connection(db_type)
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
        conn.close()
        return {row['series_name'] for row in rows}
