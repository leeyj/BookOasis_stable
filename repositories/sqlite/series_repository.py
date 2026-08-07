# -*- coding: utf-8 -*-
"""
series_repository.py – 시리즈(Series) 데이터를 그룹화하고 추출하기 위한 데이터 액세스 레이어
"""
import time
import database

class SeriesRepository:
    @staticmethod
    def fetch_books_for_grouping(db_type, library_id, search_query='', favorite_only=False, user_id=None, role=None, limit=None, offset=None):
        """시리즈 그룹핑 렌더링에 필요한 기본 도서 레코드 목록 조회 (WAL 락 경합 시 지수 백오프 자동 재시도)"""
        safe_user_id = int(user_id) if user_id is not None and int(user_id) > 0 else 1

        if db_type == 'audiobook':
            where = ["COALESCE(a.is_deleted, 0) = 0"]
            params = []
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
                like = f"%{search_query}%"
                where.append("(a.title LIKE ? OR a.author LIKE ? OR a.description LIKE ?)")
                params.extend([like, like, like])
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
                       COALESCE(a.total_tracks, 0) AS total_tracks
                FROM audiobooks a
                WHERE {' AND '.join(where)}
                ORDER BY a.library_id ASC, a.title ASC, a.id ASC
            """
            if limit is not None:
                sql += " LIMIT ?"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET ?"
                    params.append(int(offset))
        else:
            where = ["(b.is_deleted = 0 OR b.is_deleted IS NULL)"]
            params = []

            if favorite_only:
                where.append("EXISTS (SELECT 1 FROM user_favorites uf WHERE uf.book_id = b.id AND uf.user_id = ?)")
                params.append(safe_user_id)

            if library_id and str(library_id) not in ('all', 'favorite', 'history', 'home'):
                try:
                    lib_id_val = int(library_id)
                    where.append("b.library_id = ?")
                    params.append(lib_id_val)
                except (ValueError, TypeError):
                    pass

            if search_query:
                like = f"%{search_query}%"
                where.append("(b.series_name LIKE ? OR b.title LIKE ? OR b.author LIKE ?)")
                params.extend([like, like, like])

            # 일반 사용자는 허용된 카테고리만 필터링
            if role != 'admin' and user_id:
                where.append(
                    "EXISTS ("
                    "SELECT 1 FROM user_category_permissions p "
                    "WHERE p.library_id = b.library_id AND p.user_id = ? AND p.has_access = 1"
                    ")"
                )
                params.append(user_id)

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
                    WHERE {' AND '.join(sub_where)}
                    GROUP BY b2.library_id, COALESCE(NULLIF(b2.series_name, ''), b2.title)
                ) rep ON b.id = rep.rep_id
                WHERE {' AND '.join(where)}
                ORDER BY b.library_id ASC, b.series_name ASC, b.id ASC
            """
            params = sub_params + params

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
                    if db_type != 'audiobook':
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
