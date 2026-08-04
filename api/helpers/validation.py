# -*- coding: utf-8 -*-
"""
validation.py – 공통 검증 및 유틸리티 헬퍼
"""
import os
from utils.i18n import _t

MAX_LIBRARY_PATHS = 20
MAX_LIBRARY_PATH_LINE_LENGTH = 1024
MAX_LIBRARY_PATH_TEXT_LENGTH = 8192

_AUDIO_EXTENSIONS = ('.mp3', '.m4b', '.m4a', '.flac', '.aac', '.wav', '.ogg', '.opus', '.wma')
_BOOKISH_EXTENSIONS = ('.zip', '.cbz', '.rar', '.cbr', '.epub', '.pdf', '.txt')

def validate_library_paths(physical_path, category_type='local'):
    """
    물리 경로 또는 원격 링크 검증 (여러 개 지원)
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
    
    if category_type == 'gdrive':
        # 구글 드라이브 카테고리는 API Key가 반드시 필요합니다.
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('GDRIVE_API_KEY') or os.getenv('GDRIVE_API') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            return None, (
                '구글 드라이브 카테고리를 등록하려면 Google Drive API Key가 필요합니다.\n'
                '서버의 .env 파일에 GDRIVE_API_KEY=<발급받은_키> 를 추가한 후 다시 시도해 주세요.\n'
                '(Google Cloud Console → API 및 서비스 → 사용자 인증 정보 → API 키 생성)'
            )
        return target_paths, None

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


def _looks_like_audiobook_root(path, max_depth=2, max_scanned_files=300):
    """
    Lightweight heuristic to detect audiobook-oriented roots.
    Strong signals only, to avoid blocking mixed or ambiguous media folders.
    """
    if not path or not os.path.isdir(path):
        return False

    audio_file_count = 0
    book_file_count = 0
    scanned_files = 0

    root_depth = os.path.normpath(path).count(os.sep)

    for walk_root, _, files in os.walk(path):
        depth = os.path.normpath(walk_root).count(os.sep) - root_depth
        if depth > max_depth:
            continue

        lowered_names = {str(name or '').lower() for name in files}
        if 'audio.json' in lowered_names or 'metadata.json' in lowered_names:
            return True

        for file_name in files:
            lower_name = str(file_name or '').lower()
            scanned_files += 1
            if lower_name.endswith(_AUDIO_EXTENSIONS):
                audio_file_count += 1
            elif lower_name.endswith(_BOOKISH_EXTENSIONS):
                book_file_count += 1

            if scanned_files >= max_scanned_files:
                break

        if scanned_files >= max_scanned_files:
            break

    return audio_file_count >= 3 and book_file_count == 0


def _looks_like_book_root(path, max_depth=2, max_scanned_files=300):
    """
    Lightweight heuristic to detect general/adult ebook-oriented roots.
    Strong signals only, to avoid blocking mixed or ambiguous media folders.
    """
    if not path or not os.path.isdir(path):
        return False

    audio_file_count = 0
    book_file_count = 0
    scanned_files = 0

    root_depth = os.path.normpath(path).count(os.sep)

    for walk_root, _, files in os.walk(path):
        depth = os.path.normpath(walk_root).count(os.sep) - root_depth
        if depth > max_depth:
            continue

        lowered_names = {str(name or '').lower() for name in files}
        if any(name in lowered_names for name in ('comicinfo.xml', 'metadata.opf')):
            return True

        for file_name in files:
            lower_name = str(file_name or '').lower()
            scanned_files += 1
            if lower_name.endswith(_BOOKISH_EXTENSIONS):
                book_file_count += 1
            elif lower_name.endswith(_AUDIO_EXTENSIONS):
                audio_file_count += 1

            if scanned_files >= max_scanned_files:
                break

        if scanned_files >= max_scanned_files:
            break

    return book_file_count >= 3 and audio_file_count == 0


def detect_library_media_mismatch(db_type, target_paths):
    """
    Return structured mismatch info for obvious category/content mismatches.
    """
    normalized_db_type = str(db_type or 'general').strip().lower()

    for path in target_paths or []:
        if normalized_db_type != 'audiobook' and _looks_like_audiobook_root(path):
            return {
                'kind': 'audiobook_in_book_category',
                'message': (
                    '선택한 경로는 오디오북 전용 폴더로 보입니다.\n'
                    '일반/성인 도서 카테고리에는 등록할 수 없습니다.'
                ),
                'confirm_message': (
                    '선택한 경로는 오디오북 전용 폴더로 보입니다.\n\n'
                    '그래도 일반/성인 도서 카테고리로 저장하시겠습니까?\n'
                    '잘못 저장하면 스캔 결과가 의도와 다르게 등록될 수 있습니다.'
                ),
            }

        if normalized_db_type == 'audiobook' and _looks_like_book_root(path):
            return {
                'kind': 'book_in_audiobook_category',
                'message': (
                    '선택한 경로는 일반/성인 도서 전용 폴더로 보입니다.\n'
                    '오디오북 카테고리에는 등록할 수 없습니다.'
                ),
                'confirm_message': (
                    '선택한 경로는 일반/성인 도서 전용 폴더로 보입니다.\n\n'
                    '그래도 오디오북 카테고리로 저장하시겠습니까?\n'
                    '잘못 저장하면 스캔 결과가 의도와 다르게 등록될 수 있습니다.'
                ),
            }

    return None


def validate_library_media_compatibility(db_type, target_paths):
    """
    Prevent obvious category/media mismatches at add/edit time.
    Prevents obvious cross-registration between ebook and audiobook roots.
    """
    mismatch = detect_library_media_mismatch(db_type, target_paths)
    return mismatch['message'] if mismatch else None

def normalize_rclone_url(url):
    """
    rclone URL 정규화
    """
    return (url or '').strip() or None
