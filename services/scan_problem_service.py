# -*- coding: utf-8 -*-
"""
scan_problem_service.py – 일반/성인 도서 스캐너가 남기는 문제 기록 + 대량 사라짐 안전장치

설계: docs/plan_unified_notification_queue.md 3장 "결정: 대량 발생 기준" / 8장 4단계.

스캐너 흐름에서 쓰는 곳:
- 스캔 시작(카테고리 루트 접근 확인): 실패하면 report_root_unreachable, 이후 스캔이 정상 진행되면 reconcile이 해제.
- 삭제 동기화 직전: gate_deletions()가 False면 이번 스캔은 휴지통 이동을 하지 않는다.
    · 루트/마운트 접근 불가 → remote_unavailable (카테고리 카드 1장, 개별 도서 기록 없음)
    · 루트 정상 + 한 스캔에서 대량(20% AND 20건 이상) 사라짐 → mass_missing (도서별 기록, 관리자 확인 후 휴지통)
    · 그 밖 → 기존대로 휴지통 이동 + file_missing(참고) 기록
- 스캔 끝: record_scan_errors()로 파일 오류를 코드로 남기고, reconcile()로 다시 정상이 된 대상을 해제.

여기 있는 기록/해제는 스캔을 절대 실패시키지 않는다(전부 예외를 삼키고 로그만 남김).
단, gate_deletions의 판단 자체가 실패하면 안전한 쪽(삭제 보류)으로 돌아간다.
"""
import hashlib
import os

from services.problem_service import (
    ProblemService,
    get_mass_missing_thresholds,
    make_group_key,
    make_series_key,
)

CODE_FILE_MISSING = 'file_missing'
CODE_MASS_MISSING = 'mass_missing'
CODE_REMOTE_UNAVAILABLE = 'remote_unavailable'
CODE_FILE_CORRUPT = 'file_corrupt'
CODE_COVER_MISSING = 'cover_missing'
CODE_UNKNOWN = 'unknown'

# 스캐너 오류 항목(error_type) → 문제 코드
ERROR_TYPE_CODES = {
    'BadZipFile': CODE_FILE_CORRUPT,
    'OffsetError': CODE_FILE_CORRUPT,
    'OffsetAnalysis': CODE_FILE_CORRUPT,
    'NoCover': CODE_COVER_MISSING,
}
# 파일 단위로 다시 처리되면 해제되는 코드
_FILE_ERROR_CODES = (CODE_FILE_CORRUPT, CODE_COVER_MISSING, CODE_UNKNOWN)
SCANNER_CODES = (CODE_FILE_MISSING, CODE_MASS_MISSING, CODE_REMOTE_UNAVAILABLE) + _FILE_ERROR_CODES

_SOURCE = 'scanner'
_CHUNK = 500

# 루트 접근 실패로 스캔 작업이 실패할 때 오류 문구 앞에 붙는 표시. 알림센터는 이 실패를 '스캔 실패'로
# 따로 띄우지 않고 remote_unavailable 카드(순단 유예 포함) 하나로만 알린다.
ROOT_UNREACHABLE_MARKER = '[root_unreachable]'


def _norm(path):
    from tools.scanner.path_utils import canonical_path
    return canonical_path(path) if path else path


def _path_target_id(path):
    """DB에 행이 없는 파일(새 파일이 처리 실패 등)의 대상 키. target_id 길이 제한(255) 안에 들어가게 해시."""
    return 'path:' + hashlib.sha1(str(path).encode('utf-8', 'surrogateescape')).hexdigest()


def _is_remote_url(path):
    return str(path).startswith(('gdrive:', 'gdrive://', 'http://', 'https://'))


def _library_roots(cursor, library_id, fallback_paths):
    """카테고리 루트 경로 목록 (부분 경로 스캔이어도 루트 기준으로 점검한다)."""
    try:
        cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        raw = (row['physical_path'] if row else '') or ''
        roots = [p.strip() for p in str(raw).replace('\r', '').split('\n') if p.strip()]
        if roots:
            return roots
    except Exception as e:
        print(f"[ScanProblem] library root lookup failed (library_id={library_id}): {e}")
    return list(fallback_paths or [])


def check_roots(paths):
    """루트가 살아 있는가: 존재하고 목록이 비어 있지 않아야 한다 (rclone 마운트가 끊기면 빈 폴더로 보이거나 오류)."""
    failures = []
    for path in paths or []:
        if _is_remote_url(path):
            continue
        try:
            if not os.path.isdir(path):
                failures.append((path, 'not found'))
                continue
            with os.scandir(path) as it:
                if next(it, None) is None:
                    failures.append((path, 'empty'))
        except OSError as e:
            failures.append((path, str(e)))
    return not failures, failures


def is_mass_missing(db_type, library_id, missing_count, total_count):
    if missing_count <= 0 or total_count <= 0:
        return False
    th = get_mass_missing_thresholds(db_type, library_id)
    return missing_count >= th['min_count'] and (missing_count / total_count) >= th['ratio']


def report_root_unreachable(db_type, library_id, failures, missing_count=None):
    detail = '; '.join(f"{p} ({why})" for p, why in failures)[:500]
    ProblemService.report(
        CODE_REMOTE_UNAVAILABLE, 'library', library_id, db_type=db_type, library_id=library_id,
        source=_SOURCE, target_path='\n'.join(p for p, _ in failures)[:1000], message=detail,
        context={'missing_count': missing_count} if missing_count is not None else None,
    )


def _book_rows(cursor, book_ids):
    """id → {series_name, file_path, is_deleted} (시리즈별로 카드 안에 접어 올리기 위함)."""
    rows = {}
    ids = [int(i) for i in book_ids if i is not None]
    for i in range(0, len(ids), _CHUNK):
        chunk = ids[i:i + _CHUNK]
        cursor.execute(
            f"SELECT id, series_name, file_path, COALESCE(is_deleted, 0) AS is_deleted FROM books WHERE id IN ({','.join('?' * len(chunk))})",
            tuple(chunk),
        )
        for r in cursor.fetchall():
            rows[int(r['id'])] = {'series_name': r['series_name'], 'file_path': r['file_path'], 'is_deleted': int(r['is_deleted'] or 0)}
    return rows


def _report_books(cursor, code, db_type, library_id, paths, db_books, message=None):
    norm_books = {_norm(k): v for k, v in db_books.items()}
    ids = {p: norm_books.get(_norm(p)) for p in paths}
    info = _book_rows(cursor, [i for i in ids.values() if i])
    for path, book_id in ids.items():
        if not book_id:
            continue
        row = info.get(int(book_id)) or {}
        ProblemService.report(
            code, 'book', book_id, db_type=db_type, library_id=library_id, source=_SOURCE,
            target_path=path, series_key=make_series_key(library_id, row.get('series_name') or ''),
            message=message,
        )


def _already_trashed(cursor, library_id, db_books):
    """db_books(스캔 시작 시 이 카테고리 도서 전체 - 휴지통 포함) 중 이미 휴지통에 있는 경로."""
    cursor.execute("SELECT file_path FROM books WHERE library_id = ? AND COALESCE(is_deleted, 0) = 1", (library_id,))
    keys = {_norm(k) for k in (db_books or {})}
    return {_norm(r['file_path']) for r in cursor.fetchall() if _norm(r['file_path']) in keys}


def gate_deletions(cursor, db_type, library_id, deleted_paths, db_books, target_paths, found_count):
    """이번 스캔에서 사라진 도서를 휴지통으로 옮겨도 되는가.

    돌려주는 값: (진행 여부, 보류 사유, 새로 사라진 경로)
      (True, None, ...)  = 기존대로 진행
      (False, 'root', ...) = 루트 접근 불가로 보류
      (False, 'mass', ...) = 대량 사라짐으로 보류
    스캐너의 '사라진 도서' 목록에는 이미 휴지통에 있는 도서도 들어 있으므로, 판정과 기록은
    이번에 새로 사라진 도서(휴지통에 없던 것)만으로 한다."""
    newly_missing = set()
    try:
        if not deleted_paths:
            return True, None, newly_missing
        trashed = _already_trashed(cursor, library_id, db_books)
        newly_missing = {p for p in deleted_paths if _norm(p) not in trashed}
        missing = len(newly_missing)
        total = len(db_books or {}) - len(trashed)
        zero_found = found_count == 0 and total > 0
        if missing == 0:
            return True, None, newly_missing
        if not zero_found and not is_mass_missing(db_type, library_id, missing, total):
            return True, None, newly_missing
        roots = _library_roots(cursor, library_id, target_paths)
        roots_ok, failures = check_roots(roots)
        if not roots_ok or zero_found:
            report_root_unreachable(db_type, library_id, failures or [(r, 'no files found') for r in roots], missing)
            print(f"[ScanProblem] 🛑 root unreachable (db={db_type}, library_id={library_id}, missing={missing}/{total}) - deletion skipped")
            return False, 'root', newly_missing
        _report_books(cursor, CODE_MASS_MISSING, db_type, library_id, newly_missing, db_books,
                      message=f'{missing}/{total} books missing in one scan')
        print(f"[ScanProblem] 🛑 mass missing (db={db_type}, library_id={library_id}, missing={missing}/{total}) - deletion held for admin confirmation")
        return False, 'mass', newly_missing
    except Exception as e:
        print(f"[ScanProblem] gate_deletions failed, holding deletions for safety: {e}")
        return False, 'root', newly_missing


def record_trashed(cursor, db_type, library_id, deleted_paths, db_books):
    """기존대로 휴지통으로 옮긴 도서를 file_missing(참고)로 남긴다."""
    try:
        if deleted_paths:
            _report_books(cursor, CODE_FILE_MISSING, db_type, library_id, deleted_paths, db_books)
    except Exception as e:
        print(f"[ScanProblem] record_trashed failed: {e}")


def record_scan_errors(cursor, db_type, library_id, library_errors):
    """스캐너 오류 목록을 파일 단위 문제로 남긴다. 기록한 경로 집합을 돌려준다."""
    error_paths = set()
    try:
        paths = [e.get('file_path') for e in library_errors or [] if e.get('file_path')]
        if not paths:
            return error_paths
        by_path = {}
        for i in range(0, len(paths), _CHUNK):
            chunk = paths[i:i + _CHUNK]
            cursor.execute(
                f"SELECT id, series_name, file_path FROM books WHERE library_id = ? AND file_path IN ({','.join('?' * len(chunk))})",
                (library_id, *chunk),
            )
            for r in cursor.fetchall():
                by_path[_norm(r['file_path'])] = r
        for err in library_errors:
            path = err.get('file_path')
            if not path:
                continue
            code = ERROR_TYPE_CODES.get(err.get('error_type'), CODE_UNKNOWN)
            row = by_path.get(_norm(path))
            series_name = (row['series_name'] if row else None) or os.path.basename(os.path.dirname(str(path))) or ''
            ProblemService.report(
                code, 'book', row['id'] if row else _path_target_id(_norm(path)),
                db_type=db_type, library_id=library_id, source=_SOURCE, target_path=path,
                series_key=make_series_key(library_id, series_name),
                message=f"{err.get('error_type') or 'Error'}: {err.get('message') or ''}",
            )
            error_paths.add(_norm(path))
    except Exception as e:
        print(f"[ScanProblem] record_scan_errors failed: {e}")
    return error_paths


def _under(path, prefixes):
    p = _norm(path) or ''
    return any(p == pre or p.startswith(pre.rstrip('/') + '/') for pre in prefixes)


def reconcile(cursor, db_type, library_id, *, found_file_paths, processed_paths, error_paths, scope_paths, held):
    """스캔 끝: 다시 정상이 된 대상의 문제를 해제한다.

    - 루트가 살아서 삭제 판정까지 왔으면(held가 root가 아니면) remote_unavailable 해제
    - file_missing/mass_missing: 파일이 다시 보이거나, 도서가 휴지통에서 완전히 지워졌거나(행 없음),
      mass_missing인데 이후 휴지통으로 옮겨졌으면 해제
    - 파일 오류: 이번에 다시 처리됐는데 오류가 없거나, 파일이 더는 없으면 해제
    """
    from repositories.problem_repository import ProblemRepository
    from services.problem_service import now_ms
    try:
        if held != 'root':
            ProblemService.resolve(CODE_REMOTE_UNAVAILABLE, 'library', library_id, db_type=db_type)
        rows = ProblemRepository.list_open_for_library(db_type, library_id, codes=list(SCANNER_CODES))
        scope = [_norm(p) for p in scope_paths or [] if p and not _is_remote_url(p)]
        rows = [r for r in rows if r['code'] != CODE_REMOTE_UNAVAILABLE and r.get('target_path')
                and (not scope or _under(r['target_path'], scope))]
        if not rows:
            return 0
        found = {_norm(p) for p in found_file_paths or ()}
        processed = {_norm(p) for p in processed_paths or ()}
        book_ids = [int(r['target_id']) for r in rows if r['target_type'] == 'book' and str(r['target_id']).isdigit()]
        books = _book_rows(cursor, book_ids)
        done = []
        for r in rows:
            path = _norm(r['target_path'])
            book = books.get(int(r['target_id'])) if str(r['target_id']).isdigit() else None
            if r['code'] in (CODE_FILE_MISSING, CODE_MASS_MISSING):
                if held and r['code'] == CODE_MASS_MISSING and path not in found:
                    continue  # 이번에도 보류 중
                if path in found or book is None or (r['code'] == CODE_MASS_MISSING and book['is_deleted']):
                    done.append(r['id'])
            elif r['code'] in _FILE_ERROR_CODES:
                if path not in error_paths and (path in processed or path not in found):
                    done.append(r['id'])
        return ProblemRepository.resolve_ids(done, now_ms()) if done else 0
    except Exception as e:
        print(f"[ScanProblem] reconcile failed: {e}")
        return 0


# ---- 관리자 조치 ----

def confirm_trash(group_key):
    """mass_missing 카드: 지금도 파일이 없는 도서만 휴지통으로 옮기고 해제한다. (옮긴 수, 아직 남은 수)"""
    import database
    from repositories.problem_repository import ProblemRepository
    from services.problem_service import now_ms
    code, db_type, library_id = group_key.split('|', 2)
    if code != CODE_MASS_MISSING or db_type not in ('general', 'adult'):
        raise ValueError('이 카드는 휴지통 이동을 지원하지 않습니다.')
    rows = [r for r in ProblemRepository.list_open_for_library(db_type, int(library_id), codes=[CODE_MASS_MISSING])
            if r['group_key'] == group_key]
    # 루트가 다시 끊겼으면 아무것도 하지 않는다 (안전장치는 끌 수 없다).
    with database.connection(db_type) as conn:
        cursor = conn.cursor()
        roots_ok, _failures = check_roots(_library_roots(cursor, int(library_id), []))
    if not roots_ok:
        raise RuntimeError('카테고리 루트에 접근할 수 없어 휴지통 이동을 하지 않았습니다.')
    still_missing = [r for r in rows if str(r['target_id']).isdigit() and r.get('target_path')
                     and not os.path.exists(r['target_path'])]
    reappeared = [r for r in rows if r not in still_missing]
    trash_ids = [int(r['target_id']) for r in still_missing]
    if trash_ids:
        conn = database.get_connection(db_type)
        try:
            cursor = conn.cursor()
            for i in range(0, len(trash_ids), _CHUNK):
                chunk = trash_ids[i:i + _CHUNK]
                cursor.execute(
                    f"UPDATE books SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' * len(chunk))}) AND COALESCE(is_deleted, 0) = 0",
                    tuple(chunk),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    ProblemRepository.resolve_ids([r['id'] for r in rows], now_ms())
    # 휴지통으로 옮긴 도서는 다른 휴지통 이동과 같게 file_missing(참고)으로 남긴다.
    for r in still_missing:
        ProblemService.report(CODE_FILE_MISSING, 'book', r['target_id'], db_type=db_type, library_id=int(library_id),
                              source=_SOURCE, target_path=r['target_path'], series_key=r.get('series_key'))
    if trash_ids:
        try:
            from repositories.series_repository import SeriesRepository
            from services.system_health_service import SystemHealthService, series_summary_health_key
            with SystemHealthService.track(*series_summary_health_key(db_type)):
                SeriesRepository.rebuild_summary(db_type)
            from services.series_service import SeriesService
            SeriesService.invalidate_all_books_cache(db_type=db_type)
        except Exception as e:
            print(f"[ScanProblem] summary refresh after confirm_trash failed: {e}")
    return {'trashed': len(trash_ids), 'reappeared': len(reappeared)}


def card_library(group_key):
    """카드 키 → (code, db_type, library_id|None)."""
    parts = str(group_key).split('|')
    if len(parts) != 3:
        raise ValueError('잘못된 카드 키입니다.')
    code, db_type, lib = parts
    return code, db_type, (int(lib) if lib.isdigit() else None)


__all__ = [
    'SCANNER_CODES', 'ERROR_TYPE_CODES', 'ROOT_UNREACHABLE_MARKER', 'check_roots', 'is_mass_missing', 'gate_deletions', 'record_trashed',
    'record_scan_errors', 'reconcile', 'report_root_unreachable', 'confirm_trash', 'card_library', 'make_group_key',
]
