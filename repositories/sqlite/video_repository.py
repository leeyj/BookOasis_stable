# -*- coding: utf-8 -*-
"""
video_repository.py – 영상 강좌(videos, video_episodes, video_progress, video_episode_progress) 조회/수정 데이터 액세스 레이어
"""
import os
import database


class VideoRepository:
    @staticmethod
    def get_video_by_id(video_id):
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM videos WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (int(video_id),)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_favorite(video_id, is_favorite):
        """강좌 즐겨찾기 상태 갱신"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE videos SET is_favorite = ? WHERE id = ?",
                (1 if is_favorite else 0, video_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_video_episodes(video_id):
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM video_episodes WHERE video_id = ? ORDER BY episode_number ASC",
            (video_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_episode_by_id_and_video_id(episode_id, video_id):
        """특정 에피소드 ID 및 강좌 ID 매칭 조회"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM video_episodes WHERE id = ? AND video_id = ?",
            (episode_id, video_id)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_episode_probe_result(episode_id, video_id, duration, width, height, needs_transcode):
        """
        재생 시점(JIT)에 즉석으로 ffprobe한 결과를 반영한다. Lazy 백필이 아직 처리하지 않은
        (duration=0) 에피소드를 첫 재생 요청 때 바로 분석해서, "분석 전" 상태로 원본을 그대로
        내보내다 EAC3 등 브라우저 비호환 오디오가 무음이 되는 사고를 막기 위함.
        같은 강좌의 total_duration도 함께 재계산한다.
        """
        conn = database.get_connection('video')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE video_episodes SET duration = ?, width = ?, height = ?, needs_transcode = ? WHERE id = ?",
                (duration, width, height, needs_transcode, episode_id)
            )
            cursor.execute(
                "UPDATE videos SET total_duration = (SELECT COALESCE(SUM(duration), 0) FROM video_episodes WHERE video_id = ?) WHERE id = ?",
                (video_id, video_id)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_video_by_title_or_folder_name(name):
        """제목 또는 폴더명으로 강좌 조회 (series_name 폴백용)"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM videos WHERE (title = ? OR folder_name = ?) AND COALESCE(is_deleted, 0) = 0",
            (name, name)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_video_episode_progress_map(video_id, user_id):
        """강좌의 에피소드별 진행률을 episode_id -> row 딕셔너리로 한 번에 조회"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT episode_id, current_time, progress_pct, is_completed
                FROM video_episode_progress
                WHERE video_id = ? AND user_id = ?
            """, (video_id, user_id))
            return {int(row['episode_id']): dict(row) for row in cursor.fetchall()}
        except Exception:
            return {}
        finally:
            conn.close()

    @staticmethod
    def list_videos_by_library(library_id):
        """특정 라이브러리에 속한 강좌 카드 목록 조회 (제목순 정렬)"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, poster, total_episodes, total_duration, COALESCE(is_favorite, 0) AS is_favorite
            FROM videos
            WHERE library_id = ? AND COALESCE(is_deleted, 0) = 0
            ORDER BY title ASC
            """,
            (library_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_video_progress(video_id, user_id):
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM video_progress WHERE video_id = ? AND user_id = ?",
            (video_id, user_id)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def save_video_progress(video_id, user_id, current_episode_id, current_time, total_pct, playback_rate, is_completed):
        """강좌 재생 진행률 업서트"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO video_progress (
                    video_id, user_id, current_episode_id, current_time, total_progress_pct, playback_rate, is_completed, last_watched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (video_id, user_id, current_episode_id, current_time, total_pct, playback_rate, is_completed))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def save_video_episode_progress(video_id, user_id, episode_id, current_time, progress_pct, is_completed):
        conn = database.get_connection('video')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO video_episode_progress (
                    video_id, episode_id, user_id, current_time, progress_pct, is_completed, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (video_id, episode_id, user_id, current_time, progress_pct, is_completed))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_folder_paths(library_id=None):
        """저장된 강좌 폴더 경로 목록 조회"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        if library_id is not None:
            cursor.execute("SELECT folder_path FROM videos WHERE library_id = ?", (library_id,))
        else:
            cursor.execute("SELECT folder_path FROM videos")
        rows = cursor.fetchall()
        conn.close()
        return [r['folder_path'] for r in rows if r and r['folder_path']]

    @staticmethod
    def get_by_folder_path(folder_path):
        """폴더 경로 기반 강좌 상세 메타 조회"""
        conn = database.get_connection('video')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, library_id, title, sort_title, web_id, genres, poster, backdrop,
                   premiered, description, folder_name, total_duration, total_episodes
            FROM videos
            WHERE folder_path = ?
            """,
            (folder_path,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def save_video_scan(folder_path, library_id, meta, episodes):
        """강좌 폴더 스캔 결과(메타 + 에피소드 목록)를 신규/변경분만 DB에 반영.

        Returns dict: {video_id, is_new, meta_updated, episode_inserts, episode_updates, episode_deletes}
        """
        conn = database.get_connection('video')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, library_id, title, sort_title, web_id, genres, poster, backdrop,
                       premiered, description, folder_name, total_duration, total_episodes
                FROM videos
                WHERE folder_path = ?
                """,
                (folder_path,)
            )
            row = cursor.fetchone()

            existing_episodes_full = {}
            if row:
                video_id = row['id']
                cursor.execute(
                    "SELECT id, episode_number, episode_code, title, filename, file_path, "
                    "file_mtime, file_size, duration, width, height, premiered, format, subtitle_path "
                    "FROM video_episodes WHERE video_id = ?",
                    (video_id,)
                )
                for r in cursor.fetchall():
                    if not r or not r['file_path']:
                        continue
                    key = os.path.normpath(str(r['file_path']))
                    existing_episodes_full[key] = {
                        'id': int(r['id']),
                        'episode_number': int(r['episode_number'] or 0),
                        'episode_code': str(r['episode_code'] or ''),
                        'title': str(r['title'] or ''),
                        'filename': str(r['filename'] or ''),
                        'file_path': key,
                        'file_mtime': float(r['file_mtime'] or 0.0),
                        'file_size': int(r['file_size'] or 0),
                        'duration': float(r['duration'] or 0.0),
                        'width': int(r['width'] or 0),
                        'height': int(r['height'] or 0),
                        'premiered': str(r['premiered'] or ''),
                        'format': str(r['format'] or ''),
                        'subtitle_path': str(r['subtitle_path'] or ''),
                    }

            meta_updated = 0
            is_new = not row
            if row:
                video_id = row['id']
                existing_meta = (
                    row['library_id'], row['title'], row['sort_title'], row['web_id'], row['genres'],
                    row['poster'], row['backdrop'], row['premiered'], row['description'], row['folder_name'],
                    float(row['total_duration'] or 0.0), int(row['total_episodes'] or 0)
                )
                incoming_meta = (
                    library_id, meta['title'], meta['sort_title'], meta['web_id'], meta['genres'],
                    meta['poster'], meta['backdrop'], meta['premiered'], meta['description'], meta['folder_name'],
                    float(meta['total_duration'] or 0.0), int(meta['total_episodes'] or 0)
                )
                if existing_meta != incoming_meta:
                    cursor.execute("""
                        UPDATE videos SET
                            library_id = ?,
                            title = ?,
                            sort_title = ?,
                            web_id = ?,
                            genres = ?,
                            poster = ?,
                            backdrop = ?,
                            premiered = ?,
                            description = ?,
                            folder_name = ?,
                            total_duration = ?,
                            total_episodes = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        library_id, meta['title'], meta['sort_title'], meta['web_id'], meta['genres'],
                        meta['poster'], meta['backdrop'], meta['premiered'], meta['description'], meta['folder_name'],
                        meta['total_duration'], meta['total_episodes'],
                        video_id
                    ))
                    meta_updated = 1
            else:
                cursor.execute("""
                    INSERT INTO videos (
                        library_id, title, sort_title, web_id, genres, poster, backdrop,
                        premiered, description, folder_name, folder_path, total_duration, total_episodes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    library_id, meta['title'], meta['sort_title'], meta['web_id'], meta['genres'],
                    meta['poster'], meta['backdrop'], meta['premiered'], meta['description'],
                    meta['folder_name'], meta['folder_path'], meta['total_duration'], meta['total_episodes']
                ))
                video_id = cursor.lastrowid
                meta_updated = 1

            episode_inserts = 0
            episode_updates = 0
            episode_deletes = 0
            incoming_paths = set()
            for ep in episodes:
                norm_path = os.path.normpath(str(ep['file_path']))
                incoming_paths.add(norm_path)
                existing = existing_episodes_full.get(norm_path)
                if not existing:
                    cursor.execute("""
                        INSERT INTO video_episodes (
                            video_id, episode_number, episode_code, title, filename, file_path,
                            file_mtime, file_size, duration, width, height, premiered, format, subtitle_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        video_id, ep['episode_number'], ep['episode_code'], ep['title'], ep['filename'],
                        norm_path, ep['file_mtime'], ep['file_size'], ep['duration'],
                        ep['width'], ep['height'], ep['premiered'], ep['format'], ep.get('subtitle_path', '')
                    ))
                    episode_inserts += 1
                    continue

                changed = (
                    existing['episode_number'] != int(ep['episode_number']) or
                    existing['episode_code'] != str(ep['episode_code'] or '') or
                    existing['title'] != str(ep['title'] or '') or
                    existing['filename'] != str(ep['filename'] or '') or
                    int(float(existing['file_mtime'] or 0.0)) != int(float(ep['file_mtime'] or 0.0)) or
                    existing['file_size'] != int(ep['file_size'] or 0) or
                    abs(existing['duration'] - float(ep['duration'] or 0.0)) > 0.0001 or
                    existing['width'] != int(ep['width'] or 0) or
                    existing['height'] != int(ep['height'] or 0) or
                    existing['premiered'] != str(ep['premiered'] or '') or
                    existing['format'] != str(ep['format'] or '') or
                    existing['subtitle_path'] != str(ep.get('subtitle_path') or '')
                )
                if changed:
                    cursor.execute("""
                        UPDATE video_episodes SET
                            episode_number = ?,
                            episode_code = ?,
                            title = ?,
                            filename = ?,
                            file_mtime = ?,
                            file_size = ?,
                            duration = ?,
                            width = ?,
                            height = ?,
                            premiered = ?,
                            format = ?,
                            subtitle_path = ?
                        WHERE id = ?
                    """, (
                        ep['episode_number'], ep['episode_code'], ep['title'], ep['filename'],
                        ep['file_mtime'], ep['file_size'], ep['duration'],
                        ep['width'], ep['height'], ep['premiered'], ep['format'], ep.get('subtitle_path', ''),
                        existing['id']
                    ))
                    episode_updates += 1

            removed_paths = set(existing_episodes_full.keys()) - incoming_paths
            for p in removed_paths:
                cursor.execute("DELETE FROM video_episodes WHERE id = ?", (existing_episodes_full[p]['id'],))
                episode_deletes += 1

            conn.commit()
            return {
                'video_id': video_id,
                'is_new': is_new,
                'meta_updated': meta_updated,
                'episode_inserts': episode_inserts,
                'episode_updates': episode_updates,
                'episode_deletes': episode_deletes,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
