# -*- coding: utf-8 -*-
"""압축/폴더 안의 항목 중 '페이지 이미지'로 볼 것만 고르는 공용 판정.

macOS Finder로 만든 ZIP에는 `__MACOSX/` 폴더와 `._원본이름` AppleDouble 파일(수백 바이트짜리
리소스 포크)이 같이 들어간다. 확장자가 .jpg라 이미지 목록에 섞이면 페이지 수가 부풀고,
자연 정렬상 `__MACOSX/...`가 앞에 와서 0페이지가 깨진 이미지가 된다.
"""

from utils import media_types as _media_types
IMG_EXT = _media_types.IMAGE_EXTENSIONS


def is_macos_junk_name(name: str) -> bool:
    normalized = (name or '').replace('\\', '/')
    if normalized.startswith('__MACOSX/') or '/__MACOSX/' in normalized:
        return True
    return normalized.rsplit('/', 1)[-1].startswith('._')


def is_page_image_name(name: str) -> bool:
    if not name or is_macos_junk_name(name):
        return False
    return name.lower().endswith(IMG_EXT)
