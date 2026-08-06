import json
import logging
import threading
import time
import atexit
from datetime import datetime

from repositories.sqlite.reading_progress_repository import ReadingProgressRepository
from services.webhook_dispatcher import (
    build_book_event_payload,
    dispatch_standard_book_event,
    _to_unix_timestamp,
)
from utils.redis_helper import get_redis_client, make_key, redis_del, redis_acquire_lock, redis_release_lock

logger = logging.getLogger("bookoasis")

class InMemoryProgressBuffer:
    """Thread-safe 파이썬 인메모리 버퍼 (Redis 미사용 / DB 동시 쓰기 락 방지용)"""
    _lock = threading.Lock()
    _buffer = {}  # key: "db_type:user_id:book_id" -> payload dict

    @classmethod
    def set(cls, db_type: str, user_id, book_id, payload: dict):
        key = f"{db_type}:{user_id}:{book_id}"
        with cls._lock:
            cls._buffer[key] = payload

    @classmethod
    def get(cls, db_type: str, user_id, book_id):
        key = f"{db_type}:{user_id}:{book_id}"
        with cls._lock:
            val = cls._buffer.get(key)
            return dict(val) if val else None

    @classmethod
    def delete(cls, db_type: str, user_id, book_id):
        key = f"{db_type}:{user_id}:{book_id}"
        with cls._lock:
            cls._buffer.pop(key, None)

    @classmethod
    def pop_all(cls):
        with cls._lock:
            data = dict(cls._buffer)
            cls._buffer.clear()
            return data

    @classmethod
    def count(cls):
        with cls._lock:
            return len(cls._buffer)


class ReadingProgressService:
    @staticmethod
    def record_progress(db_type: str, book_id, page_idx: int, total_pages: int, user_id=1, epub_session=None):
        """독서 진행률 및 활동 로그 기록 (0ms 메모리 버퍼링 및 비동기 배치 DB 저장을 통한 SQLite Lock 완벽 방지)"""
        book_row = ReadingProgressRepository.get_book_for_progress(db_type, book_id)

        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = 0

        try:
            total_pages = int(total_pages)
        except Exception:
            total_pages = 0

        file_format = (book_row['file_format'] or '').lower() if book_row else ''
        is_epub = file_format == 'epub'

        # EPUB은 저장 단위를 0~100 퍼센트로 정규화하여 크로스 디바이스 오차를 줄인다.
        if is_epub:
            raw_total = max(1, total_pages)
            raw_idx = max(0, page_idx)
            normalized_percent = int(round(((raw_idx + 1) / raw_total) * 100))
            normalized_percent = max(0, min(100, normalized_percent))
            total_pages = 100
            page_idx = max(0, normalized_percent - 1)

        # 실제 프론트엔드에서 전달된 총 페이지(챕터) 수를 기반으로 DB 업데이트
        if total_pages > 0 and book_row and book_row['total_pages'] != total_pages:
            ReadingProgressRepository.update_book_total_pages(db_type, book_id, total_pages)

        pages_read = page_idx + 1
        is_completed = 0
        if total_pages > 0:
            if (pages_read / total_pages) >= 0.95 or pages_read >= total_pages:
                is_completed = 1

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        epub_session = epub_session or {}
        last_epub_cfi = epub_session.get('cfi')
        last_epub_href = epub_session.get('href')
        last_epub_spine_index = epub_session.get('index')
        last_epub_percent = epub_session.get('percent')
        last_epub_fingerprint = epub_session.get('fingerprint')

        if is_epub:
            if last_epub_percent is None:
                last_epub_percent = max(0, min(100, int(page_idx + 1)))
            else:
                try:
                    last_epub_percent = int(round(float(last_epub_percent)))
                except Exception:
                    last_epub_percent = max(0, min(100, int(page_idx + 1)))
                last_epub_percent = max(0, min(100, last_epub_percent))

        has_epub_pointer_update = (
            last_epub_cfi is not None
            or last_epub_href is not None
            or last_epub_spine_index is not None
            or last_epub_percent is not None
            or last_epub_fingerprint is not None
        )
        last_epub_updated_at = now_str if has_epub_pointer_update else None

        # 사용자의 최근 읽은 도서 캐시 무효화 (대시보드 실시간 반영)
        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern(f"cache:history*:{db_type}:{user_id}")
        except Exception:
            pass

        redis_client = get_redis_client()
        old_pages = 0
        old_completed = 0

        # 기존 펜딩된 메모리/레디스 버퍼나 DB에서 이전 진행 상태 확인
        mem_data = InMemoryProgressBuffer.get(db_type, user_id, book_id)
        if mem_data:
            old_pages = mem_data.get('pages_read', 0)
            old_completed = mem_data.get('is_completed', 0)
        elif redis_client:
            cache_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
            cached_data_str = redis_client.get(cache_key)
            if cached_data_str:
                try:
                    cached_data = json.loads(cached_data_str)
                    old_pages = cached_data.get('pages_read', 0)
                    old_completed = cached_data.get('is_completed', 0)
                except Exception:
                    pass
        if old_pages == 0 and old_completed == 0:
            db_row = ReadingProgressRepository.get_progress_only(db_type, book_id, user_id)
            if db_row:
                old_pages = db_row['pages_read']
                old_completed = 1 if db_row['is_completed'] == 1 else 0

        if old_completed == 1:
            is_completed = 1

        delta = max(0, pages_read - old_pages)

        progress_payload = {
            'pages_read': pages_read,
            'is_completed': is_completed,
            'last_read_at': now_str,
            'last_epub_cfi': last_epub_cfi,
            'last_epub_href': last_epub_href,
            'last_epub_spine_index': last_epub_spine_index,
            'last_epub_percent': last_epub_percent,
            'last_epub_fingerprint': last_epub_fingerprint,
            'last_epub_updated_at': last_epub_updated_at,
            'delta': delta
        }

        if redis_client:
            # 1. Redis 환경: Redis 캐시 기록 및 펜딩 큐 등록
            cache_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
            redis_client.set(cache_key, json.dumps(progress_payload))
            pending_sync_key = make_key("sync:progress:pending")
            redis_client.sadd(pending_sync_key, f"{db_type}:{user_id}:{book_id}")
        else:
            # 2. Non-Redis 환경: 파이썬 인메모리 버퍼에 0ms 즉시 기록 (DB 락 방지)
            InMemoryProgressBuffer.set(db_type, user_id, book_id, progress_payload)

        # 표준 이벤트 웹훅(book.read / book.finish) 발행
        try:
            account_name = f"user-{user_id}"
            try:
                username = ReadingProgressRepository.get_username_by_id(db_type, user_id)
                if username:
                    account_name = str(username)
            except Exception:
                pass

            effective_total_pages = total_pages if total_pages > 0 else (book_row['total_pages'] if book_row else 0)
            if effective_total_pages and effective_total_pages > 0:
                progress_percent = max(0, min(100, int(round((pages_read / effective_total_pages) * 100))))
            else:
                progress_percent = 0

            fmt = (book_row['file_format'] or '').lower() if book_row else ''
            location = None
            if fmt == 'epub':
                if last_epub_href:
                    location = last_epub_href
                elif last_epub_cfi:
                    location = last_epub_cfi
                elif last_epub_spine_index is not None:
                    location = f"spine:{last_epub_spine_index}"
            elif fmt == 'txt':
                location = f"chunk:{max(1, page_idx + 1)}"
            elif pages_read > 0:
                location = f"page:{pages_read}"

            metadata = {
                'type': 'book',
                'format': fmt,
                'title': (book_row['title'] if book_row else '') or '',
                'author': (book_row['author'] if book_row else '') or '',
                'publisher': (book_row['publisher'] if book_row else '') or '',
                'series': (book_row['series_name'] if book_row else '') or None,
                'seriesIndex': None,
                'progress': progress_percent,
                'totalPages': int(effective_total_pages) if effective_total_pages and effective_total_pages > 0 else None,
                'currentLocation': location,
                'addedAt': _to_unix_timestamp(book_row['created_at'] if book_row else None),
            }

            account = {
                'id': int(user_id),
                'title': account_name,
            }

            should_emit_read = delta > 0
            should_emit_finish = old_completed == 0 and is_completed == 1

            if should_emit_read:
                payload = build_book_event_payload('book.read', account=account, metadata=metadata, user=True)
                dispatch_standard_book_event(payload)

            if should_emit_finish:
                payload = build_book_event_payload('book.finish', account=account, metadata=metadata, user=True)
                dispatch_standard_book_event(payload)
        except Exception as webhook_err:
            print(f"[Progress Webhook] dispatch skipped due to error: {webhook_err}")

    @staticmethod
    def get_progress_state(db_type: str, book_id, user_id=1):
        row = ReadingProgressRepository.get_progress_state(db_type, book_id, user_id)
        if not row:
            return None

        file_format = (row['file_format'] or '').lower()
        total_pages = row['total_pages'] if row['total_pages'] is not None else 0
        pages_read = row['pages_read'] if row['pages_read'] is not None else 0
        last_read_at = row['last_read_at']
        last_epub_cfi = row['last_epub_cfi']
        last_epub_href = row['last_epub_href']
        last_epub_spine_index = row['last_epub_spine_index']
        last_epub_percent = row['last_epub_percent'] if row['last_epub_percent'] is not None else 0
        last_epub_fingerprint = row['last_epub_fingerprint']
        last_epub_updated_at = row['last_epub_updated_at']

        # 1. 인메모리 버퍼 펜딩 데이터 우선 병합 (Read Merge)
        mem_data = InMemoryProgressBuffer.get(db_type, user_id, book_id)
        if mem_data:
            pages_read = mem_data.get('pages_read', pages_read)
            last_read_at = mem_data.get('last_read_at', last_read_at)
            last_epub_cfi = mem_data.get('last_epub_cfi', last_epub_cfi)
            last_epub_href = mem_data.get('last_epub_href', last_epub_href)
            last_epub_spine_index = mem_data.get('last_epub_spine_index', last_epub_spine_index)
            last_epub_percent = mem_data.get('last_epub_percent', last_epub_percent)
            last_epub_fingerprint = mem_data.get('last_epub_fingerprint', last_epub_fingerprint)
            last_epub_updated_at = mem_data.get('last_epub_updated_at', last_epub_updated_at)
        else:
            # 2. 레디스 캐시 데이터 병합 가드
            redis_client = get_redis_client()
            if redis_client:
                cache_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
                cached_data_str = redis_client.get(cache_key)
                if cached_data_str:
                    try:
                        cached_data = json.loads(cached_data_str)
                        pages_read = cached_data.get('pages_read', pages_read)
                        last_read_at = cached_data.get('last_read_at', last_read_at)
                        last_epub_cfi = cached_data.get('last_epub_cfi', last_epub_cfi)
                        last_epub_href = cached_data.get('last_epub_href', last_epub_href)
                        last_epub_spine_index = cached_data.get('last_epub_spine_index', last_epub_spine_index)
                        last_epub_percent = cached_data.get('last_epub_percent', last_epub_percent)
                        last_epub_fingerprint = cached_data.get('last_epub_fingerprint', last_epub_fingerprint)
                        last_epub_updated_at = cached_data.get('last_epub_updated_at', last_epub_updated_at)
                    except Exception:
                        pass

        # 로드 시점에는 DB를 변경하지 않고, 응답 값만 비파괴 정규화
        if file_format == 'epub':
            normalized_total = 100
            normalized_pages = pages_read

            if last_epub_percent:
                normalized_pages = last_epub_percent

            try:
                normalized_pages = int(normalized_pages)
            except Exception:
                normalized_pages = 0

            normalized_pages = max(0, min(100, normalized_pages))

            total_pages = normalized_total
            pages_read = normalized_pages

        return {
            'total_pages': total_pages,
            'pages_read': pages_read,
            'last_read_at': last_read_at,
            'epub_session': {
                'cfi': last_epub_cfi,
                'href': last_epub_href,
                'index': last_epub_spine_index,
                'percent': last_epub_percent,
                'fingerprint': last_epub_fingerprint,
                'updatedAt': last_epub_updated_at,
            },
        }

    @staticmethod
    def mark_unread(db_type: str, book_id, user_id=1):
        ReadingProgressRepository.delete_user_progress_by_book(db_type, book_id, user_id)
        InMemoryProgressBuffer.delete(db_type, user_id, book_id)

        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern(f"cache:history*:{db_type}:{user_id}")
        except Exception:
            pass

        redis_client = get_redis_client()
        if not redis_client:
            return

        progress_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
        audio_progress_key = make_key(f"user:audiobook_progress:{user_id}:{book_id}")
        pending_key = make_key("sync:progress:pending")
        pending_member = f"{db_type}:{user_id}:{book_id}"

        try:
            redis_client.delete(progress_key)
            redis_client.delete(audio_progress_key)
            redis_client.srem(pending_key, pending_member)
        except Exception as e:
            logger.warning(f"[Redis] mark_unread cache invalidation failed for {pending_member}: {e}")

    @staticmethod
    def flush_progress_cache():
        """인메모리 버퍼 및 Redis 캐시에 쌓여 있는 비동기 진행률 데이터를 SQLite DB 파일에 동기화(Flush)합니다."""
        items_dict = {}

        # 1. 인메모리 버퍼 펜딩 수집
        mem_batch = InMemoryProgressBuffer.pop_all()
        for key_str, payload in mem_batch.items():
            items_dict[key_str] = payload

        # 2. Redis 펜딩 수집 (Redis 활성화 시)
        redis_client = get_redis_client()
        if redis_client:
            pending_key = make_key("sync:progress:pending")
            pending_items = redis_client.smembers(pending_key)
            if pending_items:
                for item in pending_items:
                    item_str = item.decode('utf-8') if isinstance(item, bytes) else item
                    parts = item_str.split(':')
                    if len(parts) >= 3:
                        db_type, user_id, book_id = parts[0], parts[1], parts[2]
                        cache_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
                        cached_data_str = redis_client.get(cache_key)
                        if cached_data_str:
                            try:
                                data = json.loads(cached_data_str)
                                items_dict[item_str] = data
                            except Exception:
                                pass
                        redis_client.srem(pending_key, item)

        if not items_dict:
            return 0

        logger_db = logging.getLogger("bookoasis")
        logger_db.info(f"[Progress Batch Flush] Starting sync for {len(items_dict)} items...")

        import database
        synced_count = 0

        # db_type 별로 아이템 그룹화
        items_by_db = {}
        for item_key, payload in items_dict.items():
            parts = item_key.split(':')
            if len(parts) < 3:
                continue
            db_type = parts[0]
            if db_type not in items_by_db:
                items_by_db[db_type] = []
            items_by_db[db_type].append((item_key, payload))

        for db_type, db_items in items_by_db.items():
            lock_token = None
            try:
                if redis_client:
                    lock_token = redis_acquire_lock(f"lock:db_write:{db_type}", ttl=90, wait_timeout=5.0)
                    if not lock_token:
                        logger_db.info(f"[Progress Batch Flush] DB write gate busy for db_type={db_type}; deferred {len(db_items)} items")
                        continue

                try:
                    raw_items = []
                    for item_key, data in db_items:
                        parts = item_key.split(':')
                        item_copy = dict(data)
                        item_copy['user_id'] = parts[1]
                        item_copy['book_id'] = parts[2]
                        raw_items.append(item_copy)

                    from repositories.reading_progress_repository import ReadingProgressRepository
                    synced = ReadingProgressRepository.batch_flush_progress_items(db_type, raw_items)
                    synced_count += synced
                except Exception as db_err:
                    logger_db.error(f"[Progress Batch Flush ERROR] Database transaction failed for db_type={db_type}: {db_err}")
            finally:
                if lock_token and redis_client:
                    redis_release_lock(f"lock:db_write:{db_type}", lock_token)

        logger_db.info(f"[Progress Batch Flush] Finished sync. {synced_count} items merged to SQLite.")
        return synced_count


# ── 비동기 백그라운드 워커 스레드 ──
_inmemory_worker_started = False
_inmemory_worker_lock = threading.Lock()

def start_inmemory_flush_worker():
    global _inmemory_worker_started
    with _inmemory_worker_lock:
        if _inmemory_worker_started:
            return
        _inmemory_worker_started = True

    def worker_loop():
        while True:
            try:
                time.sleep(2)
                ReadingProgressService.flush_progress_cache()
            except Exception as e:
                logger.error(f"[Progress Worker] Flush loop exception: {e}")

    t = threading.Thread(target=worker_loop, daemon=True, name="ProgressInmemoryFlushWorker")
    t.start()
    logger.info("[Progress Worker] In-memory progress flush worker started (interval=2s)")

# 모듈 초기화 시 워커 가동 및 프로세스 종료 시 Safety Flush 자동 등록
start_inmemory_flush_worker()
atexit.register(ReadingProgressService.flush_progress_cache)
