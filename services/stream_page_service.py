# -*- coding: utf-8 -*-
import os
import mimetypes

from api.cache import namelist_cache, image_cache
from utils.cache_helper import get_zip_file_hybrid, get_zip_read_lock
import database

IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


def get_img_files(file_path: str, zf) -> list:
    """ZIP 내 이미지 목록을 캐시에서 가져오거나 계산하여 캐시 저장"""
    from api.cache import disk_cache_manager

    local_path = disk_cache_manager.get_local_path(file_path)
    done_file = local_path + '.done'
    is_cached = os.path.exists(local_path) and os.path.exists(done_file)
    lookup_key = local_path if is_cached else file_path

    cached = namelist_cache.get(lookup_key)
    if cached is not None:
        return cached

    from utils.sort_helper import natural_sort_key

    img_files = sorted(
        [n for n in zf.namelist() if n.lower().endswith(IMG_EXT)],
        key=natural_sort_key,
    )
    namelist_cache.put(lookup_key, img_files)
    return img_files


def get_imgdir_files(folder_path: str) -> list:
    """이미지 폴더(imgdir) 내 정렬된 이미지 파일 절대경로 목록 반환"""
    if not folder_path or not os.path.isdir(folder_path):
        return []

    cache_key = f"imgdir:{folder_path}"
    cached = namelist_cache.get(cache_key)
    if cached is not None:
        return cached

    from utils.sort_helper import natural_sort_key

    files = sorted(
        [
            os.path.join(folder_path, n)
            for n in os.listdir(folder_path)
            if n.lower().endswith(IMG_EXT)
        ],
        key=natural_sort_key,
    )
    namelist_cache.put(cache_key, files)
    return files


class StreamPageService:
    @staticmethod
    def _book_permission_clause(user_id=None, role=None, book_alias='b'):
        is_admin = str(role or '').lower() == 'admin'
        if is_admin or not user_id:
            return '', []
        clause = (
            f" AND EXISTS ("
            f"SELECT 1 FROM user_category_permissions p "
            f"WHERE p.library_id = {book_alias}.library_id AND p.user_id = ? AND p.has_access = 1"
            f")"
        )
        return clause, [user_id]

    @staticmethod
    def get_book_file_info(db_type, book_id, user_id=None, role=None):
        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            perm_clause, perm_params = StreamPageService._book_permission_clause(user_id=user_id, role=role, book_alias='b')
            cursor.execute(
                f"SELECT b.file_path, b.file_format FROM books b WHERE b.id = ? AND COALESCE(b.is_deleted, 0) = 0{perm_clause}",
                (book_id, *perm_params),
            )
            row = cursor.fetchone()
            if not row:
                return None, None
            return row['file_path'], (row['file_format'] or '').lower()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_total_pages_for_book(db_type, book_id, file_path=None, file_format=None):
        if file_path is None or file_format is None:
            file_path, file_format = StreamPageService.get_book_file_info(db_type, book_id)
        if not file_path:
            return 0

        try:
            if file_format in ('zip', 'cbz'):
                zf = get_zip_file_hybrid(file_path)
                if zf:
                    return len(get_img_files(file_path, zf))
            elif file_format == 'imgdir' or file_path.lower().endswith('.imgdir'):
                folder_path = os.path.dirname(file_path)
                return len(get_imgdir_files(folder_path))
        except Exception as e:
            print(f"[StreamPageService] total_pages calculation failed ({book_id}): {e}")

        return 0

    @staticmethod
    def extract_page(file_path: str, page_idx: int, db_type: str = 'general', book_id=None):
        """단일 페이지를 (img_data, mime_type)으로 반환 (Zip 오프셋 최적화 및 Fallback 지원)"""
        cache_key = (file_path, page_idx)
        cached = image_cache.get(cache_key)
        if cached is not None:
            return cached

        with get_zip_read_lock(file_path):
            cached = image_cache.get(cache_key)
            if cached is not None:
                return cached

            # [IMGDIR Path] 폴더 이미지 직접 스트리밍
            if file_path.lower().endswith('.imgdir'):
                folder_path = os.path.dirname(file_path)
                img_files = get_imgdir_files(folder_path)
                if page_idx < 0 or page_idx >= len(img_files):
                    return None

                target = img_files[page_idx]
                try:
                    with open(target, 'rb') as f:
                        data = f.read()
                    mime, _ = mimetypes.guess_type(target)
                    mime = mime or 'image/jpeg'
                    result = (data, mime)
                    image_cache.put(cache_key, result, len(data))
                    return result
                except Exception as e:
                    print(f"[StreamPageService] IMGDIR page extract fail [{target}]: {e}")
                    return None

            # [Fast Path] Zip 오프셋 기반 부분 스트리밍 가속 기동
            if book_id is not None:
                conn = None
                try:
                    conn = database.get_connection(db_type)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT filename, local_header_offset, compress_size, file_size, compress_type
                        FROM book_offsets
                        WHERE book_id = ? AND page_idx = ?
                        """,
                        (book_id, page_idx),
                    )
                    row = cursor.fetchone()

                    if row and os.path.exists(file_path):
                        local_header_offset = row['local_header_offset']
                        compress_size = row['compress_size']
                        file_size = row['file_size']
                        compress_type = row['compress_type']
                        target_filename = row['filename']

                        with open(file_path, 'rb') as f:
                            # 1) 로컬 파일 헤더 분석
                            f.seek(local_header_offset)
                            header = f.read(30)
                            if len(header) == 30:
                                fn_len = int.from_bytes(header[26:28], 'little')
                                extra_len = int.from_bytes(header[28:30], 'little')
                                data_offset = local_header_offset + 30 + fn_len + extra_len

                                # 2) 실제 데이터 조각 Seek & Read
                                f.seek(data_offset)
                                raw_bytes = f.read(compress_size)

                                img_data = None
                                if compress_type == 0:  # ZIP_STORED
                                    img_data = raw_bytes
                                elif compress_type == 8:  # ZIP_DEFLATED
                                    import zlib

                                    img_data = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)

                                if img_data is not None:
                                    mime, _ = mimetypes.guess_type(target_filename)
                                    mime = mime or 'image/jpeg'
                                    result = (img_data, mime)
                                    image_cache.put(cache_key, result, len(img_data))
                                    return result
                except Exception as ex_offset:
                    print(
                        f"[Offset-SpeedRun FAIL] {os.path.basename(file_path)} [{page_idx}]: {ex_offset} (Fallback executed)"
                    )
                finally:
                    if conn:
                        conn.close()

            # [Fallback Path]
            zf = get_zip_file_hybrid(file_path)
            if zf is None:
                return None

            img_files = get_img_files(file_path, zf)
            if page_idx < 0 or page_idx >= len(img_files):
                return None

            try:
                target = img_files[page_idx]
                data = zf.read(target)
                mime, _ = mimetypes.guess_type(target)
                mime = mime or 'image/jpeg'
                result = (data, mime)

                image_cache.put(cache_key, result, len(data))
                return result
            except Exception as e:
                print(f"[StreamPageService] Page extract fail [{file_path}:{page_idx}]: {e}")
                return None

    @staticmethod
    def get_file_path(db_type, book_id, user_id=None, role=None):
        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            perm_clause, perm_params = StreamPageService._book_permission_clause(user_id=user_id, role=role, book_alias='b')
            cursor.execute(
                f"SELECT b.file_path FROM books b WHERE b.id = ? AND COALESCE(b.is_deleted, 0) = 0{perm_clause}",
                (book_id, *perm_params),
            )
            row = cursor.fetchone()
            return row['file_path'] if row else None
        finally:
            if conn:
                conn.close()
