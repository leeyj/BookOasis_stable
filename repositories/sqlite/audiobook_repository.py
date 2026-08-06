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

    @staticmethod
    def get_track_by_id_and_audiobook_id(track_id, audiobook_id):
        """특정 트랙 ID 및 오디오북 ID 매칭 조회"""
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobook_tracks WHERE id = ? AND audiobook_id = ?",
            (track_id, audiobook_id)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def save_audiobook_progress(audiobook_id, user_id, current_track_id, current_time, total_pct, playback_rate, is_completed):
        """오디오북 재생 진행률 업서트
        - SQLite: INSERT OR REPLACE (database._convert_sql 미적용)
        - MariaDB: _convert_sql이 INSERT OR REPLACE → REPLACE INTO, current_time → `current_time` 자동 변환
        """
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO audiobook_progress (
                    audiobook_id, user_id, current_track_id, current_time, total_progress_pct, playback_rate, is_completed, last_listened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (audiobook_id, user_id, current_track_id, current_time, total_pct, playback_rate, is_completed))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


    @staticmethod
    def get_folder_paths(library_id=None):
        """저장된 오디오북 폴더 경로 목록 조회"""
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        if library_id is not None:
            cursor.execute("SELECT folder_path FROM audiobooks WHERE library_id = ?", (library_id,))
        else:
            cursor.execute("SELECT folder_path FROM audiobooks")
        rows = cursor.fetchall()
        conn.close()
        return [r['folder_path'] for r in rows if r and r['folder_path']]

    @staticmethod
    def get_by_folder_path(folder_path):
        """폴더 경로 기반 오디오북 상세 메타 조회"""
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, library_id, title, web_id, author, publisher, code, poster,
                   premiered, ratings, author_intro, description,
                   folder_name, total_duration, total_tracks, file_type
            FROM audiobooks
            WHERE folder_path = ?
            """,
            (folder_path,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None