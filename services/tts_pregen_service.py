# -*- coding: utf-8 -*-
"""
tts_pregen_service.py - 듣기(TTS) 서버 미리 만들기: 작업 큐, 조각 음성 캐시, 백그라운드 합성 스레드

흐름: 듣기 화면이 책 전체를 조각으로 나눠(문장 나누기·한자 변환은 브라우저 몫) 조각 텍스트와 키를
보낸다 → 작업(tts_pregen_jobs)으로 쌓고 조각 목록은 파일로 둔다 → 이 모듈의 작업 스레드가 조각마다
합성해 책 폴더에 모아 저장한다 → 끝나면 웹훅(tts.ready)을 보낸다.
재생할 때 듣기 화면은 같은 키로 조회해 있으면 받아서 틀고, 없으면 기기에서 만든다.

저장 형식(2026-09-28, v2.8.0): <저장 경로>/<db_type>/books/<book_id>/<목소리>_<품질단계>_<속도>_<음질>/chNNNN_PP.pack
- pack = 그 챕터 조각의 완결된 m4a 파일들을 바이트로 그대로 이어 붙인 것(64MB 넘으면 _01, _02 …).
  tts_audio_pieces(목차)의 byte_offset/byte_length로 잘라내면 원래 m4a가 그대로 나오므로, 조각 URL
  (/api/media/tts/audio/<db>/<key>.m4a)과 듣기 화면의 재생 코드는 예전과 같다.
- 예전(v2.7.9)엔 조각마다 <k[:2]>/<k>.m4a로 흩어 저장해 한 권에 파일이 2만 개씩 생기고, 어떤 책 것인지·
  책별 용량을 알 수 없었다. 예전 조각은 옮기지 않고 기동 시 지운다(purge_legacy_cache) — 다시 만들면 된다.
- 디스크 상한 정리와 삭제는 책(폴더) 단위다.

- 기본 꺼짐. 관리자 설정 TTS_PREGEN_ENABLED=1일 때만 작업을 받고 처리한다.
- 저장 경로는 관리자 설정 TTS_AUDIO_ROOT(절대 경로), 비우면 <설치 폴더>/tts_audio. Docker는 컨테이너를
  다시 만들면 볼륨 밖 파일이 지워지므로, 그 경로가 볼륨 위에 있을 때만 동작한다(compose 기본: ./tts_audio:/app/tts_audio).
- gunicorn 워커 안의 데몬 스레드 하나가 한 번에 한 작업만 한다. 재시작·배포로 끊겨도 heartbeat가
  끊긴 작업을 다시 가져와 이미 만든 조각은 건너뛰고 이어서 한다.
"""
import json
import os
import re
import shutil
import threading
import time
import traceback

from repositories.tts_pregen_repository import TTSPregenRepository
from services import tts_engine
from services.settings_service import SettingsService

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_AUDIO_ROOT = os.path.join(_ROOT, 'tts_audio')
AUDIO_ROOT = None  # 테스트에서 고정할 때만 쓴다. 평소에는 audio_root()가 설정을 읽는다
DB_TYPES = ('general', 'adult')

KEY_RE = re.compile(r'^[0-9a-f]{64}$')
MAX_PIECES = 30000
MAX_PIECE_CHARS = 400
MAX_ACTIVE_PER_USER = 3
MAX_LOOKUP_KEYS = 5000
STALE_MS = 120_000          # heartbeat가 이만큼 끊긴 running 작업은 다시 가져간다
PROGRESS_EVERY = 10         # 조각 N개마다 진행률 저장
ENGINE_IDLE_SEC = 600       # 일이 없으면 모델을 내려 메모리를 돌려준다
MAX_CONSECUTIVE_FAILURES = 5
WORKER_NICE = 19           # 가장 낮은 우선순위 — 웹·스캔이 CPU를 쓰면 먼저 양보하고, 한가할 때만 전속력으로 만든다

DEFAULT_THREADS = 2
DEFAULT_DISK_GB = 10
PACK_MAX_BYTES = 64 * 1024 * 1024   # 챕터 pack 파일 하나의 최대 크기 (넘으면 다음 part로)
DISK_CAP_EVERY = 500                # 긴 책을 만드는 동안에도 조각 N개마다 상한을 확인한다
LEGACY_DIR_RE = re.compile(r'^[0-9a-f]{2}$')
LEGACY_FILE_RE = re.compile(r'^[0-9a-f]{64}\.m4a$')


def _now_ms():
    return int(time.time() * 1000)


# ---- 설정 ----
def is_enabled():
    return str(SettingsService.get('TTS_PREGEN_ENABLED', '0')).strip() in ('1', 'true', 'on', 'yes')


def _int_setting(key, default, lo, hi):
    try:
        value = int(str(SettingsService.get(key, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(lo, min(hi, value))


def thread_count():
    return _int_setting('TTS_PREGEN_THREADS', DEFAULT_THREADS, 1, 16)


def disk_cap_bytes():
    return _int_setting('TTS_PREGEN_DISK_GB', DEFAULT_DISK_GB, 1, 10000) * (1024 ** 3)


def quality_setting():
    """관리자 설정 TTS_PREGEN_QUALITY — 'standard'(64k, 기본) 또는 'compact'(32k·24kHz, 절반 크기)"""
    value = str(SettingsService.get('TTS_PREGEN_QUALITY', tts_engine.DEFAULT_QUALITY) or '').strip()
    return value if value in tts_engine.QUALITIES else tts_engine.DEFAULT_QUALITY


# ---- 저장 경로 ----
# audio_root()는 조회 한 번에 수천 번 불리므로 설정값을 프로세스 안에 캐시한다. 설정을 저장하면 invalidate_root_cache().
_root_cache = None


def _in_docker():
    return os.path.exists('/.dockerenv')


def invalidate_root_cache():
    global _root_cache
    _root_cache = None


def audio_root():
    """(경로, 오류 이유). 이유가 있으면 이 경로에 저장하면 안 된다."""
    global _root_cache
    if AUDIO_ROOT:
        return AUDIO_ROOT, ''
    if _root_cache is None:
        override = str(SettingsService.get('TTS_AUDIO_ROOT', '') or '').strip()
        _root_cache = override
    override = _root_cache
    if override and not os.path.isabs(override):
        return override, 'audio path must be absolute'
    root = override or DEFAULT_AUDIO_ROOT
    # Docker: 볼륨이 아닌 곳에 쓰면 컨테이너를 다시 만들 때 전부 사라진다 → 기본값(/app/tts_audio)이든 지정 경로든 볼륨이어야 한다
    if _in_docker() and not _on_mounted_volume(root):
        return root, f'{root} is not on a mounted volume (files would be lost when the container is recreated) — mount a volume there or set TTS_AUDIO_ROOT'
    return root, ''


def _on_mounted_volume(path):
    """path 또는 그 상위 폴더 중 '/'가 아닌 마운트 지점이 있으면 True (Docker 볼륨/바인드 마운트)."""
    current = os.path.abspath(path)
    while True:
        if current != os.path.dirname(current) and os.path.ismount(current):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def book_rel_dir(book_id, voice, steps, speed, quality):
    """책·설정별 음성 폴더 (db_type 폴더 기준 상대 경로, '/' 구분)"""
    return f'books/{int(book_id)}/{voice}_{int(steps)}_{tts_engine._js_number(speed)}_{quality}'


def book_dir(db_type, rel_dir):
    return os.path.join(audio_root()[0], db_type, *rel_dir.split('/'))


def pack_path(db_type, rel_dir, chapter, part):
    return os.path.join(book_dir(db_type, rel_dir), f'ch{int(chapter):04d}_{int(part):02d}.pack')


def _manifest_path(db_type, job_id):
    return os.path.join(audio_root()[0], db_type, 'jobs', f'{int(job_id)}.json')


# ---- 요청 처리 (라우트에서 호출) ----
def _validate_settings(payload):
    voice = payload.get('voice')
    if voice not in tts_engine.VOICES:
        raise ValueError('invalid voice')
    try:
        steps = int(payload.get('steps'))
        speed = float(payload.get('speed'))
    except (TypeError, ValueError):
        raise ValueError('invalid steps/speed')
    if steps not in tts_engine.STEPS:
        raise ValueError('invalid steps')
    if not any(abs(speed - s) < 1e-9 for s in tts_engine.SPEEDS):
        raise ValueError('invalid speed')
    return voice, steps, speed


def _validate_pieces(pieces, voice, steps, speed):
    """[{chapter, text, key}] 검증. 키는 서버가 다시 계산해 일치해야 한다(엉뚱한 키로 캐시를 오염시키지 못하게).
    같은 키는 한 번만 남긴다."""
    if not isinstance(pieces, list) or not pieces:
        raise ValueError('pieces required')
    if len(pieces) > MAX_PIECES:
        raise ValueError(f'too many pieces (max {MAX_PIECES})')
    seen = set()
    out = []
    for piece in pieces:
        if not isinstance(piece, dict):
            raise ValueError('invalid piece')
        text = piece.get('text')
        key = piece.get('key')
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_PIECE_CHARS:
            raise ValueError('invalid piece text')
        if not isinstance(key, str) or key != tts_engine.piece_key(voice, steps, speed, text):
            raise ValueError('piece key mismatch')
        try:
            chapter = max(0, int(piece.get('chapter', 0)))
        except (TypeError, ValueError):
            chapter = 0
        if key in seen:
            continue
        seen.add(key)
        out.append({'c': chapter, 't': text, 'k': key})
    return out


def create_job(db_type, book_id, user_id, payload):
    """작업을 만들고 (job, created)를 돌려준다. 같은 책·설정의 진행 중 작업이 있으면 그것을 돌려준다."""
    voice, steps, speed = _validate_settings(payload)
    _root, reason = audio_root()
    if reason:
        raise RuntimeError(reason)
    existing = TTSPregenRepository.find_active_job(db_type, book_id, voice, steps, speed)
    if existing:
        return existing, False
    pieces = _validate_pieces(payload.get('pieces'), voice, steps, speed)
    if TTSPregenRepository.count_active_by_user(db_type, user_id) >= MAX_ACTIVE_PER_USER:
        raise PermissionError(f'too many active jobs (max {MAX_ACTIVE_PER_USER})')
    job_id = TTSPregenRepository.create_job(db_type, book_id, user_id, voice, steps, speed, len(pieces), _now_ms(),
                                            quality=quality_setting())
    path = _manifest_path(db_type, job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f'{path}.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'pieces': pieces}, f, ensure_ascii=False)
    os.replace(tmp, path)
    _queued_cache['at'] = 0.0
    wake_worker()
    return TTSPregenRepository.get_job(db_type, job_id), True


def job_view(job):
    """API 응답용 요약"""
    if not job:
        return None
    total = int(job.get('total_pieces') or 0)
    done = int(job.get('done_pieces') or 0)
    return {
        'id': job['id'],
        'status': job['status'],
        'voice': job['voice'],
        'steps': int(job['steps']),
        'speed': float(job['speed']),
        'quality': job.get('quality') or tts_engine.DEFAULT_QUALITY,
        'total_pieces': total,
        'done_pieces': done,
        'percent': int(done * 100 / total) if total else 0,
        'error': job.get('error') or None,
        'created_ms': job.get('created_ms'),
        'finished_ms': job.get('finished_ms'),
    }


def latest_status(db_type, book_id):
    return job_view(TTSPregenRepository.latest_job(db_type, book_id))


def cancel_job(db_type, job_id, user_id, is_admin):
    job = TTSPregenRepository.get_job(db_type, job_id)
    if not job:
        raise LookupError('job not found')
    if not is_admin and int(job['user_id']) != int(user_id):
        raise PermissionError('not your job')
    return TTSPregenRepository.cancel(db_type, job_id, _now_ms())


def admin_status():
    """관리자 화면: 사용 가능 여부와 대기/진행 작업 수, 캐시 크기 (일반+성인 합계)"""
    available, reason = tts_engine.availability()
    root, root_reason = audio_root()
    if available and root_reason:
        available, reason = False, root_reason
    queued = running = 0
    cache_bytes = 0
    for db_type in DB_TYPES:
        try:
            counts = TTSPregenRepository.count_by_status(db_type)
            queued += counts.get('queued', 0)
            running += counts.get('running', 0)
            cache_bytes += TTSPregenRepository.total_audio_bytes(db_type)
        except Exception as e:
            print(f"[TTS-Pregen] admin status failed ({db_type}): {e}")
    return {
        'enabled': is_enabled(), 'available': available, 'reason': reason,
        'queued': queued, 'running': running, 'cache_mb': round(cache_bytes / (1024 * 1024)), 'audio_root': root,
    }


def _existing_pieces(db_type, keys):
    """{key: 목차 행} — pack 파일이 실제로 있고 그 구간까지 쓰여 있는 것만"""
    found = TTSPregenRepository.find_pieces(db_type, keys)
    sizes = {}
    out = {}
    for key, row in found.items():
        path = pack_path(db_type, row['rel_dir'], row['chapter'], row['part'])
        if path not in sizes:
            try:
                sizes[path] = os.path.getsize(path)
            except OSError:
                sizes[path] = -1
        if sizes[path] >= int(row['byte_offset']) + int(row['byte_length']):
            out[key] = row
    return out


def lookup(db_type, keys):
    """{key: duration_sec} — 파일까지 실제로 있는 것만. 찾은 조각의 책은 최근 사용 시각을 갱신한다(디스크 정리 기준)."""
    if not isinstance(keys, list):
        raise ValueError('keys must be a list')
    keys = [k for k in dict.fromkeys(keys) if isinstance(k, str) and KEY_RE.match(k)][:MAX_LOOKUP_KEYS]
    if not keys:
        return {}
    found = _existing_pieces(db_type, keys)
    if found:
        try:
            TTSPregenRepository.touch_audio_books(db_type, {row['audio_book_id'] for row in found.values()}, _now_ms())
        except Exception as e:
            print(f"[TTS-Pregen] touch failed (ignored): {e}")
    return {k: float(row['duration_sec']) for k, row in found.items()}


def read_piece(db_type, key):
    """조각 하나의 m4a 바이트 (없으면 None). pack 파일에서 목차의 구간만 읽는다."""
    row = _existing_pieces(db_type, [key]).get(key)
    if not row:
        return None
    with open(pack_path(db_type, row['rel_dir'], row['chapter'], row['part']), 'rb') as f:
        f.seek(int(row['byte_offset']))
        data = f.read(int(row['byte_length']))
    return data if len(data) == int(row['byte_length']) else None


def _remove_book_dir(db_type, rel_dir):
    path = book_dir(db_type, rel_dir)
    shutil.rmtree(path, ignore_errors=True)
    # 책 폴더(books/<book_id>)가 비면 같이 지운다
    parent = os.path.dirname(path)
    try:
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    except OSError:
        pass


# ---- 디스크 상한 ----
def enforce_disk_cap(db_type, keep_id=None):
    """캐시 합계가 상한을 넘으면 오래 안 들은 책부터 폴더째 지운다 (성인/일반은 각자 상한).
    keep_id(지금 만드는 책)는 지우지 않는다 — 한 권이 상한보다 커도 그 책은 끝까지 만든다."""
    cap = disk_cap_bytes()
    total = TTSPregenRepository.total_audio_bytes(db_type)
    while total > cap:
        victims = [b for b in TTSPregenRepository.oldest_audio_books(db_type, 50) if b['id'] != keep_id]
        if not victims:
            break
        for book in victims:
            _remove_book_dir(db_type, book['rel_dir'])
            TTSPregenRepository.delete_audio_book(db_type, book['id'])
            total -= int(book['bytes'])
            print(f"[TTS-Pregen] disk cap: removed {db_type}/{book['rel_dir']} ({int(book['bytes']) // (1024 * 1024)}MB)")
            if total <= cap:
                break


# ---- "음성 준비됨" 목록 ----
def list_ready_books(db_type, user_id, is_admin):
    """음성이 저장된 책 목록 (서버의 모든 책 — 음성은 공용이라 같은 설정이면 누구나 이어 쓴다).
    카드용 도서 정보 + 음성 설정/음질/용량/길이 + 이 사용자가 지울 수 있는지."""
    rows = TTSPregenRepository.list_audio_books(db_type)
    books = TTSPregenRepository.books_brief(db_type, {r['book_id'] for r in rows}, int(user_id or 0))
    out = []
    for r in rows:
        book = books.get(int(r['book_id']))
        if not book:
            continue
        out.append({
            **book,
            'tts': {
                'id': int(r['id']), 'voice': r['voice'], 'steps': int(r['steps']), 'speed': float(r['speed']),
                'quality': r['quality'], 'pieces': int(r['pieces']), 'bytes': int(r['bytes']),
                'duration_sec': float(r['duration_sec'] or 0), 'last_used_ms': r['last_used_ms'],
                'can_delete': bool(is_admin) or int(r['created_by']) == int(user_id or 0),
            },
        })
    return out


def delete_audio_book(db_type, audio_book_id, user_id, is_admin):
    """책 음성 폴더 삭제. 처음 만든 사람이나 관리자만. 지금 만드는 중이면 거절(먼저 취소)."""
    book = TTSPregenRepository.get_audio_book(db_type, audio_book_id)
    if not book:
        raise LookupError('not found')
    if not is_admin and int(book['created_by']) != int(user_id or 0):
        raise PermissionError('not yours')
    active = TTSPregenRepository.find_active_job(db_type, book['book_id'], book['voice'], int(book['steps']), float(book['speed']))
    if active and (active.get('quality') or tts_engine.DEFAULT_QUALITY) == book['quality']:
        raise RuntimeError('being generated')
    _remove_book_dir(db_type, book['rel_dir'])
    TTSPregenRepository.delete_audio_book(db_type, audio_book_id)
    return True


# ---- 예전(v2.7.9) 조각 단위 캐시 정리 ----
def purge_legacy_cache():
    """<저장 경로>/<db>/<2자리 hex>/<64자리 hex>.m4a와 끝난 작업의 목록 파일을 지운다. 사용자가 저장 경로를 다른
    파일과 같이 쓰는 폴더로 지정했을 수도 있어 이 이름 규칙에 맞는 것만 지운다. 몇 번 불려도 안전하다."""
    root, reason = audio_root()
    if reason or not os.path.isdir(root):
        return 0
    removed = 0
    for db_type in DB_TYPES:
        base = os.path.join(root, db_type)
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            sub = os.path.join(base, name)
            if not LEGACY_DIR_RE.match(name) or not os.path.isdir(sub):
                continue
            for fname in os.listdir(sub):
                if LEGACY_FILE_RE.match(fname):
                    try:
                        os.remove(os.path.join(sub, fname))
                        removed += 1
                    except OSError as e:
                        print(f"[TTS-Pregen] legacy remove failed: {fname}: {e}")
            try:
                if not os.listdir(sub):
                    os.rmdir(sub)
            except OSError:
                pass
        jobs_dir = os.path.join(base, 'jobs')
        if os.path.isdir(jobs_dir):
            for fname in os.listdir(jobs_dir):
                m = re.match(r'^(\d+)\.json$', fname)
                if not m:
                    continue
                try:
                    job = TTSPregenRepository.get_job(db_type, int(m.group(1)))
                    if not job or job['status'] not in ('queued', 'running'):
                        os.remove(os.path.join(jobs_dir, fname))
                except Exception as e:
                    print(f"[TTS-Pregen] legacy manifest cleanup failed: {fname}: {e}")
        try:
            TTSPregenRepository.clear_legacy_cache(db_type)
        except Exception as e:
            print(f"[TTS-Pregen] legacy index cleanup failed ({db_type}): {e}")
    if removed:
        print(f"[TTS-Pregen] removed {removed} legacy piece files (pre-v2.8.0 layout)")
    return removed


# ---- 알림 ----
def _notify_ready(db_type, job):
    """완료 알림: 사람용 알림 채널(텔레그램/디스코드 등) + 플러그인용 표준 이벤트 웹훅. 실패해도 작업 결과에는 영향 없음."""
    try:
        from repositories.book_repository import BookRepository
        from repositories.reading_progress_repository import ReadingProgressRepository
        from services.webhook_dispatcher import build_book_event_payload, dispatch_standard_book_event, dispatch_webhook_event
        book = BookRepository.get_book_reader_info(db_type, job['book_id']) or {}
        user_id = int(job['user_id'])
        username = ReadingProgressRepository.get_username_by_id(db_type, user_id) or f'user-{user_id}'
        metadata = {
            'type': 'book',
            'format': str(book.get('file_format') or '').lower(),
            'title': book.get('title') or '',
            'author': book.get('author') or '',
            'bookId': int(job['book_id']),
            'session': db_type,
            'voice': job['voice'],
            'steps': int(job['steps']),
            'speed': float(job['speed']),
            'pieces': int(job.get('total_pieces') or 0),
        }
        account = {'id': user_id, 'title': username}
        dispatch_standard_book_event(build_book_event_payload('tts.ready', account=account, metadata=metadata, user=True))
        dispatch_webhook_event('tts.ready', {'title': metadata['title'], 'account': username, 'book_id': metadata['bookId'], 'session': db_type})
    except Exception as e:
        print(f"[TTS-Pregen] notify skipped: {e}")



# ---- 알림 영역(스캔 활동 팝오버)용 상태 ----
# /api/system/status가 2초마다 부르므로 DB를 매번 치지 않는다: 진행 중 작업과 최근 완료는 작업 스레드가
# 메모리에 남기고, 대기 작업 목록만 짧게 캐시해 DB에서 읽는다(요청 직후에는 캐시를 비워 바로 보이게).
RECENT_KEEP_MS = 30 * 60 * 1000
QUEUED_CACHE_SEC = 15
_activity_lock = threading.Lock()
_running_info = None
_recent_infos = []
_queued_cache = {'at': 0.0, 'rows': []}
_title_cache = {}


def _book_title(db_type, book_id):
    key = (db_type, int(book_id))
    if key not in _title_cache:
        try:
            from repositories.book_repository import BookRepository
            info = BookRepository.get_book_reader_info(db_type, book_id) or {}
            _title_cache[key] = info.get('title') or f'#{book_id}'
        except Exception:
            return f'#{book_id}'
        if len(_title_cache) > 500:
            _title_cache.clear()
    return _title_cache[key]


def _job_info(db_type, job, status=None, done=None):
    total = int(job.get('total_pieces') or 0)
    done = int(job.get('done_pieces') or 0) if done is None else done
    return {
        'id': int(job['id']), 'db_type': db_type, 'book_id': int(job['book_id']), 'user_id': int(job['user_id']),
        'title': _book_title(db_type, job['book_id']), 'status': status or job['status'],
        'percent': int(done * 100 / total) if total else 0, 'finished_ms': job.get('finished_ms'),
        'done': done, 'total': total,
    }


def _set_running(info):
    global _running_info
    with _activity_lock:
        _running_info = info


def _update_running(done):
    with _activity_lock:
        if _running_info and _running_info.get('total'):
            _running_info['done'] = done
            _running_info['percent'] = int(done * 100 / _running_info['total'])


def _record_finished(db_type, job_id):
    global _running_info
    job = TTSPregenRepository.get_job(db_type, job_id)
    with _activity_lock:
        _running_info = None
        # 끈 탓에 멈춘 작업(running 그대로)은 완료 목록에 올리지 않는다
        if job and job['status'] in ('done', 'failed', 'cancelled'):
            _recent_infos.insert(0, _job_info(db_type, job))
            del _recent_infos[20:]
    _queued_cache['at'] = 0.0


def _queued_rows():
    now = time.time()
    if now - _queued_cache['at'] > QUEUED_CACHE_SEC:
        rows = []
        for db_type in DB_TYPES:
            try:
                rows += [_job_info(db_type, job) for job in TTSPregenRepository.list_active(db_type) if job['status'] == 'queued']
            except Exception as e:
                print(f"[TTS-Pregen] queued list failed ({db_type}): {e}")
        _queued_cache.update(at=now, rows=rows)
    return _queued_cache['rows']


def activity_for(user_id, is_admin, adult_ok):
    """스캔 활동 팝오버용: 이 사용자가 볼 수 있는 진행/대기/최근 완료 작업. 관리자는 모두, 성인 세션 작업은 권한이 있을 때만."""
    def visible(info):
        if info['db_type'] == 'adult' and not adult_ok:
            return False
        return is_admin or info['user_id'] == int(user_id or 0)

    cutoff = _now_ms() - RECENT_KEEP_MS
    with _activity_lock:
        running = dict(_running_info) if _running_info else None
        recent = [dict(i) for i in _recent_infos if (i.get('finished_ms') or 0) >= cutoff]
    items = []
    if running and visible(running):
        items.append(running)
    items += [i for i in _queued_rows() if visible(i) and not (running and i['id'] == running['id'] and i['db_type'] == running['db_type'])]
    items += [i for i in recent if visible(i)]
    for i in items:
        i.pop('user_id', None)
    return items


# ---- 작업 스레드 ----
class _Worker:
    def __init__(self):
        self._wake = threading.Event()
        self._thread = None
        self._engine = None
        self._engine_threads = None
        self._last_work = 0.0
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, name='tts-pregen', daemon=True)
            self._thread.start()

    def wake(self):
        self._wake.set()

    def _engine_for(self, threads):
        if self._engine is None or self._engine_threads != threads:
            self._engine = None
            t0 = time.time()
            self._engine = tts_engine.Engine(threads=threads)
            self._engine_threads = threads
            print(f"[TTS-Pregen] engine loaded ({threads} threads, {time.time() - t0:.1f}s)")
        return self._engine

    def _run(self):
        _lower_thread_priority()
        try:
            purge_legacy_cache()
        except Exception as e:
            print(f"[TTS-Pregen] legacy cleanup failed: {e}")
        while True:
            try:
                worked = self._tick()
            except Exception as e:
                print(f"[TTS-Pregen] worker error: {e}")
                traceback.print_exc()
                worked = False
            if worked:
                continue
            if self._engine is not None and time.time() - self._last_work > ENGINE_IDLE_SEC:
                self._engine = None
                print("[TTS-Pregen] engine released (idle)")
            self._wake.wait(30)
            self._wake.clear()

    def _tick(self):
        if not is_enabled():
            return False
        ok, _reason = tts_engine.availability()
        if not ok or audio_root()[1]:
            return False
        now = _now_ms()
        for db_type in DB_TYPES:
            try:
                job = TTSPregenRepository.claim_next(db_type, now, now - STALE_MS)
            except Exception as e:
                print(f"[TTS-Pregen] claim failed ({db_type}): {e}")
                continue
            if job:
                self._process(db_type, job)
                return True
        return False

    def _process(self, db_type, job):
        job_id = job['id']
        voice, steps, speed = job['voice'], int(job['steps']), float(job['speed'])
        try:
            with open(_manifest_path(db_type, job_id), encoding='utf-8') as f:
                pieces = json.load(f)['pieces']
        except (OSError, ValueError, KeyError) as e:
            TTSPregenRepository.finish(db_type, job_id, 'failed', _now_ms(), error=f'manifest missing: {e}')
            return
        print(f"[TTS-Pregen] job {db_type}#{job_id} book {job['book_id']}: {len(pieces)} pieces ({voice}, {steps}, {speed})")
        info = _job_info(db_type, job, status='running')
        info['total'] = len(pieces)
        _set_running(info)
        try:
            self._process_pieces(db_type, job, pieces)
        finally:
            _record_finished(db_type, job_id)
            _drop_manifest_if_finished(db_type, job_id)

    def _process_pieces(self, db_type, job, pieces):
        job_id = job['id']
        voice, steps, speed = job['voice'], int(job['steps']), float(job['speed'])
        quality = job.get('quality') or tts_engine.DEFAULT_QUALITY
        audio_book = TTSPregenRepository.get_or_create_audio_book(
            db_type, job['book_id'], voice, steps, speed, quality,
            book_rel_dir(job['book_id'], voice, steps, speed, quality), job['user_id'], _now_ms())
        packs = _BookPacks(db_type, audio_book)
        started = time.time()
        made = 0
        done = 0
        failures = 0
        failed = 0
        last_save = time.time()
        for piece in pieces:
            if not is_enabled():
                # 관리자가 끈 경우: 상태는 running 그대로 두면 heartbeat가 끊겨 다시 켤 때 이어서 한다
                print(f"[TTS-Pregen] job {db_type}#{job_id} paused (disabled)")
                return
            key = piece['k']
            if key not in packs.keys:
                try:
                    engine = self._engine_for(thread_count())
                    wav = engine.synthesize(piece['t'], voice, steps, speed)
                    data = tts_engine.encode_m4a_bytes(wav, engine.sample_rate, quality, tmp_dir=packs.tmp_dir)
                    packs.append(key, int(piece.get('c', 0)), data, len(wav) / engine.sample_rate)
                    made += 1
                    failures = 0
                    if made % DISK_CAP_EVERY == 0:
                        enforce_disk_cap(db_type, keep_id=audio_book['id'])
                except Exception as e:
                    # 조각 하나가 실패하면 건너뛰고(그 조각은 재생 때 기기가 만든다), 연달아 실패하면 작업을 멈춘다 —
                    # 그러지 않으면 heartbeat가 끊겼다가 다시 가져가기를 끝없이 되풀이한다
                    failures += 1
                    failed += 1
                    print(f"[TTS-Pregen] job {db_type}#{job_id} piece {done + 1} failed: {e}")
                    if failures >= MAX_CONSECUTIVE_FAILURES:
                        TTSPregenRepository.finish(db_type, job_id, 'failed', _now_ms(), error=str(e)[:500], done_pieces=done)
                        return
                self._last_work = time.time()
            done += 1
            _update_running(done)
            if done % PROGRESS_EVERY == 0 or time.time() - last_save > 30:
                last_save = time.time()
                if not TTSPregenRepository.update_progress(db_type, job_id, done, _now_ms()):
                    print(f"[TTS-Pregen] job {db_type}#{job_id} stopped (cancelled)")
                    return
        cached = done - made - failed
        summary = f"{made} made, {cached} cached, {failed} failed, {time.time() - started:.0f}s"
        if failed and not made and not cached:
            # 한 조각도 못 만들었으면 완료가 아니라 실패다 (조각 수가 연속 실패 한도보다 적은 책)
            TTSPregenRepository.finish(db_type, job_id, 'failed', _now_ms(), error=f'all {failed} pieces failed', done_pieces=done)
            print(f"[TTS-Pregen] job {db_type}#{job_id} failed: {summary}")
            return
        # 일부만 실패하면 완료로 두고 몇 개가 빠졌는지 남긴다 (빠진 조각은 재생 때 기기가 만든다)
        TTSPregenRepository.finish(db_type, job_id, 'done', _now_ms(), error=(f'{failed} pieces failed' if failed else None), done_pieces=done)
        print(f"[TTS-Pregen] job {db_type}#{job_id} done: {summary}")
        # 방금 만든 책이 "오래 안 들은 책"으로 먼저 지워지지 않게 사용 시각을 지금으로
        TTSPregenRepository.touch_audio_books(db_type, [audio_book['id']], _now_ms())
        try:
            enforce_disk_cap(db_type, keep_id=audio_book['id'])
        except Exception as e:
            print(f"[TTS-Pregen] disk cap failed: {e}")
        _notify_ready(db_type, TTSPregenRepository.get_job(db_type, job_id) or job)


class _BookPacks:
    """한 책 폴더의 pack 파일 쓰기. 조각 m4a를 챕터별 pack 끝에 이어 붙이고 목차 행을 넣는다.
    쓰기 → 목차 순서라 중간에 죽으면 pack 끝에 쓰레기 바이트만 남는다(무해). 시작할 때 목차가 가리키는 구간이
    파일보다 길면(반쯤 쓰인 조각) 그 목차 행은 버리고 다시 만든다."""

    def __init__(self, db_type, audio_book):
        self.db_type = db_type
        self.book = audio_book
        self.dir = book_dir(db_type, audio_book['rel_dir'])
        self.tmp_dir = os.path.join(audio_root()[0], db_type, '.tmp')  # 인코딩 임시 파일 (책 폴더를 깨끗하게)
        os.makedirs(self.dir, exist_ok=True)
        self.keys = set()
        self.parts = {}   # chapter -> 지금 쓰는 part 번호
        broken = []
        sizes = {}
        for row in TTSPregenRepository.book_pieces(db_type, audio_book['id']):
            path = pack_path(db_type, audio_book['rel_dir'], row['chapter'], row['part'])
            if path not in sizes:
                sizes[path] = os.path.getsize(path) if os.path.isfile(path) else -1
            if sizes[path] < int(row['byte_offset']) + int(row['byte_length']):
                broken.append(row['piece_key'])
                continue
            self.keys.add(row['piece_key'])
            self.parts[row['chapter']] = max(self.parts.get(row['chapter'], 0), int(row['part']))
        if broken:
            print(f"[TTS-Pregen] {db_type}/{audio_book['rel_dir']}: dropping {len(broken)} truncated pieces")
            TTSPregenRepository.remove_pieces(db_type, audio_book['id'], broken)

    def append(self, key, chapter, data, duration_sec):
        part = self.parts.get(chapter, 0)
        path = pack_path(self.db_type, self.book['rel_dir'], chapter, part)
        if os.path.isfile(path) and os.path.getsize(path) + len(data) > PACK_MAX_BYTES:
            part += 1
            path = pack_path(self.db_type, self.book['rel_dir'], chapter, part)
        with open(path, 'ab') as f:
            f.seek(0, os.SEEK_END)
            offset = f.tell()
            f.write(data)
        self.parts[chapter] = part
        TTSPregenRepository.add_piece(self.db_type, self.book['id'], key, chapter, part, offset, len(data), duration_sec)
        self.keys.add(key)


def _drop_manifest_if_finished(db_type, job_id):
    """끝난(완료·실패·취소) 작업의 조각 목록 파일은 더 필요 없다"""
    try:
        job = TTSPregenRepository.get_job(db_type, job_id)
        if job and job['status'] in ('done', 'failed', 'cancelled'):
            os.remove(_manifest_path(db_type, job_id))
    except OSError:
        pass
    except Exception as e:
        print(f"[TTS-Pregen] manifest cleanup failed: {e}")


def _lower_thread_priority():
    """이 스레드(작업 스레드)의 우선순위를 가장 낮춘다. 리눅스는 nice가 스레드 단위이고 새 스레드는 만든 스레드의
    값을 물려받으므로, 모델을 불러오기 전에 해 두면 onnxruntime 계산 스레드와 ffmpeg까지 모두 낮은 우선순위로 돈다.
    권한이 필요 없는 방향(낮추기)이라 Docker에서도 된다. 지원하지 않는 OS(Windows)는 그냥 넘어간다."""
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), WORKER_NICE)
        print(f"[TTS-Pregen] worker priority lowered (nice {os.getpriority(os.PRIO_PROCESS, threading.get_native_id())})")
    except (AttributeError, OSError) as e:
        print(f"[TTS-Pregen] could not lower worker priority (ignored): {e}")


_worker = _Worker()


def start_worker():
    """core.py 기동 시 한 번 호출. 꺼져 있어도 스레드는 떠 있고, 켜지면 30초 안에(요청이 오면 즉시) 일을 시작한다."""
    _worker.start()


def wake_worker():
    _worker.wake()
