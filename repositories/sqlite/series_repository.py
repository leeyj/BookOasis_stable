# -*- coding: utf-8 -*-
"""
series_repository.py – 시리즈(Series) 데이터를 그룹화하고 추출하기 위한 데이터 액세스 레이어
"""
import time
import database
from repositories.series_metadata_utils import book_metadata_select_expr
from repositories.series_search_query import parse_series_search_query

class SeriesRepository:
    @staticmethod
    def rebuild_summary(db_type, only_if_unready=False):
        """현재 books 데이터를 기준으로 시리즈 요약 테이블(series_summary)을 재생성한다.

        MariaDB 백엔드는 이 요약 테이블을 이미 사용해 목록 조회를 상수 시간에 가깝게
        처리하는데, SQLite 쪽은 이 함수가 그동안 스텁(return False)이라 매 목록 요청마다
        books 테이블 전체를 GROUP BY로 실시간 재집계했다 - 대형 라이브러리(수만 권)에서
        요청마다 수 초가 걸리는 원인이었다. 스키마의 series_summary/series_summary_state
        테이블 자체는 이미 존재했으므로(services/db_migration_service.py) 채우는 로직만
        MariaDB 쪽 구현을 그대로 이식한다."""
        if db_type in ('audiobook', 'video'):
            return False

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if only_if_unready:
                cursor.execute("SELECT is_ready FROM series_summary_state WHERE id = 1")
                state = cursor.fetchone()
                if state and int(state['is_ready'] or 0):
                    return False

            cursor.execute("DELETE FROM series_summary")
            cursor.execute("""
                INSERT INTO series_summary (
                    library_id, series_key, representative_book_id,
                    series_book_count, sort_series_name, latest_added
                )
                SELECT rep.library_id, rep.series_key, rep.rep_id,
                       rep.series_book_count, COALESCE(b.series_name, ''), rep.latest_added
                FROM (
                    SELECT b2.library_id,
                           COALESCE(NULLIF(b2.series_name, ''), b2.title) AS series_key,
                           COALESCE(
                               MIN(CASE WHEN b2.cover_image IS NOT NULL AND b2.cover_image != '' THEN b2.id END),
                               MIN(b2.id)
                           ) AS rep_id,
                           COUNT(*) AS series_book_count,
                           -- created_at이 NULL인 행이 하나라도 있으면 NOT NULL 컬럼 위반으로 재생성 전체가
                           -- 롤백돼 요약 테이블이 통째로 멈춘다(2026-09 홈 서버 실사례) - 빈 문자열로 대체.
                           COALESCE(MAX(b2.created_at), '') AS latest_added
                    FROM books b2
                    WHERE (b2.is_deleted = 0 OR b2.is_deleted IS NULL)
                    GROUP BY b2.library_id, COALESCE(NULLIF(b2.series_name, ''), b2.title)
                ) rep
                INNER JOIN books b ON b.id = rep.rep_id
            """)
            cursor.execute("""
                INSERT OR REPLACE INTO series_summary_state (id, is_ready, refreshed_at)
                VALUES (1, 1, CURRENT_TIMESTAMP)
            """)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _fetch_summary_rows(db_type, library_id, user_id, role, limit, offset, favorite_user_id, sort='asc', include_has_metadata=False):
        """series_summary가 준비돼 있으면 그걸로 목록을 조회, 아니면 None(호출측이 실시간
        GROUP BY 경로로 폴백)."""
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
                    where.append("s.library_id = ?")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if role != 'admin' and user_id:
                # MariaDB에서 확인된 것과 동일한 이유(라이브러리별 상관관계 EXISTS는 정렬 인덱스
                # 기반 조기 LIMIT을 막을 수 있음) - 권한 있는 library_id를 먼저 뽑아 정적 IN
                # 목록으로 넘긴다.
                cursor.execute(
                    "SELECT library_id FROM user_category_permissions WHERE user_id = ? AND has_access = 1",
                    (user_id,)
                )
                allowed_library_ids = [int(row['library_id']) for row in cursor.fetchall()]
                if not allowed_library_ids:
                    return []
                placeholders = ','.join(['?'] * len(allowed_library_ids))
                where.append(f"s.library_id IN ({placeholders})")
                params.extend(allowed_library_ids)

            sql = f"""
                SELECT b.id, b.series_name, b.series_alias, b.title, b.title_alias, b.author,
                       b.file_path, b.file_format, b.cover_image, b.cover_updated_at,
                       COALESCE(b.cover_align, 'center') AS cover_align,
                       0 AS is_favorite,
                       b.created_at, b.genre, b.tags, b.books_lv, b.publication_status, b.library_id,
                       COALESCE(b.metadata_locked, 0) AS metadata_locked,
                       {book_metadata_select_expr('b', include_has_metadata)} AS has_metadata,
                       s.series_book_count, s.latest_added AS series_latest_added
                FROM series_summary s
                INNER JOIN books b ON b.id = s.representative_book_id
            """
            if where:
                sql += " WHERE " + " AND ".join(where)

            sort_norm = str(sort or 'asc').lower()
            if sort_norm in ('date_asc', 'date_desc'):
                date_dir = 'DESC' if sort_norm == 'date_desc' else 'ASC'
                sql += f" ORDER BY s.latest_added {date_dir}, s.representative_book_id ASC"
            else:
                title_dir = 'DESC' if sort_norm == 'desc' else 'ASC'
                sql += f" ORDER BY s.library_id ASC, s.sort_series_name {title_dir}, s.representative_book_id ASC"

            if limit is not None:
                sql += " LIMIT ?"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET ?"
                    params.append(int(offset))

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            from repositories.sqlite.user_repository import UserRepository
            fav_set = UserRepository.get_user_favorite_book_ids(db_type, favorite_user_id) if favorite_user_id else set()
            result = []
            for row in rows:
                item = dict(row)
                item['is_favorite'] = 1 if item['id'] in fav_set else 0
                result.append(item)
            return result
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
                    where.append("s.library_id = ?")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if role != 'admin' and user_id:
                cursor.execute(
                    "SELECT library_id FROM user_category_permissions WHERE user_id = ? AND has_access = 1",
                    (user_id,)
                )
                allowed_library_ids = [int(row['library_id']) for row in cursor.fetchall()]
                if not allowed_library_ids:
                    return {'total_series_count': 0, 'total_book_count': 0}
                placeholders = ','.join(['?'] * len(allowed_library_ids))
                where.append(f"s.library_id IN ({placeholders})")
                params.extend(allowed_library_ids)

            sql = "SELECT COUNT(*) AS total_series_count, COALESCE(SUM(s.series_book_count), 0) AS total_book_count FROM series_summary s"
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
    def fetch_books_for_grouping(db_type, library_id, search_query='', favorite_only=False, genre_filters=None, tag_filters=None, user_id=None, role=None, limit=None, offset=None, sort='asc', include_has_metadata=False):
        """시리즈 그룹핑 렌더링에 필요한 기본 도서 레코드 목록 조회 (WAL 락 경합 시 지수 백오프 자동 재시도)

        sort='desc'일 때 SQL 자체를 제목 내림차순으로 뒤집는다. 예전에는 항상 오름차순으로
        SQL LIMIT/OFFSET을 적용한 뒤 호출부(series_service.py)에서 그 결과만 파이썬으로
        재정렬했는데, 페이지 1을 넘어가면 애초에 SQL이 오름차순 기준으로 잘못된(=오름차순
        페이지의) 행 구간을 가져와버려서 내림차순 결과가 뒤죽박죽 나오는 버그가 있었다.
        (제목의 특수문자 때문이 아니라 페이지네이션 방향 자체가 항상 오름차순으로 고정돼 있던
        구조적 버그 — library_id/id는 보조 정렬 기준이라 그대로 오름차순 유지)"""
        safe_user_id = int(user_id) if user_id is not None and int(user_id) > 0 else 1
        genre_filters = [str(v).strip() for v in (genre_filters or []) if str(v).strip()]
        tag_filters = [str(v).strip() for v in (tag_filters or []) if str(v).strip()]
        search_mode, search_term = parse_series_search_query(search_query)
        sort_norm = str(sort or 'asc').lower()
        is_date_sort = sort_norm in ('date_asc', 'date_desc')
        title_dir = 'DESC' if sort_norm == 'desc' else 'ASC'
        date_dir = 'DESC' if sort_norm == 'date_desc' else 'ASC'

        if db_type not in ('audiobook', 'video') and not search_query and not favorite_only and not genre_filters and not tag_filters:
            try:
                summary_rows = SeriesRepository._fetch_summary_rows(
                    db_type, library_id, user_id, role, limit, offset, safe_user_id, sort=sort,
                    include_has_metadata=include_has_metadata
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
                    where.append("a.library_id = ?")
                    params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode == 'author':
                    where.append("COALESCE(a.author, '') LIKE ?")
                    params.append(f"%{search_term}%")
                elif search_mode in ('cover_artist', 'topic'):
                    where.append("1 = 0")
                else:
                    where.append("COALESCE(a.title, '') LIKE ?")
                    params.append(f"%{search_term}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS ("
                    "SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = a.library_id AND p.user_id = ? AND p.has_access = 1"
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
                           WHERE ap.audiobook_id = a.id AND ap.user_id = ?
                       ), 0) AS is_completed
                FROM audiobooks a
                WHERE {' AND '.join(where)}
                ORDER BY {"a.created_at " + date_dir if is_date_sort else "a.library_id ASC, a.title " + title_dir}, a.id ASC
            """
            if limit is not None:
                sql += " LIMIT ?"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET ?"
                    params.append(int(offset))
        elif db_type == 'video':
            where = ["COALESCE(v.is_deleted, 0) = 0"]
            params = [safe_user_id]
            if favorite_only:
                where.append("v.is_favorite = 1")
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    lib_id_val = int(library_id)
                    where.append("v.library_id = ?")
                    params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode in ('author', 'cover_artist', 'topic'):
                    where.append("1 = 0")
                else:
                    where.append("COALESCE(v.title, '') LIKE ?")
                    params.append(f"%{search_term}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS ("
                    "SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = v.library_id AND p.user_id = ? AND p.has_access = 1"
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
                           WHERE vp.video_id = v.id AND vp.user_id = ?
                       ), 0) AS is_completed
                FROM videos v
                WHERE {' AND '.join(where)}
                ORDER BY {"v.created_at " + date_dir if is_date_sort else "v.library_id ASC, v.title " + title_dir}, v.id ASC
            """
            if limit is not None:
                sql += " LIMIT ?"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET ?"
                    params.append(int(offset))
        else:
            sub_where = ["(b2.is_deleted = 0 OR b2.is_deleted IS NULL)"]
            sub_params = []
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    lib_id_val = int(library_id)
                    sub_where.append("b2.library_id = ?")
                    sub_params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass

            if role != 'admin' and user_id:
                sub_where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p WHERE p.library_id = b2.library_id AND p.user_id = ? AND p.has_access = 1)"
                )
                sub_params.append(user_id)

            if search_query:
                if not search_term:
                    sub_where.append("1 = 0")
                elif search_mode == 'author':
                    sub_where.append("COALESCE(b2.author, '') LIKE ?")
                    sub_params.append(f"%{search_term}%")
                elif search_mode == 'cover_artist':
                    sub_where.append("COALESCE(b2.cover_artist, '') LIKE ?")
                    sub_params.append(f"%{search_term}%")
                elif search_mode == 'topic':
                    sub_where.append("(COALESCE(b2.genre, '') LIKE ? OR COALESCE(b2.tags, '') LIKE ?)")
                    sub_params.extend([f"%{search_term}%", f"%{search_term}%"])
                else:
                    like = f"%{search_term}%"
                    sub_where.append(
                        "(COALESCE(b2.title, '') LIKE ? "
                        "OR COALESCE(b2.title_alias, '') LIKE ? "
                        "OR COALESCE(b2.series_name, '') LIKE ? "
                        "OR COALESCE(b2.series_alias, '') LIKE ?)"
                    )
                    sub_params.extend([like, like, like, like])

            for genre in genre_filters:
                compact = genre.replace(' ', '')
                sub_where.append("(',' || REPLACE(COALESCE(b2.genre, ''), ' ', '') || ',') LIKE ?")
                sub_params.append(f"%,{compact},%")

            for tag in tag_filters:
                compact = tag.replace(' ', '')
                sub_where.append("(',' || REPLACE(COALESCE(b2.tags, ''), ' ', '') || ',') LIKE ?")
                sub_params.append(f"%,{compact},%")

            sub_join = ""
            if role != 'admin' and user_id:
                sub_join = " JOIN user_category_permissions p ON p.library_id = b2.library_id AND p.user_id = ? AND p.has_access = 1 "
                sub_params = [user_id] + sub_params

            outer_where = ["(b.is_deleted = 0 OR b.is_deleted IS NULL)"]
            params = list(sub_params)
            # 검색 결과 카드에 "왜 검색됐는지" 보여주기 위해 회차 제목이 일치한 권의 제목 하나를 내려준다.
            matched_title_expr = "NULL"
            if search_query and search_term and search_mode not in ('author', 'cover_artist', 'topic'):
                matched_title_expr = (
                    "MIN(CASE WHEN COALESCE(b2.title, '') LIKE ? OR COALESCE(b2.title_alias, '') LIKE ? "
                    "THEN COALESCE(NULLIF(b2.title_alias, ''), b2.title) END)"
                )
                params = [f"%{search_term}%", f"%{search_term}%"] + params
            if favorite_only:
                outer_where.append("EXISTS (SELECT 1 FROM user_favorites uf WHERE uf.book_id = b.id AND uf.user_id = ?)")
                params.append(safe_user_id)

            sql = f"""
                SELECT b.id, b.series_name, b.series_alias, b.title, b.title_alias, b.author, b.file_path, b.file_format,
                       b.cover_image, b.cover_updated_at, COALESCE(b.cover_align, 'center') AS cover_align,
                       0 AS is_favorite,
                       b.created_at,
                       b.genre, b.tags, b.books_lv, b.publication_status, b.library_id, COALESCE(b.metadata_locked, 0) AS metadata_locked,
                       {book_metadata_select_expr('b', include_has_metadata)} AS has_metadata,
                       rep.series_book_count AS series_book_count, rep.series_latest_added AS series_latest_added,
                       rep.matched_title AS matched_title
                FROM books b
                INNER JOIN (
                    SELECT COALESCE(
                        MIN(CASE WHEN b2.cover_image IS NOT NULL AND b2.cover_image != '' THEN b2.id END),
                        MIN(b2.id)
                    ) AS rep_id,
                    COUNT(*) AS series_book_count,
                    MAX(b2.created_at) AS series_latest_added,
                    {matched_title_expr} AS matched_title
                    FROM books b2
                    {sub_join}
                    WHERE {' AND '.join(sub_where)}
                    GROUP BY b2.library_id, COALESCE(NULLIF(b2.series_name, ''), b2.title)
                ) rep ON b.id = rep.rep_id
                WHERE {' AND '.join(outer_where)}
                ORDER BY {"rep.series_latest_added " + date_dir if is_date_sort else "b.library_id ASC, b.series_name " + title_dir}, b.id ASC
            """

            if limit is not None:
                sql += " LIMIT ?"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET ?"
                    params.append(int(offset))

        from repositories.sqlite.user_repository import UserRepository
        fav_set = UserRepository.get_user_favorite_book_ids(db_type, safe_user_id) if safe_user_id else set()

        max_attempts = 4
        for attempt in range(1, max_attempts + 1):
            conn = None
            try:
                conn = database.get_connection(db_type)
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    if db_type not in ('audiobook', 'video'):
                        item['is_favorite'] = 1 if item['id'] in fav_set else 0
                    result.append(item)
                conn.close()
                return result
            except Exception as e:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                err_str = str(e).lower()
                is_contention = ('malformed' in err_str or 'locked' in err_str or 'busy' in err_str)
                if is_contention and attempt < max_attempts:
                    wait_sec = 0.15 * attempt
                    print(f"[SeriesRepository] ⚠️ WAL read contention caught: {e}. Retrying ({attempt}/{max_attempts}) in {wait_sec:.2f}s...")
                    time.sleep(wait_sec)
                    continue
                raise e

    @staticmethod
    def fetch_recent_additions(db_type, days):
        """최근 N일 안에 추가된 권을 (library_id, series_name)별로 센다 - 목록 카드의
        "NEW / +N권" 배지용. created_at 기본값(CURRENT_TIMESTAMP)과 같은 시계로 기준 시각을
        DB에서 직접 계산해야 서버/DB 타임존 차이로 배지가 어긋나지 않는다.
        반환: (cutoff 문자열, [{library_id, series_name, cnt}, ...])"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT datetime('now', '-' || ? || ' days') AS cutoff", (int(days),))
            cutoff_row = cursor.fetchone()
            cutoff = cutoff_row['cutoff'] if cutoff_row else None
            if not cutoff:
                return None, []
            cursor.execute("""
                SELECT library_id, COALESCE(series_name, '') AS series_name, COUNT(*) AS cnt
                FROM books
                WHERE created_at >= ?
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                GROUP BY library_id, COALESCE(series_name, '')
            """, (cutoff,))
            return str(cutoff), [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def fetch_library_totals_bulk(db_type):
        """사이드바에 표시할 라이브러리별 시리즈 수/도서 권수를 한 번의 쿼리로 일괄 조회한다
        (검색/필터/권한 조건 없이 항목별 카운트만 필요 - 접근 가능 라이브러리 필터링은
        호출측(CategoryService.get_libraries)이 이미 처리한 목록에 병합하는 방식으로 적용됨)."""
        if db_type == 'audiobook':
            sql = """
                SELECT library_id,
                       COUNT(*) AS series_count,
                       COALESCE(SUM(total_tracks), 0) AS book_count
                FROM audiobooks
                WHERE COALESCE(is_deleted, 0) = 0
                GROUP BY library_id
            """
        elif db_type == 'video':
            sql = """
                SELECT library_id,
                       COUNT(*) AS series_count,
                       COALESCE(SUM(total_episodes), 0) AS book_count
                FROM videos
                WHERE COALESCE(is_deleted, 0) = 0
                GROUP BY library_id
            """
        else:
            sql = None

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if sql is None:
                try:
                    cursor.execute("SELECT is_ready FROM series_summary_state WHERE id = 1")
                    state = cursor.fetchone()
                    if state and int(state['is_ready'] or 0):
                        sql = """
                            SELECT library_id,
                                   COUNT(*) AS series_count,
                                   COALESCE(SUM(series_book_count), 0) AS book_count
                            FROM series_summary
                            GROUP BY library_id
                        """
                except Exception:
                    sql = None

                if sql is None:
                    sql = """
                        SELECT library_id, COUNT(*) AS series_count, COALESCE(SUM(cnt), 0) AS book_count
                        FROM (
                            SELECT b.library_id AS library_id,
                                   COALESCE(NULLIF(b.series_name, ''), b.title) AS series_key,
                                   COUNT(*) AS cnt
                            FROM books b
                            WHERE (b.is_deleted = 0 OR b.is_deleted IS NULL)
                            GROUP BY b.library_id, series_key
                        ) t
                        GROUP BY library_id
                    """
            cursor.execute(sql)
            rows = cursor.fetchall()
            return {
                int(row['library_id']): {
                    'series_count': int(row['series_count'] or 0),
                    'book_count': int(row['book_count'] or 0),
                }
                for row in rows if row['library_id'] is not None
            }
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
                    where.append("a.library_id = ?")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode == 'author':
                    where.append("COALESCE(a.author, '') LIKE ?")
                    params.append(f"%{search_term}%")
                elif search_mode in ('cover_artist', 'topic'):
                    where.append("1 = 0")
                else:
                    where.append("COALESCE(a.title, '') LIKE ?")
                    params.append(f"%{search_term}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = a.library_id AND p.user_id = ? AND p.has_access = 1)"
                )
                params.append(user_id)
            sql = f"""
                SELECT COUNT(*) AS total_series_count, COALESCE(SUM(a.total_tracks), 0) AS total_book_count
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
                    where.append("v.library_id = ?")
                    params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if search_query:
                if not search_term:
                    where.append("1 = 0")
                elif search_mode in ('author', 'cover_artist', 'topic'):
                    where.append("1 = 0")
                else:
                    where.append("COALESCE(v.title, '') LIKE ?")
                    params.append(f"%{search_term}%")
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = v.library_id AND p.user_id = ? AND p.has_access = 1)"
                )
                params.append(user_id)
            sql = f"""
                SELECT COUNT(*) AS total_series_count, COALESCE(SUM(v.total_episodes), 0) AS total_book_count
                FROM videos v
                WHERE {' AND '.join(where)}
            """
        else:
            sub_where = ["(b2.is_deleted = 0 OR b2.is_deleted IS NULL)"]
            sub_params = []
            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    sub_where.append("b2.library_id = ?")
                    sub_params.append(int(library_id))
                except (ValueError, TypeError):
                    pass
            if role != 'admin' and user_id:
                sub_where.append(
                    "EXISTS (SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = b2.library_id AND p.user_id = ? AND p.has_access = 1)"
                )
                sub_params.append(user_id)
            if search_query:
                if not search_term:
                    sub_where.append("1 = 0")
                elif search_mode == 'author':
                    sub_where.append("COALESCE(b2.author, '') LIKE ?")
                    sub_params.append(f"%{search_term}%")
                elif search_mode == 'cover_artist':
                    sub_where.append("COALESCE(b2.cover_artist, '') LIKE ?")
                    sub_params.append(f"%{search_term}%")
                elif search_mode == 'topic':
                    sub_where.append("(COALESCE(b2.genre, '') LIKE ? OR COALESCE(b2.tags, '') LIKE ?)")
                    sub_params.extend([f"%{search_term}%", f"%{search_term}%"])
                else:
                    like = f"%{search_term}%"
                    sub_where.append(
                        "(COALESCE(b2.title, '') LIKE ? OR COALESCE(b2.title_alias, '') LIKE ? "
                        "OR COALESCE(b2.series_name, '') LIKE ? OR COALESCE(b2.series_alias, '') LIKE ?)"
                    )
                    sub_params.extend([like, like, like, like])
            for genre in genre_filters:
                compact = genre.replace(' ', '')
                sub_where.append("(',' || REPLACE(COALESCE(b2.genre, ''), ' ', '') || ',') LIKE ?")
                sub_params.append(f"%,{compact},%")
            for tag in tag_filters:
                compact = tag.replace(' ', '')
                sub_where.append("(',' || REPLACE(COALESCE(b2.tags, ''), ' ', '') || ',') LIKE ?")
                sub_params.append(f"%,{compact},%")

            sub_join = ""
            if role != 'admin' and user_id:
                sub_join = " JOIN user_category_permissions p ON p.library_id = b2.library_id AND p.user_id = ? AND p.has_access = 1 "
                sub_params = [user_id] + sub_params
            outer_where = ["(b.is_deleted = 0 OR b.is_deleted IS NULL)"]
            params = list(sub_params)
            if favorite_only:
                outer_where.append("EXISTS (SELECT 1 FROM user_favorites uf WHERE uf.book_id = b.id AND uf.user_id = ?)")
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
