# -*- coding: utf-8 -*-
"""
kosync_repository.py (MariaDB) – KOReader 진행 동기화(kosync 호환 API) 저장소. general DB만 쓴다.
"""
import database

_DB = 'general'


class KosyncRepository:
    @staticmethod
    def get_credential(user_id):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key_hash FROM kosync_credentials WHERE user_id = %s", (int(user_id),))
            row = cursor.fetchone()
        return row['key_hash'] if row else None

    @staticmethod
    def set_credential(user_id, key_hash):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO kosync_credentials (user_id, key_hash, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                    "ON DUPLICATE KEY UPDATE key_hash = VALUES(key_hash), updated_at = CURRENT_TIMESTAMP",
                    (int(user_id), key_hash)
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def delete_credential(user_id):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM kosync_credentials WHERE user_id = %s", (int(user_id),))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def get_document(document):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT db_type, book_id FROM kosync_documents WHERE document = %s", (str(document),))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def save_document(document, db_type, book_id):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO kosync_documents (document, db_type, book_id) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE db_type = VALUES(db_type), book_id = VALUES(book_id)",
                    (str(document), str(db_type), int(book_id))
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def get_progress(user_id, document):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT document, progress, percentage, device, device_id, timestamp FROM kosync_progress "
                "WHERE user_id = %s AND document = %s",
                (int(user_id), str(document))
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def save_progress(user_id, document, progress, percentage, device, device_id, timestamp):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO kosync_progress (user_id, document, progress, percentage, device, device_id, timestamp) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE progress = VALUES(progress), percentage = VALUES(percentage), device = VALUES(device), device_id = VALUES(device_id), timestamp = VALUES(timestamp)",
                    (int(user_id), str(document), progress, percentage, device, device_id, int(timestamp))
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def get_latest_progress_for_book(user_id, db_type, book_id, exclude_document):
        """같은 책에 묶인 다른 문서(원본·최적화본·옛 프로필 등) 중 이 사용자의 가장 최근 기록 (없으면 None)."""
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT p.document, p.progress, p.percentage, p.device, p.device_id, p.timestamp "
                "FROM kosync_progress p JOIN kosync_documents d ON d.document = p.document "
                "WHERE p.user_id = %s AND d.db_type = %s AND d.book_id = %s AND p.document <> %s "
                "ORDER BY p.timestamp DESC LIMIT 1",
                (int(user_id), str(db_type), int(book_id), str(exclude_document))
            )
            row = cursor.fetchone()
        return dict(row) if row else None
