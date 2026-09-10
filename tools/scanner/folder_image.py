# -*- coding: utf-8 -*-
import os

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
COMMON_COVER_NAMES = (
    'cover.jpg', 'cover.png', 'covers.jpg', 'covers.png', 'folder.jpg', 'folder.png',
    'cover.jpeg', 'covers.jpeg', 'folder.jpeg',
    'cover.webp', 'covers.webp', 'folder.webp',
    'cover.bmp', 'covers.bmp', 'folder.bmp',
    'cover.gif', 'covers.gif', 'folder.gif',
)


def find_individual_cover(folder_path, filename):
    """Return the first matching 1:1 cover image next to the book file."""
    if not folder_path or not filename:
        return None

    base_name, _ = os.path.splitext(filename)
    for ext_candidate in IMAGE_EXTENSIONS:
        cand_filename = base_name + ext_candidate
        cand_path = os.path.join(folder_path, cand_filename)
        if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
            return cand_path
    return None


def find_common_cover(folder_path):
    """Return the first common folder cover image such as cover.jpg or folder.png."""
    if not folder_path:
        return None

    for cand in COMMON_COVER_NAMES:
        cand_path = os.path.join(folder_path, cand)
        if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
            return cand_path
    return None


COMMON_BANNER_NAMES = (
    'banner.jpg', 'banner.jpeg', 'banner.png', 'banner.webp', 'banner.bmp', 'banner.gif',
)


def find_common_banner(folder_path):
    """Return the first loose banner image file (banner.jpg/png/webp/...) directly in the folder.
    공유 드라이브 도서관리 담당자와 합의된 배너 이미지 지원 - 없으면 그냥 None (배너는 필수가 아님)."""
    if not folder_path:
        return None

    for cand in COMMON_BANNER_NAMES:
        cand_path = os.path.join(folder_path, cand)
        if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
            return cand_path
    return None