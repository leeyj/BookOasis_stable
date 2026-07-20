# -*- coding: utf-8 -*-
"""
metadata_repository.py – 도서 상세 메타데이터 및 외부 매핑 데이터 액세스 레이어
"""
import database

class MetadataRepository:
    @staticmethod
    def get_book_metadata(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT author, publisher, score, summary, tags, genre, cover_image, is_favorite 
            FROM books WHERE id = ?
            """,
            (book_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_metadata(db_type, book_id, author, publisher, score, summary, tags, genre):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE books SET
                    author = ?, publisher = ?, score = ?, summary = ?, tags = ?, genre = ?,
                    metadata_locked = 1
                WHERE id = ?
                """,
                (author, publisher, score, summary, tags, genre, book_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_all_settings(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}

    @staticmethod
    def get_setting_value(db_type, key):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def get_meta_recommend(db_type, series_name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT MIN(id) AS id, series_name, author, publisher, summary, MAX(cover_image) AS cover_image
            FROM books
            WHERE series_name LIKE ? AND (summary IS NOT NULL AND summary != '' AND summary != '등록된 설명이 없습니다.')
            GROUP BY series_name
            LIMIT 3
            """,
            (f"%{series_name}%",)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def copy_metadata(db_type, target_series, target_lib_id, source_book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT author, isbn, publisher, summary, link, score
                FROM books WHERE id = ?
                """,
                (source_book_id,)
            )
            source = cursor.fetchone()
            if not source:
                return False, '원본 메타데이터를 찾을 수 없습니다.'

            cursor.execute(
                """
                UPDATE books
                SET author = ?, isbn = ?, publisher = ?, summary = ?, link = ?, score = ?, metadata_locked = 1
                WHERE series_name = ? AND library_id = ?
                """,
                (
                    source['author'],
                    source['isbn'],
                    source['publisher'],
                    source['summary'],
                    source['link'],
                    source['score'],
                    target_series,
                    target_lib_id
                )
            )
            conn.commit()
            return True, f'"{target_series}"에 추천 메타데이터가 정상 복사 및 적재되었습니다.'
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
