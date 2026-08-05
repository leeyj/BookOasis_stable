# -*- coding: utf-8 -*-
"""
audiobook_repository.py – 오디오북(audiobooks, audiobook_tracks, audiobook_progress) 조회/수정 데이터 액세스 레이어
"""
import database


class AudiobookRepository:
    @staticmethod
    def get_audiobook_by_id(audiobook_id):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobooks WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (int(audiobook_id),)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_audiobook_by_series_or_folder_name(series_name):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobooks WHERE (title = ? OR folder_name = ?) AND COALESCE(is_deleted, 0) = 0",
            (series_name, series_name)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_first_audiobook():
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobooks WHERE COALESCE(is_deleted, 0) = 0 ORDER BY id ASC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_audiobook_progress(audiobook_id, user_id):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobook_progress WHERE audiobook_id = ? AND user_id = ?",
            (audiobook_id, user_id)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_audiobook_tracks(audiobook_id):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobook_tracks WHERE audiobook_id = ? ORDER BY track_number ASC",
            (audiobook_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_media_detail(series_name, author, web_id, publisher, summary, cover_image_url=None):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            if cover_image_url:
                cursor.execute(
                    """
                    UPDATE audiobooks
                    SET author = ?,
                        web_id = ?,
                        publisher = ?,
                        description = ?,
                        cover_image = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE title = ? OR folder_name = ?
                    """,
                    (author, web_id, publisher, summary, cover_image_url, series_name, series_name)
                )
            else:
                cursor.execute(
                    """
                    UPDATE audiobooks
                    SET author = ?,
                        web_id = ?,
                        publisher = ?,
                        description = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE title = ? OR folder_name = ?
                    """,
                    (author, web_id, publisher, summary, series_name, series_name)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()