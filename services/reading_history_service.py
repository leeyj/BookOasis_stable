# -*- coding: utf-8 -*-
import json
from repositories.sqlite.reading_progress_repository import ReadingProgressRepository
from services.book_service import get_cover_image_with_t
from utils.redis_helper import redis_get, redis_set


def _merge_live_progress_from_redis(db_type, user_id, item):
    if not item or not item.get('id'):
        return item

    cached_progress = redis_get(f"user:progress:{db_type}:{user_id}:{item['id']}")
    if not cached_progress:
        return item

    try:
        progress = json.loads(cached_progress)
    except Exception:
        return item

    pages_read = progress.get('pages_read')
    last_read_at = progress.get('last_read_at')
    is_completed = progress.get('is_completed')

    if pages_read is not None:
        item['pages_read'] = pages_read
    if last_read_at:
        item['last_read_at'] = last_read_at
    if is_completed is not None:
        item['is_completed'] = is_completed

    return item

class ReadingHistoryService:
    @staticmethod
    def get_history(db_type, user_id=1):
        def apply_live_progress(items):
            merged = [
                _merge_live_progress_from_redis(db_type, user_id, dict(item))
                for item in (items or [])
            ]
            merged.sort(key=lambda item: str(item.get('last_read_at') or ''), reverse=True)
            return merged

        # 1. Redis 캐시 확인
        cache_key = f"cache:history:{db_type}:{user_id}"
        cached_data = redis_get(cache_key)
        if cached_data:
            try:
                return apply_live_progress(json.loads(cached_data))
            except Exception:
                pass

        # 표시 건수 설정 조회
        row_limit = ReadingProgressRepository.get_settings_value(db_type, 'RECENT_BOOKS_LIMIT')
        limit = 30
        if row_limit and str(row_limit).isdigit():
            limit = int(row_limit)

        # 완독 도서 숨김 설정 조회
        row_hide = ReadingProgressRepository.get_settings_value(db_type, 'HIDE_COMPLETED_IN_HISTORY')
        hide_completed = (row_hide == '1')

        rows = ReadingProgressRepository.fetch_reading_history(db_type, user_id, limit, hide_completed)
        
        result = [
            {
                'id'          : r['id'],
                'library_id'  : r['library_id'],
                'title'       : r['title'],
                'series_name' : r['series_name'] or '기타 단행본',
                'cover_image' : get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_format' : r['file_format'],
                'pages_read'  : r['pages_read']  or 0,
                'total_pages' : r['total_pages'] or 0,
                'is_completed': r['is_completed'] or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'last_read_at': r['last_read_at'],
            }
            for r in rows
        ]

        result = apply_live_progress(result)

        # 2. Redis 캐시 세팅 (3600초=1시간 만료 설정)
        try:
            redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=3600)
        except Exception:
            pass

        return result


    @staticmethod
    def get_recently_added(db_type, user_id=None, role=None):
        # 1. Redis 캐시 확인
        cache_key = f"cache:recent_added:{db_type}:{user_id}:{role}"
        cached_data = redis_get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                pass

        if user_id and role != 'admin':
            rows = ReadingProgressRepository.fetch_recently_added_by_user(db_type, user_id)
        else:
            rows = ReadingProgressRepository.fetch_recently_added_all(db_type, user_id)
            
        result = [
            {
                'id'          : r['id'],
                'library_id'  : r['library_id'],
                'title'       : r['title'],
                'series_name' : r['series_name'] or '기타 단행본',
                'cover_image' : get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_format' : r['file_format'],
                'total_pages' : r['total_pages'] or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'created_at'  : r['created_at'],
            }
            for r in rows
        ]

        # 2. Redis 캐시 세팅 (3600초=1시간 만료 설정)
        try:
            redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=3600)
        except Exception:
            pass

        return result
