# -*- coding: utf-8 -*-
import json
from repositories.reading_progress_repository import ReadingProgressRepository
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


def _history_group_key(item):
    series_name = str(item.get('series_name') or '').strip()
    if series_name:
      return (item.get('library_id'), series_name)
    return (item.get('library_id'), f"__single__:{item.get('id')}")


def _group_history_items(items):
    groups = {}
    order = []

    for item in items or []:
        key = _history_group_key(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(dict(item))

    grouped = []
    for key in order:
        group_items = groups[key]
        group_items.sort(key=lambda item: str(item.get('last_read_at') or ''), reverse=True)
        current = group_items[0]

        if len(group_items) <= 1:
            payload = {
                **current,
                'book_count': max(1, int(current.get('history_book_count') or 1)),
                'representative_book_id': current.get('id'),
                'representative_title': current.get('title_alias') or current.get('title') or '',
            }
            current_total_tracks = int(current.get('total_tracks') or 0)
            if current_total_tracks > 0:
                payload['total_tracks'] = current_total_tracks
            grouped.append({
                **payload,
            })
            continue

        group_total_tracks = max((int(item.get('total_tracks') or 0) for item in group_items), default=0)

        grouped_item = {
            'id': current.get('id'),
            'library_id': current.get('library_id'),
            'title': current.get('title'),
            'title_alias': current.get('title_alias', '') or '',
            'series_name': current.get('series_name') or '기타 단행본',
            'series_alias': current.get('series_alias', '') or '',
            'cover_image': current.get('cover_image'),
            'file_format': current.get('file_format'),
            'pages_read': current.get('pages_read') or 0,
            'total_pages': current.get('total_pages') or 0,
            'is_completed': current.get('is_completed') or 0,
            'has_unfinished_siblings': 1 if any((item.get('has_unfinished_siblings') or 0) == 1 for item in group_items) else 0,
            'is_favorite': 1 if any((item.get('is_favorite') or 0) == 1 for item in group_items) else 0,
            'last_read_at': current.get('last_read_at'),
            'metadata_locked': 1 if any((item.get('metadata_locked') or 0) == 1 for item in group_items) else 0,
            'book_count': len(group_items),
            'representative_book_id': current.get('id'),
            'representative_title': current.get('title_alias') or current.get('title') or '',
        }
        if group_total_tracks > 0:
            grouped_item['total_tracks'] = group_total_tracks
        grouped.append(grouped_item)

    grouped.sort(key=lambda item: str(item.get('last_read_at') or ''), reverse=True)
    return grouped

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

        row_limit = ReadingProgressRepository.get_settings_value(db_type, 'RECENT_BOOKS_LIMIT')
        limit = 30
        if row_limit and str(row_limit).isdigit():
            limit = max(1, min(int(row_limit), 100))

        row_hide = ReadingProgressRepository.get_settings_value(db_type, 'HIDE_COMPLETED_IN_HISTORY')
        hide_completed = (row_hide == '1')

        # 설정별로 캐시를 분리해 노출 개수 변경을 즉시 반영한다.
        cache_key = f"cache:history:v7:{db_type}:{user_id}:{limit}:{int(hide_completed)}"
        cached_data = redis_get(cache_key)
        if cached_data:
            try:
                parsed = json.loads(cached_data)
                if parsed and isinstance(parsed, list):
                    if len(parsed) == 0:
                        return parsed

                    first = parsed[0]
                    has_base_fields = ('series_alias' in first and 'book_count' in first)
                    if not has_base_fields:
                        pass
                    elif db_type == 'audiobook':
                        # v5 오디오북 캐시는 total_tracks 필드가 필수이다.
                        # 구버전 캐시(v4 등)는 해당 필드가 없어 카드 수치가 1로 폴백될 수 있다.
                        if 'total_tracks' in first:
                            return parsed
                    else:
                        return parsed
            except Exception:
                pass

        rows = ReadingProgressRepository.fetch_reading_history(db_type, user_id, limit, hide_completed)
        
        result = [
            {
                'id'          : r['id'],
                'library_id'  : r['library_id'],
                'title'       : r['title'],
                'title_alias' : r.get('title_alias', '') or '',
                'series_name' : r['series_name'] or '기타 단행본',
                'series_alias': r.get('series_alias', '') or '',
                'cover_image' : get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_format' : r['file_format'],
                'pages_read'  : r['pages_read']  or 0,
                'total_pages' : r['total_pages'] or 0,
                'is_completed': r['is_completed'] or 0,
                'has_unfinished_siblings': r.get('has_unfinished_siblings', 0) or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'last_read_at': r['last_read_at'],
                'metadata_locked': r.get('metadata_locked', 0),
                **({'total_tracks': (r.get('total_tracks', 0) or 0)} if db_type == 'audiobook' else {}),
            }
            for r in rows
        ]

        result = apply_live_progress(result)
        result = _group_history_items(result)[:limit]

        # 2. Redis 캐시 세팅 (3600초=1시간 만료 설정)
        try:
            redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=3600)
        except Exception:
            pass

        return result


    @staticmethod
    def get_recently_added(db_type, user_id=None, role=None):
        # 1. Redis 캐시 확인 (구형 캐시에 series_alias 없으면 DB 재조회)
        cache_key = f"cache:recent_added:v2:{db_type}:{user_id}:{role}"
        cached_data = redis_get(cache_key)
        if cached_data:
            try:
                parsed = json.loads(cached_data)
                if parsed and isinstance(parsed, list) and (len(parsed) == 0 or 'series_alias' in parsed[0]):
                    return parsed
            except Exception:
                pass

        if role == 'admin':
            # 관리자: 전체 카테고리 도서 조회
            rows = ReadingProgressRepository.fetch_recently_added_all(db_type, user_id)
        else:
            # 일반 유저 또는 user_id=None: 권한 있는 카테고리만 조회
            # user_id=None이면 user_category_permissions JOIN 매칭 없음 → 빈 목록 반환
            rows = ReadingProgressRepository.fetch_recently_added_by_user(db_type, user_id)
            
        result = [
            {
                'id'          : r['id'],
                'library_id'  : r['library_id'],
                'title'       : r['title'],
                'title_alias' : r.get('title_alias', '') or '',
                'series_name' : r['series_name'] or '기타 단행본',
                'series_alias': r.get('series_alias', '') or '',
                'cover_image' : get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_format' : r['file_format'],
                'total_pages' : r['total_pages'] or 0,
                'is_favorite' : r['is_favorite'] or 0,
                'created_at'  : r['created_at'],
                'metadata_locked': r.get('metadata_locked', 0),
            }
            for r in rows
        ]

        # 2. Redis 캐시 세팅 (3600초=1시간 만료 설정)
        try:
            redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=3600)
        except Exception:
            pass

        return result
