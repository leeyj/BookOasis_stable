# -*- coding: utf-8 -*-
"""e-paper 기기 피드(/opds-epaper/v1) 조회 - SQLite/MariaDB 공용 SQL (자리표시자만 다르다).

EPUB/TXT만 보이고, 관리자가 아닌 사용자에게는 카테고리 권한(user_category_permissions)을 적용한다.
권한 행이 하나도 없는 사용자는 전체를 본다(검색 피드와 같은 규칙).
"""
import database

FEED_FORMATS = ('epub', 'txt')
_BOOK_COLUMNS = 'b.id, b.title, b.author, b.series_name, b.summary, b.file_format, b.cover_image, b.library_id'


def _escape_like(term):
    return str(term).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def make_repository(ph):
    """ph: '?' (SQLite) 또는 '%s' (MariaDB)."""
    fmt_in = f"b.file_format IN ({','.join([ph] * len(FEED_FORMATS))})"
    base_where = f"COALESCE(b.is_deleted, 0) = 0 AND {fmt_in}"

    def _allowed_libraries(cursor, user_id, role):
        """None = 제한 없음, [] = 아무것도 못 봄."""
        if role == 'admin' or user_id is None:
            return None
        cursor.execute(f"SELECT library_id, has_access FROM user_category_permissions WHERE user_id = {ph}", (int(user_id),))
        rows = cursor.fetchall()
        if not rows:
            return None
        return [int(r['library_id']) for r in rows if int(r['has_access'] or 0) == 1]

    def _scope(cursor, user_id, role, where, params):
        allowed = _allowed_libraries(cursor, user_id, role)
        if allowed is None:
            return where, params, True
        if not allowed:
            return where, params, False
        return where + f" AND b.library_id IN ({','.join([ph] * len(allowed))})", params + allowed, True

    class EpaperFeedRepository:
        @staticmethod
        def list_libraries(db_type, user_id, role):
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                where, params, ok = _scope(cursor, user_id, role, base_where, list(FEED_FORMATS))
                if not ok:
                    return []
                cursor.execute(
                    f"SELECT l.id, l.name, COUNT(b.id) AS book_count FROM libraries l "
                    f"JOIN books b ON b.library_id = l.id "
                    f"WHERE COALESCE(l.pending_delete, 0) = 0 AND {where} "
                    f"GROUP BY l.id, l.name ORDER BY l.name, l.id", tuple(params))
                return [dict(r) for r in cursor.fetchall()]

        @staticmethod
        def can_view_library(db_type, lib_id, user_id, role):
            with database.connection(db_type) as conn:
                allowed = _allowed_libraries(conn.cursor(), user_id, role)
            return allowed is None or int(lib_id) in allowed

        @staticmethod
        def list_series(db_type, lib_id, user_id, role, limit, offset):
            """(rows, total). rows: series_name, book_count, cover_book_id"""
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                where, params, ok = _scope(cursor, user_id, role, base_where + f" AND b.library_id = {ph}",
                                           list(FEED_FORMATS) + [int(lib_id)])
                if not ok:
                    return [], 0
                cursor.execute(f"SELECT COUNT(DISTINCT COALESCE(b.series_name, '')) AS total FROM books b WHERE {where}",
                               tuple(params))
                total = int(cursor.fetchone()['total'] or 0)
                cursor.execute(
                    f"SELECT COALESCE(b.series_name, '') AS series_name, COUNT(b.id) AS book_count, "
                    f"COALESCE(MIN(CASE WHEN b.cover_image IS NOT NULL AND b.cover_image != '' THEN b.id END), MIN(b.id)) AS cover_book_id "
                    f"FROM books b WHERE {where} GROUP BY COALESCE(b.series_name, '') "
                    f"ORDER BY COALESCE(b.series_name, '') LIMIT {ph} OFFSET {ph}",
                    tuple(params + [int(limit), int(offset)]))
                return [dict(r) for r in cursor.fetchall()], total

        @staticmethod
        def list_books(db_type, lib_id, series_name, user_id, role, limit, offset):
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                cond = base_where + f" AND b.library_id = {ph}"
                params = list(FEED_FORMATS) + [int(lib_id)]
                if series_name:
                    cond += f" AND b.series_name = {ph}"
                    params.append(series_name)
                else:
                    cond += " AND (b.series_name IS NULL OR b.series_name = '')"
                where, params, ok = _scope(cursor, user_id, role, cond, params)
                if not ok:
                    return [], 0
                cursor.execute(f"SELECT COUNT(*) AS total FROM books b WHERE {where}", tuple(params))
                total = int(cursor.fetchone()['total'] or 0)
                cursor.execute(f"SELECT {_BOOK_COLUMNS} FROM books b WHERE {where} ORDER BY b.title, b.id LIMIT {ph} OFFSET {ph}",
                               tuple(params + [int(limit), int(offset)]))
                return [dict(r) for r in cursor.fetchall()], total

        @staticmethod
        def recently_added(db_type, user_id, role, limit, offset):
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                where, params, ok = _scope(cursor, user_id, role, base_where, list(FEED_FORMATS))
                if not ok:
                    return [], 0
                cursor.execute(f"SELECT {_BOOK_COLUMNS} FROM books b WHERE {where} "
                               f"ORDER BY b.created_at DESC, b.id DESC LIMIT {ph} OFFSET {ph}",
                               tuple(params + [int(limit), int(offset)]))
                return [dict(r) for r in cursor.fetchall()], None

        @staticmethod
        def recently_read(db_type, user_id, role, limit, offset):
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                where, params, ok = _scope(cursor, user_id, role, base_where + f" AND p.user_id = {ph}",
                                           list(FEED_FORMATS) + [int(user_id)])
                if not ok:
                    return [], 0
                cursor.execute(f"SELECT {_BOOK_COLUMNS} FROM user_progress p JOIN books b ON p.book_id = b.id "
                               f"WHERE {where} ORDER BY p.last_read_at DESC LIMIT {ph} OFFSET {ph}",
                               tuple(params + [int(limit), int(offset)]))
                return [dict(r) for r in cursor.fetchall()], None

        @staticmethod
        def search(db_type, query, user_id, role, limit, offset):
            terms = [t for t in str(query or '').split() if t][:10]
            if not terms:
                return [], 0
            cond = base_where
            params = list(FEED_FORMATS)
            for term in terms:
                like = f"%{_escape_like(term)}%"
                # MariaDB는 기본 이스케이프 문자가 백슬래시라 ESCAPE 절이 필요 없다
                esc = '' if ph == '%s' else " ESCAPE '\\'"
                cond += (f" AND (COALESCE(b.title, '') LIKE {ph}{esc} OR COALESCE(b.series_name, '') LIKE {ph}{esc} "
                         f"OR COALESCE(b.author, '') LIKE {ph}{esc})")
                params += [like, like, like]
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                where, params, ok = _scope(cursor, user_id, role, cond, params)
                if not ok:
                    return [], 0
                cursor.execute(f"SELECT COUNT(*) AS total FROM books b WHERE {where}", tuple(params))
                total = int(cursor.fetchone()['total'] or 0)
                cursor.execute(f"SELECT {_BOOK_COLUMNS} FROM books b WHERE {where} ORDER BY b.title, b.id LIMIT {ph} OFFSET {ph}",
                               tuple(params + [int(limit), int(offset)]))
                return [dict(r) for r in cursor.fetchall()], total

        @staticmethod
        def get_book(db_type, book_id, user_id, role):
            """다운로드·표지용 한 권 (권한·형식 검사 포함). 없으면 None."""
            with database.connection(db_type) as conn:
                cursor = conn.cursor()
                where, params, ok = _scope(cursor, user_id, role, base_where + f" AND b.id = {ph}",
                                           list(FEED_FORMATS) + [int(book_id)])
                if not ok:
                    return None
                cursor.execute(f"SELECT {_BOOK_COLUMNS}, b.file_path FROM books b WHERE {where}", tuple(params))
                row = cursor.fetchone()
                return dict(row) if row else None

    return EpaperFeedRepository
