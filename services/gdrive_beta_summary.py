# -*- coding: utf-8 -*-
"""구글 드라이브 링크 기능(클로즈 베타) 로그 요약 — MCP(get_gdrive_beta_summary)와 CLI가 함께 쓴다. 읽기 전용.

logs/scanner.log·media_server.log(회전된 .zip 포함)의 '[GDRIVE-BETA] <event> k=v' 줄(utils/gdrive_beta_log.py)을
읽어 카테고리별 스캔(목록·메타·건너뛴 폴더·신규)과 열람(사본 받기 시간/크기/실패, 미리 받기, 열 때 표지),
캐시 정리를 묶고, 지금 상태(뷰어 캐시 사용량, 열린 관리자 경고)를 덧붙인다.
"""
import glob
import os
import re
import shlex
import zipfile
from datetime import datetime, timedelta

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
_LINE_RE = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[GDRIVE-BETA\] (\S+)(.*)$')
_LOG_BASES = ('scanner.log', 'media_server.log')


def _iter_log_lines(logs_dir):
    for base in _LOG_BASES:
        for path in sorted(glob.glob(os.path.join(logs_dir, f'{base}_*.zip'))):
            try:
                with zipfile.ZipFile(path) as zf:
                    for name in zf.namelist():
                        with zf.open(name) as fh:
                            for raw in fh:
                                yield raw.decode('utf-8', errors='replace')
            except (OSError, zipfile.BadZipFile):
                continue
        path = os.path.join(logs_dir, base)
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                yield from fh


def _parse(line):
    if 'GDRIVE-BETA' not in line:
        return None
    m = _LINE_RE.match(line.rstrip('\n'))
    if not m:
        return None
    try:
        row = {'ts': datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S'), 'event': m.group(2)}
        for token in shlex.split(m.group(3)):
            key, _, value = token.partition('=')
            row[key] = value
    except ValueError:
        return None
    return row


def read_events(hours=24, logs_dir=LOGS_DIR, library_id=None):
    since = datetime.now() - timedelta(hours=hours) if hours else None
    rows = []
    for line in _iter_log_lines(logs_dir):
        row = _parse(line)
        if not row or (since and row['ts'] < since):
            continue
        if library_id and row.get('lib') and str(row['lib']) != str(library_id):
            continue
        rows.append(row)
    rows.sort(key=lambda r: r['ts'])
    return rows


def _num(row, key):
    try:
        return float(row.get(key, 0) or 0)
    except ValueError:
        return 0.0


def _dist(values):
    if not values:
        return None
    s = sorted(values)
    pick = lambda p: s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
    return {'n': len(s), 'p50': round(pick(0.5), 2), 'p90': round(pick(0.9), 2), 'max': round(s[-1], 2)}


def _short(row, *keys):
    out = {'at': row['ts'].strftime('%Y-%m-%d %H:%M:%S')}
    out.update({k: row[k] for k in keys if k in row})
    return out


def _cache_usage():
    try:
        from services.gdrive_view_copy_service import view_cache_root, VIEW_CACHE_MAX_BYTES
    except Exception:
        return None
    root = view_cache_root()
    per_lib = {}
    if os.path.isdir(root):
        for lib_dir in sorted(os.listdir(root)):
            total = 0
            for dp, _d, fs in os.walk(os.path.join(root, lib_dir)):
                for f in fs:
                    try:
                        total += os.path.getsize(os.path.join(dp, f))
                    except OSError:
                        pass
            per_lib[lib_dir] = round(total / 1e6, 1)
    return {'mb_by_category': per_lib, 'total_mb': round(sum(per_lib.values()), 1),
            'limit_mb': round(VIEW_CACHE_MAX_BYTES / 1e6, 1)}


def _active_warnings():
    try:
        from services.system_health_service import SystemHealthService
        return [w for w in SystemHealthService.get_active_warnings() if str(w.get('key', '')).startswith('gdrive_')]
    except Exception:
        return []


def summarize(hours=24, library_id=None, logs_dir=LOGS_DIR, include_live=True):
    rows = read_events(hours, logs_dir, library_id)
    by_event = {}
    for r in rows:
        by_event.setdefault(r['event'], []).append(r)

    scans = {}
    for r in by_event.get('scan.summary', []):
        scans.setdefault(r.get('lib', '?'), []).append(r)
    listing = {}
    for r in by_event.get('scan.listing', []):
        listing.setdefault(r.get('lib', '?'), []).append(r)
    scan_section = {}
    for lib in sorted(set(scans) | set(listing), key=str):
        s_rows, l_rows = scans.get(lib, []), listing.get(lib, [])
        scan_section[lib] = {
            'scans': len(s_rows),
            'total_seconds': _dist([_num(r, 'took') for r in s_rows]),
            'listing_seconds': _dist([_num(r, 'took') for r in l_rows]),
            'listing_via': sorted({r.get('via') for r in l_rows if r.get('via')}),
            'last_scan': _short(s_rows[-1], 'folders', 'skipped', 'processed', 'new', 'removed',
                                'deletion_held', 'traversal_errors', 'took') if s_rows else None,
            'new_books_total': int(sum(_num(r, 'new') for r in s_rows)),
        }

    downloads = by_event.get('view.download', [])
    failures = by_event.get('view.download_failed', [])
    by_kind = {}
    for r in downloads:
        by_kind.setdefault(r.get('kind', '?'), []).append(r)
    prefetch = by_event.get('view.prefetch', [])

    result = {
        'window_hours': hours or 'all',
        'library_id': library_id or 'all',
        'events': len(rows),
        'scan': scan_section,
        'scan_failures': {
            'listing_failed': [_short(r, 'lib', 'remote', 'err') for r in by_event.get('scan.listing_failed', [])][-5:],
            'meta_mirror_failed': [_short(r, 'lib', 'err') for r in by_event.get('scan.meta_mirror_failed', [])][-5:],
            'meta_mirror_partial': [_short(r, 'lib', 'mode', 'fetched', 'failed')
                                    for r in by_event.get('scan.meta_mirror', []) if _num(r, 'failed') > 0][-5:],
        },
        'view': {
            'downloads': len(downloads),
            'failed': len(failures),
            'failure_rate': round(len(failures) / (len(downloads) + len(failures)), 3) if (downloads or failures) else None,
            'by_kind': {k: {'seconds': _dist([_num(r, 'took') for r in v]), 'mb': _dist([_num(r, 'mb') for r in v])}
                        for k, v in sorted(by_kind.items())},
            'recent_failures': [_short(r, 'lib', 'book', 'kind', 'took', 'err') for r in failures][-5:],
            'prefetch': {'ok': sum(1 for r in prefetch if r.get('ok') == 'True'),
                         'failed': sum(1 for r in prefetch if r.get('ok') != 'True')},
            # 다른 요청이 받는 중이라 기다리다 마감을 넘겨 원본으로 간 요청 수 (다운로드 정체 신호)
            'lock_wait_timeouts': len(by_event.get('view.lock_wait_timeout', [])),
            'covers_made_on_open': len(by_event.get('view.cover_on_open', [])),
            'cover_on_open_failed': len(by_event.get('view.cover_on_open_failed', [])),
        },
        'cache': {
            'evictions': len(by_event.get('cache.evict', [])),
            'evicted_copies': int(sum(_num(r, 'removed') for r in by_event.get('cache.evict', []))),
            'freed_mb': round(sum(_num(r, 'freed_mb') for r in by_event.get('cache.evict', [])), 1),
            'ttl_removed': int(sum(_num(r, 'removed') for r in by_event.get('cache.ttl_cleanup', []))),
        },
    }
    if include_live:
        from utils.drive_helper import gdrive_link_beta_enabled
        result['beta_enabled'] = gdrive_link_beta_enabled()
        result['cache']['now'] = _cache_usage()
        result['active_warnings'] = _active_warnings()
    return result
