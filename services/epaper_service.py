# -*- coding: utf-8 -*-
"""
epaper_service.py – e-paper 리더용 변환본 캐시 (코어 쪽 접점).

- 변환기 services/epaper/ 를 부르는 곳은 여기 하나다(변환기는 DB·설정을 모른다).
- 변환은 기기 피드(/opds-epaper/v1)의 받기 링크와 웹 메뉴 "기기용 받기"(/api/media/books/<id>/epaper)를 요청할 때만,
  그 책 한 권만 한다. 표준 /opds 와 웹 다운로드 버튼은 원본을 그대로 보낸다.
- 프로필: 피드·피드 표지·업로드는 사용자 설정 EPAPER_FEED_DEVICE(없으면 v1), 웹 메뉴는 EPAPER_WEB_DEVICE(없으면 기능 꺼짐).
  설정값은 모델 id이고 services/epaper/devices.py 가 프로필로 바꾼다. TXT 원본은 늘 TXT_PROFILE_ID(v1)로 변환한다.
- 첫 요청 때 변환을 시작하고 EPAPER_CONVERT_TIMEOUT_SEC(기본 45초)까지 기다린다. 넘으면 '변환 중'으로 답하고
  백그라운드에서 마저 한다. 같은 책을 동시에 요청해도 변환은 한 번이다(책별 작업 하나).
- 캐시 키: 책 = <db_type>/<book_id>.<프로필>.epub, 업로드 = upload/<sha256>.<프로필>.epub. 옆에 .json(보고서·digest·원본 stat).
  원본 크기·수정 시각, 전역 CONVERTER_REVISION, EPUB이면 프로필 revision(메타에 없으면 1)이 바뀌면 다시 변환한다.
  캐시는 언제 지워도 다시 만들 수 있다.
- 정리: 마지막 다운로드(파일 mtime) 기준 EPAPER_CACHE_DAYS(30일) 지난 것, 그리고 EPAPER_CACHE_MAX_MB(2048) 넘으면
  오래된 것부터. 변환 중·전송 중인 파일은 건너뛴다.
- 변환본 digest(KOReader partial MD5)를 kosync 문서 매핑에 원본과 같은 book_id로 등록한다.
"""
import hashlib
import json
import os
import re
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


def default_profile():
    from services.epaper import DEFAULT_PROFILE
    return DEFAULT_PROFILE


def converter_revision():
    from services.epaper import CONVERTER_REVISION
    return CONVERTER_REVISION


# ---- 사용자 → 프로필 ----

DEVICE_SETTING_KEYS = {'web': 'EPAPER_WEB_DEVICE', 'feed': 'EPAPER_FEED_DEVICE'}


def user_device(user_id, kind):
    """사용자의 기기 설정 → {'model_id', 'model', 'missing'}. 사용자 값만 읽는다(전역값으로 넘어가지 않는다).
    빈 값 = 설정 없음. 표에 없거나 쓰는 곳이 맞지 않는 id = 없음으로 동작하고 missing=True."""
    from services.epaper import devices
    key = DEVICE_SETTING_KEYS[kind]
    raw = ''
    if user_id is not None:
        try:
            from services.settings_service import SettingsService
            raw = str(SettingsService.get_user_value(user_id, key, '') or '').strip()
        except Exception:
            raw = ''
    if not raw:
        return {'model_id': '', 'model': None, 'missing': False}
    model = devices.get_model(raw)
    if not devices.usable_for(model, kind):
        print(f"[EPAPER] device setting not found user={user_id} key={key} value={raw[:64]} - treated as none")
        return {'model_id': raw, 'model': None, 'missing': True}
    return {'model_id': raw, 'model': model, 'missing': False}


def profile_for_user(user_id, kind):
    """kind='feed' → 피드 기기 프로필(없으면 기본 v1). kind='web' → 웹 받기 기기 프로필(없으면 None = 기능 꺼짐)."""
    from services.epaper import PROFILES
    model = user_device(user_id, kind)['model']
    if model is not None:
        return PROFILES[model.profile]
    return default_profile() if kind == 'feed' else None


def _is_txt(fmt):
    return str(fmt or '').lower() in ('txt', 'text')


def _effective_profile(fmt, prof):
    """TXT는 프로필과 무관하게 TXT_PROFILE_ID 하나로 변환·캐시한다."""
    from services.epaper import PROFILES, TXT_PROFILE_ID
    if _is_txt(fmt):
        return PROFILES[TXT_PROFILE_ID]
    return prof or default_profile()


def _fresh(meta, epub_path, source_stat=None, prof=None):
    """캐시 변환본을 그대로 써도 되는가: 파일이 있고, 같은 변환기 리비전이고, 원본이 바뀌지 않았고,
    EPUB이면 같은 프로필 revision이다(메타에 값이 없으면 1 = 3.2.0 캐시). TXT는 전역 리비전만 본다."""
    if not (bool(meta) and os.path.exists(epub_path) and meta.get('revision') == converter_revision()
            and (source_stat is None or meta.get('source') == source_stat)):
        return False
    if prof is not None and not _is_txt(meta.get('source_format')):
        return int(meta.get('profile_revision') or 1) == int(prof.revision)
    return True


def _book_key(db_type, book_id, prof):
    return f'{db_type}/{int(book_id)}.{prof.id}'


def upload_key(sha256, prof):
    return f'upload/{sha256}.{prof.id}'


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


def _run_conversion(key, src_path, fmt, title, author, db_type=None, book_id=None, source_stat=None, prof=None):
    from services import epaper
    from services.kosync_service import partial_md5
    epub_path, meta_path = _paths(key)
    os.makedirs(os.path.dirname(epub_path), exist_ok=True)
    started = time.time()
    try:
        prof = _effective_profile(fmt, prof)
        report = epaper.convert(src_path, epub_path, fmt, title=title, author=author, profile=prof)
        digest = partial_md5(epub_path)
        seconds = round(time.time() - started, 2)
        meta = {'key': key, 'profile': report.get('profile') or prof.id, 'revision': converter_revision(),
                'source_format': fmt, 'digest': digest,
                'db_type': db_type, 'book_id': book_id, 'source': source_stat, 'seconds': seconds,
                'size': os.path.getsize(epub_path), 'converted_at': int(time.time()), 'report': report}
        if not _is_txt(fmt):
            meta['profile_revision'] = int(prof.revision)
        _write_meta(meta_path, meta)
        if db_type and book_id is not None:
            _register_digest(digest, db_type, book_id)
        print(f"[EPAPER] convert ok key={key} profile={meta['profile']} format={fmt} seconds={seconds} size={meta['size']} digest={digest} "
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


def _ensure(key, src_path, fmt, title, author, db_type=None, book_id=None, source_stat=None, timeout=None, prof=None):
    """캐시에 있으면 (epub_path, meta), 없으면 변환. 시간 안에 못 끝나면 Pending, 실패면 ConversionFailed."""
    epub_path, meta_path = _paths(key)
    with _lock:
        job = _jobs.get(key)
        if job is None:
            meta = _read_meta(meta_path)
            if _fresh(meta, epub_path, source_stat, prof):
                return epub_path, meta
            failure = _failures.get(key)
            if failure and time.time() - failure['at'] < FAILURE_RETRY_SEC and failure.get('source') == source_stat:
                raise ConversionFailed(failure['reason'])
            job = {'event': threading.Event(), 'error': None, 'started': time.time()}
            _jobs[key] = job

            def worker():
                try:
                    job['error'] = _run_conversion(key, src_path, fmt, title, author, db_type, book_id, source_stat, prof)
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


def get_book_epub(db_type, book, profile=None, timeout=None):
    """도서관 책(dict: id, file_path, file_format, title, author) → (epub_path, meta).
    profile을 안 주면 기본 프로필. TXT는 profile과 상관없이 TXT_PROFILE_ID."""
    src = book['file_path']
    fmt = str(book['file_format'] or '').lower()
    prof = _effective_profile(fmt, profile)
    try:
        stat = _source_stat(src)
    except OSError as e:
        raise ConversionFailed(f'source not readable: {e}')
    return _ensure(_book_key(db_type, book['id'], prof), src, fmt,
                   book.get('title') or '', book.get('author') or '', db_type=db_type, book_id=int(book['id']),
                   source_stat=stat, timeout=timeout, prof=prof)


def glyph_summary(meta, prof):
    """변환 보고서 → 받는 기기용 글자 요약. BookOasis 펌웨어 기기가 아니거나 □가 될 글자가 없으면 None.
    {'font': 기본 폰트, 'missing': 글자 수, 'kinds': 종류 수, 'sample': 견본, 'better': [[폰트, 글자 수], ...]}
    better = 기본 폰트보다 덜 빠지는 폰트(적은 순, 최대 2개)."""
    if prof is None or not prof.bookoasis_firmware:
        return None
    g = ((meta or {}).get('report') or {}).get('glyphs') or {}
    if not g.get('missing_chars') or not isinstance(g.get('fonts'), dict):
        return None
    better = sorted(((name, int(f.get('missing_chars') or 0)) for name, f in g['fonts'].items()
                     if int(f.get('missing_chars') or 0) < g['missing_chars']), key=lambda x: (x[1], x[0]))
    return {'font': g.get('default_font') or '', 'missing': int(g['missing_chars']),
            'kinds': int(g.get('missing_distinct') or 0), 'sample': str(g.get('missing_sample') or '')[:10],
            'better': [list(x) for x in better[:2]]}


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


# ---- 업로드 (원본 SHA-256 기준, 프로필은 요청한 사용자의 피드 기기) ----

def find_upload(sha256, prof):
    epub_path, meta_path = _paths(upload_key(sha256, prof))
    meta = _read_meta(meta_path)
    if _fresh(meta, epub_path, prof=prof):
        return epub_path, meta
    return None


def upload_job_state(sha256, prof):
    key = upload_key(sha256, prof)
    with _lock:
        if key in _jobs:
            return {'state': 'converting'}
        failure = _failures.get(key)
    if find_upload(sha256, prof):
        return {'state': 'done'}
    if failure:
        return {'state': 'failed', 'reason': failure['reason']}
    return {'state': 'unknown'}


def start_upload_conversion(sha256, src_path, prof, title=''):
    """업로드된 EPUB(격리 디렉터리)을 비동기 변환한다. 끝나면 원본 임시 디렉터리를 지운다.
    prof는 POST 시점에 정한다(변환 스레드에는 요청 맥락이 없다)."""
    key = upload_key(sha256, prof)

    def run():
        try:
            _ensure(key, src_path, 'epub', title, '', timeout=24 * 3600, prof=prof)
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

_COVER_TAG = re.compile(r'^[0-9a-f]{12}$')


def _is_profile_cover(name, book_id, prof):
    """프로필 하나의 표지 파일인가. v1은 3.2.0 형식(<id>.<tag>.jpg) 그대로, 나머지는 <id>.<프로필>.<tag>.jpg."""
    parts = name.split('.')
    if parts[-1] != 'jpg' or parts[0] != str(int(book_id)) or not _COVER_TAG.match(parts[-2]):
        return False
    middle = parts[1:-2]
    return middle == ([] if prof.id == default_profile().id else [prof.id])


def feed_cover(db_type, book, prof=None):
    """책 표지 → 그레이스케일 JPEG 경로 (없으면 None). prof를 안 주면 기본 프로필."""
    prof = prof or default_profile()
    cover = str(book.get('cover_image') or '').strip()
    if not cover:
        return None
    from services.cover_storage_service import get_covers_dir
    covers_root = os.path.realpath(get_covers_dir())
    src = os.path.realpath(os.path.join(covers_root, cover))
    if not src.startswith(covers_root + os.sep) or not os.path.isfile(src):
        return None
    stat = _source_stat(src)
    tag_src = f"{cover}:{stat['size']}:{stat['mtime_ns']}:{prof.id}"
    if int(prof.revision) != 1:
        tag_src += f":r{int(prof.revision)}"  # revision 1은 넣지 않아 3.2.0 표지 이름을 지킨다
    tag = hashlib.md5(tag_src.encode()).hexdigest()[:12]
    middle = '' if prof.id == default_profile().id else f'{prof.id}.'
    out = os.path.join(cache_dir(), 'covers', db_type, f"{int(book['id'])}.{middle}{tag}.jpg")
    if os.path.exists(out):
        return out
    from services import epaper
    with open(src, 'rb') as f:
        data = epaper.to_feed_jpeg(f.read(), prof)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, out)
    # 같은 책·같은 프로필의 옛 표지 정리 (다른 프로필의 표지는 그대로 둔다)
    for name in os.listdir(os.path.dirname(out)):
        if _is_profile_cover(name, book['id'], prof) and name != os.path.basename(out):
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


def _profile_of_cache_file(path):
    """변환본 파일 이름 <id 또는 sha>.<프로필>.epub → 프로필 id."""
    stem = os.path.basename(path)[:-5]
    return stem.rsplit('.', 1)[-1] if '.' in stem else '?'


def status():
    """관리용 현황 (MCP 도구). profiles = 프로필별 변환본 수·크기(표지는 파일 이름으로 프로필을 다 알 수 없어 뺀다)."""
    files = _cache_files()
    with _lock:
        converting = sorted(_jobs)
    per_profile = {}
    for path, size, _mtime in files:
        if not path.endswith('.epub'):
            continue
        entry = per_profile.setdefault(_profile_of_cache_file(path), {'files': 0, 'bytes': 0})
        entry['files'] += 1
        entry['bytes'] += size
    return {
        'default_profile': default_profile().id,
        'profiles': dict(sorted(per_profile.items())),
        'cache_dir': cache_dir(),
        'epub_files': sum(1 for f in files if f[0].endswith('.epub')),
        'cover_files': sum(1 for f in files if f[0].endswith('.jpg')),
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
