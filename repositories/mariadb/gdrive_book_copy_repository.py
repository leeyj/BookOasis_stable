# -*- coding: utf-8 -*-
"""
gdrive_book_copy_repository.py – gdrive 공유 카테고리 뷰어용 책 단위 사전복사 매핑
(source Drive file_id -> 로컬 rclone 마운트 경로) 데이터 액세스 레이어 (MariaDB)
"""
import database


class GdriveBookCopyRepository:
    @staticmethod
    def get_by_book_id(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT book_id, library_id, source_file_id, status, local_path, error_message
            FROM gdrive_book_copies
            WHERE book_id = %s
            """,
            (book_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def upsert_copied(db_type, book_id, library_id, source_file_id, local_path):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO gdrive_book_copies (book_id, library_id, source_file_id, status, local_path, error_message)
            VALUES (%s, %s, %s, 'copied', %s, NULL)
            ON DUPLICATE KEY UPDATE
                library_id = VALUES(library_id),
                source_file_id = VALUES(source_file_id),
                status = 'copied',
                local_path = VALUES(local_path),
                error_message = NULL
            """,
            (book_id, library_id, source_file_id, local_path),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_stale_copied(db_type, older_than_hours):
        """지정 시간(older_than_hours)보다 오래된 'copied' 상태 레코드를 모두 조회.
        하루 지난 뷰캐시 사본 정리(TTL cleanup)에 사용."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT book_id, library_id, local_path
            FROM gdrive_book_copies
            WHERE status = 'copied'
              AND updated_at <= DATE_SUB(NOW(), INTERVAL %s HOUR)
            """,
            (older_than_hours,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def delete_by_book_id(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gdrive_book_copies WHERE book_id = %s", (book_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def upsert_unsupported(db_type, book_id, library_id, source_file_id, error_message):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO gdrive_book_copies (book_id, library_id, source_file_id, status, local_path, error_message)
            VALUES (%s, %s, %s, 'unsupported', NULL, %s)
            ON DUPLICATE KEY UPDATE
                library_id = VALUES(library_id),
                source_file_id = VALUES(source_file_id),
                status = 'unsupported',
                local_path = NULL,
                error_message = VALUES(error_message)
            """,
            (book_id, library_id, source_file_id, error_message),
        )
        conn.commit()
        conn.close()
