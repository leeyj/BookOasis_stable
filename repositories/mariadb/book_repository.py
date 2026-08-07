# -*- coding: utf-8 -*-
"""
book_repository.py – MariaDB 전용 도서(books), 즐겨찾기(user_favorites) 정보 데이터 액세스 레이어
"""
import database

class BookRepository:
    @staticmethod
    def get_book_basic_info(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, series_name, library_id, file_path FROM books WHERE id = %s AND COALESCE(is_deleted, 0) = 0",
            (book_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_books_by_series(db_type, series_name, library_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.title, b.file_format, b.total_pages, b.cover_image, b.cover_updated_at, b.file_path, p.pages_read
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = %s
            WHERE COALESCE(b.is_deleted, 0) = 0 AND b.series_name = %s AND b.library_id = %s
        """, (user_id, series_name, library_id))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_favorite(db_type, book_id, is_favorite, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if int(is_favorite) == 1:
                cursor.execute(
                    "INSERT IGNORE INTO user_favorites (user_id, book_id, created_at) VALUES (%s, %s, CURRENT_TIMESTAMP)",
                    (user_id, book_id)
                )
            else:
                cursor.execute("DELETE FROM user_favorites WHERE user_id = %s AND book_id = %s", (user_id, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_series_favorite(db_type, series_name, is_favorite, user_id):
        safe_user_id = int(user_id) if user_id is not None and int(user_id) > 0 else 1
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if int(is_favorite) == 1:
                cursor.execute(
                    """
                    INSERT IGNORE INTO user_favorites (user_id, book_id, created_at)
                    SELECT %s, id, CURRENT_TIMESTAMP
                    FROM books
                    WHERE (series_name = %s OR (COALESCE(series_name, '') = '' AND title = %s))
                      AND COALESCE(is_deleted, 0) = 0
                    """,
                    (safe_user_id, series_name, series_name)
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM user_favorites
                    WHERE user_id = %s AND book_id IN (
                        SELECT id FROM books
                        WHERE (series_name = %s OR (COALESCE(series_name, '') = '' AND title = %s))
                          AND COALESCE(is_deleted, 0) = 0
                    )
                    """,
                    (safe_user_id, series_name, series_name)
                )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_media_tags(db_type, library_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if library_id and library_id not in ('all', 'favorite', 'history', 'home'):
            cursor.execute(
                "SELECT DISTINCT tags FROM books WHERE library_id = %s AND (is_deleted = 0 OR is_deleted IS NULL) AND tags IS NOT NULL AND tags != ''",
                (library_id,)
            )
        else:
            cursor.execute("SELECT DISTINCT tags FROM books WHERE (is_deleted = 0 OR is_deleted IS NULL) AND tags IS NOT NULL AND tags != ''")
        rows = cursor.fetchall()
        conn.close()
        values = []
        for r in rows:
            if isinstance(r, dict):
                v = r.get('tags')
            else:
                v = r[0] if r else None
            if v:
                values.append(v)
        return values

    @staticmethod
    def get_media_genres(db_type, library_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if library_id and library_id not in ('all', 'favorite', 'history', 'home'):
            cursor.execute(
                "SELECT DISTINCT genre FROM books WHERE library_id = %s AND (is_deleted = 0 OR is_deleted IS NULL) AND genre IS NOT NULL AND genre != ''",
                (library_id,)
            )
        else:
            cursor.execute("SELECT DISTINCT genre FROM books WHERE (is_deleted = 0 OR is_deleted IS NULL) AND genre IS NOT NULL AND genre != ''")
        rows = cursor.fetchall()
        conn.close()
        values = []
        for r in rows:
            if isinstance(r, dict):
                v = r.get('genre')
            else:
                v = r[0] if r else None
            if v:
                values.append(v)
        return values

    @staticmethod
    def get_book_file_info_with_permission(db_type, book_id, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT b.file_path, b.file_format FROM books b WHERE b.id = %s AND COALESCE(b.is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (book_id, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_book_file_path_with_permission(db_type, book_id, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT b.file_path FROM books b WHERE b.id = %s AND COALESCE(b.is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (book_id, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['file_path'] if row else None

    @staticmethod
    def get_book_cover_image(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, cover_image FROM books WHERE id = %s", (book_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_book_pages_and_path(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT total_pages, file_path, file_format FROM books WHERE id = %s", (book_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_pages(db_type, book_id, total_pages):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE books SET total_pages = %s WHERE id = %s", (total_pages, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_representative_book_info(db_type, book_id, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT id, series_name, library_id, file_path, file_format FROM books WHERE id = %s AND COALESCE(is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (book_id, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def resolve_series_name_by_alias(db_type, query_series_name, perm_clause, perm_params):
        if not query_series_name:
            return query_series_name
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT series_name FROM books WHERE (series_name = %s OR series_alias = %s) AND COALESCE(is_deleted, 0) = 0{perm_clause} LIMIT 1"
        cursor.execute(query, (query_series_name, query_series_name, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['series_name'] if row and row['series_name'] else query_series_name

    @staticmethod
    def resolve_series_library_id(db_type, series_name, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT library_id FROM books WHERE series_name = %s AND COALESCE(is_deleted, 0) = 0{perm_clause} LIMIT 1"
        cursor.execute(query, (series_name, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['library_id'] if row else None

    @staticmethod
    def get_series_meta(db_type, series_name, library_id, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        if library_id and library_id not in ('all', 'history', 'favorite', 'home'):
            query1 = f"""
                SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                FROM books
                WHERE series_name = %s AND library_id = %s AND COALESCE(is_deleted, 0) = 0{perm_clause}
                  AND (summary IS NOT NULL AND summary != '')
                LIMIT 1
            """
            cursor.execute(query1, (series_name, library_id, *perm_params))
            row = cursor.fetchone()
            if not row:
                query2 = f"""
                    SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                    FROM books WHERE series_name = %s AND library_id = %s AND COALESCE(is_deleted, 0) = 0{perm_clause}
                    LIMIT 1
                """
                cursor.execute(query2, (series_name, library_id, *perm_params))
                row = cursor.fetchone()
        else:
            query1 = f"""
                SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                FROM books
                WHERE series_name = %s AND COALESCE(is_deleted, 0) = 0{perm_clause}
                  AND (summary IS NOT NULL AND summary != '')
                LIMIT 1
            """
            cursor.execute(query1, (series_name, *perm_params))
            row = cursor.fetchone()
            if not row:
                query2 = f"""
                    SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                    FROM books WHERE series_name = %s AND COALESCE(is_deleted, 0) = 0{perm_clause}
                    LIMIT 1
                """
                cursor.execute(query2, (series_name, *perm_params))
                row = cursor.fetchone()
                
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_books_by_series_detail(db_type, series_name, library_id, user_id, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        use_lib = library_id and library_id not in ('all', 'history', 'favorite', 'home')
        if use_lib:
            query = f"""
                SELECT b.id, b.title, b.title_alias, b.series_name, b.series_alias, b.file_format, b.total_pages, b.has_offsets, b.cover_image, b.cover_updated_at,
                       b.file_path, p.pages_read, p.is_completed,
                       CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                       b.library_id, p.last_read_at, COALESCE(b.metadata_locked, 0) AS metadata_locked
                FROM books b
                LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = %s
                LEFT JOIN user_favorites uf ON b.id = uf.book_id AND uf.user_id = %s
                WHERE COALESCE(b.is_deleted, 0) = 0 AND b.series_name = %s AND b.library_id = %s{perm_clause}
            """
            cursor.execute(query, (user_id, user_id, series_name, library_id, *perm_params))
        else:
            query = f"""
                SELECT b.id, b.title, b.title_alias, b.series_name, b.series_alias, b.file_format, b.total_pages, b.has_offsets, b.cover_image, b.cover_updated_at,
                       b.file_path, p.pages_read, p.is_completed,
                       CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                       b.library_id, p.last_read_at, COALESCE(b.metadata_locked, 0) AS metadata_locked
                FROM books b
                LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = %s
                LEFT JOIN user_favorites uf ON b.id = uf.book_id AND uf.user_id = %s
                WHERE COALESCE(b.is_deleted, 0) = 0 AND b.series_name = %s{perm_clause}
            """
            cursor.execute(query, (user_id, user_id, series_name, *perm_params))
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_series_latest_updated(db_type, series_name, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT MAX(cover_updated_at) AS latest_updated FROM books WHERE series_name = %s AND COALESCE(is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (series_name, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['latest_updated'] if row else None

    @staticmethod
    def update_media_detail(db_type, series_name, author, isbn, publisher, summary, link, genre, tags, series_alias=None, cover_image_url=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if cover_image_url:
                cursor.execute("""
                    UPDATE books
                    SET author = %s,
                        isbn = %s,
                        publisher = %s,
                        summary = %s,
                        link = %s,
                        genre = %s,
                        tags = %s,
                        series_alias = %s,
                        cover_image = %s,
                        metadata_locked = 1,
                        cover_updated_at = CURRENT_TIMESTAMP
                    WHERE series_name = %s
                """, (author, isbn, publisher, summary, link, genre, tags, series_alias, cover_image_url, series_name))
            else:
                cursor.execute("""
                    UPDATE books
                    SET author = %s,
                        isbn = %s,
                        publisher = %s,
                        summary = %s,
                        link = %s,
                        genre = %s,
                        tags = %s,
                        series_alias = %s,
                        metadata_locked = 1,
                        cover_updated_at = CURRENT_TIMESTAMP
                    WHERE series_name = %s
                """, (author, isbn, publisher, summary, link, genre, tags, series_alias, series_name))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def unlock_media_metadata(db_type, series_name=None, library_id=None, book_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            where = []
            params = []
            if series_name:
                where.append("series_name = %s")
                params.append(series_name)
                if library_id is not None and str(library_id).strip() != '':
                    where.append("library_id = %s")
                    params.append(int(library_id))
            elif book_id is not None and str(book_id).strip() != '':
                where.append("id = %s")
                params.append(int(book_id))
            
            if not where:
                return False
            
            sql = f"UPDATE books SET metadata_locked = 0 WHERE {' AND '.join(where)}"
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_series_cover_candidates(db_type, series_name, library_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if library_id is not None:
            cursor.execute(
                """
                SELECT cover_image 
                FROM books 
                WHERE series_name = %s AND library_id = %s AND COALESCE(is_deleted, 0) = 0 AND cover_image IS NOT NULL AND cover_image != ''
                ORDER BY title ASC
                """,
                (series_name, library_id)
            )
        else:
            cursor.execute(
                """
                SELECT cover_image 
                FROM books 
                WHERE series_name = %s AND COALESCE(is_deleted, 0) = 0 AND cover_image IS NOT NULL AND cover_image != ''
                ORDER BY title ASC
                """,
                (series_name,)
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_series_alias(db_type, series_name, series_alias):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE books
                SET series_alias = %s,
                    metadata_locked = 1
                WHERE series_name = %s
            """, (series_alias if series_alias else None, series_name))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_book_alias(db_type, book_id, title_alias):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE books
                SET title_alias = %s,
                    metadata_locked = 1
                WHERE id = %s
            """, (title_alias if title_alias else None, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
