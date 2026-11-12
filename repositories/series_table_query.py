# -*- coding: utf-8 -*-
"""관리자 테이블 뷰(시리즈 한 줄 = 표 한 행)의 조회 SQL - sqlite/mariadb series_repository 공용.

그리드의 요약 경로(_fetch_summary_rows)와 같은 기준이다: series_summary 한 행 + 그 대표 권(books) 한 행.
정렬·빈 값 필터도 대표 권의 값으로 한다 (메타 수정은 시리즈 전체 권에 같은 값을 쓰므로 대표 권이 곧 시리즈 값).

사용자가 보낸 정렬/필터 키는 아래 COLUMNS의 키로만 받는다 - 표현식은 전부 이 파일의 상수라
입력 문자열이 SQL에 그대로 들어가는 일이 없다.
"""
from repositories.series_search_query import parse_series_search_query

# kind: text(빈 문자열/NULL이 빈 값) | number(NULL/0이 빈 값) | fixed(빈 값 개념 없음)
# editable: 셀에서 고칠 수 있는 필드 (services/series_metadata_patch.py의 허용 필드와 같아야 한다)
COLUMNS = {
    'cover':              {'expr': 'b.cover_image',        'kind': 'text',   'sortable': False, 'missing': True,  'editable': False},
    'series_name':        {'expr': 's.sort_series_name',   'kind': 'fixed',  'sortable': True,  'missing': False, 'editable': False},
    'series_alias':       {'expr': 'b.series_alias',       'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'author':             {'expr': 'b.author',             'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'publisher':          {'expr': 'b.publisher',          'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'isbn':               {'expr': 'b.isbn',               'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'genre':              {'expr': 'b.genre',              'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'tags':               {'expr': 'b.tags',               'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'books_lv':           {'expr': 'b.books_lv',           'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    'publication_status': {'expr': 'b.publication_status', 'kind': 'text',   'sortable': True,  'missing': True,  'editable': True},
    # 설명은 긴 글이라 정렬하지 않는다. 표에서는 아이콘(있음/없음)으로 보이고 팝업에서 고친다
    'summary':            {'expr': 'b.summary',            'kind': 'text',   'sortable': False, 'missing': True,  'editable': True},
    'score':              {'expr': 'b.score',              'kind': 'number', 'sortable': True,  'missing': True,  'editable': False},
    'book_count':         {'expr': 's.series_book_count',  'kind': 'fixed',  'sortable': True,  'missing': False, 'editable': False},
    'file_format':        {'expr': 'b.file_format',        'kind': 'fixed',  'sortable': True,  'missing': False, 'editable': False},
    'latest_added':       {'expr': 's.latest_added',       'kind': 'fixed',  'sortable': True,  'missing': False, 'editable': False},
    'metadata_locked':    {'expr': 'COALESCE(b.metadata_locked, 0)', 'kind': 'fixed', 'sortable': True, 'missing': False, 'editable': False},
}

SORT_KEYS = tuple(key for key, col in COLUMNS.items() if col['sortable'])
MISSING_KEYS = tuple(key for key, col in COLUMNS.items() if col['missing'])
EDITABLE_KEYS = tuple(key for key, col in COLUMNS.items() if col['editable'])
DEFAULT_SORT = 'series_name'

SELECT_COLUMNS = """
    b.id AS representative_book_id, b.library_id, b.series_name, b.series_alias,
    b.author, b.publisher, b.isbn, b.genre, b.tags, b.books_lv, b.publication_status, b.summary,
    b.score, b.file_format, b.cover_image, b.cover_updated_at,
    COALESCE(b.metadata_locked, 0) AS metadata_locked,
    s.series_key, s.series_book_count AS book_count, s.latest_added
"""
FROM_CLAUSE = "FROM series_summary s INNER JOIN books b ON b.id = s.representative_book_id"

_SPECIAL_LIBRARY_IDS = ('all', 'favorite', 'history', 'home')


def normalize_sort_key(sort):
    value = str(sort or '').strip().lower()
    return value if value in SORT_KEYS else DEFAULT_SORT


def normalize_direction(direction):
    return 'DESC' if str(direction or '').strip().lower() == 'desc' else 'ASC'


def normalize_missing_keys(missing):
    """쉼표 문자열 또는 목록 → 허용된 빈 값 필터 키 목록 (모르는 키는 버리고, 순서·중복 정리)."""
    if isinstance(missing, str):
        missing = missing.split(',')
    result = []
    for raw in (missing or []):
        key = str(raw or '').strip().lower()
        if key in MISSING_KEYS and key not in result:
            result.append(key)
    return result


def _empty_expr(key):
    col = COLUMNS[key]
    if col['kind'] == 'number':
        return f"({col['expr']} IS NULL OR {col['expr']} = 0)"
    return f"({col['expr']} IS NULL OR {col['expr']} = '')"


def build_order_by(sort, direction):
    """정렬 키 → ORDER BY 본문. 값이 빈 행은 방향과 상관없이 뒤로 보낸다 (정리할 때 채워진 값부터 보이게)."""
    key = normalize_sort_key(sort)
    direction = normalize_direction(direction)
    rep = 's.representative_book_id'
    if key == 'series_name':
        # 그리드 가나다순과 같은 순서 - (library_id, sort_series_name, representative_book_id) 인덱스를 그대로 탄다
        return f"s.library_id ASC, s.sort_series_name {direction}, {rep} ASC"
    if key in ('book_count', 'latest_added'):
        # 동률도 같은 방향이어야 MariaDB 10.6(내림차순 인덱스 없음)이 인덱스를 거꾸로 읽는다 (series_list_options와 같은 이유)
        return f"{COLUMNS[key]['expr']} {direction}, {rep} {direction}"
    expr = COLUMNS[key]['expr']
    if COLUMNS[key]['kind'] in ('text', 'number'):
        # 비교식은 sqlite/mariadb 둘 다 0/1로 평가된다 - 빈 값(1)이 뒤로
        return f"{_empty_expr(key)} ASC, {expr} {direction}, {rep} ASC"
    return f"{expr} {direction}, {rep} ASC"


def build_where(dialect, library_id=None, missing=None, search='', genres=None, tags=None, filter_mode='and'):
    """반환: (조건 SQL 목록, 파라미터 목록). dialect: 'sqlite' | 'mariadb'."""
    ph = '?' if dialect == 'sqlite' else '%s'
    where, params = [], []

    if library_id is not None and str(library_id).strip().lower() not in _SPECIAL_LIBRARY_IDS and str(library_id).strip() != '':
        try:
            lib_id = int(library_id)
        except (ValueError, TypeError):
            lib_id = None
        if lib_id is not None:
            where.append(f"s.library_id = {ph}")
            params.append(lib_id)

    for key in normalize_missing_keys(missing):
        where.append(_empty_expr(key))

    mode, term = parse_series_search_query(search)
    term = term.lower()
    if str(search or '').strip():
        if not term:
            where.append("1 = 0")
        elif mode == 'author':
            where.append(f"LOWER(COALESCE(b.author, '')) LIKE {ph}")
            params.append(f"%{term}%")
        elif mode == 'cover_artist':
            where.append(f"LOWER(COALESCE(b.cover_artist, '')) LIKE {ph}")
            params.append(f"%{term}%")
        elif mode == 'topic':
            where.append(f"(LOWER(COALESCE(b.genre, '')) LIKE {ph} OR LOWER(COALESCE(b.tags, '')) LIKE {ph})")
            params.extend([f"%{term}%", f"%{term}%"])
        else:
            where.append(
                f"(LOWER(COALESCE(b.series_name, '')) LIKE {ph} "
                f"OR LOWER(COALESCE(b.series_alias, '')) LIKE {ph} "
                f"OR LOWER(COALESCE(b.author, '')) LIKE {ph})"
            )
            params.extend([f"%{term}%"] * 3)

    def token_match(expr):
        compact = f"REPLACE(COALESCE({expr}, ''), ' ', '')"
        if dialect == 'sqlite':
            return f"(',' || {compact} || ',') LIKE {ph}"
        return f"CONCAT(',', {compact}, ',') LIKE {ph}"

    topic_clauses, topic_params = [], []
    for expr, values in (('b.genre', genres), ('b.tags', tags)):
        for value in (values or []):
            compact = str(value or '').strip().replace(' ', '')
            if not compact:
                continue
            topic_clauses.append(token_match(expr))
            topic_params.append(f"%,{compact},%")
    if topic_clauses:
        joiner = ' OR ' if str(filter_mode or '').lower() == 'or' else ' AND '
        where.append('(' + joiner.join(topic_clauses) + ')')
        params.extend(topic_params)

    return where, params


def build_table_queries(dialect, library_id=None, sort=None, direction=None, missing=None, search='',
                        genres=None, tags=None, filter_mode='and', limit=None, offset=None):
    """반환: (행 SQL, 행 파라미터, 건수 SQL, 건수 파라미터)."""
    ph = '?' if dialect == 'sqlite' else '%s'
    where, params = build_where(dialect, library_id, missing, search, genres, tags, filter_mode)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    count_sql = f"SELECT COUNT(*) AS total {FROM_CLAUSE}{where_sql}"
    rows_sql = f"SELECT {SELECT_COLUMNS} {FROM_CLAUSE}{where_sql} ORDER BY {build_order_by(sort, direction)}"
    rows_params = list(params)
    if limit is not None:
        rows_sql += f" LIMIT {ph}"
        rows_params.append(int(limit))
        if offset is not None:
            rows_sql += f" OFFSET {ph}"
            rows_params.append(int(offset))
    return rows_sql, rows_params, count_sql, list(params)
