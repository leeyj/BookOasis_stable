# -*- coding: utf-8 -*-
"""
permission_clause.py – books.library_id 기준 user_category_permissions 권한 체크용 SQL 절 빌더.
서비스 레이어에서 리포지토리 메서드로 넘길 EXISTS(...) 절 문자열을 한 곳에서 생성한다.
"""


def build_library_permission_clause(user_id=None, role=None, alias='books'):
    """
    관리자이거나 user_id가 없으면 권한 제약이 필요 없으므로 빈 절을 반환한다.
    Returns: (clause: str, params: list)
    """
    if role == 'admin' or not user_id:
        return '', []
    clause = (
        f" AND EXISTS ("
        f"SELECT 1 FROM user_category_permissions p "
        f"WHERE p.library_id = {alias}.library_id AND p.user_id = ? AND p.has_access = 1"
        f")"
    )
    return clause, [user_id]
