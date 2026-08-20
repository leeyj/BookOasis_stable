# -*- coding: utf-8 -*-
"""
book_repository.py – 도서(books), 즐겨찾기(user_favorites) 정보 조회 및 조작 데이터 액세스 레이어
"""
import database

class BookRepository:
    @staticmethod
    def get_book_basic_info(db_type, book_id):
        """도서 단일 행의 시리즈명, 라이브러리ID, 파일경로 기본 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, series_name, library_id, file_path, file_format FROM books WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (book_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_book_reader_info(db_type, book_id, user_id=None):
        """킷오스크/외부 딥링크에서 openReader()에 바로 넘길 도서 메타(제목/포맷/진척도) 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.id, b.title, b.file_format, b.total_pages, b.file_path, p.pages_read
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE b.id = ? AND COALESCE(b.is_deleted, 0) = 0
            """,
            (user_id, book_id)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_book_annotation_context_info(db_type, book_id):
        """하이라이트(주석) 플러그인 컨텍스트 메뉴에 전달할 도서 요약 정보(제목/시리즈명/커버) 조회.
        title에는 이 프로젝트 파일명 관례상 보통 권/화 번호가 이미 포함돼 있어(예: '05권')
        별도의 편수 컬럼 없이도 플러그인이 title만으로 식별 가능하다."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT title, series_name, cover_image FROM books WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (book_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_books_by_series(db_type, series_name, library_id=None, user_id=None):
        """동일 시리즈 내 전체 도서 목록 조회 (유저 읽기 진척도 포함)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        where = ["COALESCE(b.is_deleted, 0) = 0", "b.series_name = ?"]
        params = [series_name]
        if library_id is not None:
            where.append("b.library_id = ?")
            params.append(library_id)
        
        sql = f"""
            SELECT b.id, b.title, b.file_format, b.total_pages, b.cover_image, b.cover_updated_at, b.file_path, p.pages_read
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE {' AND '.join(where)}
        """
        cursor.execute(sql, (user_id, *params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_favorite(db_type, book_id, is_favorite, user_id):
        """특정 도서 즐겨찾기 등록/해제"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if int(is_favorite) == 1:
                cursor.execute(
                    "INSERT OR IGNORE INTO user_favorites (user_id, book_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (user_id, book_id)
                )
            else:
                cursor.execute("DELETE FROM user_favorites WHERE user_id = ? AND book_id = ?", (user_id, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_series_favorite(db_type, series_name, is_favorite, user_id):
        """특정 시리즈의 모든 도서 즐겨찾기 일괄 등록/해제"""
        safe_user_id = int(user_id) if user_id is not None and int(user_id) > 0 else 1
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if int(is_favorite) == 1:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO user_favorites (user_id, book_id, created_at)
                    SELECT ?, id, CURRENT_TIMESTAMP
                    FROM books
                    WHERE (series_name = ? OR (COALESCE(series_name, '') = '' AND title = ?))
                      AND COALESCE(is_deleted, 0) = 0
                    """,
                    (safe_user_id, series_name, series_name)
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM user_favorites
                    WHERE user_id = ? AND book_id IN (
                        SELECT id FROM books
                        WHERE (series_name = ? OR (COALESCE(series_name, '') = '' AND title = ?))
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
        """특정 라이브러리 또는 전체 도서의 고유 태그 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if library_id and library_id not in ('all', 'favorite', 'history', 'home'):
            cursor.execute(
                "SELECT DISTINCT tags FROM books WHERE library_id = ? AND (is_deleted = 0 OR is_deleted IS NULL) AND tags IS NOT NULL AND tags != ''",
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
        """특정 라이브러리 또는 전체 도서의 고유 장르 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if library_id and library_id not in ('all', 'favorite', 'history', 'home'):
            cursor.execute(
                "SELECT DISTINCT genre FROM books WHERE library_id = ? AND (is_deleted = 0 OR is_deleted IS NULL) AND genre IS NOT NULL AND genre != ''",
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
    def get_series_genre_tags_index(db_type):
        """스마트 추천용: 시리즈 단위 대표 정보(대표 book id, 커버, 포맷, 장르, 태그, 평점) 인덱스 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT series_name, library_id,
                   MIN(id) AS id,
                   MAX(cover_image) AS cover_image,
                   MAX(cover_updated_at) AS cover_updated_at,
                   MAX(file_format) AS file_format,
                   MAX(genre) AS genre,
                   MAX(tags) AS tags,
                   MAX(author) AS author,
                   MAX(score) AS score
            FROM books
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND series_name IS NOT NULL AND series_name != ''
              AND ((genre IS NOT NULL AND genre != '') OR (tags IS NOT NULL AND tags != '') OR (author IS NOT NULL AND author != ''))
            GROUP BY series_name, library_id
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_latest_series_by_library(db_type, library_id, limit=30):
        """스마트 추천 폴백용: 장르/태그 정보가 없는 시리즈를 대신할 동일 카테고리 최신 등록 시리즈 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT series_name, library_id,
                   MIN(id) AS id,
                   MAX(cover_image) AS cover_image,
                   MAX(cover_updated_at) AS cover_updated_at,
                   MAX(file_format) AS file_format,
                   MAX(score) AS score,
                   MAX(created_at) AS created_at
            FROM books
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND library_id = ?
              AND series_name IS NOT NULL AND series_name != ''
            GROUP BY series_name
            ORDER BY MAX(created_at) DESC
            LIMIT ?
            """,
            (library_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_book_file_info_with_permission(db_type, book_id, perm_clause, perm_params):
        """권한 체크를 수용하여 도서의 파일 경로 및 포맷 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT b.file_path, b.file_format FROM books b WHERE b.id = ? AND COALESCE(b.is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (book_id, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_book_file_path_with_permission(db_type, book_id, perm_clause, perm_params):
        """권한 체크를 수용하여 도서의 파일 경로만 단순 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT b.file_path FROM books b WHERE b.id = ? AND COALESCE(b.is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (book_id, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['file_path'] if row else None

    @staticmethod
    def get_book_cover_image(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, cover_image FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_book_pages_and_path(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT total_pages, file_path, file_format FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_pages(db_type, book_id, total_pages):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))
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
        query = f"SELECT id, series_name, library_id, file_path, file_format FROM books WHERE id = ? AND COALESCE(is_deleted, 0) = 0{perm_clause}"
        cursor.execute(query, (book_id, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def resolve_series_name_by_alias(db_type, query_series_name, perm_clause, perm_params):
        """series_name 또는 series_alias로 요청이 왔을 때 실제 DB의 원본 series_name 매칭"""
        if not query_series_name:
            return query_series_name
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT series_name FROM books WHERE (series_name = ? OR series_alias = ?) AND COALESCE(is_deleted, 0) = 0{perm_clause} LIMIT 1"
        cursor.execute(query, (query_series_name, query_series_name, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['series_name'] if row and row['series_name'] else query_series_name

    @staticmethod
    def resolve_series_library_id(db_type, series_name, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT library_id FROM books WHERE series_name = ? AND COALESCE(is_deleted, 0) = 0{perm_clause} LIMIT 1"
        cursor.execute(query, (series_name, *perm_params))
        row = cursor.fetchone()
        conn.close()
        return row['library_id'] if row else None

    @staticmethod
    def get_series_meta(db_type, series_name, library_id, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        # 1. library_id 필터 유무 분기
        if library_id and library_id not in ('all', 'history', 'favorite', 'home'):
            # 요약 설명이 채워진 것을 먼저 매칭
            query1 = f"""
                SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                FROM books
                WHERE series_name = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0{perm_clause}
                  AND (summary IS NOT NULL AND summary != '')
                LIMIT 1
            """
            cursor.execute(query1, (series_name, library_id, *perm_params))
            row = cursor.fetchone()
            if not row:
                query2 = f"""
                    SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                    FROM books WHERE series_name = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0{perm_clause}
                    LIMIT 1
                """
                cursor.execute(query2, (series_name, library_id, *perm_params))
                row = cursor.fetchone()
        else:
            query1 = f"""
                SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                FROM books
                WHERE series_name = ? AND COALESCE(is_deleted, 0) = 0{perm_clause}
                  AND (summary IS NOT NULL AND summary != '')
                LIMIT 1
            """
            cursor.execute(query1, (series_name, *perm_params))
            row = cursor.fetchone()
            if not row:
                query2 = f"""
                    SELECT author, isbn, publisher, link, score, summary, genre, tags, series_alias, COALESCE(metadata_locked, 0) AS metadata_locked
                    FROM books WHERE series_name = ? AND COALESCE(is_deleted, 0) = 0{perm_clause}
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
                LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
                LEFT JOIN user_favorites uf ON b.id = uf.book_id AND uf.user_id = ?
                WHERE COALESCE(b.is_deleted, 0) = 0 AND b.series_name = ? AND b.library_id = ?{perm_clause}
            """
            cursor.execute(query, (user_id, user_id, series_name, library_id, *perm_params))
        else:
            query = f"""
                SELECT b.id, b.title, b.title_alias, b.series_name, b.series_alias, b.file_format, b.total_pages, b.has_offsets, b.cover_image, b.cover_updated_at,
                       b.file_path, p.pages_read, p.is_completed,
                       CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                       b.library_id, p.last_read_at, COALESCE(b.metadata_locked, 0) AS metadata_locked
                FROM books b
                LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
                LEFT JOIN user_favorites uf ON b.id = uf.book_id AND uf.user_id = ?
                WHERE COALESCE(b.is_deleted, 0) = 0 AND b.series_name = ?{perm_clause}
            """
            cursor.execute(query, (user_id, user_id, series_name, *perm_params))
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_series_latest_updated(db_type, series_name, perm_clause, perm_params):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        query = f"SELECT MAX(cover_updated_at) AS latest_updated FROM books WHERE series_name = ? AND COALESCE(is_deleted, 0) = 0{perm_clause}"
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
                    SET author = ?,
                        isbn = ?,
                        publisher = ?,
                        summary = ?,
                        link = ?,
                        genre = ?,
                        tags = ?,
                        series_alias = ?,
                        cover_image = ?,
                        metadata_locked = 1,
                        cover_updated_at = CURRENT_TIMESTAMP
                    WHERE series_name = ?
                """, (author, isbn, publisher, summary, link, genre, tags, series_alias, cover_image_url, series_name))
            else:
                cursor.execute("""
                    UPDATE books
                    SET author = ?,
                        isbn = ?,
                        publisher = ?,
                        summary = ?,
                        link = ?,
                        genre = ?,
                        tags = ?,
                        series_alias = ?,
                        metadata_locked = 1,
                        cover_updated_at = CURRENT_TIMESTAMP
                    WHERE series_name = ?
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
        """도서/시리즈 메타데이터 잠금 해제 (metadata_locked = 0)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            where = []
            params = []
            if series_name:
                where.append("series_name = ?")
                params.append(series_name)
                if library_id is not None and str(library_id).strip() != '':
                    where.append("CAST(library_id AS TEXT) = ?")
                    params.append(str(library_id))
            elif book_id is not None and str(book_id).strip() != '':
                where.append("id = ?")
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
        """시리즈에 속한 실존하는 커버 이미지 후보 리스트 획득"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if library_id is not None:
            cursor.execute(
                """
                SELECT cover_image 
                FROM books 
                WHERE series_name = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0 AND cover_image IS NOT NULL AND cover_image != ''
                ORDER BY title ASC
                """,
                (series_name, library_id)
            )
        else:
            cursor.execute(
                """
                SELECT cover_image 
                FROM books 
                WHERE series_name = ? AND COALESCE(is_deleted, 0) = 0 AND cover_image IS NOT NULL AND cover_image != ''
                ORDER BY title ASC
                """,
                (series_name,)
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_series_alias(db_type, series_name, series_alias):
        """시리즈 표시 별칭 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE books
                SET series_alias = ?,
                    metadata_locked = 1
                WHERE series_name = ?
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
        """단일 도서 표시 별칭 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE books
                SET title_alias = ?,
                    metadata_locked = 1
                WHERE id = ?
            """, (title_alias if title_alias else None, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

