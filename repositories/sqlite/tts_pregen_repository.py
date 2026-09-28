# -*- coding: utf-8 -*-
"""
tts_pregen_repository.py – SQLite 전용 듣기(TTS) 서버 미리 만들기 데이터 액세스 레이어

tts_pregen_jobs: 책 단위 작업 큐 (queued → running → done/failed/cancelled).
tts_audio_books / tts_audio_pieces: 책·설정별 음성 폴더와 그 안 조각의 위치(목차). 조각 키는 합성 입력 전체의 sha256.
시각은 DB 시간대 차이가 없는 epoch ms.
"""
import database

ACTIVE_STATUSES = ('queued', 'running')


class TTSPregenRepository:
    # ---- 작업 ----
    @staticmethod
    def create_job(db_type, book_id, user_id, voice, steps, speed, total_pieces, now_ms, quality='standard'):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tts_pregen_jobs (book_id, user_id, voice, steps, speed, status, total_pieces, done_pieces, created_ms, quality) "
                "VALUES (?, ?, ?, ?, ?, 'queued', ?, 0, ?, ?)",
                (book_id, user_id, voice, steps, speed, total_pieces, now_ms, quality),
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
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def find_active_job(db_type, book_id, voice, steps, speed):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tts_pregen_jobs WHERE book_id = ? AND voice = ? AND steps = ? AND ABS(speed - ?) < 0.001 "
                "AND status IN ('queued', 'running') ORDER BY id DESC LIMIT 1",
                (book_id, voice, steps, speed),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def latest_job(db_type, book_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE book_id = ? ORDER BY id DESC LIMIT 1", (book_id,))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def count_active_by_user(db_type, user_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM tts_pregen_jobs WHERE user_id = ? AND status IN ('queued', 'running')",
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
                "OR (status = 'running' AND (heartbeat_ms IS NULL OR heartbeat_ms < ?)) ORDER BY id LIMIT 1",
                (stale_before_ms,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            job_id = row['id']
            cursor.execute(
                "UPDATE tts_pregen_jobs SET status = 'running', heartbeat_ms = ? WHERE id = ? "
                "AND (status = 'queued' OR (status = 'running' AND (heartbeat_ms IS NULL OR heartbeat_ms < ?)))",
                (now_ms, job_id, stale_before_ms),
            )
            conn.commit()
            if cursor.rowcount != 1:
                return None
            cursor.execute("SELECT * FROM tts_pregen_jobs WHERE id = ?", (job_id,))
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
                "UPDATE tts_pregen_jobs SET done_pieces = ?, heartbeat_ms = ? WHERE id = ? AND status = 'running'",
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
                    "UPDATE tts_pregen_jobs SET status = ?, error = ?, finished_ms = ? WHERE id = ? AND status = 'running'",
                    (status, error, now_ms, job_id),
                )
            else:
                cursor.execute(
                    "UPDATE tts_pregen_jobs SET status = ?, error = ?, finished_ms = ?, done_pieces = ? WHERE id = ? AND status = 'running'",
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
                "UPDATE tts_pregen_jobs SET status = 'cancelled', finished_ms = ? WHERE id = ? AND status IN ('queued', 'running')",
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

    # ---- 책 단위 음성 저장 (tts_audio_books + tts_audio_pieces) ----
    @staticmethod
    def get_or_create_audio_book(db_type, book_id, voice, steps, speed, quality, rel_dir, user_id, now_ms):
        """이 책·설정·음질의 음성 폴더 행. 없으면 만든다(처음 요청한 사용자가 created_by)."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM tts_audio_books WHERE book_id = ? AND voice = ? AND steps = ? AND ABS(speed - ?) < 0.001 AND quality = ?",
                (book_id, voice, steps, speed, quality),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            cursor.execute(
                "INSERT INTO tts_audio_books (book_id, voice, steps, speed, quality, rel_dir, pieces, bytes, duration_sec, created_by, created_ms, last_used_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?)",
                (book_id, voice, steps, speed, quality, rel_dir, user_id, now_ms, now_ms),
            )
            conn.commit()
            cursor.execute("SELECT * FROM tts_audio_books WHERE id = ?", (cursor.lastrowid,))
            return dict(cursor.fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_audio_book(db_type, audio_book_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_audio_books WHERE id = ?", (audio_book_id,))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_audio_books(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_audio_books WHERE pieces > 0 ORDER BY last_used_ms DESC")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def book_pieces(db_type, audio_book_id):
        """[{piece_key, chapter, part, byte_offset, byte_length, duration_sec}] — 이 책 폴더의 목차 전체"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT piece_key, chapter, part, byte_offset, byte_length, duration_sec FROM tts_audio_pieces WHERE audio_book_id = ?",
                (audio_book_id,),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def add_piece(db_type, audio_book_id, key, chapter, part, byte_offset, byte_length, duration_sec):
        """목차 한 줄 추가 + 책 합계 갱신 (pack 파일에 쓴 다음에 부른다)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tts_audio_pieces (audio_book_id, piece_key, chapter, part, byte_offset, byte_length, duration_sec) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (audio_book_id, key, chapter, part, byte_offset, byte_length, duration_sec),
            )
            cursor.execute(
                "UPDATE tts_audio_books SET pieces = pieces + 1, bytes = bytes + ?, duration_sec = duration_sec + ? WHERE id = ?",
                (byte_length, duration_sec, audio_book_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def remove_pieces(db_type, audio_book_id, keys):
        """목차에서 지우고 책 합계를 다시 계산한다 (pack 파일이 잘린 경우의 정리용)"""
        keys = list(keys)
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                placeholders = ', '.join(['?'] * len(chunk))
                cursor.execute(
                    f"DELETE FROM tts_audio_pieces WHERE audio_book_id = ? AND piece_key IN ({placeholders})",
                    tuple([audio_book_id] + chunk),
                )
            cursor.execute(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(byte_length), 0) AS total, COALESCE(SUM(duration_sec), 0) AS sec "
                "FROM tts_audio_pieces WHERE audio_book_id = ?",
                (audio_book_id,),
            )
            row = cursor.fetchone()
            cursor.execute(
                "UPDATE tts_audio_books SET pieces = ?, bytes = ?, duration_sec = ? WHERE id = ?",
                (int(row['cnt']), int(row['total']), float(row['sec']), audio_book_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def find_pieces(db_type, keys):
        """{key: row} — 여러 책에 같은 키가 있으면 최근에 들은 책 것. row에 rel_dir, audio_book_id, 위치가 들어 있다."""
        keys = list(keys)
        found = {}
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                placeholders = ', '.join(['?'] * len(chunk))
                cursor.execute(
                    "SELECT p.piece_key, p.audio_book_id, p.chapter, p.part, p.byte_offset, p.byte_length, p.duration_sec, "
                    "b.rel_dir, b.last_used_ms FROM tts_audio_pieces p JOIN tts_audio_books b ON b.id = p.audio_book_id "
                    f"WHERE p.piece_key IN ({placeholders})",
                    tuple(chunk),
                )
                for row in cursor.fetchall():
                    row = dict(row)
                    prev = found.get(row['piece_key'])
                    if prev is None or row['last_used_ms'] > prev['last_used_ms']:
                        found[row['piece_key']] = row
        return found

    @staticmethod
    def touch_audio_books(db_type, audio_book_ids, now_ms):
        ids = [int(i) for i in audio_book_ids]
        if not ids:
            return
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            placeholders = ', '.join(['?'] * len(ids))
            cursor.execute(f"UPDATE tts_audio_books SET last_used_ms = ? WHERE id IN ({placeholders})", tuple([now_ms] + ids))
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
            cursor.execute("SELECT COALESCE(SUM(bytes), 0) AS total FROM tts_audio_books")
            row = cursor.fetchone()
        return int(row['total'] if row else 0)

    @staticmethod
    def oldest_audio_books(db_type, limit):
        """오래 안 들은 순 [{id, rel_dir, bytes}]"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, rel_dir, bytes FROM tts_audio_books ORDER BY last_used_ms LIMIT ?", (int(limit),))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def delete_audio_book(db_type, audio_book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tts_audio_pieces WHERE audio_book_id = ?", (audio_book_id,))
            cursor.execute("DELETE FROM tts_audio_books WHERE id = ?", (audio_book_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def clear_legacy_cache(db_type):
        """예전(v2.7.9) 조각 단위 캐시 색인을 비운다"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tts_audio_cache")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def books_brief(db_type, book_ids, user_id):
        """"음성 준비됨" 목록 카드용 도서 정보 {book_id: row} (삭제된 책은 빠진다)"""
        ids = [int(i) for i in book_ids]
        if not ids:
            return {}
        out = {}
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                placeholders = ', '.join(['?'] * len(chunk))
                cursor.execute(
                    "SELECT b.id, b.library_id, b.title, b.series_name, b.series_alias, b.author, b.file_format, b.total_pages, "
                    "b.cover_image, b.cover_updated_at, b.cover_align, p.pages_read, p.is_completed "
                    "FROM books b LEFT JOIN user_progress p ON p.book_id = b.id AND p.user_id = ? "
                    f"WHERE b.id IN ({placeholders}) AND COALESCE(b.is_deleted, 0) = 0",
                    tuple([user_id] + chunk),
                )
                for row in cursor.fetchall():
                    out[int(row['id'])] = dict(row)
        return out
