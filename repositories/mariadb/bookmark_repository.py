# -*- coding: utf-8 -*-
"""
bookmark_repository.py – MariaDB 전용 EPUB/TXT 뷰어 북마크(현재 위치 표식) CRUD 데이터 액세스 레이어.
"""
import database

class BookmarkRepository:
    @staticmethod
    def create_bookmark(db_type, book_id, user_id, format, chapter_idx, percent=0, label=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO epub_bookmarks (book_id, user_id, format, chapter_idx, percent, label)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (book_id, user_id, format, chapter_idx, percent, label)
            )
            bookmark_id = cursor.lastrowid
            conn.commit()
            return bookmark_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_book_bookmarks(db_type, book_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT * FROM epub_bookmarks
                WHERE book_id = %s AND user_id = %s
                ORDER BY chapter_idx ASC, created_at ASC
                """,
                (book_id, user_id)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()

    @staticmethod
    def delete_bookmark(db_type, bookmark_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM epub_bookmarks WHERE id = %s AND user_id = %s", (bookmark_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
