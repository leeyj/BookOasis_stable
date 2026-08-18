# -*- coding: utf-8 -*-
"""
series_repository.py – MariaDB 전용 시리즈(Series) 데이터 그룹핑 및 추출 데이터 액세스 레이어
"""
import time
import re
import database
from repositories.series_search_query import parse_series_search_query

class SeriesRepository:
    @staticmethod
    def rebuild_summary(db_type, only_if_unready=False):
        """현재 books 데이터를 기준으로 시리즈 요약을 트랜잭션 안에서 재생성한다."""
        if db_type in ('audiobook', 'video'):
            return False

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        lock_name = f'media_server:series_summary:{db_type}'
        lock_acquired = False
        try:
            cursor.execute("SELECT GET_LOCK(%s, 30) AS acquired", (lock_name,))
            lock_row = cursor.fetchone()
            lock_acquired = bool(lock_row and int(lock_row['acquired'] or 0))
            if not lock_acquired:
                raise RuntimeError(f'series summary rebuild lock timeout: {db_type}')
            if only_if_unready:
                cursor.execute("SELECT is_ready FROM series_summary_state WHERE id = 1")
                state = cursor.fetchone()
                if state and int(state['is_ready'] or 0):
                    return False

            cursor.execute("SHOW FULL COLUMNS FROM books WHERE Field = 'series_name'")
            source_column = cursor.fetchone()
            source_collation = source_column.get('Collation') if source_column else None
            cursor.execute("SHOW FULL COLUMNS FROM series_summary WHERE Field = 'sort_series_name'")
            summary_column = cursor.fetchone()
            summary_collation = summary_column.get('Collation') if summary_column else None
            if (
                source_collation
                and source_collation != summary_collation
                and re.fullmatch(r'[A-Za-z0-9_]+', source_collation)
            ):
                cursor.execute("""
                    INSERT INTO series_summary_state (id, is_ready, refreshed_at)
                    VALUES (1, 0, NULL)
                    ON DUPLICATE KEY UPDATE is_ready = 0
                """)
                cursor.execute("DELETE FROM series_summary")
                conn.commit()
                cursor.execute(f"""
                    ALTER TABLE series_summary
                    MODIFY series_key VARCHAR(500) COLLATE {source_collation} NOT NULL,
                    MODIFY sort_series_name VARCHAR(500) COLLATE {source_collation} NOT NULL DEFAULT ''
                """)

            cursor.execute("DELETE FROM series_summary")
            cursor.execute("""
                INSERT INTO series_summary (
                    library_id, series_key, representative_book_id,
                    series_book_count, sort_series_name
                )
                SELECT rep.library_id, rep.series_key, rep.rep_id,
                       rep.series_book_count, COALESCE(b.series_name, '')
                FROM (
                    SELECT b2.library_id,
                           COALESCE(NULLIF(b2.series_name, ''), b2.title) AS series_key,
                           COALESCE(
                               MIN(CASE WHEN b2.cover_image IS NOT NULL AND b2.cover_image != '' THEN b2.id END),
                               MIN(b2.id)
                           ) AS rep_id,
                           COUNT(*) AS series_book_count
                    FROM books b2
                    WHERE (b2.is_deleted = 0 OR b2.is_deleted IS NULL)
                    GROUP BY b2.library_id, COALESCE(NULLIF(b2.series_name, ''), b2.title)
                ) rep
                INNER JOIN books b ON b.id = rep.rep_id
            """)
            cursor.execute("""
                INSERT INTO series_summary_state (id, is_ready, refreshed_at)
                VALUES (1, 1, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE is_ready = 1, refreshed_at = CURRENT_TIMESTAMP
            """)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            if lock_acquired:
                try:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                except Exception:
                    pass
            conn.close()

    @staticmethod
    def _fetch_summary_rows(db_type, library_id, user_id, role, limit, offset, favorite_user_id, sort='asc'):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT is_ready FROM series_summary_state WHERE id = 1")
            state = cursor.fetchone()
            if not state or not int(state['is_ready'] or 0):
                return None

            where = []
            params = [favorite_user_id]
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    where.append("s.library_id = %s")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = s.library_id AND p.user_id = %s AND p.has_access = 1)"
                )
                params.append(user_id)

            sql = """
                SELECT b.id, b.series_name, b.series_alias, b.title, b.title_alias,
                       b.author, b.file_path, b.file_format, b.cover_image, b.cover_updated_at,
                       EXISTS (
                           SELECT 1 FROM user_favorites uf
                           WHERE uf.book_id = b.id AND uf.user_id = %s
                       ) AS is_favorite,
                       b.created_at, b.genre, b.tags, b.library_id,
                       COALESCE(b.metadata_locked, 0) AS metadata_locked,
                       s.series_book_count
                FROM series_summary s
                INNER JOIN books b ON b.id = s.representative_book_id
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            # sort='desc'일 때 SQL 자체를 내림차순으로 뒤집는다 - 예전에는 항상 오름차순으로
            # LIMIT/OFFSET을 적용한 뒤 호출부에서 그 결과만 파이썬으로 재정렬해서, 페이지 1을
            # 넘어가면 SQL이 애초에 오름차순 기준 행 구간을 가져와버려 결과가 뒤죽박죽이었다.
            title_dir = 'DESC' if str(sort or 'asc').lower() == 'desc' else 'ASC'
            sql += f" ORDER BY s.library_id ASC, s.sort_series_name {title_dir}, s.representative_book_id ASC"
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET %s"
                    params.append(int(offset))
            cursor.execute(sql, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _fetch_summary_totals(db_type, library_id, user_id, role):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT is_ready FROM series_summary_state WHERE id = 1")
            state = cursor.fetchone()
            if not state or not int(state['is_ready'] or 0):
                return None

            where = []
            params = []
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    where.append("s.library_id = %s")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = s.library_id AND p.user_id = %s AND p.has_access = 1)"
                )
                params.append(user_id)

            sql = """
                SELECT COUNT(*) AS total_series_count,
                       COALESCE(SUM(s.series_book_count), 0) AS total_book_count
                FROM series_summary s
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            return {
                'total_series_count': int(row['total_series_count'] or 0) if row else 0,
                'total_book_count': int(row['total_book_count'] or 0) if row else 0,
            }
        finally:
            conn.close()

    @staticmethod
    def fetch_books_for_grouping(db_type, library_id, search_query='', favorite_only=False, genre_filters=None, tag_filters=None, user_id=None, role=None, limit=None, offset=None, sort='asc'):
        """시리즈 그룹핑 렌더링에 필요한 기본 도서 레코드 목록 조회 (MariaDB Native)"""
        safe_user_id = int(user_id) if user_id is not None and int(user_id) > 0 else 1
        genre_filters = [str(v).strip() for v in (genre_filters or []) if str(v).strip()]
        tag_filters = [str(v).strip() for v in (tag_filters or []) if str(v).strip()]
        search_mode, search_term = parse_series_search_query(search_query)
        title_dir = 'DESC' if str(sort or 'asc').lower() == 'desc' else 'ASC'

        if db_type not in ('audiobook', 'video') and not search_query and not favorite_only and not genre_filters and not tag_filters:
            try:
                summary_rows = SeriesRepository._fetch_summary_rows(
                    db_type, library_id, user_id, role, limit, offset, safe_user_id, sort=sort
                )
                if summary_rows is not None:
                    return summary_rows
            except Exception:
                pass

        if db_type == 'audiobook':
            where = ["COALESCE(a.is_deleted, 0) = 0"]
            params = [safe_user_id]
            if favorite_only:
                where.append("a.is_favorite = 1")
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    lib_id_val = int(library_id)
                    where.append("a.library_id = %s")
                    params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode == 'author':
                    where.append("LOWER(COALESCE(a.author, '')) LIKE %s")
                    params.append(f"%{search_term.lower()}%")
                else:
                    where.append("LOWER(COALESCE(a.title, '')) LIKE %s")
                    params.append(f"%{search_term.lower()}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS ("
                    "SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = a.library_id AND p.user_id = %s AND p.has_access = 1"
                    ")"
                )
                params.append(user_id)

            sql = f"""
                SELECT a.id, a.title AS series_name, '' AS series_alias, a.title, '' AS title_alias,
                       a.author, a.folder_path AS file_path, 'audiobook' AS file_format,
                       CONCAT('/api/media/audiobooks/', a.id, '/cover') AS cover_image,
                       a.updated_at AS cover_updated_at,
                       COALESCE(a.is_favorite, 0) AS is_favorite,
                       a.created_at, '' AS genre, '' AS tags, a.library_id, 0 AS metadata_locked,
                       COALESCE(a.total_tracks, 0) AS total_tracks,
                       COALESCE((
                           SELECT MAX(ap.is_completed) FROM audiobook_progress ap
                           WHERE ap.audiobook_id = a.id AND ap.user_id = %s
                       ), 0) AS is_completed,
                       1 AS series_book_count
                FROM audiobooks a
                WHERE {' AND '.join(where)}
                ORDER BY a.library_id ASC, a.title {title_dir}, a.id ASC
            """
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET %s"
                    params.append(int(offset))
        elif db_type == 'video':
            where = ["COALESCE(v.is_deleted, 0) = 0"]
            params = [safe_user_id]
            if favorite_only:
                where.append("v.is_favorite = 1")
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    lib_id_val = int(library_id)
                    where.append("v.library_id = %s")
                    params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode == 'author':
                    where.append("1 = 0")
                else:
                    where.append("LOWER(COALESCE(v.title, '')) LIKE %s")
                    params.append(f"%{search_term.lower()}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS ("
                    "SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = v.library_id AND p.user_id = %s AND p.has_access = 1"
                    ")"
                )
                params.append(user_id)

            sql = f"""
                SELECT v.id, v.title AS series_name, '' AS series_alias, v.title, '' AS title_alias,
                       '' AS author, v.folder_path AS file_path, 'video' AS file_format,
                       CONCAT('/api/media/videos/', v.id, '/cover') AS cover_image,
                       v.updated_at AS cover_updated_at,
                       COALESCE(v.is_favorite, 0) AS is_favorite,
                       v.created_at, v.genres AS genre, '' AS tags, v.library_id, 0 AS metadata_locked,
                       COALESCE(v.total_episodes, 0) AS total_tracks,
                       COALESCE((
                           SELECT MAX(vp.is_completed) FROM video_progress vp
                           WHERE vp.video_id = v.id AND vp.user_id = %s
                       ), 0) AS is_completed,
                       1 AS series_book_count
                FROM videos v
                WHERE {' AND '.join(where)}
                ORDER BY v.library_id ASC, v.title {title_dir}, v.id ASC
            """
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET %s"
                    params.append(int(offset))
        else:
            sub_where = ["(b2.is_deleted = 0 OR b2.is_deleted IS NULL)"]
            sub_params = []
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    lib_id_val = int(library_id)
                    sub_where.append("b2.library_id = %s")
                    sub_params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass

            if role != 'admin' and user_id:
                sub_where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p WHERE p.library_id = b2.library_id AND p.user_id = %s AND p.has_access = 1)"
                )
                sub_params.append(user_id)

            if search_query:
                if not search_term:
                    sub_where.append("1 = 0")
                elif search_mode == 'author':
                    sub_where.append("LOWER(COALESCE(b2.author, '')) LIKE %s")
                    sub_params.append(f"%{search_term.lower()}%")
                else:
                    like = f"%{search_term.lower()}%"
                    sub_where.append(
                        "(LOWER(COALESCE(b2.title, '')) LIKE %s "
                        "OR LOWER(COALESCE(b2.title_alias, '')) LIKE %s "
                        "OR LOWER(COALESCE(b2.series_name, '')) LIKE %s "
                        "OR LOWER(COALESCE(b2.series_alias, '')) LIKE %s)"
                    )
                    sub_params.extend([like, like, like, like])

            for genre in genre_filters:
                compact = genre.replace(' ', '')
                sub_where.append("CONCAT(',', REPLACE(COALESCE(b2.genre, ''), ' ', ''), ',') LIKE %s")
                sub_params.append(f"%,{compact},%")

            for tag in tag_filters:
                compact = tag.replace(' ', '')
                sub_where.append("CONCAT(',', REPLACE(COALESCE(b2.tags, ''), ' ', ''), ',') LIKE %s")
                sub_params.append(f"%,{compact},%")

            sub_join = ""
            if role != 'admin' and user_id:
                sub_join = " JOIN user_category_permissions p ON p.library_id = b2.library_id AND p.user_id = %s AND p.has_access = 1 "
                sub_params = [user_id] + sub_params

            outer_where = ["(b.is_deleted = 0 OR b.is_deleted IS NULL)"]
            params = list(sub_params)
            if favorite_only:
                outer_where.append("EXISTS (SELECT 1 FROM user_favorites uf WHERE uf.book_id = b.id AND uf.user_id = %s)")
                params.append(safe_user_id)

            sql = f"""
                SELECT b.id, b.series_name, b.series_alias, b.title, b.title_alias, b.author, b.file_path, b.file_format,
                       b.cover_image, b.cover_updated_at,
                       0 AS is_favorite,
                       b.created_at,
                       b.genre, b.tags, b.library_id, COALESCE(b.metadata_locked, 0) AS metadata_locked,
                       rep.series_book_count AS series_book_count
                FROM books b
                INNER JOIN (
                    SELECT COALESCE(
                        MIN(CASE WHEN b2.cover_image IS NOT NULL AND b2.cover_image != '' THEN b2.id END),
                        MIN(b2.id)
                    ) AS rep_id,
                    COUNT(*) AS series_book_count
                    FROM books b2
                    {sub_join}
                    WHERE {' AND '.join(sub_where)}
                    GROUP BY b2.library_id, COALESCE(NULLIF(b2.series_name, ''), b2.title)
                ) rep ON b.id = rep.rep_id
                WHERE {' AND '.join(outer_where)}
                ORDER BY b.library_id ASC, b.series_name {title_dir}, b.id ASC
            """

            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET %s"
                    params.append(int(offset))

        from repositories.mariadb.user_repository import UserRepository
        fav_set = UserRepository.get_user_favorite_book_ids(db_type, safe_user_id) if safe_user_id else set()

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                item = dict(row)
                if db_type not in ('audiobook', 'video'):
                    item['is_favorite'] = 1 if item['id'] in fav_set else 0
                result.append(item)
            return result
        finally:
            conn.close()

    @staticmethod
    def fetch_grouping_totals(db_type, library_id, search_query='', favorite_only=False, genre_filters=None, tag_filters=None, user_id=None, role=None):
        safe_user_id = int(user_id) if user_id is not None and int(user_id) > 0 else 1
        genre_filters = [str(value).strip() for value in (genre_filters or []) if str(value).strip()]
        tag_filters = [str(value).strip() for value in (tag_filters or []) if str(value).strip()]
        search_mode, search_term = parse_series_search_query(search_query)

        if db_type not in ('audiobook', 'video') and not search_query and not favorite_only and not genre_filters and not tag_filters:
            try:
                summary_totals = SeriesRepository._fetch_summary_totals(db_type, library_id, user_id, role)
                if summary_totals is not None:
                    return summary_totals
            except Exception:
                pass

        if db_type == 'audiobook':
            where = ["COALESCE(a.is_deleted, 0) = 0"]
            params = []
            if favorite_only:
                where.append("a.is_favorite = 1")
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    where.append("a.library_id = %s")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode == 'author':
                    where.append("LOWER(COALESCE(a.author, '')) LIKE %s")
                    params.append(f"%{search_term.lower()}%")
                else:
                    where.append("LOWER(COALESCE(a.title, '')) LIKE %s")
                    params.append(f"%{search_term.lower()}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = a.library_id AND p.user_id = %s AND p.has_access = 1)"
                )
                params.append(user_id)
            sql = f"""
                SELECT COUNT(*) AS total_series_count, COUNT(*) AS total_book_count
                FROM audiobooks a
                WHERE {' AND '.join(where)}
            """
        elif db_type == 'video':
            where = ["COALESCE(v.is_deleted, 0) = 0"]
            params = []
            if favorite_only:
                where.append("v.is_favorite = 1")
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    where.append("v.library_id = %s")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode == 'author':
                    where.append("1 = 0")
                else:
                    where.append("LOWER(COALESCE(v.title, '')) LIKE %s")
                    params.append(f"%{search_term.lower()}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = v.library_id AND p.user_id = %s AND p.has_access = 1)"
                )
                params.append(user_id)
            sql = f"""
                SELECT COUNT(*) AS total_series_count, COUNT(*) AS total_book_count
                FROM videos v
                WHERE {' AND '.join(where)}
            """
        else:
            sub_where = ["(b2.is_deleted = 0 OR b2.is_deleted IS NULL)"]
            sub_params = []
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    sub_where.append("b2.library_id = %s")
                    sub_params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if role != 'admin' and user_id:
                sub_where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = b2.library_id AND p.user_id = %s AND p.has_access = 1)"
                )
                sub_params.append(user_id)
            if search_query:
                if not search_term:
                    sub_where.append("1 = 0")
                elif search_mode == 'author':
                    sub_where.append("LOWER(COALESCE(b2.author, '')) LIKE %s")
                    sub_params.append(f"%{search_term.lower()}%")
                else:
                    like = f"%{search_term.lower()}%"
                    sub_where.append(
                        "(LOWER(COALESCE(b2.title, '')) LIKE %s OR LOWER(COALESCE(b2.title_alias, '')) LIKE %s "
                        "OR LOWER(COALESCE(b2.series_name, '')) LIKE %s OR LOWER(COALESCE(b2.series_alias, '')) LIKE %s)"
                    )
                    sub_params.extend([like, like, like, like])
            for genre in genre_filters:
                compact = genre.replace(' ', '')
                sub_where.append("CONCAT(',', REPLACE(COALESCE(b2.genre, ''), ' ', ''), ',') LIKE %s")
                sub_params.append(f"%,{compact},%")
            for tag in tag_filters:
                compact = tag.replace(' ', '')
                sub_where.append("CONCAT(',', REPLACE(COALESCE(b2.tags, ''), ' ', ''), ',') LIKE %s")
                sub_params.append(f"%,{compact},%")

            sub_join = ""
            if role != 'admin' and user_id:
                sub_join = " JOIN user_category_permissions p ON p.library_id = b2.library_id AND p.user_id = %s AND p.has_access = 1 "
                sub_params = [user_id] + sub_params
            outer_where = ["(b.is_deleted = 0 OR b.is_deleted IS NULL)"]
            params = list(sub_params)
            if favorite_only:
                outer_where.append("EXISTS (SELECT 1 FROM user_favorites uf WHERE uf.book_id = b.id AND uf.user_id = %s)")
                params.append(safe_user_id)
            sql = f"""
                SELECT COUNT(*) AS total_series_count,
                       COALESCE(SUM(rep.series_book_count), 0) AS total_book_count
                FROM books b
                INNER JOIN (
                    SELECT COALESCE(
                        MIN(CASE WHEN b2.cover_image IS NOT NULL AND b2.cover_image != '' THEN b2.id END),
                        MIN(b2.id)
                    ) AS rep_id,
                    COUNT(*) AS series_book_count
                    FROM books b2
                    {sub_join}
                    WHERE {' AND '.join(sub_where)}
                    GROUP BY b2.library_id, COALESCE(NULLIF(b2.series_name, ''), b2.title)
                ) rep ON b.id = rep.rep_id
                WHERE {' AND '.join(outer_where)}
            """

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            return {
                'total_series_count': int(row['total_series_count'] or 0) if row else 0,
                'total_book_count': int(row['total_book_count'] or 0) if row else 0,
            }
        finally:
            conn.close()
