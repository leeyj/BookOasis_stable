# -*- coding: utf-8 -*-
"""
epaper_service.py – e-paper 리더용 변환본 캐시 (코어 쪽 접점).

- 변환기 services/epaper/ 를 부르는 곳은 여기 하나다(변환기는 DB·설정을 모른다).
- 변환은 기기 피드(/opds-epaper/v1)에서 받기 링크를 요청할 때만, 그 책 한 권만 한다. 표준 /opds 는 원본을 그대로 보낸다.
- 첫 요청 때 변환을 시작하고 EPAPER_CONVERT_TIMEOUT_SEC(기본 45초)까지 기다린다. 넘으면 '변환 중'으로 답하고
  백그라운드에서 마저 한다. 같은 책을 동시에 요청해도 변환은 한 번이다(책별 작업 하나).
- 캐시 키: 책 = <db_type>/<book_id>.<프로필>.epub, 업로드 = upload/<sha256>.<프로필>.epub. 옆에 .json(보고서·digest·원본 stat).
  원본 크기·수정 시각이 바뀌면 다시 변환한다. 캐시는 언제 지워도 다시 만들 수 있다.
- 정리: 마지막 다운로드(파일 mtime) 기준 EPAPER_CACHE_DAYS(30일) 지난 것, 그리고 EPAPER_CACHE_MAX_MB(2048) 넘으면
  오래된 것부터. 변환 중·전송 중인 파일은 건너뛴다.
- 변환본 digest(KOReader partial MD5)를 kosync 문서 매핑에 원본과 같은 book_id로 등록한다.
"""
import hashlib
import json
import os
import shutil
import threading
import time

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CACHE_DIR = os.path.join(MEDIA_SERVER_DIR, 'cache', 'epaper')
DEFAULTS = {
    'EPAPER_CACHE_DIR': '',
    'EPAPER_CACHE_DAYS': 30,
    'EPAPER_CACHE_MAX_MB': 2048,
    'EPAPER_CONVERT_TIMEOUT_SEC': 45,
}
FAILURE_RETRY_SEC = 600      # 실패한 책은 10분 동안 다시 변환하지 않고 같은 오류를 준다
HEALTH_KEY = 'epaper_cache_cleanup'
HEALTH_LABEL = 'e-paper 변환본 캐시 정리'

_jobs = {}                   # cache_key -> {'event', 'error', 'started'}
_failures = {}               # cache_key -> {'at', 'reason', ...}
_in_use = {}                 # 파일 경로 -> 전송 중 수
_lock = threading.Lock()


# ---- 설정 ----

def _setting(key):
    default = DEFAULTS[key]
    try:
        from services.settings_service import SettingsService
        value = SettingsService.get(key, '')
    except Exception:
        value = ''
    value = str(value if value is not None else '').strip()
    if not value:
        return default
    if isinstance(default, int):
        try:
            return max(1, int(value))
        except ValueError:
            return default
    return value


def cache_dir():
    return _setting('EPAPER_CACHE_DIR') or DEFAULT_CACHE_DIR


def profile_version():
    from services.epaper import PROFILE_VERSION
    return PROFILE_VERSION


def converter_revision():
    from services.epaper import CONVERTER_REVISION
    return CONVERTER_REVISION


def _fresh(meta, epub_path, source_stat=None):
    """캐시 변환본을 그대로 써도 되는가: 파일이 있고, 같은 변환기 리비전이고, 원본이 바뀌지 않았다."""
    return (bool(meta) and os.path.exists(epub_path) and meta.get('revision') == converter_revision()
            and (source_stat is None or meta.get('source') == source_stat))


def _book_key(db_type, book_id):
    return f'{db_type}/{int(book_id)}.{profile_version()}'


def upload_key(sha256):
    return f'upload/{sha256}.{profile_version()}'


def _paths(key):
    base = os.path.join(cache_dir(), *key.split('/'))
    return base + '.epub', base + '.json'


def _read_meta(meta_path):
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_meta(meta_path, meta):
    tmp = meta_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, meta_path)


def _source_stat(path):
    st = os.stat(path)
    return {'size': st.st_size, 'mtime_ns': st.st_mtime_ns}


# ---- 변환 ----

class Pending(Exception):
    """아직 변환 중. retry_after 초 뒤에 다시 요청하면 된다."""

    def __init__(self, retry_after):
        super().__init__('converting')
        self.retry_after = retry_after


class ConversionFailed(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _run_conversion(key, src_path, fmt, title, author, db_type=None, book_id=None, source_stat=None):
    from services import epaper
    from services.kosync_service import partial_md5
    epub_path, meta_path = _paths(key)
    os.makedirs(os.path.dirname(epub_path), exist_ok=True)
    started = time.time()
    try:
        report = epaper.convert(src_path, epub_path, fmt, title=title, author=author)
        digest = partial_md5(epub_path)
        seconds = round(time.time() - started, 2)
        meta = {'key': key, 'profile': profile_version(), 'revision': converter_revision(),
                'source_format': fmt, 'digest': digest,
                'db_type': db_type, 'book_id': book_id, 'source': source_stat, 'seconds': seconds,
                'size': os.path.getsize(epub_path), 'converted_at': int(time.time()), 'report': report}
        _write_meta(meta_path, meta)
        if db_type and book_id is not None:
            _register_digest(digest, db_type, book_id)
        print(f"[EPAPER] convert ok key={key} format={fmt} seconds={seconds} size={meta['size']} digest={digest} "
              f"warnings={len(report.get('warnings') or [])} repaired={len(report.get('repaired_documents') or [])}")
        for warning in (report.get('warnings') or [])[:10]:
            print(f"[EPAPER] convert warning key={key}: {warning}")
        with _lock:
            _failures.pop(key, None)
        return None
    except Exception as e:
        reason = f'{type(e).__name__}: {e}'
        print(f"[EPAPER] convert failed key={key} format={fmt} seconds={round(time.time() - started, 2)} reason={reason}")
        for path in (epub_path, meta_path):
            try:
                os.remove(path)
            except OSError:
                pass
        with _lock:
            _failures[key] = {'at': time.time(), 'reason': reason, 'key': key, 'db_type': db_type,
                              'book_id': book_id, 'format': fmt}
        _append_failure_log(_failures[key])
        return reason


FAILURE_LOG_NAME = 'failures.json'
FAILURE_LOG_KEEP = 50


def _append_failure_log(failure):
    """최근 실패 목록을 파일에도 남긴다 - MCP 서버는 별도 프로세스라 웹 프로세스 메모리를 못 본다."""
    path = os.path.join(cache_dir(), FAILURE_LOG_NAME)
    try:
        items = _read_failure_log()
        items = [f for f in items if f.get('key') != failure['key']]
        items.insert(0, {k: failure.get(k) for k in ('key', 'db_type', 'book_id', 'format', 'reason')}
                     | {'at': int(failure['at'])})
        os.makedirs(cache_dir(), exist_ok=True)
        _write_meta(path, items[:FAILURE_LOG_KEEP])
    except Exception as e:
        print(f"[EPAPER] failure log write failed: {e}")


def _read_failure_log():
    data = _read_meta(os.path.join(cache_dir(), FAILURE_LOG_NAME))
    return data if isinstance(data, list) else []


def _register_digest(digest, db_type, book_id):
    try:
        from repositories.kosync_repository import KosyncRepository
        KosyncRepository.save_document(digest, db_type, int(book_id))
    except Exception as e:
        print(f"[EPAPER] kosync digest registration failed (book={db_type}:{book_id}): {e}")


def _ensure(key, src_path, fmt, title, author, db_type=None, book_id=None, source_stat=None, timeout=None):
    """캐시에 있으면 (epub_path, meta), 없으면 변환. 시간 안에 못 끝나면 Pending, 실패면 ConversionFailed."""
    epub_path, meta_path = _paths(key)
    with _lock:
        job = _jobs.get(key)
        if job is None:
            meta = _read_meta(meta_path)
            if _fresh(meta, epub_path, source_stat):
                return epub_path, meta
            failure = _failures.get(key)
            if failure and time.time() - failure['at'] < FAILURE_RETRY_SEC and failure.get('source') == source_stat:
                raise ConversionFailed(failure['reason'])
            job = {'event': threading.Event(), 'error': None, 'started': time.time()}
            _jobs[key] = job

            def worker():
                try:
                    job['error'] = _run_conversion(key, src_path, fmt, title, author, db_type, book_id, source_stat)
                    with _lock:
                        if key in _failures:
                            _failures[key]['source'] = source_stat
                finally:
                    with _lock:
                        _jobs.pop(key, None)
                    job['event'].set()

            threading.Thread(target=worker, name=f'epaper-convert-{key}', daemon=True).start()
    timeout = _setting('EPAPER_CONVERT_TIMEOUT_SEC') if timeout is None else timeout
    if not job['event'].wait(timeout):
        print(f"[EPAPER] convert over time limit key={key} limit={timeout}s - continuing in background")
        raise Pending(retry_after=30)
    if job['error']:
        raise ConversionFailed(job['error'])
    meta = _read_meta(meta_path)
    if not meta or not os.path.exists(epub_path):
        raise ConversionFailed('converted file missing')
    return epub_path, meta


def get_book_epub(db_type, book, timeout=None):
    """도서관 책(dict: id, file_path, file_format, title, author) → (epub_path, meta)."""
    src = book['file_path']
    try:
        stat = _source_stat(src)
    except OSError as e:
        raise ConversionFailed(f'source not readable: {e}')
    return _ensure(_book_key(db_type, book['id']), src, str(book['file_format'] or '').lower(),
                   book.get('title') or '', book.get('author') or '', db_type=db_type, book_id=int(book['id']),
                   source_stat=stat, timeout=timeout)


def mark_downloaded(epub_path, meta):
    """다운로드 시각 = 파일 mtime (정리 기준). digest 매핑도 다시 확인한다."""
    try:
        os.utime(epub_path, None)
    except OSError:
        pass
    if meta.get('db_type') and meta.get('book_id') is not None and meta.get('digest'):
        _register_digest(meta['digest'], meta['db_type'], meta['book_id'])


def acquire(path):
    with _lock:
        _in_use[path] = _in_use.get(path, 0) + 1


def release(path):
    with _lock:
        n = _in_use.get(path, 0) - 1
        if n > 0:
            _in_use[path] = n
        else:
            _in_use.pop(path, None)


# ---- 업로드 (원본 SHA-256 기준) ----

def find_upload(sha256):
    epub_path, meta_path = _paths(upload_key(sha256))
    meta = _read_meta(meta_path)
    if _fresh(meta, epub_path):
        return epub_path, meta
    return None


def upload_job_state(sha256):
    key = upload_key(sha256)
    with _lock:
        if key in _jobs:
            return {'state': 'converting'}
        failure = _failures.get(key)
    if find_upload(sha256):
        return {'state': 'done'}
    if failure:
        return {'state': 'failed', 'reason': failure['reason']}
    return {'state': 'unknown'}


def start_upload_conversion(sha256, src_path, title=''):
    """업로드된 EPUB(격리 디렉터리)을 비동기 변환한다. 끝나면 원본 임시 디렉터리를 지운다."""
    key = upload_key(sha256)

    def run():
        try:
            _ensure(key, src_path, 'epub', title, '', timeout=24 * 3600)
        except (Pending, ConversionFailed):
            pass
        finally:
            shutil.rmtree(os.path.dirname(src_path), ignore_errors=True)

    threading.Thread(target=run, name=f'epaper-upload-{sha256[:8]}', daemon=True).start()


def upload_staging_dir():
    path = os.path.join(cache_dir(), 'staging')
    os.makedirs(path, exist_ok=True)
    return path


# ---- 표지 (피드용 JPEG) ----

def feed_cover(db_type, book):
    """책 표지 → 그레이스케일 JPEG 경로 (없으면 None)."""
    cover = str(book.get('cover_image') or '').strip()
    if not cover:
        return None
    from services.cover_storage_service import get_covers_dir
    covers_root = os.path.realpath(get_covers_dir())
    src = os.path.realpath(os.path.join(covers_root, cover))
    if not src.startswith(covers_root + os.sep) or not os.path.isfile(src):
        return None
    stat = _source_stat(src)
    tag = hashlib.md5(f"{cover}:{stat['size']}:{stat['mtime_ns']}:{profile_version()}".encode()).hexdigest()[:12]
    out = os.path.join(cache_dir(), 'covers', db_type, f"{int(book['id'])}.{tag}.jpg")
    if os.path.exists(out):
        return out
    from services import epaper
    with open(src, 'rb') as f:
        data = epaper.to_feed_jpeg(f.read())
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, out)
    # 같은 책의 옛 표지 정리
    prefix = f"{int(book['id'])}."
    for name in os.listdir(os.path.dirname(out)):
        if name.startswith(prefix) and name != os.path.basename(out):
            try:
                os.remove(os.path.join(os.path.dirname(out), name))
            except OSError:
                pass
    return out


# ---- 정리 / 현황 ----

def _cache_files():
    root = cache_dir()
    files = []
    if not os.path.isdir(root):
        return files
    for dirpath, _dirs, names in os.walk(root):
        if os.path.basename(dirpath) == 'staging':
            continue
        for name in names:
            if name.endswith(('.epub', '.jpg')):
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                files.append((path, st.st_size, st.st_mtime))
    return files


def _remove_entry(path):
    removed = 0
    targets = [path]
    if path.endswith('.epub'):
        targets.append(path[:-5] + '.json')
    for target in targets:
        try:
            removed += os.path.getsize(target)
            os.remove(target)
        except OSError:
            pass
    return removed


def cleanup(now=None):
    """오래된 것과 용량 초과분을 지운다. {'removed', 'freed_bytes', 'kept', 'total_bytes'}."""
    from services.system_health_service import SystemHealthService
    with SystemHealthService.track(HEALTH_KEY, HEALTH_LABEL):
        now = now or time.time()
        max_age = _setting('EPAPER_CACHE_DAYS') * 86400
        max_bytes = _setting('EPAPER_CACHE_MAX_MB') * 1024 * 1024
        with _lock:
            busy = set(_in_use)
            busy_keys = set(_jobs)
        busy |= {_paths(k)[0] for k in busy_keys}
        files = sorted(_cache_files(), key=lambda f: f[2])
        removed = freed = 0
        kept = []
        for path, size, mtime in files:
            if path not in busy and now - mtime > max_age:
                freed += _remove_entry(path)
                removed += 1
            else:
                kept.append((path, size, mtime))
        total = sum(f[1] for f in kept)
        survivors = []
        for path, size, mtime in kept:
            if total > max_bytes and path not in busy:
                freed += _remove_entry(path)
                removed += 1
                total -= size
            else:
                survivors.append(path)
        # 오래 남은 업로드 임시 디렉터리 (하루)
        staging = os.path.join(cache_dir(), 'staging')
        if os.path.isdir(staging):
            for name in os.listdir(staging):
                path = os.path.join(staging, name)
                try:
                    if now - os.path.getmtime(path) > 86400:
                        shutil.rmtree(path, ignore_errors=True)
                except OSError:
                    pass
        if removed:
            print(f"[EPAPER] cache cleanup removed={removed} freed={freed} kept={len(survivors)} total={total}")
        return {'removed': removed, 'freed_bytes': freed, 'kept': len(survivors), 'total_bytes': total}


def status():
    """관리용 현황 (MCP 도구)."""
    files = _cache_files()
    with _lock:
        converting = sorted(_jobs)
    return {
        'profile': profile_version(),
        'cache_dir': cache_dir(),
        'books': sum(1 for f in files if f[0].endswith('.epub')),
        'total_bytes': sum(f[1] for f in files),
        'limits': {'days': _setting('EPAPER_CACHE_DAYS'), 'max_mb': _setting('EPAPER_CACHE_MAX_MB'),
                   'convert_timeout_sec': _setting('EPAPER_CONVERT_TIMEOUT_SEC')},
        'converting': converting,   # 이 프로세스에서 변환 중인 것 (MCP 프로세스에서는 늘 빈 목록)
        'recent_failures': _read_failure_log(),
    }


def clear_cache():
    """변환본·표지 캐시를 모두 지운다(변환 중·전송 중인 파일 제외). 지운 수."""
    with _lock:
        busy = set(_in_use) | {_paths(k)[0] for k in _jobs}
    removed = 0
    for path, _size, _mtime in _cache_files():
        if path not in busy:
            _remove_entry(path)
            removed += 1
    with _lock:
        _failures.clear()
    try:
        os.remove(os.path.join(cache_dir(), FAILURE_LOG_NAME))
    except OSError:
        pass
    print(f"[EPAPER] cache cleared removed={removed}")
    return removed
