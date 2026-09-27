# -*- coding: utf-8 -*-
"""
tts_pregen_repository.py – MariaDB 전용 듣기(TTS) 서버 미리 만들기 데이터 액세스 레이어

tts_pregen_jobs: 책 단위 작업 큐 (queued → running → done/failed/cancelled).
tts_audio_cache: 조각 음성 캐시 색인. 키는 합성 입력 전체의 sha256이라 책·작업과 무관하게 공유된다.
시각은 DB 시간대 차이가 없는 epoch ms.
"""
import database

ACTIVE_STATUSES = ('queued', 'running')


class TTSPregenRepository:
    # ---- 작업 ----
    @staticmethod
    def create_job(db_type, book_id, user_id, voice, steps, speed, total_pieces, now_ms):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tts_pregen_jobs (book_id, user_id, voice, steps, speed, status, total_pieces, done_pieces, created_ms) "
                "VALUES (%s, %s, %s, %s, %s, 'queued', %s, 0, %s)",
                (book_id, user_id, voice, steps, speed, total_pieces, now_ms),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_job(db_type, job_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def find_active_job(db_type, book_id, voice, steps, speed):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tts_pregen_jobs WHERE book_id = %s AND voice = %s AND steps = %s AND ABS(speed - %s) < 0.001 "
                "AND status IN ('queued', 'running') ORDER BY id DESC LIMIT 1",
                (book_id, voice, steps, speed),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def latest_job(db_type, book_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE book_id = %s ORDER BY id DESC LIMIT 1", (book_id,))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def count_active_by_user(db_type, user_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM tts_pregen_jobs WHERE user_id = %s AND status IN ('queued', 'running')",
                (user_id,),
            )
            row = cursor.fetchone()
        return int(row['cnt'] if row else 0)

    @staticmethod
    def claim_next(db_type, now_ms, stale_before_ms):
        """가장 오래된 queued 작업(또는 heartbeat가 끊긴 running 작업)을 running으로 가져온다.
        조건부 UPDATE라 두 프로세스가 동시에 가져가도 한쪽만 성공한다."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM tts_pregen_jobs WHERE status = 'queued' "
                "OR (status = 'running' AND (heartbeat_ms IS NULL OR heartbeat_ms < %s)) ORDER BY id LIMIT 1",
                (stale_before_ms,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            job_id = row['id']
            cursor.execute(
                "UPDATE tts_pregen_jobs SET status = 'running', heartbeat_ms = %s WHERE id = %s "
                "AND (status = 'queued' OR (status = 'running' AND (heartbeat_ms IS NULL OR heartbeat_ms < %s)))",
                (now_ms, job_id, stale_before_ms),
            )
            conn.commit()
            if cursor.rowcount != 1:
                return None
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE id = %s", (job_id,))
            claimed = cursor.fetchone()
            return dict(claimed) if claimed else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def update_progress(db_type, job_id, done_pieces, now_ms):
        """진행률과 heartbeat 갱신. 그 사이 취소됐으면 False (running이 아니면 갱신하지 않는다)."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE tts_pregen_jobs SET done_pieces = %s, heartbeat_ms = %s WHERE id = %s AND status = 'running'",
                (done_pieces, now_ms, job_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def finish(db_type, job_id, status, now_ms, error=None, done_pieces=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if done_pieces is None:
                cursor.execute(
                    "UPDATE tts_pregen_jobs SET status = %s, error = %s, finished_ms = %s WHERE id = %s AND status = 'running'",
                    (status, error, now_ms, job_id),
                )
            else:
                cursor.execute(
                    "UPDATE tts_pregen_jobs SET status = %s, error = %s, finished_ms = %s, done_pieces = %s WHERE id = %s AND status = 'running'",
                    (status, error, now_ms, done_pieces, job_id),
                )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def cancel(db_type, job_id, now_ms):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE tts_pregen_jobs SET status = 'cancelled', finished_ms = %s WHERE id = %s AND status IN ('queued', 'running')",
                (now_ms, job_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def list_active(db_type):
        """대기·진행 중 작업 (알림 영역용, 오래된 순)"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE status IN ('queued', 'running') ORDER BY id LIMIT 50")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def count_by_status(db_type):
        """{status: count} (관리자 화면용)"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) AS cnt FROM tts_pregen_jobs GROUP BY status")
            rows = cursor.fetchall()
        return {row['status']: int(row['cnt']) for row in rows}

    # ---- 조각 음성 캐시 ----
    @staticmethod
    def get_audio(db_type, keys):
        """{key: duration_sec} (있는 것만)"""
        keys = list(keys)
        found = {}
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                placeholders = ', '.join(['%s'] * len(chunk))
                cursor.execute(
                    f"SELECT piece_key, duration_sec FROM tts_audio_cache WHERE piece_key IN ({placeholders})",
                    tuple(chunk),
                )
                for row in cursor.fetchall():
                    found[row['piece_key']] = float(row['duration_sec'])
        return found

    @staticmethod
    def put_audio(db_type, key, duration_sec, size_bytes, now_ms):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tts_audio_cache (piece_key, duration_sec, bytes, created_ms, last_used_ms) VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE duration_sec = VALUES(duration_sec), bytes = VALUES(bytes), last_used_ms = VALUES(last_used_ms)",
                (key, duration_sec, size_bytes, now_ms, now_ms),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def touch_audio(db_type, keys, now_ms):
        keys = list(keys)
        if not keys:
            return
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                placeholders = ', '.join(['%s'] * len(chunk))
                cursor.execute(
                    f"UPDATE tts_audio_cache SET last_used_ms = %s WHERE piece_key IN ({placeholders})",
                    tuple([now_ms] + chunk),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def total_audio_bytes(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(bytes), 0) AS total FROM tts_audio_cache")
            row = cursor.fetchone()
        return int(row['total'] if row else 0)

    @staticmethod
    def oldest_audio(db_type, limit):
        """[(key, bytes)] — 오래 안 쓴 순"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT piece_key, bytes FROM tts_audio_cache ORDER BY last_used_ms LIMIT %s",
                (int(limit),),
            )
            rows = cursor.fetchall()
        return [(row['piece_key'], int(row['bytes'])) for row in rows]

    @staticmethod
    def delete_audio(db_type, keys):
        keys = list(keys)
        if not keys:
            return
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                placeholders = ', '.join(['%s'] * len(chunk))
                cursor.execute(f"DELETE FROM tts_audio_cache WHERE piece_key IN ({placeholders})", tuple(chunk))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
