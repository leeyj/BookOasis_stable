# -*- coding: utf-8 -*-
import os
import threading
import time

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
COMMON_COVER_NAMES = (
    'cover.jpg', 'cover.png', 'covers.jpg', 'covers.png', 'folder.jpg', 'folder.png',
    'cover.jpeg', 'covers.jpeg', 'folder.jpeg',
    'cover.webp', 'covers.webp', 'folder.webp',
    'cover.bmp', 'covers.bmp', 'folder.bmp',
    'cover.gif', 'covers.gif', 'folder.gif',
)


# 폴더 안 표지/배너 후보를 찾을 때 후보 이름마다 os.path.exists를 부르면(공통 표지 18개, 개별 표지 6개, 책마다)
# rclone/FUSE 같은 원격 마운트에서 stat 호출이 많고, 리눅스는 대소문자를 구분해서 Windows에서 만든
# "Cover.JPG" 같은 파일을 놓친다. 그래서 폴더 목록을 한 번만 읽어(소문자 이름 -> 실제 이름) 그 안에서
# 후보를 찾고, 같은 폴더를 책마다 다시 읽지 않도록 아주 짧은 시간만 캐시한다.
_LISTING_CACHE_TTL_SECONDS = 3.0
_LISTING_CACHE_MAX_FOLDERS = 64
_listing_cache = {}
_listing_cache_lock = threading.Lock()


def clear_folder_listing_cache():
    """스캔을 시작할 때 호출해서, 방금 폴더에 넣은 표지 파일이 캐시 때문에 안 보이는 일을 막는다."""
    with _listing_cache_lock:
        _listing_cache.clear()


def _folder_file_map(folder_path):
    """{소문자 파일명: 실제 파일명}. 대소문자만 다른 파일이 둘 이상이면 이미 소문자인 이름을 우선한다."""
    now = time.monotonic()
    with _listing_cache_lock:
        cached = _listing_cache.get(folder_path)
        if cached and now - cached[0] < _LISTING_CACHE_TTL_SECONDS:
            return cached[1]

    mapping = {}
    try:
        for name in sorted(os.listdir(folder_path)):
            lowered = name.lower()
            if lowered not in mapping or name == lowered:
                mapping[lowered] = name
    except OSError:
        mapping = {}

    with _listing_cache_lock:
        if len(_listing_cache) >= _LISTING_CACHE_MAX_FOLDERS:
            oldest = min(_listing_cache, key=lambda key: _listing_cache[key][0])
            del _listing_cache[oldest]
        _listing_cache[folder_path] = (now, mapping)
    return mapping


def _first_existing_image(folder_path, candidate_names):
    """후보 이름을 우선순위 순서대로 폴더 목록에서 찾아, 비어 있지 않은 첫 파일의 경로를 반환한다."""
    file_map = _folder_file_map(folder_path)
    if not file_map:
        return None
    for candidate in candidate_names:
        actual_name = file_map.get(candidate.lower())
        if not actual_name:
            continue
        cand_path = os.path.join(folder_path, actual_name)
        try:
            if os.path.getsize(cand_path) > 0:
                return cand_path
        except OSError:
            continue
    return None


def find_individual_cover(folder_path, filename):
    """Return the first matching 1:1 cover image next to the book file (extension case-insensitive)."""
    if not folder_path or not filename:
        return None

    base_name, _ = os.path.splitext(filename)
    return _first_existing_image(folder_path, [base_name + ext for ext in IMAGE_EXTENSIONS])


def find_common_cover(folder_path):
    """Return the first common folder cover image such as cover.jpg or folder.png."""
    if not folder_path:
        return None

    return _first_existing_image(folder_path, COMMON_COVER_NAMES)


COMMON_BANNER_NAMES = (
    'banner.jpg', 'banner.jpeg', 'banner.png', 'banner.webp', 'banner.bmp', 'banner.gif',
)


def find_common_banner(folder_path):
    """Return the first loose banner image file (banner.jpg/png/webp/...) directly in the folder.
    공유 드라이브 도서관리 담당자와 합의된 배너 이미지 지원 - 없으면 그냥 None (배너는 필수가 아님)."""
    if not folder_path:
        return None

    return _first_existing_image(folder_path, COMMON_BANNER_NAMES)
