# -*- coding: utf-8 -*-
"""
reading_progress_repository.py – MariaDB 전용 독서 진행률(user_progress) 및 활동 로그(user_reading_log) 데이터 액세스 레이어
"""
import database

class ReadingProgressRepository:
    @staticmethod
    def get_book_for_progress(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_format, total_pages, title, author, publisher, series_name, created_at
            FROM books WHERE id = %s
            """,
            (book_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_total_pages(db_type, book_id, total_pages):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE books SET total_pages = %s WHERE id = %s", (total_pages, book_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_progress_only(db_type, book_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pages_read, is_completed FROM user_progress WHERE book_id = %s AND user_id = %s",
            (book_id, user_id),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_progress_state(db_type, book_id, user_id):
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
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = %s
            WHERE b.id = %s
            """,
            (user_id, book_id),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def insert_empty_progress(db_type, book_id, user_id, now_str):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT IGNORE INTO user_progress (
                    book_id, user_id, pages_read, is_completed, last_read_at,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE user_progress
                SET pages_read=%s, is_completed=%s, last_read_at=%s,
                    last_epub_cfi=%s, last_epub_href=%s, last_epub_spine_index=%s,
                    last_epub_percent=%s, last_epub_fingerprint=%s, last_epub_updated_at=%s
                WHERE book_id=%s AND user_id=%s
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE user_progress SET pages_read=%s, is_completed=%s, last_read_at=%s WHERE book_id=%s AND user_id=%s",
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM user_reading_log WHERE book_id=%s AND user_id=%s AND read_date=%s",
                (book_id, user_id, today_str),
            )
            log_row = cursor.fetchone()
            if log_row:
                cursor.execute(
                    "UPDATE user_reading_log SET pages_read_delta=pages_read_delta+%s WHERE id=%s",
                    (delta, log_row['id']),
                )
            else:
                cursor.execute(
                    "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (%s,%s,%s,60,%s)",
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['username'] if row else None

    @staticmethod
    def get_settings_value(db_type, key):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT `value` FROM settings WHERE `key` = %s", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def fetch_reading_history(db_type, user_id, limit, hide_completed):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT a.id, a.library_id, a.title, '' AS title_alias, a.title AS series_name, '' AS series_alias,
                       CONCAT('/api/media/audiobooks/', a.id, '/cover') AS cover_image,
                       a.updated_at AS cover_updated_at, 'audiobook' AS file_format,
                       COALESCE(p.current_time, 0) AS pages_read, a.total_tracks AS total_pages, a.total_tracks AS total_tracks,
                       COALESCE(a.is_favorite, 0) AS is_favorite, COALESCE(p.is_completed, 0) AS is_completed,
                       0 AS has_unfinished_siblings, p.last_listened_at AS last_read_at, 0 AS metadata_locked
                FROM audiobooks a
                JOIN audiobook_progress p ON a.id = p.audiobook_id
                WHERE p.user_id = %s AND COALESCE(a.is_deleted, 0) = 0 AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
                ORDER BY p.last_listened_at DESC
                LIMIT %s
            """, (user_id, int(limit)))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        if db_type == 'video':
            cursor.execute("""
                SELECT v.id, v.library_id, v.title, '' AS title_alias, v.title AS series_name, '' AS series_alias,
                       CONCAT('/api/media/videos/', v.id, '/cover') AS cover_image,
                       v.updated_at AS cover_updated_at, 'video' AS file_format,
                       COALESCE(p.current_time, 0) AS pages_read, v.total_episodes AS total_pages, v.total_episodes AS total_tracks,
                       COALESCE(v.is_favorite, 0) AS is_favorite, COALESCE(p.is_completed, 0) AS is_completed,
                       0 AS has_unfinished_siblings, p.last_watched_at AS last_read_at, 0 AS metadata_locked
                FROM videos v
                JOIN video_progress p ON v.id = p.video_id
                WHERE p.user_id = %s AND COALESCE(v.is_deleted, 0) = 0 AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
                ORDER BY p.last_watched_at DESC
                LIMIT %s
            """, (user_id, int(limit)))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        optimized_query = """
                SELECT limited_history.*,
                       CASE
                           WHEN limited_history.series_name IS NULL OR limited_history.series_name = '' THEN
                               CASE WHEN COALESCE(limited_history.is_completed, 0) = 0
                                             OR (COALESCE(limited_history.total_pages, 0) > 0
                                                 AND COALESCE(limited_history.pages_read, 0) < COALESCE(limited_history.total_pages, 0))
                                    THEN 1 ELSE 0 END
                           WHEN EXISTS (
                               SELECT 1
                               FROM books b2
                               LEFT JOIN user_progress p2 FORCE INDEX (uq_user_book_progress)
                                   ON b2.id = p2.book_id AND p2.user_id = limited_history.user_id
                               WHERE COALESCE(b2.is_deleted, 0) = 0
                                   AND b2.library_id = limited_history.library_id
                                   AND b2.series_name = limited_history.series_name
                                   AND (
                                       p2.book_id IS NULL
                                       OR COALESCE(p2.is_completed, 0) = 0
                                       OR (COALESCE(b2.total_pages, 0) > 0
                                           AND COALESCE(p2.pages_read, 0) < COALESCE(b2.total_pages, 0))
                                   )
                           ) THEN 1 ELSE 0
                       END AS has_unfinished_siblings
                FROM (
                    SELECT ranked_history.*
                    FROM (
                        SELECT b.id, b.library_id, b.title, b.title_alias, b.series_name, b.series_alias,
                               b.cover_image, b.cover_updated_at, b.file_format, p.pages_read, b.total_pages,
                               p.last_read_at, p.user_id,
                               CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                               p.is_completed, COALESCE(b.metadata_locked, 0) AS metadata_locked,
                               ROW_NUMBER() OVER (
                                   PARTITION BY b.library_id,
                                       CASE WHEN b.series_name IS NOT NULL AND TRIM(b.series_name) != ''
                                            THEN b.series_name ELSE CONCAT('__single__:', b.id) END
                                   ORDER BY p.last_read_at DESC, b.id DESC
                               ) AS series_rank,
                               COUNT(*) OVER (
                                   PARTITION BY b.library_id,
                                       CASE WHEN b.series_name IS NOT NULL AND TRIM(b.series_name) != ''
                                            THEN b.series_name ELSE CONCAT('__single__:', b.id) END
                               ) AS history_book_count
                        FROM user_progress p
                        JOIN books b ON p.book_id = b.id
                        JOIN user_category_permissions ucp
                            ON b.library_id = ucp.library_id
                            AND ucp.user_id = p.user_id
                            AND ucp.has_access = 1
                        LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = p.user_id
                        WHERE COALESCE(b.is_deleted, 0) = 0
                            AND p.user_id = %s
                            AND COALESCE(p.pages_read, 0) > 0
                    ) ranked_history
                    WHERE ranked_history.series_rank = 1
                    ORDER BY ranked_history.last_read_at DESC
                    LIMIT %s
                    OFFSET %s
                ) limited_history
                ORDER BY limited_history.last_read_at DESC
        """

        target_limit = int(limit)
        page_size = target_limit if not hide_completed else max(50, target_limit * 2)
        offset = 0
        selected_rows = []

        while True:
            cursor.execute(optimized_query, (user_id, page_size, offset))
            batch = [dict(row) for row in cursor.fetchall()]

            if not hide_completed:
                conn.close()
                return batch

            selected_rows.extend(
                row for row in batch
                if int(row.get('has_unfinished_siblings') or 0) == 1
            )
            if len(selected_rows) >= target_limit or len(batch) < page_size:
                conn.close()
                return selected_rows[:target_limit]

            offset += page_size

    @staticmethod
    def fetch_recently_added_by_user(db_type, user_id):
        if db_type == 'audiobook':
            safe_user_id = int(user_id) if user_id is not None else -1
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.library_id, a.title, '' AS title_alias, a.title AS series_name, '' AS series_alias,
                       CONCAT('/api/media/audiobooks/', a.id, '/cover') AS cover_image,
                       a.updated_at AS cover_updated_at, 'audiobook' AS file_format, a.total_tracks AS total_pages, a.total_tracks AS total_tracks, a.created_at,
                       COALESCE(a.is_favorite, 0) AS is_favorite, 0 AS metadata_locked
                FROM audiobooks a
                JOIN user_category_permissions p ON a.library_id = p.library_id
                WHERE COALESCE(a.is_deleted, 0) = 0 AND p.user_id = %s AND p.has_access = 1
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
                       CONCAT('/api/media/videos/', v.id, '/cover') AS cover_image,
                       v.updated_at AS cover_updated_at, 'video' AS file_format, v.total_episodes AS total_pages, v.created_at,
                       COALESCE(v.is_favorite, 0) AS is_favorite, 0 AS metadata_locked
                FROM videos v
                JOIN user_category_permissions p ON v.library_id = p.library_id
                WHERE COALESCE(v.is_deleted, 0) = 0 AND p.user_id = %s AND p.has_access = 1
                ORDER BY v.created_at DESC, v.id DESC
                LIMIT 20
            """, (safe_user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

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
                GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CONCAT(id, '') END
            ) g ON b.id = g.max_id
            JOIN user_category_permissions p ON b.library_id = p.library_id
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = %s
            WHERE COALESCE(b.is_deleted, 0) = 0 AND p.user_id = %s AND p.has_access = 1
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 20
        """, (safe_user_id, safe_user_id))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def fetch_recently_added_all(db_type, user_id):
        if db_type == 'audiobook':
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.library_id, a.title, '' AS title_alias, a.title AS series_name, '' AS series_alias,
                       CONCAT('/api/media/audiobooks/', a.id, '/cover') AS cover_image,
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
                       CONCAT('/api/media/videos/', v.id, '/cover') AS cover_image,
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
                GROUP BY CASE WHEN series_name IS NOT NULL AND series_name != '' THEN series_name ELSE CONCAT(id, '') END
            ) g ON b.id = g.max_id
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = %s
            WHERE COALESCE(b.is_deleted, 0) = 0
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 20
        """, (int(user_id) if user_id is not None else 0,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def delete_user_progress_by_book(db_type, book_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if db_type == 'audiobook':
                cursor.execute("DELETE FROM audiobook_progress WHERE audiobook_id = %s AND user_id = %s", (book_id, user_id))
            else:
                cursor.execute("DELETE FROM user_progress WHERE book_id = %s AND user_id = %s", (book_id, user_id))
                cursor.execute("DELETE FROM user_reading_log WHERE book_id = %s AND user_id = %s", (book_id, user_id))
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
                    "SELECT id FROM audiobooks WHERE title = %s AND library_id = %s AND COALESCE(is_deleted, 0) = 0",
                    (series_name, library_id)
                )
                book_ids = [row['id'] for row in cursor.fetchall()]
                if book_ids:
                    placeholders = ','.join('%s' for _ in book_ids)
                    cursor.execute(
                        f"DELETE FROM audiobook_progress WHERE user_id = %s AND audiobook_id IN ({placeholders})",
                        (user_id, *book_ids)
                    )
            else:
                cursor.execute(
                    "SELECT id FROM books WHERE series_name = %s AND library_id = %s AND COALESCE(is_deleted, 0) = 0",
                    (series_name, library_id)
                )
                book_ids = [row['id'] for row in cursor.fetchall()]
                if book_ids:
                    placeholders = ','.join('%s' for _ in book_ids)
                    params = (user_id, *book_ids)
                    cursor.execute(
                        f"DELETE FROM user_progress WHERE user_id = %s AND book_id IN ({placeholders})",
                        params
                    )
                    cursor.execute(
                        f"DELETE FROM user_reading_log WHERE user_id = %s AND book_id IN ({placeholders})",
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT DISTINCT DATE(p.last_listened_at) AS read_date
                FROM audiobook_progress p
                JOIN audiobooks a ON p.audiobook_id = a.id
                JOIN user_category_permissions ucp ON a.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
                WHERE p.user_id = %s
                  AND p.last_listened_at IS NOT NULL
                  AND COALESCE(a.is_deleted, 0) = 0
                  AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
                ORDER BY read_date DESC
            """, (user_id,))
            rows = cursor.fetchall()
            conn.close()
            normalized = []
            for r in rows:
                if isinstance(r, dict):
                    val = r.get('read_date')
                else:
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
            WHERE p.user_id = %s AND p.last_read_at IS NOT NULL AND COALESCE(b.is_deleted, 0) = 0
            ORDER BY read_date DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        normalized = []
        for r in rows:
            if isinstance(r, dict):
                val = r.get('read_date')
            else:
                try:
                    val = r['read_date']
                except Exception:
                    val = r[0] if r else None
            if val:
                normalized.append(str(val))
        return normalized

    @staticmethod
    def get_completed_count_by_year(db_type, user_id, year_str):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT COUNT(*)
                FROM audiobook_progress p
                JOIN audiobooks a ON p.audiobook_id = a.id
                JOIN user_category_permissions ucp ON a.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
                WHERE p.user_id = %s
                  AND COALESCE(p.is_completed, 0) = 1
                  AND DATE_FORMAT(p.last_listened_at, '%%Y') = %s
                  AND COALESCE(a.is_deleted, 0) = 0
            """, (user_id, str(year_str)))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return 0
            if isinstance(row, dict):
                return int(row.get('COUNT(*)', 0) or 0)
            try:
                return int(row[0] or 0)
            except Exception:
                return 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            WHERE p.user_id = %s AND (p.is_completed = 1 OR p.last_epub_percent >= 99) 
              AND DATE_FORMAT(p.last_read_at, '%%Y') = %s AND COALESCE(b.is_deleted, 0) = 0
        """, (user_id, str(year_str)))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return 0
        if isinstance(row, dict):
            return int(row.get('COUNT(*)', 0) or 0)
        try:
            return int(row[0] or 0)
        except Exception:
            return 0

    @staticmethod
    def get_completed_count_by_month(db_type, user_id, year_month_str):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        if db_type == 'audiobook':
            cursor.execute("""
                SELECT COUNT(*)
                FROM audiobook_progress p
                JOIN audiobooks a ON p.audiobook_id = a.id
                JOIN user_category_permissions ucp ON a.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
                WHERE p.user_id = %s
                  AND COALESCE(p.is_completed, 0) = 1
                  AND DATE_FORMAT(p.last_listened_at, '%%Y-%%m') = %s
                  AND COALESCE(a.is_deleted, 0) = 0
            """, (user_id, year_month_str))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return 0
            if isinstance(row, dict):
                return int(row.get('COUNT(*)', 0) or 0)
            try:
                return int(row[0] or 0)
            except Exception:
                return 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM user_progress p
            JOIN books b ON p.book_id = b.id
            JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1
            WHERE p.user_id = %s AND (p.is_completed = 1 OR p.last_epub_percent >= 99) 
              AND DATE_FORMAT(p.last_read_at, '%%Y-%%m') = %s AND COALESCE(b.is_deleted, 0) = 0
        """, (user_id, year_month_str))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return 0
        if isinstance(row, dict):
            return int(row.get('COUNT(*)', 0) or 0)
        try:
            return int(row[0] or 0)
        except Exception:
            return 0

    @staticmethod
    def batch_flush_progress_items(db_type, items):
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
                    "SELECT pages_read, is_completed FROM user_progress WHERE book_id = %s AND user_id = %s",
                    (book_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        """
                        INSERT IGNORE INTO user_progress (
                            book_id, user_id, pages_read, is_completed, last_read_at,
                            last_epub_cfi, last_epub_href, last_epub_spine_index,
                            last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (book_id, user_id, 0, 0, last_read_at, None, None, None, 0, None, None),
                    )

                cursor.execute(
                    """
                    UPDATE user_progress
                    SET pages_read=%s, is_completed=%s, last_read_at=%s,
                        last_epub_cfi=%s, last_epub_href=%s, last_epub_spine_index=%s,
                        last_epub_percent=%s, last_epub_fingerprint=%s, last_epub_updated_at=%s
                    WHERE book_id=%s AND user_id=%s
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
                        "SELECT id FROM user_reading_log WHERE book_id=%s AND user_id=%s AND read_date=%s",
                        (book_id, user_id, today_str),
                    )
                    log_row = cursor.fetchone()
                    if log_row:
                        cursor.execute(
                            "UPDATE user_reading_log SET pages_read_delta=pages_read_delta+%s WHERE id=%s",
                            (delta, log_row['id']),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (%s,%s,%s,60,%s)",
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
