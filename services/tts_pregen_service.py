# -*- coding: utf-8 -*-
"""
tts_pregen_service.py - 듣기(TTS) 서버 미리 만들기: 작업 큐, 조각 음성 캐시, 백그라운드 합성 스레드

흐름: 듣기 화면이 책 전체를 조각으로 나눠(문장 나누기·한자 변환은 브라우저 몫) 조각 텍스트와 키를
보낸다 → 작업(tts_pregen_jobs)으로 쌓고 조각 목록은 파일로 둔다 → 이 모듈의 작업 스레드가 조각마다
합성해 <저장 경로>/<db_type>/<k[:2]>/<k>.m4a로 저장한다 → 끝나면 웹훅(tts.ready)을 보낸다.
재생할 때 듣기 화면은 같은 키로 조회해 있으면 받아서 틀고, 없으면 기기에서 만든다.

- 기본 꺼짐. 관리자 설정 TTS_PREGEN_ENABLED=1일 때만 작업을 받고 처리한다.
- 저장 경로는 관리자 설정 TTS_AUDIO_ROOT(절대 경로), 비우면 <설치 폴더>/tts_audio. Docker는 컨테이너를
  다시 만들면 볼륨 밖 파일이 지워지므로, 그 경로가 볼륨 위에 있을 때만 동작한다(compose 기본: ./tts_audio:/app/tts_audio).
- gunicorn 워커 안의 데몬 스레드 하나가 한 번에 한 작업만 한다. 재시작·배포로 끊겨도 heartbeat가
  끊긴 작업을 다시 가져와 이미 만든 조각은 건너뛰고 이어서 한다.
"""
import json
import os
import re
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


# ---- 저장 경로 ----
# audio_path()는 조회 한 번에 수천 번 불리므로 설정값을 프로세스 안에 캐시한다. 설정을 저장하면 invalidate_root_cache().
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


def audio_path(db_type, key):
    return os.path.join(audio_root()[0], db_type, key[:2], f'{key}.m4a')


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
    job_id = TTSPregenRepository.create_job(db_type, book_id, user_id, voice, steps, speed, len(pieces), _now_ms())
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


def lookup(db_type, keys):
    """{key: duration_sec} — 파일까지 실제로 있는 것만. 찾은 조각은 최근 사용 시각을 갱신한다(디스크 정리 기준)."""
    if not isinstance(keys, list):
        raise ValueError('keys must be a list')
    keys = [k for k in dict.fromkeys(keys) if isinstance(k, str) and KEY_RE.match(k)][:MAX_LOOKUP_KEYS]
    if not keys:
        return {}
    found = TTSPregenRepository.get_audio(db_type, keys)
    found = {k: sec for k, sec in found.items() if os.path.isfile(audio_path(db_type, k))}
    if found:
        try:
            TTSPregenRepository.touch_audio(db_type, found.keys(), _now_ms())
        except Exception as e:
            print(f"[TTS-Pregen] touch failed (ignored): {e}")
    return found


# ---- 디스크 상한 ----
def enforce_disk_cap(db_type):
    """캐시 합계가 상한을 넘으면 오래 안 쓴 조각부터 지운다 (성인/일반은 각자 상한)."""
    cap = disk_cap_bytes()
    total = TTSPregenRepository.total_audio_bytes(db_type)
    while total > cap:
        batch = TTSPregenRepository.oldest_audio(db_type, 500)
        if not batch:
            break
        removed = []
        for key, size in batch:
            try:
                os.remove(audio_path(db_type, key))
            except FileNotFoundError:
                pass
            except OSError as e:
                print(f"[TTS-Pregen] remove failed: {key}: {e}")
                continue
            removed.append(key)
            total -= size
            if total <= cap:
                break
        TTSPregenRepository.delete_audio(db_type, removed)
        if not removed:
            break


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

    def _process_pieces(self, db_type, job, pieces):
        job_id = job['id']
        voice, steps, speed = job['voice'], int(job['steps']), float(job['speed'])
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
            if not (os.path.isfile(audio_path(db_type, key)) and TTSPregenRepository.get_audio(db_type, [key])):
                try:
                    engine = self._engine_for(thread_count())
                    wav = engine.synthesize(piece['t'], voice, steps, speed)
                    size = tts_engine.encode_m4a(wav, engine.sample_rate, audio_path(db_type, key))
                    TTSPregenRepository.put_audio(db_type, key, len(wav) / engine.sample_rate, size, _now_ms())
                    made += 1
                    failures = 0
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
        try:
            enforce_disk_cap(db_type)
        except Exception as e:
            print(f"[TTS-Pregen] disk cap failed: {e}")
        _notify_ready(db_type, TTSPregenRepository.get_job(db_type, job_id) or job)


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
