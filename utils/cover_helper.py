# -*- coding: utf-8 -*-
import os
import hashlib

def get_cover_image_with_t(cover_image, updated_at):
    """표지 이미지명에 캐시 갱신용 타임스탬프를 덧붙여 반환"""
    if not cover_image:
        return ''
    if not updated_at:
        return cover_image
    import datetime
    try:
        if isinstance(updated_at, str):
            dt = datetime.datetime.fromisoformat(updated_at.replace(' ', 'T'))
            ts = int(dt.timestamp())
        elif hasattr(updated_at, 'timestamp'):
            ts = int(updated_at.timestamp())
        else:
            ts = int(datetime.datetime.now().timestamp())
    except Exception:
        ts = 0
    return f"{cover_image}?t={ts}"

_SERIES_COVER_MEM_CACHE = {}

def resolve_series_cover(series_name, lib_id, db_cover, covers_dir, conn=None, candidates_rows=None, allow_series_cover=True, db_type='general'):
    """시리즈 대표 커버의 물리적 실존을 카테고리별 분할 구조에 맞추어 검사하고,
    유실된 경우 실존하는 다른 도서 커버로 대체(Fallback) - 순수 파이썬 In-Memory Dict 초고속 연동
    """
    series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
    cache_key = f"{db_type}:{lib_id}:{series_hash}"

    # 1. 순수 파이썬 In-Memory Dict 룩업 (0.000001초 소요)
    cached_cover = _SERIES_COVER_MEM_CACHE.get(cache_key)
    if cached_cover:
        cached_path = os.path.join(covers_dir, cached_cover)
        if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
            return cached_cover

    # 카테고리 분할 경로
    series_cover_name = f"{lib_id}/series_{series_hash}.jpg" if lib_id is not None else f"series_{series_hash}.jpg"
    series_cover_path = os.path.join(covers_dir, series_cover_name)
    
    # 구형 레거시 경로
    legacy_series_cover_name = f"series_{series_hash}.jpg"
    legacy_series_cover_path = os.path.join(covers_dir, legacy_series_cover_name)

    resolved_cover = None

    if allow_series_cover:
        if os.path.exists(series_cover_path) and os.path.getsize(series_cover_path) > 0:
            resolved_cover = series_cover_name
        elif os.path.exists(legacy_series_cover_path) and os.path.getsize(legacy_series_cover_path) > 0:
            resolved_cover = legacy_series_cover_name

    if not resolved_cover:
        db_cover_path = os.path.join(covers_dir, db_cover) if db_cover else None
        if db_cover_path and os.path.exists(db_cover_path) and os.path.getsize(db_cover_path) > 0:
            resolved_cover = db_cover

    # Fallback 탐색
    if not resolved_cover:
        if candidates_rows is not None:
            for cand in candidates_rows:
                cand_cover = cand['cover_image']
                if cand_cover:
                    cand_path = os.path.join(covers_dir, cand_cover)
                    if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                        resolved_cover = cand_cover
                        break
        else:
            from repositories.book_repository import BookRepository
            try:
                candidates = BookRepository.get_series_cover_candidates(db_type, series_name, lib_id)
                for cand in candidates:
                    cand_cover = cand['cover_image']
                    cand_path = os.path.join(covers_dir, cand_cover)
                    if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                        resolved_cover = cand_cover
                        break
            except Exception as e:
                print(f"[resolve_series_cover WARNING] Failed to fetch cover candidates: {e}")

    final_cover = resolved_cover or db_cover

    # 2. 파이썬 메모리 Dict에 저장
    if final_cover:
        _SERIES_COVER_MEM_CACHE[cache_key] = final_cover

    return final_cover


def invalidate_series_cover_cache(db_type='general', lib_id=None, series_name=None):
    """표지 변경/스캔 완료 시 해당 시리즈의 In-Memory 커버 캐시 파기"""
    global _SERIES_COVER_MEM_CACHE
    if series_name is not None and lib_id is not None:
        series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
        cache_key = f"{db_type}:{lib_id}:{series_hash}"
        _SERIES_COVER_MEM_CACHE.pop(cache_key, None)
    else:
        _SERIES_COVER_MEM_CACHE.clear()



