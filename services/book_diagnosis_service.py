# -*- coding: utf-8 -*-
"""
book_diagnosis_service.py – 도서 1권 [진단] 체크리스트 (알림센터 5단계)

설계: docs/plan_unified_notification_queue.md 6장 / 8장 5단계.
웹(도서 메뉴·문제 카드의 [진단], api/routes/problem_routes.py)과 MCP 도구(tools/mcp_server.py diagnose_book)가
같은 함수를 부른다. 실패한 점검 항목이 곧 원인이고, 결론에 맞는 조치 버튼(재스캔)을 함께 돌려준다.

    ✓ DB 기록       도서 행이 있는가 / 휴지통에 있는가
    ✓ 원격 연결     카테고리 루트(마운트)가 살아 있는가
    ✗ 파일 존재     파일이 그 경로에 있는가
    ✓ 파일 형식     압축/PDF 머리말이 정상인가 (가벼운 확인만)
    → 결론 + 조치

진단은 읽기만 한다(아무것도 고치거나 지우지 않는다). 원격 드라이브가 멈춰 있어도 웹 요청이 붙잡히지
않도록 파일 시스템 점검은 시간 제한 안에서만 기다린다.
"""
import os
import threading
import zipfile
from datetime import datetime, timedelta

from services.problem_service import ProblemService, catalog_entry

DIAGNOSE_DB_TYPES = ('general', 'adult')
# GDrive(rclone) 첫 접근은 몇 초 걸린다(테스트 서버 실측: 루트+파일+형식 합계 약 8초) - 느림을 끊김으로 오판하지 않게 넉넉히.
FS_TIMEOUT_SECONDS = 15
TRASH_PURGE_DAYS = 7

OK, FAIL, WARN, SKIP = 'ok', 'fail', 'warn', 'skip'

_ZIP_FORMATS = ('zip', 'cbz', 'epub')


def _check(check_id, status, key, **vars_):
    return {'id': check_id, 'status': status, 'key': f'diagnose.check.{check_id}.{key}', 'vars': vars_}


def _with_timeout(fn, seconds=None):
    """fn()을 별도 스레드에서 돌려 seconds 안에 끝나면 (True, 결과), 아니면 (False, None).

    rclone 마운트가 멈추면 os.stat 자체가 오래 걸린다 - 그 스레드는 버려 두고(데몬) 요청은 바로 돌려준다."""
    box = {}

    def run():
        try:
            box['value'] = fn()
        except Exception as e:  # 점검 함수 안의 예외도 결과로 돌려준다
            box['error'] = e

    t = threading.Thread(target=run, daemon=True, name='book-diagnose-fs')
    t.start()
    t.join(FS_TIMEOUT_SECONDS if seconds is None else seconds)
    if t.is_alive():
        return False, None
    if 'error' in box:
        raise box['error']
    return True, box.get('value')


def _is_remote_url(path):
    return str(path or '').startswith(('gdrive:', 'gdrive://', 'http://', 'https://'))


def _load_book(db_type, book_id):
    import database
    with database.connection(db_type) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, file_path, file_format, library_id, series_name, is_deleted, deleted_at "
            "FROM books WHERE id = ?",
            (int(book_id),),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def _library(db_type, library_id):
    if library_id is None:
        return None
    try:
        from repositories.category_repository import CategoryRepository
        return CategoryRepository.get_library_by_id(db_type, library_id)
    except Exception as e:
        print(f"[Diagnose] library lookup failed ({db_type}:{library_id}): {e}")
        return None


def _roots(lib):
    return [p.strip() for p in str((lib or {}).get('physical_path') or '').replace('\r', '').split('\n') if p.strip()]


def _file_state(path):
    """('missing'|'empty'|'ok', size)"""
    if not os.path.isfile(path):
        return 'missing', 0
    size = os.path.getsize(path)
    return ('empty' if size == 0 else 'ok'), size


def _format_state(path, fmt):
    """가벼운 형식 확인 - 압축 계열은 중앙 디렉터리(파일 끝)만, PDF는 머리말 5바이트만 읽는다."""
    fmt = (fmt or '').lower()
    if fmt in _ZIP_FORMATS:
        return 'ok' if zipfile.is_zipfile(path) else 'bad'
    if fmt == 'pdf':
        with open(path, 'rb') as f:
            return 'ok' if f.read(5) == b'%PDF-' else 'bad'
    return 'skip'


def _human_size(size):
    value = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f"{value:.0f} {unit}" if unit == 'B' else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _purge_date(deleted_at):
    if not deleted_at:
        return ''
    try:
        value = deleted_at if isinstance(deleted_at, datetime) else datetime.fromisoformat(str(deleted_at).strip().replace('T', ' '))
        return (value + timedelta(days=TRASH_PURGE_DAYS)).strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        return ''


def _open_problems(db_type, book_id):
    # 열린 행 전체(대량 사라짐이면 수만 건)를 읽지 않도록 카탈로그 코드별로 이 도서 행만 조회한다.
    from repositories.problem_repository import ProblemRepository
    from services.problem_service import CATALOG
    rows = []
    for code in CATALOG:
        try:
            row = ProblemRepository.get(code, db_type, 'book', str(book_id))
        except Exception as e:
            print(f"[Diagnose] problem lookup failed ({code}): {e}")
            continue
        if row and row.get('status') == 'open':
            rows.append(row)
    out = []
    for r in rows:
        entry = catalog_entry(r.get('code'))
        out.append({
            'code': r.get('code'),
            'title_key': entry['title_key'],
            'severity': r.get('severity'),
            'occurrence_count': int(r.get('occurrence_count') or 0),
            'message': (r.get('message') or '')[:300],
        })
    return out


def diagnose_book(db_type, book_id):
    """도서 1권 진단. 반환: {book, checks[], conclusion{key, vars}, actions[], problems[]} — 도서가 없으면 book=None."""
    db_type = (db_type or 'general').strip().lower()
    if db_type not in DIAGNOSE_DB_TYPES:
        raise ValueError(f'진단은 일반/성인 도서만 지원합니다: {db_type}')
    book_id = int(book_id)
    checks, actions = [], []

    book = _load_book(db_type, book_id)
    if not book:
        checks.append(_check('db', FAIL, 'missing', id=book_id))
        return {'book': None, 'checks': checks, 'conclusion': {'key': 'diagnose.result.no_record', 'vars': {}},
                'actions': [], 'problems': _open_problems(db_type, book_id)}

    lib = _library(db_type, book.get('library_id'))
    roots = _roots(lib)
    path = book.get('file_path') or ''
    from services.problem_card_service import relative_scan_path
    folder_scan_path = relative_scan_path(roots, os.path.dirname(path)) if path else None
    info = {
        'id': book['id'], 'title': book.get('title'), 'file_path': path, 'file_format': book.get('file_format'),
        'library_id': book.get('library_id'), 'library': (lib or {}).get('name') or '', 'series_name': book.get('series_name'),
        'db_type': db_type, 'is_deleted': bool(book.get('is_deleted')), 'deleted_at': str(book.get('deleted_at') or ''),
    }
    problems = _open_problems(db_type, book_id)
    rescan_folder = {'id': 'rescan_path', 'library_id': book.get('library_id'), 'scan_path': folder_scan_path} \
        if folder_scan_path is not None else None
    rescan_book = {'id': 'rescan_book', 'book_id': book['id']}

    def result(key, **vars_):
        return {'book': info, 'checks': checks, 'conclusion': {'key': f'diagnose.result.{key}', 'vars': vars_},
                'actions': [a for a in actions if a], 'problems': problems}

    # 1. DB 기록
    if book.get('is_deleted'):
        checks.append(_check('db', WARN, 'trashed', purge=_purge_date(book.get('deleted_at'))))
    else:
        checks.append(_check('db', OK, 'ok'))
    if not lib:
        checks.append(_check('library', FAIL, 'missing', id=book.get('library_id')))
        return result('no_library')

    # 2. 원격 연결 (카테고리 루트) - 스캐너 안전장치와 같은 판정
    if _is_remote_url(path):
        checks.append(_check('remote', SKIP, 'remote_url'))
        checks.append(_check('file', SKIP, 'remote_url'))
        return result('remote_url')
    from services.scan_problem_service import check_roots
    done, value = _with_timeout(lambda: check_roots(roots))
    if not done:
        checks.append(_check('remote', FAIL, 'timeout', seconds=FS_TIMEOUT_SECONDS))
        return result('remote_slow')  # 응답이 없을 뿐 끊겼다고 단정하지 않는다
    roots_ok, failures = value
    if not roots_ok:
        checks.append(_check('remote', FAIL, 'unreachable', path='; '.join(p for p, _ in failures)))
        return result('remote_unavailable')
    checks.append(_check('remote', OK, 'ok'))

    # 3. 파일 존재
    done, value = _with_timeout(lambda: _file_state(path))
    if not done:
        checks.append(_check('file', FAIL, 'timeout', seconds=FS_TIMEOUT_SECONDS))
        return result('remote_slow')
    state, size = value
    if state == 'missing':
        checks.append(_check('file', FAIL, 'missing', path=path))
        actions.append(rescan_folder)
        return result('trashed_missing' if book.get('is_deleted') else 'file_moved')
    if state == 'empty':
        checks.append(_check('file', FAIL, 'empty', path=path))
        actions.append(rescan_book)
        return result('file_corrupt')
    checks.append(_check('file', OK, 'ok', size=_human_size(size)))

    # 4. 파일 형식
    done, value = _with_timeout(lambda: _format_state(path, book.get('file_format')))
    if not done:
        checks.append(_check('format', FAIL, 'timeout', seconds=FS_TIMEOUT_SECONDS))
        return result('remote_slow')
    if value == 'bad':
        checks.append(_check('format', FAIL, 'bad', format=(book.get('file_format') or '').upper()))
        actions.append(rescan_book)
        return result('file_corrupt')
    checks.append(_check('format', SKIP if value == 'skip' else OK, value))

    if book.get('is_deleted'):
        # 파일이 다시 있다 → 다음 스캔(폴더 재스캔)에서 휴지통에서 복구된다
        actions.append(rescan_folder)
        return result('trashed_but_present')
    if problems:
        actions.append(rescan_book)
        return result('healthy_with_problems', count=len(problems))
    return result('healthy')
