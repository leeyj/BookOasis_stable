# -*- coding: utf-8 -*-
"""
recommendation_service.py – 읽은 시리즈의 장르/태그 겹침 기반 "스마트 추천" 계산
"""
import json
import time
from repositories.book_repository import BookRepository
from services.reading_history_service import ReadingHistoryService
from utils.cover_helper import get_cover_image_with_t
from utils.redis_helper import redis_get, redis_set

RECOMMEND_LIMIT = 20
INDEX_CACHE_TTL = 1800

# 시리즈별 장르/태그 인덱스는 수만 건 규모라 Redis에 직렬화해 왕복시키면 오히려 DB 재조회보다 느려진다.
# DB 조회 자체는 가볍기 때문에(28만 행 기준 0.5초 내외) 프로세스 메모리에만 TTL로 캐싱한다.
_series_index_cache = {}


def _tokenize(raw):
    if not raw:
        return set()
    return {token.strip() for token in str(raw).split(',') if token.strip()}


def _get_series_index(db_type):
    cached = _series_index_cache.get(db_type)
    if cached and cached['expires_at'] > time.time():
        return cached['rows']

    index_rows = BookRepository.get_series_genre_tags_index(db_type)
    for row in index_rows:
        row['_genre_tokens'] = _tokenize(row.get('genre'))
        row['_tags_tokens'] = _tokenize(row.get('tags'))
        row['_author_tokens'] = _tokenize(row.get('author'))

    _series_index_cache[db_type] = {'rows': index_rows, 'expires_at': time.time() + INDEX_CACHE_TTL}
    return index_rows


def _to_card_item(row):
    return {
        'id': row['id'],
        'series_name': row['series_name'],
        'library_id': row['library_id'],
        'file_format': row.get('file_format'),
        'cover_image': get_cover_image_with_t(row.get('cover_image'), row.get('cover_updated_at')),
        'score': row.get('score') or 0,
    }


def _rank_candidates(target_tokens, candidates, token_field, exclude_series_names, limit):
    scored = []
    if not target_tokens:
        return []
    for row in candidates:
        if row['series_name'] in exclude_series_names:
            continue
        overlap = len(target_tokens & row[token_field])
        if overlap <= 0:
            continue
        scored.append((overlap, row.get('score') or 0, row))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [_to_card_item(row) for _, _, row in scored[:limit]]


def _fallback_latest(db_type, library_id, exclude_series_names, limit):
    """장르/태그 정보가 없는 시리즈를 위한 폴백: 동일 카테고리(library)의 최신 등록 시리즈"""
    if library_id is None:
        return []
    try:
        rows = BookRepository.get_latest_series_by_library(db_type, library_id, limit=limit + len(exclude_series_names) + 10)
    except Exception:
        return []
    result = []
    for row in rows:
        if row['series_name'] in exclude_series_names:
            continue
        result.append(_to_card_item(row))
        if len(result) >= limit:
            break
    return result


class RecommendationService:
    @staticmethod
    def get_similar_series(db_type, series_name, library_id=None, user_id=1, limit=RECOMMEND_LIMIT):
        cache_key = f"cache:smart_rec:v3:{db_type}:{library_id}:{series_name}:{limit}"
        cached = redis_get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        index_rows = _get_series_index(db_type)

        target_row = next(
            (r for r in index_rows if r['series_name'] == series_name and (library_id is None or str(r['library_id']) == str(library_id))),
            None
        )
        if target_row is None:
            target_row = next((r for r in index_rows if r['series_name'] == series_name), None)

        history = ReadingHistoryService.get_history(db_type, user_id=user_id)
        exclude_series_names = {item['series_name'] for item in history}
        exclude_series_names.add(series_name)

        if target_row is None:
            # 시리즈 자체가 인덱스에 없음 = 장르/태그/작가 정보가 전혀 없는 시리즈 -> 카테고리 최신 도서로 폴백
            fallback = _fallback_latest(db_type, library_id, exclude_series_names, limit)
            result = {
                'genre': fallback, 'tags': fallback, 'author': [],
                'genre_is_fallback': True, 'tags_is_fallback': True,
            }
        else:
            series_library_id = target_row['library_id']
            if target_row['_genre_tokens']:
                genre_matches = _rank_candidates(target_row['_genre_tokens'], index_rows, '_genre_tokens', exclude_series_names, limit)
                genre_is_fallback = False
            else:
                genre_matches = _fallback_latest(db_type, series_library_id, exclude_series_names, limit)
                genre_is_fallback = True

            if target_row['_tags_tokens']:
                tag_matches = _rank_candidates(target_row['_tags_tokens'], index_rows, '_tags_tokens', exclude_series_names, limit)
                tags_is_fallback = False
            else:
                tag_matches = _fallback_latest(db_type, series_library_id, exclude_series_names, limit)
                tags_is_fallback = True

            # 작가 추천은 라이브러리(카테고리) 제한 없이 전체 기준으로 겹치는 시리즈를 찾는다.
            # 폴백 대상이 없는 정보이므로 매칭이 없으면 그냥 빈 목록으로 둔다(섹션은 UI에서 비어있음으로 표시).
            author_matches = _rank_candidates(target_row['_author_tokens'], index_rows, '_author_tokens', exclude_series_names, limit)

            result = {
                'genre': genre_matches, 'tags': tag_matches, 'author': author_matches,
                'genre_is_fallback': genre_is_fallback, 'tags_is_fallback': tags_is_fallback,
            }

        try:
            redis_set(cache_key, json.dumps(result), ex=3600)
        except Exception:
            pass

        return result
