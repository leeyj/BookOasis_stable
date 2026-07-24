# -*- coding: utf-8 -*-
"""
reading_progress_repository.py – 독서 진행률(user_progress) 및 활동 로그(user_reading_log) 조회/업데이트 데이터 액세스 레이어
"""
import database

class ReadingProgressRepository:
    @staticmethod
    def get_book_for_progress(db_type, book_id):
        """진행률 기록에 필요한 도서 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_format, total_pages, title, author, publisher, series_name, created_at
            FROM books WHERE id = ?
            """,
            (book_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_total_pages(db_type, book_id, total_pages):
        """도서의 총 페이지 수 수정"""
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
    def get_progress_only(db_type, book_id, user_id):
        """특정 사용자의 도서 읽기 진행률만 단순 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pages_read, is_completed FROM user_progress WHERE book_id = ? AND user_id = ?",
            (book_id, user_id),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_progress_state(db_type, book_id, user_id):
        """특정 사용자의 도서 진행 상태 상세 조회 (책 포맷 정보 결합)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                b.file_format,
                b.total_pages,
                p.pages_read,
                p.last_read_at,
                p.last_epub_cfi,
                p.last_epub_href,
                p.last_epub_spine_index,
                p.last_epub_percent,
                p.last_epub_fingerprint,
                p.last_epub_updated_at
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE b.id = ?
            """,
            (user_id, book_id),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def insert_empty_progress(db_type, book_id, user_id, now_str):
        """최초 독서 시 빈 진행률 레코드 생성"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_progress (
                    book_id, user_id, pages_read, is_completed, last_read_at,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (book_id, user_id, 0, 0, now_str, None, None, None, 0, None, None),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_progress_full(db_type, book_id, user_id, pages_read, is_completed, now_str,
                             last_epub_cfi, last_epub_href, last_epub_spine_index,
                             last_epub_percent, last_epub_fingerprint, last_epub_updated_at):
        """EPUB 등 상세 포인터 데이터를 포함한 진행률 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE user_progress
                SET pages_read=?, is_completed=?, last_read_at=?,
                    last_epub_cfi=?, last_epub_href=?, last_epub_spine_index=?,
                    last_epub_percent=?, last_epub_fingerprint=?, last_epub_updated_at=?
                WHERE book_id=? AND user_id=?
                """,
                (
                    pages_read,
                    is_completed,
                    now_str,
                    last_epub_cfi,
                    last_epub_href,
                    last_epub_spine_index,
                    last_epub_percent,
                    last_epub_fingerprint,
                    last_epub_updated_at,
                    book_id,
                    user_id,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_progress_simple(db_type, book_id, user_id, pages_read, is_completed, now_str):
        """일반 도서 포맷의 단순 진행률 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE user_progress SET pages_read=?, is_completed=?, last_read_at=? WHERE book_id=? AND user_id=?",
                (pages_read, is_completed, now_str, book_id, user_id),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_or_insert_reading_log(db_type, book_id, user_id, delta, today_str):
        """일일 활동 로그 누적 기록 반영"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM user_reading_log WHERE book_id=? AND user_id=? AND read_date=?",
                (book_id, user_id, today_str),
            )
            log_row = cursor.fetchone()
            if log_row:
                cursor.execute(
                    "UPDATE user_reading_log SET pages_read_delta=pages_read_delta+? WHERE id=?",
                    (delta, log_row['id']),
                )
            else:
                cursor.execute(
                    "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?,?,?,60,?)",
                    (book_id, user_id, delta, today_str),
                )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_username_by_id(db_type, user_id):
        """특정 사용자의 사용자명 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['username'] if row else None

    @staticmethod
    def get_settings_value(db_type, key):
        """설정 테이블에서 특정 설정 키 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def fetch_reading_history(db_type, user_id, limit, hide_completed):
        """특정 사용자의 독서 진척 이력 조회 (완독 숨김 옵션 결합)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        base_select = """
            SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format,
                   p.pages_read, b.total_pages, p.last_read_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                   p.is_completed, COALESCE(b.metadata_locked, 0) AS metadata_locked
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = p.user_id
            WHERE COALESCE(b.is_deleted, 0) = 0 AND p.user_id = ?
        """
        if hide_completed:
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
        return [dict(row) for row in rows]

    @staticmethod
    def fetch_recently_added_by_user(db_type, user_id):
        """일반 유저 권한 카테고리에 한해 최근 추가된 도서 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite, COALESCE(b.metadata_locked, 0) AS metadata_locked
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
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def fetch_recently_added_all(db_type, user_id):
        """어드민 등 제한 없이 최근 추가된 도서 목록 전체 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.library_id, b.title, b.series_name, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite, COALESCE(b.metadata_locked, 0) AS metadata_locked
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
        return [dict(row) for row in rows]

    @staticmethod
    def delete_user_progress_by_book(db_type, book_id, user_id):
        """특정 도서의 독서 진척도 및 일일 로그 삭제"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, user_id))
            cursor.execute("DELETE FROM user_reading_log WHERE book_id = ? AND user_id = ?", (book_id, user_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
