# -*- coding: utf-8 -*-
"""
problem_card_service.py – 문제 카드 상세(카드 → 시리즈 줄 → 도서 목록) 조회

웹 알림센터(api/routes/problem_routes.py)와 MCP 도구(tools/mcp_server.py list_problems/get_problem_card)가
같은 함수를 부른다. 조치(재스캔 등)는 기존 스캔 API를 그대로 쓰므로 여기서는 화면에 필요한
대상 정보(scan_path, book_id)만 붙여 준다.
"""
import os

from services.problem_service import ProblemService, parse_context, to_iso

_LINE_LIMIT_MAX = 200
_ITEM_LIMIT_MAX = 200


def _split_series_key(series_key):
    if not series_key or '|' not in series_key:
        return None, None
    lib, name = series_key.split('|', 1)
    return (int(lib) if lib.isdigit() else None), name


def _library_roots(db_type, library_id):
    if library_id is None:
        return []
    try:
        from repositories.category_repository import CategoryRepository
        lib = CategoryRepository.get_library_by_id(db_type, library_id) or {}
        return [p.strip() for p in str(lib.get('physical_path') or '').replace('\r', '').split('\n') if p.strip()]
    except Exception as e:
        print(f"[ProblemCard] library lookup failed ({db_type}:{library_id}): {e}")
        return []


def relative_scan_path(roots, path):
    """카테고리 루트 기준 상대 경로 (scan-path API 인자). 루트 밖이면 None."""
    if not path:
        return None
    norm = str(path).replace('\\', '/')
    for root in roots:
        r = str(root).replace('\\', '/').rstrip('/')
        if norm == r:
            return ''
        if norm.startswith(r + '/'):
            return norm[len(r) + 1:]
    return None


def _series_totals(db_type, library_id, names):
    """시리즈 이름 → 그 시리즈 전체 권수 (휴지통 포함) - 'N권 전체 / M권 중 N권' 표시용."""
    names = [n for n in names if n is not None]
    if not names or library_id is None or db_type not in ('general', 'adult'):
        return {}
    import database
    totals = {}
    try:
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            for i in range(0, len(names), 200):
                chunk = names[i:i + 200]
                cursor.execute(
                    f"SELECT COALESCE(series_name, '') AS s, COUNT(*) AS n FROM books WHERE library_id = ? "
                    f"AND COALESCE(series_name, '') IN ({','.join('?' * len(chunk))}) GROUP BY COALESCE(series_name, '')",
                    (library_id, *chunk),
                )
                for r in cursor.fetchall():
                    totals[r['s']] = int(r['n'])
    except Exception as e:
        print(f"[ProblemCard] series totals failed: {e}")
    return totals


def _book_titles(db_type, book_ids):
    ids = [int(i) for i in book_ids]
    if not ids or db_type not in ('general', 'adult', 'audiobook', 'video'):
        return {}
    import database
    titles = {}
    try:
        table = {'audiobook': 'audiobooks', 'video': 'videos'}.get(db_type, 'books')
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, title FROM {table} WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
            for r in cursor.fetchall():
                titles[int(r['id'])] = r['title']
    except Exception as e:
        print(f"[ProblemCard] title lookup failed: {e}")
    return titles


def _find_card(group_key):
    for card in ProblemService.list_cards(include_muted=True):
        if card['group_key'] == group_key:
            return card
    return None


def get_card(group_key, offset=0, limit=50):
    """카드 + 시리즈 줄 목록. 카드가 없으면(이미 해결됨) None."""
    card = _find_card(group_key)
    if not card:
        return None
    limit = max(1, min(int(limit or 50), _LINE_LIMIT_MAX))
    offset = max(0, int(offset or 0))
    raw_lines = ProblemService.list_card_series(group_key, limit=limit + 1, offset=offset)
    has_more = len(raw_lines) > limit
    raw_lines = raw_lines[:limit]
    db_type = card.get('db_type') or 'general'
    library_id = card.get('library_id')
    roots = _library_roots(db_type, library_id)
    totals = _series_totals(db_type, library_id, [_split_series_key(l.get('series_key'))[1] for l in raw_lines])
    lines = []
    for line in raw_lines:
        _lib, series_name = _split_series_key(line.get('series_key'))
        count = int(line.get('open_count') or 0)
        sample_path = line.get('sample_path')
        folder = os.path.dirname(sample_path) if sample_path and line.get('target_type') == 'book' else None
        lines.append({
            'line_key': line.get('line_key'),
            'series_key': line.get('series_key'),
            'series_name': series_name,
            'target_type': line.get('target_type'),
            'open_count': count,
            'series_total': totals.get(series_name) if series_name is not None else None,
            'sample_path': sample_path,
            'scan_path': relative_scan_path(roots, folder) if folder else None,
            'single_target_id': line.get('sample_target_id') if count == 1 else None,
            'last_seen_at': to_iso(line.get('last_seen_ms')),
        })
    return {'card': card, 'lines': lines, 'offset': offset, 'has_more': has_more}


def get_card_items(group_key, series_key=None, offset=0, limit=50):
    card = _find_card(group_key)
    if not card:
        return None
    limit = max(1, min(int(limit or 50), _ITEM_LIMIT_MAX))
    offset = max(0, int(offset or 0))
    rows, total = ProblemService.list_card_items(group_key, series_key=series_key, limit=limit, offset=offset)
    db_type = card.get('db_type') or 'general'
    roots = _library_roots(db_type, card.get('library_id'))
    titles = _book_titles(db_type, [r['target_id'] for r in rows if r['target_type'] == 'book' and str(r['target_id']).isdigit()])
    items = []
    for r in rows:
        book_id = int(r['target_id']) if r['target_type'] == 'book' and str(r['target_id']).isdigit() else None
        path = r.get('target_path')
        items.append({
            'id': r['id'],
            'code': r['code'],
            'target_type': r['target_type'],
            'target_id': r['target_id'],
            'book_id': book_id,
            'title': titles.get(book_id) if book_id else None,
            'target_path': path,
            'file_name': os.path.basename(path) if path else None,
            'scan_path': relative_scan_path(roots, os.path.dirname(path)) if path and r['target_type'] == 'book' else None,
            'message': r.get('message') or '',
            'occurrence_count': int(r.get('occurrence_count') or 0),
            'first_seen_at': r.get('first_seen_at'),
            'last_seen_at': r.get('last_seen_at'),
        })
        if (card.get('plugin') or {}).get('id'):
            # 플러그인 문제: 플러그인이 준 문구 + 행별 조치(액션 RPC)
            ctx = parse_context(r.get('context'))
            items[-1]['title'] = items[-1]['title'] or r.get('title')
            items[-1]['detail'] = r.get('detail') or ''
            if ctx.get('action_id'):
                items[-1]['plugin_action'] = {'plugin_id': card['plugin']['id'], 'action_id': ctx['action_id'],
                                              'label': ctx.get('action_label') or ''}
    return {'card': card, 'items': items, 'total': total, 'offset': offset, 'limit': limit}
