"""큐에 등록할 배치 도서 스캔의 실제 대상 권 목록을 확정한다."""


def resolve_batch_book_scan_targets(cursor, requested_book_ids, scope='book'):
    """요청된 도서를 그대로(book) 또는 같은 시리즈의 모든 권으로 확장(series)해서 반환한다.

    시리즈 소속은 클라이언트가 보낸 시리즈명이 아니라 앵커 도서의 DB 값(library_id + series_name)으로
    확정한다 - 같은 시리즈명이 다른 라이브러리에 있어도 섞이지 않고, 삭제된 권은 제외된다.
    series_name이 없는 단행본은 확장 없이 앵커 자신만 대상이 된다.
    """
    if scope not in ('book', 'series'):
        raise ValueError('지원하지 않는 스캔 범위입니다.')

    placeholders = ', '.join('?' for _ in requested_book_ids)
    cursor.execute(
        f"SELECT id, library_id, title, series_name FROM books "
        f"WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 0",
        tuple(requested_book_ids),
    )
    anchor_rows = cursor.fetchall()
    found_ids = {int(row['id']) for row in anchor_rows}
    if found_ids != set(requested_book_ids):
        raise LookupError('요청한 도서 중 현재 데이터베이스에서 찾을 수 없는 항목이 있습니다.')
    if scope == 'book':
        return anchor_rows

    series_keys = set()
    for row in anchor_rows:
        series_name = str(row['series_name'] or '').strip()
        if series_name and row['library_id'] is not None:
            series_keys.add((row['library_id'], row['series_name']))

    conditions = []
    params = []
    for library_id, series_name in sorted(series_keys, key=lambda key: (str(key[0]), str(key[1]))):
        conditions.append('(library_id = ? AND series_name = ?)')
        params.extend((library_id, series_name))

    # 단행본은 그대로 유지하고, 선택한 앵커는 항상 포함되도록 보장한다.
    conditions.append(f"id IN ({', '.join('?' for _ in requested_book_ids)})")
    params.extend(requested_book_ids)
    cursor.execute(
        "SELECT id, library_id, title FROM books "
        f"WHERE COALESCE(is_deleted, 0) = 0 AND ({' OR '.join(conditions)}) "
        "ORDER BY id",
        tuple(params),
    )
    return cursor.fetchall()
