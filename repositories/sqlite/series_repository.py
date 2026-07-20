# -*- coding: utf-8 -*-
"""
series_repository.py – 시리즈(Series) 데이터를 그룹화하고 추출하기 위한 데이터 액세스 레이어
"""
import database

class SeriesRepository:
    @staticmethod
    def fetch_books_for_grouping(db_type, library_id, search_query='', favorite_only=False, user_id=None, role=None):
        """시리즈 그룹핑 렌더링에 필요한 기본 도서 레코드 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        safe_user_id = int(user_id) if user_id is not None else 0
        where = ["COALESCE(b.is_deleted, 0) = 0"]
        params = [safe_user_id]

        if favorite_only:
            where.append("uf.book_id IS NOT NULL")

        if library_id and library_id != 'all':
            where.append("b.library_id = ?")
            params.append(library_id)

        if search_query:
            like = f"%{search_query}%"
            where.append("(b.series_name LIKE ? OR b.author LIKE ?)")
            params.extend([like, like])

        # 일반 사용자는 허용된 카테고리만 필터링
        if role != 'admin' and user_id:
            where.append(
                "EXISTS ("
                "SELECT 1 FROM user_category_permissions p "
                "WHERE p.library_id = b.library_id AND p.user_id = ? AND p.has_access = 1"
                ")"
            )
            params.append(user_id)

        sql = f"""
            SELECT b.id, b.series_name, b.title, b.author, b.file_path, b.file_format,
                   b.cover_image, b.cover_updated_at,
                   CASE WHEN uf.book_id IS NULL THEN 0 ELSE 1 END AS is_favorite,
                   b.created_at,
                   b.genre, b.tags, b.library_id
            FROM books b
            LEFT JOIN user_favorites uf ON uf.book_id = b.id AND uf.user_id = ?
            WHERE {' AND '.join(where)}
            ORDER BY b.library_id ASC, b.series_name ASC, b.id ASC
        """
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
