# -*- coding: utf-8 -*-
"""
validation.py – 공통 검증 및 유틸리티 헬퍼
"""
import os
from utils.i18n import _t

MAX_LIBRARY_PATHS = 20
MAX_LIBRARY_PATH_LINE_LENGTH = 1024
MAX_LIBRARY_PATH_TEXT_LENGTH = 8192

def validate_library_paths(physical_path):
    """
    물리 경로 검증 (여러 개 지원)
    반환: (target_paths 리스트, 오류메시지 또는 None)
    """
    raw_text = str(physical_path or '').replace('\r', '')
    if len(raw_text) > MAX_LIBRARY_PATH_TEXT_LENGTH:
        return None, f'경로 입력 길이가 너무 깁니다. 최대 {MAX_LIBRARY_PATH_TEXT_LENGTH}자까지 허용됩니다.'

    target_paths = [p.strip() for p in raw_text.split('\n') if p.strip()]
    if not target_paths:
        return None, _t('api.err_physical_path_required')

    if len(target_paths) > MAX_LIBRARY_PATHS:
        return None, f'경로는 최대 {MAX_LIBRARY_PATHS}개까지 입력할 수 있습니다.'

    too_long_paths = [p for p in target_paths if len(p) > MAX_LIBRARY_PATH_LINE_LENGTH]
    if too_long_paths:
        return None, f'각 경로는 최대 {MAX_LIBRARY_PATH_LINE_LENGTH}자까지 허용됩니다.'
    
    invalid_paths = [p for p in target_paths if not os.path.exists(p)]
    if invalid_paths:
        error_msg = _t('api.err_invalid_paths', paths='\n'.join(invalid_paths))
        return None, error_msg
    
    return target_paths, None

def parse_remote_flag(is_remote_val, target_paths):
    """
    원격 드라이브 플래그 파싱
    """
    if is_remote_val in ('1', 'true', 'on'):
        return 1
    elif is_remote_val in ('0', 'false'):
        return 0
    else:
        from utils.drive_helper import is_remote_path
        return 1 if any(is_remote_path(p) for p in target_paths) else 0

def normalize_rclone_url(url):
    """
    rclone URL 정규화
    """
    return (url or '').strip() or None
