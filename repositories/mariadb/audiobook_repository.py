# -*- coding: utf-8 -*-
"""
audiobook_repository.py – MariaDB 전용 오디오북(audiobooks, audiobook_tracks, audiobook_progress) 데이터 액세스 레이어
"""
import os
import database

class AudiobookRepository:
    @staticmethod
    def _ensure_track_progress_table(conn):
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audiobook_track_progress (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                audiobook_id BIGINT NOT NULL,
                track_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL DEFAULT 1,
                `current_time` DOUBLE DEFAULT 0.0,
                progress_pct DOUBLE DEFAULT 0.0,
                is_completed INT DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_audiobook_track_user_progress (audiobook_id, track_id, user_id),
                INDEX idx_audiobook_track_progress_lookup (audiobook_id, user_id, track_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
        """)

    @staticmethod
    def get_audiobook_by_id(audiobook_id):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobooks WHERE id = %s AND COALESCE(is_deleted, 0) = 0",
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
            "SELECT * FROM audiobooks WHERE (title = %s OR folder_name = %s) AND COALESCE(is_deleted, 0) = 0",
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
    def update_favorite(audiobook_id, is_favorite):
        """오디오북 즐겨찾기 상태 갱신"""
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE audiobooks SET is_favorite = %s WHERE id = %s",
                (1 if is_favorite else 0, audiobook_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_all_authors_with_ids():
        """작가별 모음(정규화 매칭) 일괄 즐겨찾기를 위해 전체 오디오북의 id/author만 가져온다."""
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, author FROM audiobooks WHERE COALESCE(is_deleted, 0) = 0 AND COALESCE(author, '') != ''"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_favorites_bulk(audiobook_ids, is_favorite):
        """오디오북 id 목록에 대한 즐겨찾기 상태 일괄 갱신 (작가별 모음 카드 즐겨찾기용).
        audiobooks.is_favorite은 사용자별이 아니라 엔티티 단일 컬럼이라 user_id가 필요 없다."""
        if not audiobook_ids:
            return True
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            placeholders = ','.join('%s' for _ in audiobook_ids)
            cursor.execute(
                f"UPDATE audiobooks SET is_favorite = %s WHERE id IN ({placeholders})",
                [1 if is_favorite else 0] + list(audiobook_ids)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_audiobook_progress(audiobook_id, user_id):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobook_progress WHERE audiobook_id = %s AND user_id = %s",
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
            "SELECT * FROM audiobook_tracks WHERE audiobook_id = %s ORDER BY track_number ASC",
            (audiobook_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_audiobook_track_progress(audiobook_id, user_id):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            AudiobookRepository._ensure_track_progress_table(conn)
            cursor.execute("""
                SELECT track_id, `current_time`, progress_pct, is_completed
                FROM audiobook_track_progress
                WHERE audiobook_id = %s AND user_id = %s
            """, (audiobook_id, user_id))
            return {int(row['track_id']): dict(row) for row in cursor.fetchall()}
        except Exception:
            return {}
        finally:
            conn.close()

    @staticmethod
    def update_media_detail(series_name, author, web_id, publisher, summary, cover_image_url=None):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            if cover_image_url:
                cursor.execute(
                    """
                    UPDATE audiobooks
                    SET author = %s,
                        web_id = %s,
                        publisher = %s,
                        description = %s,
                        cover_image = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE title = %s OR folder_name = %s
                    """,
                    (author, web_id, publisher, summary, cover_image_url, series_name, series_name)
                )
            else:
                cursor.execute(
                    """
                    UPDATE audiobooks
                    SET author = %s,
                        web_id = %s,
                        publisher = %s,
                        description = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE title = %s OR folder_name = %s
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
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audiobook_tracks WHERE id = %s AND audiobook_id = %s",
            (track_id, audiobook_id)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def save_audiobook_progress(audiobook_id, user_id, current_track_id, current_time, total_pct, playback_rate, is_completed):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                REPLACE INTO audiobook_progress (
                    audiobook_id, user_id, current_track_id, `current_time`, total_progress_pct, playback_rate, is_completed, last_listened_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (audiobook_id, user_id, current_track_id, current_time, total_pct, playback_rate, is_completed))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def save_audiobook_track_progress(audiobook_id, user_id, track_id, current_time, progress_pct, is_completed):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            AudiobookRepository._ensure_track_progress_table(conn)
            cursor.execute("""
                REPLACE INTO audiobook_track_progress (
                    audiobook_id, track_id, user_id, `current_time`, progress_pct, is_completed, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (audiobook_id, track_id, user_id, current_time, progress_pct, is_completed))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def mark_audiobook_tracks_completed(audiobook_id, user_id, tracks):
        if not tracks:
            return 0
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            AudiobookRepository._ensure_track_progress_table(conn)
            values = [
                (audiobook_id, int(track['id']), user_id, float(track.get('duration') or 0.0), 100.0, 1)
                for track in tracks
            ]
            cursor.executemany("""
                REPLACE INTO audiobook_track_progress (
                    audiobook_id, track_id, user_id, `current_time`, progress_pct, is_completed, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, values)
            conn.commit()
            return len(values)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_folder_paths(library_id=None):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        if library_id is not None:
            cursor.execute("SELECT folder_path FROM audiobooks WHERE library_id = %s", (library_id,))
        else:
            cursor.execute("SELECT folder_path FROM audiobooks")
        rows = cursor.fetchall()
        conn.close()
        return [r['folder_path'] for r in rows if r and r['folder_path']]

    @staticmethod
    def _has_file_mtime_column(cursor):
        try:
            cursor.execute("SHOW COLUMNS FROM audiobook_tracks LIKE 'file_mtime'")
            return cursor.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def save_audiobook_scan(folder_path, library_id, meta, tracks):
        """오디오북 폴더 스캔 결과(메타 + 트랙 목록)를 신규/변경분만 DB에 반영.

        Returns dict: {audiobook_id, is_new, meta_updated, track_inserts, track_updates, track_deletes}
        """
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        try:
            has_file_mtime_col = AudiobookRepository._has_file_mtime_column(cursor)

            cursor.execute(
                """
                SELECT id, library_id, title, web_id, author, publisher, code, poster,
                       premiered, ratings, author_intro, description,
                       folder_name, total_duration, total_tracks, file_type
                FROM audiobooks
                WHERE folder_path = %s
                """,
                (folder_path,)
            )
            row = cursor.fetchone()

            existing_tracks_full = {}
            if row:
                audiobook_id = row['id']
                track_select_sql = (
                    "SELECT id, track_number, track_code, filename, file_path, file_mtime, file_size, duration, format "
                    "FROM audiobook_tracks WHERE audiobook_id = %s"
                    if has_file_mtime_col else
                    "SELECT id, track_number, track_code, filename, file_path, 0.0 AS file_mtime, file_size, duration, format "
                    "FROM audiobook_tracks WHERE audiobook_id = %s"
                )
                cursor.execute(track_select_sql, (audiobook_id,))
                for r in cursor.fetchall():
                    if not r or not r['file_path']:
                        continue
                    key = os.path.normpath(str(r['file_path']))
                    existing_tracks_full[key] = {
                        'id': int(r['id']),
                        'track_number': int(r['track_number'] or 0),
                        'track_code': str(r['track_code'] or ''),
                        'filename': str(r['filename'] or ''),
                        'file_path': key,
                        'file_mtime': float(r['file_mtime'] or 0.0),
                        'file_size': int(r['file_size'] or 0),
                        'duration': float(r['duration'] or 0.0),
                        'format': str(r['format'] or '')
                    }

            meta_updated = 0
            is_new = not row
            if row:
                audiobook_id = row['id']
                existing_meta = (
                    row['library_id'], row['title'], row['web_id'], row['author'], row['publisher'],
                    row['code'], row['poster'], row['premiered'], float(row['ratings'] or 0.0),
                    row['author_intro'], row['description'], row['folder_name'],
                    float(row['total_duration'] or 0.0), int(row['total_tracks'] or 0), row['file_type']
                )
                incoming_meta = (
                    library_id, meta['title'], meta['web_id'], meta['author'], meta['publisher'],
                    meta['code'], meta['poster'], meta['premiered'], float(meta['ratings'] or 0.0),
                    meta['author_intro'], meta['description'], meta['folder_name'],
                    float(meta['total_duration'] or 0.0), int(meta['total_tracks'] or 0), meta['file_type']
                )
                if existing_meta != incoming_meta:
                    cursor.execute("""
                        UPDATE audiobooks SET
                            library_id = %s,
                            title = %s,
                            web_id = %s,
                            author = %s,
                            publisher = %s,
                            code = %s,
                            poster = %s,
                            premiered = %s,
                            ratings = %s,
                            author_intro = %s,
                            description = %s,
                            folder_name = %s,
                            total_duration = %s,
                            total_tracks = %s,
                            file_type = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        library_id, meta['title'], meta['web_id'], meta['author'], meta['publisher'],
                        meta['code'], meta['poster'], meta['premiered'], meta['ratings'],
                        meta['author_intro'], meta['description'], meta['folder_name'],
                        meta['total_duration'], meta['total_tracks'], meta['file_type'],
                        audiobook_id
                    ))
                    meta_updated = 1
            else:
                cursor.execute("""
                    INSERT INTO audiobooks (
                        library_id, title, web_id, author, publisher, code, poster,
                        premiered, ratings, author_intro, description,
                        folder_name, folder_path, total_duration, total_tracks, file_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    library_id, meta['title'], meta['web_id'], meta['author'], meta['publisher'],
                    meta['code'], meta['poster'], meta['premiered'], meta['ratings'],
                    meta['author_intro'], meta['description'], meta['folder_name'],
                    meta['folder_path'], meta['total_duration'], meta['total_tracks'],
                    meta['file_type']
                ))
                audiobook_id = cursor.lastrowid
                meta_updated = 1

            track_inserts = 0
            track_updates = 0
            track_deletes = 0
            incoming_paths = set()
            for t in tracks:
                norm_path = os.path.normpath(str(t['file_path']))
                incoming_paths.add(norm_path)
                existing = existing_tracks_full.get(norm_path)
                if not existing:
                    if has_file_mtime_col:
                        cursor.execute("""
                            INSERT INTO audiobook_tracks (
                                audiobook_id, track_number, track_code, filename, file_path, file_mtime, file_size, duration, format
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            audiobook_id, t['track_number'], t['track_code'], t['filename'],
                            norm_path, t['file_mtime'], t['file_size'], t['duration'], t['format']
                        ))
                    else:
                        cursor.execute("""
                            INSERT INTO audiobook_tracks (
                                audiobook_id, track_number, track_code, filename, file_path, file_size, duration, format
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            audiobook_id, t['track_number'], t['track_code'], t['filename'],
                            norm_path, t['file_size'], t['duration'], t['format']
                        ))
                    track_inserts += 1
                    continue

                changed = (
                    existing['track_number'] != int(t['track_number']) or
                    existing['track_code'] != str(t['track_code'] or '') or
                    existing['filename'] != str(t['filename'] or '') or
                    int(float(existing['file_mtime'] or 0.0)) != int(float(t['file_mtime'] or 0.0)) or
                    existing['file_size'] != int(t['file_size'] or 0) or
                    abs(existing['duration'] - float(t['duration'] or 0.0)) > 0.0001 or
                    existing['format'] != str(t['format'] or '')
                )
                if changed:
                    if has_file_mtime_col:
                        cursor.execute("""
                            UPDATE audiobook_tracks SET
                                track_number = %s,
                                track_code = %s,
                                filename = %s,
                                file_mtime = %s,
                                file_size = %s,
                                duration = %s,
                                format = %s
                            WHERE id = %s
                        """, (
                            t['track_number'], t['track_code'], t['filename'],
                            t['file_mtime'],
                            t['file_size'], t['duration'], t['format'],
                            existing['id']
                        ))
                    else:
                        cursor.execute("""
                            UPDATE audiobook_tracks SET
                                track_number = %s,
                                track_code = %s,
                                filename = %s,
                                file_size = %s,
                                duration = %s,
                                format = %s
                            WHERE id = %s
                        """, (
                            t['track_number'], t['track_code'], t['filename'],
                            t['file_size'], t['duration'], t['format'],
                            existing['id']
                        ))
                    track_updates += 1

            removed_paths = set(existing_tracks_full.keys()) - incoming_paths
            for p in removed_paths:
                cursor.execute("DELETE FROM audiobook_tracks WHERE id = %s", (existing_tracks_full[p]['id'],))
                track_deletes += 1

            conn.commit()
            return {
                'audiobook_id': audiobook_id,
                'is_new': is_new,
                'meta_updated': meta_updated,
                'track_inserts': track_inserts,
                'track_updates': track_updates,
                'track_deletes': track_deletes,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_by_folder_path(folder_path):
        conn = database.get_connection('audiobook')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, library_id, title, web_id, author, publisher, code, poster,
                   premiered, ratings, author_intro, description,
                   folder_name, total_duration, total_tracks, file_type
            FROM audiobooks
            WHERE folder_path = %s
            """,
            (folder_path,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
