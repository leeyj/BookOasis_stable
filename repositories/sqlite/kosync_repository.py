# -*- coding: utf-8 -*-
"""
kosync_repository.py (SQLite) – KOReader 진행 동기화(kosync 호환 API) 저장소. general DB만 쓴다.
"""
import database

_DB = 'general'


class KosyncRepository:
    @staticmethod
    def get_credential(user_id):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key_hash FROM kosync_credentials WHERE user_id = ?", (int(user_id),))
            row = cursor.fetchone()
        return row['key_hash'] if row else None

    @staticmethod
    def set_credential(user_id, key_hash):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO kosync_credentials (user_id, key_hash, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(user_id) DO UPDATE SET key_hash = excluded.key_hash, updated_at = CURRENT_TIMESTAMP",
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
                cursor.execute("DELETE FROM kosync_credentials WHERE user_id = ?", (int(user_id),))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def get_document(document):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT db_type, book_id FROM kosync_documents WHERE document = ?", (str(document),))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def save_document(document, db_type, book_id):
        with database.connection(_DB) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO kosync_documents (document, db_type, book_id) VALUES (?, ?, ?) ON CONFLICT(document) DO UPDATE SET db_type = excluded.db_type, book_id = excluded.book_id",
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
                "WHERE user_id = ? AND document = ?",
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
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, document) DO UPDATE SET progress = excluded.progress, percentage = excluded.percentage, device = excluded.device, device_id = excluded.device_id, timestamp = excluded.timestamp",
                    (int(user_id), str(document), progress, percentage, device, device_id, int(timestamp))
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
