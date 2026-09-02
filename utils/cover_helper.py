# -*- coding: utf-8 -*-
import os
import hashlib


def get_or_cache_remote_poster_webp(poster_source, category, library_id=None, timeout=5):
    """오디오북/영상 강좌 포스터(로컬 경로 또는 원격 URL)를 covers/{category}/{library_id}/ 아래
    WebP로 변환해 로컬 캐시하고, 캐시 파일의 절대 경로를 반환한다. 도서 표지가
    covers/{library_id}/... 로 라이브러리별로 나뉘는 것과 동일한 구조를 맞춘다
    (라이브러리 삭제 시 정리하기 쉽고, 한 폴더에 파일이 무한정 쌓이는 것도 방지).

    도서 표지(tools/scanner/cover.py)와 달리 이쪽은 스캔 시점이 아니라 최초 요청
    시점에 지연 생성(lazy)된다 — 대량 스캔 중 네트워크 호출이 끼어들어 스캔 자체가
    느려지는 것을 피하고, 실제로 화면에 노출된 것만 캐싱하기 위함. 캐시 키(파일명)는
    도서 표지와 동일하게 숫자 id가 아니라 포스터 소스 문자열(경로/URL)의 MD5 해시라서,
    재스캔으로 포스터 소스가 바뀌면 새 해시로 자연스럽게 재캐싱된다(별도 무효화 로직 불필요).
    실패 시 None을 반환하며, 호출부는 기존 폴백(SVG 플레이스홀더)을 그대로 사용하면 된다.
    """
    if not poster_source:
        return None

    from tools.scanner.cover import save_as_thumbnail_webp
    from services.cover_storage_service import get_covers_dir
    covers_dir = get_covers_dir()
    cache_dir = os.path.join(covers_dir, category, str(library_id)) if library_id is not None else os.path.join(covers_dir, category)
    os.makedirs(cache_dir, exist_ok=True)

    source_hash = hashlib.md5(str(poster_source).encode('utf-8')).hexdigest()
    cache_path = os.path.join(cache_dir, f"{source_hash}.webp")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path

    img_data = None
    is_remote = str(poster_source).startswith(('http://', 'https://'))
    if is_remote:
        try:
            import requests
        except Exception:
            return None
        try:
            resp = requests.get(poster_source, timeout=timeout)
            if resp.ok and resp.content:
                img_data = resp.content
        except Exception:
            return None
    else:
        if not os.path.exists(poster_source):
            return None
        try:
            with open(poster_source, 'rb') as f:
                img_data = f.read()
        except Exception:
            return None

    if not img_data:
        return None

    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(img_data)) as img:
            save_as_thumbnail_webp(img, cache_path)
        return cache_path
    except Exception as e:
        print(f"[Cover-Cache] Poster WebP conversion failed ({poster_source}): {e}")
        return None

def get_or_cache_external_image_webp(url, category, max_bytes=2 * 1024 * 1024, timeout=5):
    """플러그인이 클라이언트 요청마다 넘기는 임의의 외부 이미지 URL(방송사 로고 등)을
    안전하게 받아와 WebP로 로컬 캐싱한다. get_or_cache_remote_poster_webp()와 달리
    - 대상 URL이 (관리자가 스캔 시점에 등록한 값이 아니라) 매 요청마다 클라이언트가 보내는
      임의 문자열이라 services/ssrf_guard.py로 사설/루프백 IP 여부를 검증하고,
    - 응답 크기를 max_bytes로 캡해 과도한 다운로드를 막는다.
    다만 이 리소스들은 도메인이 소스마다 제각각이라(방송사/채널별 CDN) 사용자 화이트리스트
    등록까지 요구하면 실사용이 불가능해, 도메인 제한 없이 사설 IP만 차단한다(SSRF 최소 방어).
    실패 시 None을 반환한다."""
    if not url or not str(url).startswith(('http://', 'https://')):
        return None

    from tools.scanner.cover import save_as_thumbnail_webp
    from services.cover_storage_service import get_covers_dir
    cache_dir = os.path.join(get_covers_dir(), category)
    os.makedirs(cache_dir, exist_ok=True)

    source_hash = hashlib.md5(str(url).encode('utf-8')).hexdigest()
    cache_path = os.path.join(cache_dir, f"{source_hash}.webp")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path

    from services.ssrf_guard import (
        SSRFBlockedError,
        fetch_public_url_with_redirect_revalidation,
        read_capped,
    )

    try:
        response = fetch_public_url_with_redirect_revalidation(url, method='GET', timeout=timeout)
    except SSRFBlockedError as e:
        print(f"[Cover-Cache] External image blocked ({url}): {e.reason}")
        return None
    except Exception as e:
        print(f"[Cover-Cache] External image fetch failed ({url}): {e}")
        return None

    try:
        img_data = read_capped(response, max_bytes)
    except SSRFBlockedError as e:
        print(f"[Cover-Cache] External image too large ({url}): {e.reason}")
        return None
    finally:
        response.close()

    if not img_data:
        return None

    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(img_data)) as img:
            save_as_thumbnail_webp(img, cache_path)
        return cache_path
    except Exception as e:
        print(f"[Cover-Cache] External image WebP conversion failed ({url}): {e}")
        return None


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
    series_hash = hashlib.md5(str(series_name or '').encode('utf-8')).hexdigest()
    cache_key = f"{db_type}:{lib_id}:{series_hash}"

    # 1. Fast path: db_cover가 이미 API URL이거나 유효한 파일명 형태면 디스크 IO 없이 즉시 반환 (수만 건 전체보기 시 0.001초 응답)
    if db_cover:
        db_cover_str = str(db_cover).strip()
        if db_cover_str.startswith('/') or db_cover_str.startswith('http') or ('.' in os.path.basename(db_cover_str) and not db_cover_str.endswith('/') and not db_cover_str.endswith('\\')):
            _SERIES_COVER_MEM_CACHE[cache_key] = db_cover_str
            return db_cover_str

    # 2. 순수 파이썬 In-Memory Dict 룩업
    cached_cover = _SERIES_COVER_MEM_CACHE.get(cache_key)
    if cached_cover:
        return str(cached_cover)

    # 카테고리 분할 경로
    series_cover_name = f"{lib_id}/series_{series_hash}.jpg" if lib_id is not None else f"series_{series_hash}.jpg"
    series_cover_path = os.path.join(covers_dir, str(series_cover_name))
    
    # 구형 레거시 경로
    legacy_series_cover_name = f"series_{series_hash}.jpg"
    legacy_series_cover_path = os.path.join(covers_dir, str(legacy_series_cover_name))

    resolved_cover = None

    if allow_series_cover:
        if os.path.exists(series_cover_path) and os.path.getsize(series_cover_path) > 0:
            resolved_cover = series_cover_name
        elif os.path.exists(legacy_series_cover_path) and os.path.getsize(legacy_series_cover_path) > 0:
            resolved_cover = legacy_series_cover_name

    if not resolved_cover and db_cover:
        resolved_cover = str(db_cover)

    # Fallback 탐색
    if not resolved_cover:
        if candidates_rows is not None:
            for cand in candidates_rows:
                cand_cover = cand.get('cover_image')
                if cand_cover:
                    cand_cover_str = str(cand_cover)
                    cand_path = os.path.join(covers_dir, cand_cover_str)
                    if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                        resolved_cover = cand_cover_str
                        break
        else:
            from repositories.book_repository import BookRepository
            try:
                candidates = BookRepository.get_series_cover_candidates(db_type, series_name, lib_id)
                for cand in candidates:
                    cand_cover = cand.get('cover_image')
                    if cand_cover:
                        cand_cover_str = str(cand_cover)
                        cand_path = os.path.join(covers_dir, cand_cover_str)
                        if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                            resolved_cover = cand_cover_str
                            break
            except Exception as e:
                print(f"[resolve_series_cover WARNING] Failed to fetch cover candidates: {e}")

    final_cover = resolved_cover or (str(db_cover) if db_cover else '')
    if final_cover:
        cleaned_final = final_cover.strip().rstrip('/\\')
        if not cleaned_final or '.' not in os.path.basename(cleaned_final):
            final_cover = ''

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



