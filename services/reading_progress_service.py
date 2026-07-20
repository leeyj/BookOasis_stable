# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime

from repositories.reading_progress_repository import ReadingProgressRepository
from services.webhook_dispatcher import (
    build_book_event_payload,
    dispatch_standard_book_event,
    _to_unix_timestamp,
)
from utils.redis_helper import get_redis_client, make_key

class ReadingProgressService:
    @staticmethod
    def record_progress(db_type: str, book_id, page_idx: int, total_pages: int, user_id=1, epub_session=None):
        """독서 진행률 및 활동 로그 기록 (EPUB 및 TXT도 실제 챕터 단위를 그대로 사용)"""
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

        # ── [레디스 캐시 분기 가드] ──
        redis_client = get_redis_client()
        
        # 1. 사용자의 최근 읽은 도서 캐시 무효화 (대시보드 실시간 반영)
        from utils.redis_helper import redis_del
        redis_del(f"cache:history:{db_type}:{user_id}")

        if redis_client:
            cache_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
            cached_data_str = redis_client.get(cache_key)
            old_pages = 0
            old_completed = 0

            if cached_data_str:
                try:
                    cached_data = json.loads(cached_data_str)
                    old_pages = cached_data.get('pages_read', 0)
                    old_completed = cached_data.get('is_completed', 0)
                except Exception:
                    pass
            else:
                db_row = ReadingProgressRepository.get_progress_only(db_type, book_id, user_id)
                if db_row:
                    old_pages = db_row['pages_read']
                    old_completed = 1 if db_row['is_completed'] == 1 else 0

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

            # Redis 캐시 기록 및 펜딩 큐 등록
            redis_client.set(cache_key, json.dumps(progress_payload))
            pending_sync_key = make_key("sync:progress:pending")
            redis_client.sadd(pending_sync_key, f"{db_type}:{user_id}:{book_id}")
        else:
            # ── 레디스가 없으면 기존 SQLite 트랜잭션 구동 ──
            row = ReadingProgressRepository.get_progress_only(db_type, book_id, user_id)
            old_completed = 1 if (row and row['is_completed'] == 1) else 0

            if not row:
                ReadingProgressRepository.insert_empty_progress(db_type, book_id, user_id, now_str)
                delta = pages_read
            else:
                old_pages = row['pages_read']
                delta = max(0, pages_read - old_pages)

            if has_epub_pointer_update:
                ReadingProgressRepository.update_progress_full(
                    db_type, book_id, user_id, pages_read, is_completed, now_str,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                )
            else:
                ReadingProgressRepository.update_progress_simple(
                    db_type, book_id, user_id, pages_read, is_completed, now_str
                )

            if delta > 0:
                today_str = datetime.now().strftime('%Y-%m-%d')
                ReadingProgressRepository.update_or_insert_reading_log(db_type, book_id, user_id, delta, today_str)

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

        # ── [레디스 캐시 리드 병합 가드] ──
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
    def flush_progress_cache():
        """Redis 캐시에 쌓여 있는 비동기 진행률 데이터를 SQLite DB 파일에 동기화(Flush)합니다."""
        redis_client = get_redis_client()
        if not redis_client:
            return 0

        pending_key = make_key("sync:progress:pending")
        pending_items = redis_client.smembers(pending_key)
        if not pending_items:
            return 0

        logger_db = logging.getLogger("bookoasis")
        logger_db.info(f"[Redis Cache Flush] Starting sync for {len(pending_items)} items...")

        synced_count = 0
        
        for item in pending_items:
            parts = item.split(':')
            if len(parts) < 3:
                continue
            db_type, user_id, book_id = parts[0], parts[1], parts[2]
            
            cache_key = make_key(f"user:progress:{db_type}:{user_id}:{book_id}")
            cached_data_str = redis_client.get(cache_key)
            if not cached_data_str:
                redis_client.srem(pending_key, item)
                continue
                
            try:
                data = json.loads(cached_data_str)
                pages_read = data.get('pages_read')
                is_completed = data.get('is_completed')
                last_read_at = data.get('last_read_at')
                last_epub_cfi = data.get('last_epub_cfi')
                last_epub_href = data.get('last_epub_href')
                last_epub_spine_index = data.get('last_epub_spine_index')
                last_epub_percent = data.get('last_epub_percent')
                last_epub_fingerprint = data.get('last_epub_fingerprint')
                last_epub_updated_at = data.get('last_epub_updated_at')
                delta = data.get('delta', 0)
                
                # 1. user_progress 테이블 반영
                row = ReadingProgressRepository.get_progress_only(db_type, book_id, user_id)
                if not row:
                    ReadingProgressRepository.insert_empty_progress(db_type, book_id, user_id, last_read_at)
                
                ReadingProgressRepository.update_progress_full(
                    db_type, book_id, user_id, pages_read, is_completed, last_read_at,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                )
                
                # 2. 일일 활동 로그 반영
                if delta > 0:
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    ReadingProgressRepository.update_or_insert_reading_log(db_type, book_id, user_id, delta, today_str)
                        
                redis_client.srem(pending_key, item)
                synced_count += 1
            except Exception as e:
                logger_db.error(f"[Redis Cache Flush ERROR] Failed to sync progress for item {item}: {e}")

        logger_db.info(f"[Redis Cache Flush] Finished sync. {synced_count} items merged to SQLite.")
        return synced_count
