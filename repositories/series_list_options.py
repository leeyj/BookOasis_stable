"""도서 보관함 목록의 정렬/읽음 필터 옵션 - sqlite/mariadb series_repository 공용.

정렬 값
- asc/desc: 가나다 (폴더명에서 앞쪽 [태그]를 뗀 기준 - 서비스 계층에서 페이지 내 재정렬)
- folder_asc/folder_desc: 폴더 이름 그대로 ([태그] 포함 원본 series_name)
- date_desc/date_asc: 최신/과거 추가순
- count_desc/count_asc: 시리즈 도서 수 많은/적은 순
- score_desc: 별점(대표 도서 메타 score 0~100) 높은 순, 점수 없는 시리즈는 뒤로

읽음 필터 값 (시리즈의 모든 권을 완독해야 '읽음')
- exclude_read: 읽은 시리즈 제외
- only_read: 읽은 시리즈만
"""

SORT_VALUES = (
    'asc', 'desc',
    'folder_asc', 'folder_desc',
    'date_desc', 'date_asc',
    'count_desc', 'count_asc',
    'score_desc',
)
READ_FILTER_VALUES = ('exclude_read', 'only_read')


def normalize_sort(sort):
    value = str(sort or 'asc').strip().lower()
    return value if value in SORT_VALUES else 'asc'


def normalize_read_filter(read_filter):
    value = str(read_filter or '').strip().lower()
    return value if value in READ_FILTER_VALUES else ''


def is_score_sort(sort):
    return normalize_sort(sort) == 'score_desc'


def build_order_by(sort, *, lib_col, name_col, date_col, count_col, id_col, score_col=None, score_id_col=None):
    """정렬 값을 ORDER BY 절 본문으로 바꾼다 (기존 asc/desc/date 정렬은 예전과 같은 SQL)."""
    value = normalize_sort(sort)
    if value == 'score_desc':
        # (score, id) 인덱스를 거꾸로 읽어 LIMIT에서 멈추려면 정렬 열이 인덱스 열 그대로여야 한다.
        # 평점 열이 없는 목록(영상)은 점수가 없으니 최근 추가 순과 같게 둔다.
        if not score_col:
            return f"{id_col} DESC"
        return f"{score_col} DESC, {score_id_col or id_col} DESC"
    if value in ('date_asc', 'date_desc'):
        direction = 'DESC' if value == 'date_desc' else 'ASC'
        return f"{date_col} {direction}, {id_col} ASC"
    if value in ('count_desc', 'count_asc'):
        # 동률은 대표 도서 ID(=먼저/나중에 추가된 시리즈)로 같은 방향으로 정렬한다. 이름처럼 방향이
        # 섞이면 MariaDB 10.8 미만(내림차순 인덱스 미지원)에서 인덱스를 못 타고 시리즈 전체를
        # filesort한다 - 6.4만 시리즈에서 페이지마다 약 290ms(2026-10-10 홈 서버 ANALYZE 실측).
        # (series_book_count, representative_book_id) 인덱스를 정/역방향으로 그대로 쓴다.
        direction = 'DESC' if value == 'count_desc' else 'ASC'
        return f"{count_col} {direction}, {id_col} {direction}"
    direction = 'DESC' if value in ('desc', 'folder_desc') else 'ASC'
    return f"{lib_col} ASC, {name_col} {direction}, {id_col} ASC"


def build_read_series_filter(read_filter, read_keys, *, lib_col, key_col, placeholder):
    """다 읽은 시리즈 목록({library_id: {series_key, ...}})으로 WHERE 조건을 만든다.

    반환: (조건 SQL 또는 None, 파라미터 목록). 읽은 시리즈가 없으면 '읽은 도서만'은
    아무것도 안 나오게(1 = 0), '읽은 도서 제외'는 조건 없이 전부 보여 준다."""
    value = normalize_read_filter(read_filter)
    if not value:
        return None, []

    clauses = []
    params = []
    for library_id in sorted((read_keys or {}).keys()):
        keys = sorted(read_keys[library_id])
        if not keys:
            continue
        marks = ','.join([placeholder] * len(keys))
        clauses.append(f"({lib_col} = {placeholder} AND {key_col} IN ({marks}))")
        params.append(int(library_id))
        params.extend(keys)

    if not clauses:
        return ("1 = 0", []) if value == 'only_read' else (None, [])

    joined = '(' + ' OR '.join(clauses) + ')'
    return (joined if value == 'only_read' else f"NOT {joined}"), params


def build_completed_exists(read_filter, *, progress_table, id_col, row_id_col, placeholder):
    """오디오북/영상처럼 한 행이 곧 한 작품인 목록용: 사용자가 완료한 작품만/제외 조건."""
    value = normalize_read_filter(read_filter)
    if not value:
        return None
    exists = (
        f"EXISTS (SELECT 1 FROM {progress_table} rp "
        f"WHERE rp.{id_col} = {row_id_col} AND rp.user_id = {placeholder} AND rp.is_completed = 1)"
    )
    return exists if value == 'only_read' else f"NOT {exists}"


def group_fully_read_series(done_rows, total_rows):
    """완독 권수(done_rows)와 전체 권수(total_rows)로 다 읽은 시리즈를 고른다.

    done_rows/total_rows: (library_id, series_key, count) 튜플들."""
    totals = {(int(lib), str(key)): int(cnt or 0) for lib, key, cnt in total_rows}
    result = {}
    for lib, key, done in done_rows:
        total = totals.get((int(lib), str(key)), 0)
        if total > 0 and int(done or 0) >= total:
            result.setdefault(int(lib), set()).add(str(key))
    return result
