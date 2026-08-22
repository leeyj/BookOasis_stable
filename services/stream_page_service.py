# -*- coding: utf-8 -*-
import os
import mimetypes

from api.cache import namelist_cache, image_cache
from utils.cache_helper import get_zip_file_hybrid, get_zip_read_lock
from utils.permission_clause import build_library_permission_clause
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


from api.cache import LRUCache, PREFETCH_AHEAD
import threading

_book_info_cache = LRUCache(capacity=2000)

class StreamPageService:
    @staticmethod
    def _book_permission_clause(user_id=None, role=None, book_alias='b'):
        return build_library_permission_clause(user_id, role, alias=book_alias)

    @staticmethod
    def get_book_file_info(db_type, book_id, user_id=None, role=None):
        cache_key = f"{db_type}:{book_id}:{user_id}:{role}"
        cached = _book_info_cache.get(cache_key)
        if cached is not None:
            return cached if cached != 'NOT_FOUND' else (None, None)

        from repositories.book_repository import BookRepository
        perm_clause, perm_params = StreamPageService._book_permission_clause(user_id=user_id, role=role, book_alias='b')
        row = BookRepository.get_book_file_info_with_permission(db_type, book_id, perm_clause, perm_params)
        if not row:
            _book_info_cache.put(cache_key, 'NOT_FOUND')
            return None, None
        file_path = StreamPageService._resolve_gdrive_view_copy(db_type, book_id, row['file_path'], row.get('library_id'))
        result = (file_path, (row['file_format'] or '').lower())
        # gdrive 사전복사가 아직 로컬 경로로 못 바꾼 경우(일시적 실패 등) file_path는 여전히
        # gdrive:// 가상 경로 그대로다 — 이 상태를 그대로 캐싱해버리면 다음 요청들이 캐시
        # 히트로 재시도 로직(_resolve_gdrive_view_copy)을 아예 건너뛰어, 복사가 나중에
        # 성공해도 이 캐시 엔트리가 만료될 때까지 계속 원본 스트리밍(또는 실패)에 갇힌다.
        # 아직 해결 안 된 상태는 캐시하지 않아 다음 요청이 항상 재시도하게 한다.
        from utils.drive_helper import is_gdrive_url
        if not is_gdrive_url(file_path):
            _book_info_cache.put(cache_key, result)
        return result

    @staticmethod
    def _resolve_gdrive_view_copy(db_type, book_id, file_path, library_id):
        """gdrive 공유 카테고리 책이면 책 단위 사전복사 결과(있으면 로컬 경로)로 바꿔치기한다.
        gdrive 경로가 아니거나 library_id가 없으면 file_path를 그대로 반환한다(no-op)."""
        from utils.drive_helper import is_gdrive_url
        if not file_path or not is_gdrive_url(file_path) or library_id is None:
            return file_path

        from repositories.category_repository import CategoryRepository
        from services.gdrive_view_copy_service import resolve_viewable_path
        library = CategoryRepository.get_library_by_id(db_type, library_id)
        return resolve_viewable_path(db_type, book_id, file_path, library)

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
    def _trigger_background_prefetch(file_path: str, current_page_idx: int, db_type: str, book_id):
        """현재 읽고 있는 페이지 다음 PREFETCH_AHEAD (4페이지)를 백그라운드 사전 추출.

        로컬 디스크는 순차로도 충분히 빠르지만, gdrive:// 가상 경로는 페이지 하나당
        Range 요청이 두 번(헤더+데이터) 걸려 순차 프리페치로는 사용자가 빠르게 다음 페이지로
        넘어가는 속도를 못 따라갈 수 있다 — 여러 페이지를 동시에(스레드풀) 미리 받는다."""
        def _prefetch_one(target_idx):
            target_cache_key = (file_path, target_idx)
            if image_cache.get(target_cache_key) is not None:
                return
            try:
                StreamPageService.extract_page(file_path, target_idx, db_type=db_type, book_id=book_id, is_prefetch=True)
            except Exception:
                pass

        def _prefetch_worker():
            from concurrent.futures import ThreadPoolExecutor
            targets = [current_page_idx + offset for offset in range(1, PREFETCH_AHEAD + 1)]
            with ThreadPoolExecutor(max_workers=min(4, len(targets))) as executor:
                list(executor.map(_prefetch_one, targets))

        thread = threading.Thread(target=_prefetch_worker, daemon=True)
        thread.start()

    @staticmethod
    def extract_page(file_path: str, page_idx: int, db_type: str = 'general', book_id=None, is_prefetch=False):
        """단일 페이지를 (img_data, mime_type)으로 반환 (Zip 오프셋 최적화, 백그라운드 프리페치 및 Fallback 지원)"""
        cache_key = (file_path, page_idx)
        cached = image_cache.get(cache_key)
        if cached is not None:
            if not is_prefetch and book_id is not None:
                StreamPageService._trigger_background_prefetch(file_path, page_idx, db_type, book_id)
            return cached

        # ─── Redis 캐시 조회 ───
        redis_cache_key = f"cache:stream:book:{db_type}:{book_id}:page:{page_idx}" if book_id else None
        if redis_cache_key:
            try:
                from utils.redis_helper import redis_get
                redis_data = redis_get(redis_cache_key)
                if redis_data:
                    import base64
                    import json
                    payload = json.loads(redis_data)
                    img_data = base64.b64decode(payload['data'])
                    mime_type = payload['mime']
                    result = (img_data, mime_type)
                    image_cache.put(cache_key, result, len(img_data))
                    if not is_prefetch and book_id is not None:
                        StreamPageService._trigger_background_prefetch(file_path, page_idx, db_type, book_id)
                    return result
            except Exception as r_err:
                print(f"[Redis Cache Get ERROR] {r_err}")

        with get_zip_read_lock(file_path):
            cached = image_cache.get(cache_key)
            if cached is not None:
                if not is_prefetch and book_id is not None:
                    StreamPageService._trigger_background_prefetch(file_path, page_idx, db_type, book_id)
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
                    
                    # Redis 캐시 저장
                    if redis_cache_key:
                        try:
                            from utils.redis_helper import redis_set
                            import base64
                            import json
                            payload = {
                                'mime': mime,
                                'data': base64.b64encode(data).decode('utf-8')
                            }
                            redis_set(redis_cache_key, json.dumps(payload), ex=3600)
                        except Exception as r_err:
                            print(f"[Redis Cache Put ERROR] {r_err}")
                            
                    if not is_prefetch and book_id is not None:
                        StreamPageService._trigger_background_prefetch(file_path, page_idx, db_type, book_id)
                    return result
                except Exception as e:
                    print(f"[StreamPageService] IMGDIR page extract fail [{target}]: {e}")
                    return None

            # [Fast Path] Zip 오프셋 기반 부분 스트리밍 가속 기동
            if book_id is not None:
                try:
                    from repositories.book_offset_repository import BookOffsetRepository
                    row = BookOffsetRepository.get_book_offset(db_type, book_id, page_idx)

                    if row:
                        local_header_offset = row['local_header_offset']
                        compress_size = row['compress_size']
                        file_size = row['file_size']
                        compress_type = row['compress_type']
                        target_filename = row['filename']

                        raw_bytes = None
                        if os.path.exists(file_path):
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
                        else:
                            # 로컬에 파일이 없는 경우(구글 드라이브 gdrive:// 가상 경로) — 전체를
                            # 다운로드하지 않고, 이 페이지의 압축 바이트만 Range 요청으로 받아온다.
                            # (로컬 파일 헤더 조회 + 데이터 조각 조회, 총 두 번의 부분 요청)
                            from utils.drive_helper import is_gdrive_url, split_gdrive_file_id, fetch_gdrive_page_bytes
                            if is_gdrive_url(file_path):
                                _, gdrive_file_id = split_gdrive_file_id(file_path)
                                if gdrive_file_id:
                                    raw_bytes = fetch_gdrive_page_bytes(gdrive_file_id, local_header_offset, compress_size)

                        if raw_bytes is not None:
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

                                # Redis 캐시 저장
                                if redis_cache_key:
                                    try:
                                        from utils.redis_helper import redis_set
                                        import base64
                                        import json
                                        payload = {
                                            'mime': mime,
                                            'data': base64.b64encode(img_data).decode('utf-8')
                                        }
                                        redis_set(redis_cache_key, json.dumps(payload), ex=3600)
                                    except Exception as r_err:
                                        print(f"[Redis Cache Put ERROR] {r_err}")

                                if not is_prefetch and book_id is not None:
                                    StreamPageService._trigger_background_prefetch(file_path, page_idx, db_type, book_id)
                                return result
                except Exception as ex_offset:
                    print(
                        f"[Offset-SpeedRun FAIL] {os.path.basename(file_path)} [{page_idx}]: {ex_offset} (Fallback executed)"
                    )

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
                
                # Redis 캐시 저장
                if redis_cache_key:
                    try:
                        from utils.redis_helper import redis_set
                        import base64
                        import json
                        payload = {
                            'mime': mime,
                            'data': base64.b64encode(data).decode('utf-8')
                        }
                        redis_set(redis_cache_key, json.dumps(payload), ex=3600)
                    except Exception as r_err:
                        print(f"[Redis Cache Put ERROR] {r_err}")

                if not is_prefetch and book_id is not None:
                    StreamPageService._trigger_background_prefetch(file_path, page_idx, db_type, book_id)
                return result
            except Exception as e:
                print(f"[StreamPageService] Page extract fail [{file_path}:{page_idx}]: {e}")
                return None

    @staticmethod
    def get_file_path(db_type, book_id, user_id=None, role=None):
        from repositories.book_repository import BookRepository
        perm_clause, perm_params = StreamPageService._book_permission_clause(user_id=user_id, role=role, book_alias='b')
        row = BookRepository.get_book_file_path_with_permission(db_type, book_id, perm_clause, perm_params)
        if not row:
            return None
        return StreamPageService._resolve_gdrive_view_copy(db_type, book_id, row['file_path'], row.get('library_id'))
