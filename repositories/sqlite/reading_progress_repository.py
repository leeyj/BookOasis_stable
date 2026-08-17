# -*- coding: utf-8 -*-
"""
reading_progress_repository.py – 독서 진행률(user_progress) 및 활동 로그(user_reading_log) 조회/업데이트 데이터 액세스 레이어
"""
import database

class ReadingProgressRepository:
    @staticmethod
    def get_book_for_progress(db_type, book_id):
        """진행률 기록에 필요한 도서 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_format, total_pages, title, author, publisher, series_name, created_at
            FROM books WHERE id = ?
            """,
            (book_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_total_pages(db_type, book_id, total_pages):
        """도서의 총 페이지 수 수정"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_progress_only(db_type, book_id, user_id):
        """특정 사용자의 도서 읽기 진행률만 단순 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pages_read, is_completed FROM user_progress WHERE book_id = ? AND user_id = ?",
            (book_id, user_id),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_progress_state(db_type, book_id, user_id):
        """특정 사용자의 도서 진행 상태 상세 조회 (책 포맷 정보 결합)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                b.file_format,
                b.total_pages,
                p.pages_read,
                p.last_read_at,
                p.last_epub_cfi,
                p.last_epub_href,
                p.last_epub_spine_index,
                p.last_epub_percent,
                p.last_epub_fingerprint,
                p.last_epub_updated_at
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE b.id = ?
            """,
            (user_id, book_id),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def insert_empty_progress(db_type, book_id, user_id, now_str):
        """최초 독서 시 빈 진행률 레코드 생성"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_progress (
                    book_id, user_id, pages_read, is_completed, last_read_at,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (book_id, user_id, 0, 0, now_str, None, None, None, 0, None, None),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_progress_full(db_type, book_id, user_id, pages_read, is_completed, now_str,
                             last_epub_cfi, last_epub_href, last_epub_spine_index,
                             last_epub_percent, last_epub_fingerprint, last_epub_updated_at):
        """EPUB 등 상세 포인터 데이터를 포함한 진행률 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE user_progress
                SET pages_read=?, is_completed=?, last_read_at=?,
                    last_epub_cfi=?, last_epub_href=?, last_epub_spine_index=?,
                    last_epub_percent=?, last_epub_fingerprint=?, last_epub_updated_at=?
                WHERE book_id=? AND user_id=?
                """,
                (
                    pages_read,
                    is_completed,
                    now_str,
                    last_epub_cfi,
                    last_epub_href,
                    last_epub_spine_index,
                    last_epub_percent,
                    last_epub_fingerprint,
                    last_epub_updated_at,
                    book_id,
                    user_id,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_progress_simple(db_type, book_id, user_id, pages_read, is_completed, now_str):
        """일반 도서 포맷의 단순 진행률 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE user_progress SET pages_read=?, is_completed=?, last_read_at=? WHERE book_id=? AND user_id=?",
                (pages_read, is_completed, now_str, book_id, user_id),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_or_insert_reading_log(db_type, book_id, user_id, delta, today_str):
        """일일 활동 로그 누적 기록 반영"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM user_reading_log WHERE book_id=? AND user_id=? AND read_date=?",
                (book_id, user_id, today_str),
            )
            log_row = cursor.fetchone()
            if log_row:
                cursor.execute(
                    "UPDATE user_reading_log SET pages_read_delta=pages_read_delta+? WHERE id=?",
                    (delta, log_row['id']),
                )
            else:
                cursor.execute(
                    "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?,?,?,60,?)",
                    (book_id, user_id, delta, today_str),
                )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_username_by_id(db_type, user_id):
        """특정 사용자의 사용자명 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['username'] if row else None

    @staticmethod
    def get_settings_value(db_type, key):
        """설정 테이블에서 특정 설정 키 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT `value` FROM settings WHERE `key` = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def fetch_reading_history(db_type, user_id, limit, hide_completed):
        """특정 사용자의 독서 진척 이력 조회 (완독 숨김 옵션 결합)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT a.id, a.library_id, a.title, '' AS title_alias, a.title AS series_name, '' AS series_alias,
                       '/api/media/audiobooks/' || a.id || '/cover' AS cover_image,
                       a.updated_at AS cover_updated_at, 'audiobook' AS file_format,
                       COALESCE(p.current_time, 0) AS pages_read, a.total_tracks AS total_pages, a.total_tracks AS total_tracks,
                       COALESCE(a.is_favorite, 0) AS is_favorite, COALESCE(p.is_completed, 0) AS is_completed,
                       0 AS has_unfinished_siblings, p.last_listened_at AS last_read_at, 0 AS metadata_locked
                FROM audiobooks a
                JOIN audiobook_progress p ON a.id = p.audiobook_id
                WHERE p.user_id = ? AND COALESCE(a.is_deleted, 0) = 0 AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
                ORDER BY p.last_listened_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        if db_type == 'video':
            cursor.execute("""
                SELECT v.id, v.library_id, v.title, '' AS title_alias, v.title AS series_name, '' AS series_alias,
                       '/api/media/videos/' || v.id || '/cover' AS cover_image,
                       v.updated_at AS cover_updated_at, 'video' AS file_format,
                       COALESCE(p.current_time, 0) AS pages_read, v.total_episodes AS total_pages, v.total_episodes AS total_tracks,
                       COALESCE(v.is_favorite, 0) AS is_favorite, COALESCE(p.is_completed, 0) AS is_completed,
                       0 AS has_unfinished_siblings, p.last_watched_at AS last_read_at, 0 AS metadata_locked
                FROM videos v
                JOIN video_progress p ON v.id = p.video_id
                WHERE p.user_id = ? AND COALESCE(v.is_deleted, 0) = 0 AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
                ORDER BY p.last_watched_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        base_select = """
            SELECT * FROM (
            SELECT b.id, b.library_id, b.title, b.title_alias, b.series_name, b.series_alias, b.cover_image, b.cover_updated_at, b.file_format,
                   p.pages_read, b.total_pages, p.last_read_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                                     p.is_completed,
                                     CASE WHEN EXISTS (
                                             SELECT 1
                                             FROM books b2
                                             LEFT JOIN user_progress p2 ON b2.id = p2.book_id AND p2.user_id = p.user_id
                                             WHERE COALESCE(b2.is_deleted, 0) = 0
                                                 AND b2.library_id = b.library_id
                                                 AND COALESCE(NULLIF(b2.series_name, ''), CAST(b2.id AS TEXT)) = COALESCE(NULLIF(b.series_name, ''), CAST(b.id AS TEXT))
                                                 AND (
                                                     p2.book_id IS NULL
                                                     OR COALESCE(p2.is_completed, 0) = 0
                                                     OR (COALESCE(b2.total_pages, 0) > 0 AND COALESCE(p2.pages_read, 0) < COALESCE(b2.total_pages, 0))
                                                 )
                                     ) THEN 1 ELSE 0 END AS has_unfinished_siblings,
                                     COALESCE(b.metadata_locked, 0) AS metadata_locked,
                   ROW_NUMBER() OVER (
                       PARTITION BY b.library_id, COALESCE(NULLIF(TRIM(b.series_name), ''), '__single__:' || CAST(b.id AS TEXT))
                       ORDER BY p.last_read_at DESC, b.id DESC
                   ) AS series_rank,
                   COUNT(*) OVER (
                       PARTITION BY b.library_id, COALESCE(NULLIF(TRIM(b.series_name), ''), '__single__:' || CAST(b.id AS TEXT))
                   ) AS history_book_count
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = p.user_id
            WHERE COALESCE(b.is_deleted, 0) = 0 AND p.user_id = ? AND COALESCE(p.pages_read, 0) > 0
        """
        if hide_completed:
            base_select += """
                            AND NOT (
                                (COALESCE(p.is_completed, 0) = 1 OR (COALESCE(b.total_pages, 0) > 0 AND COALESCE(p.pages_read, 0) >= COALESCE(b.total_pages, 0)))
                                AND NOT EXISTS (
                                    SELECT 1
                                    FROM books b2
                                    LEFT JOIN user_progress p2 ON b2.id = p2.book_id AND p2.user_id = p.user_id
                                    WHERE COALESCE(b2.is_deleted, 0) = 0
                                        AND b2.library_id = b.library_id
                                        AND COALESCE(NULLIF(b2.series_name, ''), CAST(b2.id AS TEXT)) = COALESCE(NULLIF(b.series_name, ''), CAST(b.id AS TEXT))
                                        AND (
                                            p2.book_id IS NULL
                                            OR COALESCE(p2.is_completed, 0) = 0
                                            OR (COALESCE(b2.total_pages, 0) > 0 AND COALESCE(p2.pages_read, 0) < COALESCE(b2.total_pages, 0))
                                        )
                                )
                            )
            """
        base_select += """
            ) ranked_history
            WHERE series_rank = 1
            ORDER BY last_read_at DESC
            LIMIT ?
        """
        cursor.execute(base_select, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def fetch_recently_added_by_user(db_type, user_id):
        """일반 유저 권한 카테고리에 한해 최근 추가된 도서 목록 조회.
        user_id=None인 경우 user_category_permissions에 매칭 행이 없으므로 빈 목록 반환.
        """
        if db_type == 'audiobook':
            safe_user_id = int(user_id) if user_id is not None else -1
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.library_id, a.title, '' AS title_alias, a.title AS series_name, '' AS series_alias,
                       '/api/media/audiobooks/' || a.id || '/cover' AS cover_image,
                       a.updated_at AS cover_updated_at, 'audiobook' AS file_format, a.total_tracks AS total_pages, a.total_tracks AS total_tracks, a.created_at,
                       COALESCE(a.is_favorite, 0) AS is_favorite, 0 AS metadata_locked
                FROM audiobooks a
                JOIN user_category_permissions p ON a.library_id = p.library_id
                WHERE COALESCE(a.is_deleted, 0) = 0 AND p.user_id = ? AND p.has_access = 1
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT 20
            """, (safe_user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        if db_type == 'video':
            safe_user_id = int(user_id) if user_id is not None else -1
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.library_id, v.title, '' AS title_alias, v.title AS series_name, '' AS series_alias,
                       '/api/media/videos/' || v.id || '/cover' AS cover_image,
                       v.updated_at AS cover_updated_at, 'video' AS file_format, v.total_episodes AS total_pages, v.created_at,
                       COALESCE(v.is_favorite, 0) AS is_favorite, 0 AS metadata_locked
                FROM videos v
                JOIN user_category_permissions p ON v.library_id = p.library_id
                WHERE COALESCE(v.is_deleted, 0) = 0 AND p.user_id = ? AND p.has_access = 1
                ORDER BY v.created_at DESC, v.id DESC
                LIMIT 20
            """, (safe_user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        # user_id=None 이면 매칭 불가한 값(-1)으로 치환 → 권한 행 없음 → 빈 결과
        safe_user_id = int(user_id) if user_id is not None else -1
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.library_id, b.title, b.title_alias, b.series_name, b.series_alias, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite, COALESCE(b.metadata_locked, 0) AS metadata_locked
            FROM books b
            INNER JOIN (
                SELECT MAX(id) as max_id
                FROM (
                    SELECT id, series_name
                    FROM books
                    WHERE COALESCE(is_deleted, 0) = 0
                    ORDER BY id DESC
                    LIMIT 1000
                ) sub
                GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CAST(id AS TEXT) END
            ) g ON b.id = g.max_id
            JOIN user_category_permissions p ON b.library_id = p.library_id
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = ?
            WHERE COALESCE(b.is_deleted, 0) = 0 AND p.user_id = ? AND p.has_access = 1
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 20
        """, (safe_user_id, safe_user_id))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def fetch_recently_added_all(db_type, user_id):
        """어드민 등 제한 없이 최근 추가된 도서 목록 전체 조회"""
        if db_type == 'audiobook':
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.library_id, a.title, '' AS title_alias, a.title AS series_name, '' AS series_alias,
                       '/api/media/audiobooks/' || a.id || '/cover' AS cover_image,
                       a.updated_at AS cover_updated_at, 'audiobook' AS file_format, a.total_tracks AS total_pages, a.total_tracks AS total_tracks, a.created_at,
                       COALESCE(a.is_favorite, 0) AS is_favorite, 0 AS metadata_locked
                FROM audiobooks a
                WHERE COALESCE(a.is_deleted, 0) = 0
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        if db_type == 'video':
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.library_id, v.title, '' AS title_alias, v.title AS series_name, '' AS series_alias,
                       '/api/media/videos/' || v.id || '/cover' AS cover_image,
                       v.updated_at AS cover_updated_at, 'video' AS file_format, v.total_episodes AS total_pages, v.created_at,
                       COALESCE(v.is_favorite, 0) AS is_favorite, 0 AS metadata_locked
                FROM videos v
                WHERE COALESCE(v.is_deleted, 0) = 0
                ORDER BY v.created_at DESC, v.id DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.library_id, b.title, b.title_alias, b.series_name, b.series_alias, b.cover_image, b.cover_updated_at, b.file_format, b.total_pages, b.created_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite, COALESCE(b.metadata_locked, 0) AS metadata_locked
            FROM books b
            INNER JOIN (
                SELECT MAX(id) as max_id
                FROM (
                    SELECT id, series_name
                    FROM books
                    WHERE COALESCE(is_deleted, 0) = 0
                    ORDER BY id DESC
                    LIMIT 1000
                ) sub
                GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CAST(id AS TEXT) END
            ) g ON b.id = g.max_id
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = ?
            WHERE COALESCE(b.is_deleted, 0) = 0
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 20
        """, (int(user_id) if user_id is not None else 0,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def delete_user_progress_by_book(db_type, book_id, user_id):
        """특정 도서의 독서 진척도 및 일일 로그 삭제"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if db_type == 'audiobook':
                cursor.execute("DELETE FROM audiobook_progress WHERE audiobook_id = ? AND user_id = ?", (book_id, user_id))
            elif db_type == 'video':
                cursor.execute("DELETE FROM video_progress WHERE video_id = ? AND user_id = ?", (book_id, user_id))
                cursor.execute("DELETE FROM video_episode_progress WHERE video_id = ? AND user_id = ?", (book_id, user_id))
            else:
                cursor.execute("DELETE FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, user_id))
                cursor.execute("DELETE FROM user_reading_log WHERE book_id = ? AND user_id = ?", (book_id, user_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_user_progress_by_series(db_type, series_name, library_id, user_id):
        """특정 시리즈의 사용자 독서 진척도 및 일일 로그를 일괄 삭제"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if db_type == 'audiobook':
                cursor.execute(
                    "SELECT id FROM audiobooks WHERE title = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0",
                    (series_name, library_id)
                )
                book_ids = [row['id'] for row in cursor.fetchall()]
                if book_ids:
                    placeholders = ','.join('?' for _ in book_ids)
                    cursor.execute(
                        f"DELETE FROM audiobook_progress WHERE user_id = ? AND audiobook_id IN ({placeholders})",
                        (user_id, *book_ids)
                    )
            elif db_type == 'video':
                cursor.execute(
                    "SELECT id FROM videos WHERE title = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0",
                    (series_name, library_id)
                )
                book_ids = [row['id'] for row in cursor.fetchall()]
                if book_ids:
                    placeholders = ','.join('?' for _ in book_ids)
                    params = (user_id, *book_ids)
                    cursor.execute(
                        f"DELETE FROM video_progress WHERE user_id = ? AND video_id IN ({placeholders})",
                        params
                    )
                    cursor.execute(
                        f"DELETE FROM video_episode_progress WHERE user_id = ? AND video_id IN ({placeholders})",
                        params
                    )
            else:
                cursor.execute(
                    "SELECT id FROM books WHERE series_name = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0",
                    (series_name, library_id)
                )
                book_ids = [row['id'] for row in cursor.fetchall()]
                if book_ids:
                    placeholders = ','.join('?' for _ in book_ids)
                    params = (user_id, *book_ids)
                    cursor.execute(
                        f"DELETE FROM user_progress WHERE user_id = ? AND book_id IN ({placeholders})",
                        params
                    )
                    cursor.execute(
                        f"DELETE FROM user_reading_log WHERE user_id = ? AND book_id IN ({placeholders})",
                        params
                    )
            conn.commit()
            return book_ids
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_distinct_read_dates(db_type, user_id):
        """특정 사용자가 책을 읽은 고유 날짜 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT DISTINCT DATE(p.last_listened_at) AS read_date
                FROM audiobook_progress p
                JOIN audiobooks a ON p.audiobook_id = a.id
                JOIN user_category_permissions ucp ON a.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
                WHERE p.user_id = ?
                  AND p.last_listened_at IS NOT NULL
                  AND COALESCE(a.is_deleted, 0) = 0
                  AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
                ORDER BY read_date DESC
            """, (user_id,))
            rows = cursor.fetchall()
            conn.close()
            normalized = []
            for r in rows:
                try:
                    val = r['read_date']
                except Exception:
                    val = r[0] if r else None
                if val:
                    normalized.append(str(val))
            return normalized

        cursor.execute("""
            SELECT DISTINCT DATE(p.last_read_at) as read_date
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            WHERE p.user_id = ? AND p.last_read_at IS NOT NULL AND COALESCE(b.is_deleted, 0) = 0
            ORDER BY read_date DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        normalized = []
        for r in rows:
            try:
                val = r['read_date']
            except Exception:
                val = r[0] if r else None
            if val:
                normalized.append(str(val))
        return normalized

    @staticmethod
    def get_completed_count_by_year(db_type, user_id, year_str):
        """연간 완독 도서 수 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT COUNT(*)
                FROM audiobook_progress p
                JOIN audiobooks a ON p.audiobook_id = a.id
                JOIN user_category_permissions ucp ON a.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
                WHERE p.user_id = ?
                  AND COALESCE(p.is_completed, 0) = 1
                  AND strftime('%Y', p.last_listened_at) = ?
                  AND COALESCE(a.is_deleted, 0) = 0
            """, (user_id, str(year_str)))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return 0
            try:
                return int(row[0] or 0)
            except Exception:
                try:
                    return int(row['COUNT(*)'] or 0)
                except Exception:
                    return 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            WHERE p.user_id = ? AND (p.is_completed = 1 OR p.last_epub_percent >= 99) 
              AND strftime('%Y', p.last_read_at) = ? AND COALESCE(b.is_deleted, 0) = 0
        """, (user_id, str(year_str)))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return 0
        try:
            return int(row[0] or 0)
        except Exception:
            try:
                return int(row['COUNT(*)'] or 0)
            except Exception:
                return 0

    @staticmethod
    def get_completed_count_by_month(db_type, user_id, year_month_str):
        """월간 완독 도서 수 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT COUNT(*)
                FROM audiobook_progress p
                JOIN audiobooks a ON p.audiobook_id = a.id
                JOIN user_category_permissions ucp ON a.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
                WHERE p.user_id = ?
                  AND COALESCE(p.is_completed, 0) = 1
                  AND strftime('%Y-%m', p.last_listened_at) = ?
                  AND COALESCE(a.is_deleted, 0) = 0
            """, (user_id, year_month_str))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return 0
            try:
                return int(row[0] or 0)
            except Exception:
                try:
                    return int(row['COUNT(*)'] or 0)
                except Exception:
                    return 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            WHERE p.user_id = ? AND (p.is_completed = 1 OR p.last_epub_percent >= 99) 
              AND strftime('%Y-%m', p.last_read_at) = ? AND COALESCE(b.is_deleted, 0) = 0
        """, (user_id, year_month_str))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return 0
        try:
            return int(row[0] or 0)
        except Exception:
            try:
                return int(row['COUNT(*)'] or 0)
            except Exception:
                return 0

    @staticmethod
    def batch_flush_progress_items(db_type, items):
        """인메모리 버퍼 배치 항목을 DB에 일괄 반영"""
        from datetime import datetime
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        synced_count = 0
        try:
            today_str = datetime.now().strftime('%Y-%m-%d')
            for data in items:
                book_id = data.get('book_id')
                user_id = data.get('user_id')
                pages_read = data.get('pages_read')
                is_completed = data.get('is_completed')
                last_read_at = data.get('last_read_at')
                last_epub_cfi = data.get('last_epub_cfi')
                last_epub_href = data.get('last_epub_href')
                last_epub_spine_index = data.get('last_epub_spine_index')
                last_epub_percent = data.get('last_epub_percent')
                last_epub_fingerprint = data.get('last_epub_fingerprint')
                last_epub_updated_at = data.get('last_epub_updated_at')
                delta = data.get('delta', 0)

                cursor.execute(
                    "SELECT pages_read, is_completed FROM user_progress WHERE book_id = ? AND user_id = ?",
                    (book_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO user_progress (
                            book_id, user_id, pages_read, is_completed, last_read_at,
                            last_epub_cfi, last_epub_href, last_epub_spine_index,
                            last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (book_id, user_id, 0, 0, last_read_at, None, None, None, 0, None, None),
                    )

                cursor.execute(
                    """
                    UPDATE user_progress
                    SET pages_read=?, is_completed=?, last_read_at=?,
                        last_epub_cfi=?, last_epub_href=?, last_epub_spine_index=?,
                        last_epub_percent=?, last_epub_fingerprint=?, last_epub_updated_at=?
                    WHERE book_id=? AND user_id=?
                    """,
                    (
                        pages_read, is_completed, last_read_at,
                        last_epub_cfi, last_epub_href, last_epub_spine_index,
                        last_epub_percent, last_epub_fingerprint, last_epub_updated_at,
                        book_id, user_id,
                    ),
                )

                if delta > 0:
                    cursor.execute(
                        "SELECT id FROM user_reading_log WHERE book_id=? AND user_id=? AND read_date=?",
                        (book_id, user_id, today_str),
                    )
                    log_row = cursor.fetchone()
                    if log_row:
                        cursor.execute(
                            "UPDATE user_reading_log SET pages_read_delta=pages_read_delta+? WHERE id=?",
                            (delta, log_row['id']),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?,?,?,60,?)",
                            (book_id, user_id, delta, today_str),
                        )
                synced_count += 1
            conn.commit()
            return synced_count
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
