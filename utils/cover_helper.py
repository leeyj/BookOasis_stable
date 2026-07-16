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

def resolve_series_cover(series_name, lib_id, db_cover, covers_dir, conn, candidates_rows=None, allow_series_cover=True):
    """시리즈 대표 커버의 물리적 실존을 카테고리별 분할 구조에 맞추어 검사하고,
    유실된 경우 실존하는 다른 도서 커버로 대체(Fallback)
    """
    series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
    
    # 카테고리 분할 경로
    series_cover_name = f"{lib_id}/series_{series_hash}.jpg" if lib_id is not None else f"series_{series_hash}.jpg"
    series_cover_path = os.path.join(covers_dir, series_cover_name)
    
    # 구형 레거시 경로
    legacy_series_cover_name = f"series_{series_hash}.jpg"
    legacy_series_cover_path = os.path.join(covers_dir, legacy_series_cover_name)

    if allow_series_cover:
        if os.path.exists(series_cover_path) and os.path.getsize(series_cover_path) > 0:
            return series_cover_name
        if os.path.exists(legacy_series_cover_path) and os.path.getsize(legacy_series_cover_path) > 0:
            return legacy_series_cover_name

    db_cover_path = os.path.join(covers_dir, db_cover) if db_cover else None
    if db_cover_path and os.path.exists(db_cover_path) and os.path.getsize(db_cover_path) > 0:
        return db_cover

    # Fallback 탐색
    if candidates_rows is not None:
        for cand in candidates_rows:
            cand_cover = cand['cover_image']
            if cand_cover:
                cand_path = os.path.join(covers_dir, cand_cover)
                if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                    return cand_cover
    else:
        fallback_cursor = conn.cursor()
        if lib_id is not None:
            fallback_cursor.execute("""
            SELECT cover_image 
            FROM books 
            WHERE series_name = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0 AND cover_image IS NOT NULL AND cover_image != ''
            ORDER BY title ASC
            """, (series_name, lib_id))
        else:
            fallback_cursor.execute("""
            SELECT cover_image 
            FROM books 
            WHERE series_name = ? AND COALESCE(is_deleted, 0) = 0 AND cover_image IS NOT NULL AND cover_image != ''
            ORDER BY title ASC
            """, (series_name,))
        candidates = fallback_cursor.fetchall()
        for cand in candidates:
            cand_cover = cand['cover_image']
            cand_path = os.path.join(covers_dir, cand_cover)
            if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                return cand_cover

    return db_cover
