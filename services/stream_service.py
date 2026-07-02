# -*- coding: utf-8 -*-
import os
import re
import mimetypes
from datetime import datetime
from api.cache import namelist_cache, image_cache, PREFETCH_AHEAD
from utils.cache_helper import get_zip_file_hybrid, get_zip_read_lock
import database

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
    img_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
    from utils.sort_helper import natural_sort_key
    img_files = sorted(
        [n for n in zf.namelist() if n.lower().endswith(img_ext)],
        key=natural_sort_key
    )
    namelist_cache.put(lookup_key, img_files)
    return img_files

class StreamService:
    @staticmethod
    def extract_page(file_path: str, page_idx: int, db_type: str = 'general', book_id = None):
        """단일 페이지를 (img_data, mime_type)으로 반환 (Zip 오프셋 최적화 및 Fallback 지원)"""
        cache_key = (file_path, page_idx)
        cached = image_cache.get(cache_key)
        if cached is not None:
            return cached

        with get_zip_read_lock(file_path):
            cached = image_cache.get(cache_key)
            if cached is not None:
                return cached

            # ── [Fast Path] Zip 오프셋 기반 부분 스트리밍 가속 기동 ──
            if book_id is not None:
                conn = None
                try:
                    conn = database.get_connection(db_type)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT filename, local_header_offset, compress_size, file_size, compress_type
                        FROM book_offsets
                        WHERE book_id = ? AND page_idx = ?
                    """, (book_id, page_idx))
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
                                if compress_type == 0:  # ZIP_STORED (압축 해제 불필요)
                                    img_data = raw_bytes
                                    # print(f"[Offset-SpeedRun] STORED Serving: {target_filename} ({compress_size} bytes)")
                                elif compress_type == 8:  # ZIP_DEFLATED (압축 적용)
                                    import zlib
                                    img_data = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
                                    # print(f"[Offset-SpeedRun] DEFLATED Serving: {target_filename} (Original: {file_size} bytes)")

                                if img_data is not None:
                                    mime, _ = mimetypes.guess_type(target_filename)
                                    mime = mime or 'image/jpeg'
                                    result = (img_data, mime)
                                    image_cache.put(cache_key, result, len(img_data))
                                    return result
                except Exception as ex_offset:
                    print(f"[Offset-SpeedRun FAIL] {os.path.basename(file_path)} [{page_idx}]: {ex_offset} (Fallback executed)")
                finally:
                    if conn:
                        conn.close()

            # ── [Fallback Path] 오프셋 조회 불가 또는 실패 시 기존 전체 복사/Seek 캐시 엔진 사용 ──
            # print(f"[Offset-Fallback] Legacy loader executed: {os.path.basename(file_path)}")
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
                print(f"[StreamService] Page extract fail [{file_path}:{page_idx}]: {e}")
                return None

    @staticmethod
    def record_progress(db_type: str, book_id, page_idx: int, total_pages: int, user_id=1):
        """독서 진행률 및 활동 로그 기록 (EPUB 등 페이지 수가 없는 도서의 자동 동기화 포함)"""
        conn   = database.get_connection(db_type)
        cursor = conn.cursor()
        
        # ── [동적 페이지 수집] DB의 total_pages가 0일 경우 뷰어가 전달한 값으로 갱신 (EPUB 대응) ──
        if total_pages > 0:
            cursor.execute("SELECT total_pages FROM books WHERE id = ?", (book_id,))
            book_row = cursor.fetchone()
            if book_row and book_row['total_pages'] == 0:
                cursor.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))
                
        cursor.execute("SELECT pages_read FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, user_id))
        row = cursor.fetchone()

        pages_read   = page_idx + 1
        is_completed = 0
        if total_pages > 0:
            if (pages_read / total_pages) >= 0.95 or pages_read >= total_pages:
                is_completed = 1
        now_str      = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if row:
            old_pages = row['pages_read']
            delta     = max(0, pages_read - old_pages)
            cursor.execute(
                "UPDATE user_progress SET pages_read=?, is_completed=?, last_read_at=? WHERE book_id=? AND user_id=?",
                (pages_read, is_completed, now_str, book_id, user_id)
            )
        else:
            delta = pages_read
            cursor.execute(
                "INSERT INTO user_progress (book_id, user_id, pages_read, is_completed, last_read_at) VALUES (?,?,?,?,?)",
                (book_id, user_id, pages_read, is_completed, now_str)
            )

        if delta > 0:
            today_str = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT id FROM user_reading_log WHERE book_id=? AND user_id=? AND read_date=?", (book_id, user_id, today_str))
            log_row = cursor.fetchone()
            if log_row:
                cursor.execute("UPDATE user_reading_log SET pages_read_delta=pages_read_delta+? WHERE id=?", (delta, log_row['id']))
            else:
                cursor.execute(
                    "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?,?,?,60,?)",
                    (book_id, user_id, delta, today_str)
                )

        conn.commit()
        conn.close()

    @staticmethod
    def get_txt_content(file_path):
        """TXT 소설 파일의 자동 인코딩 디코딩 처리"""
        if not os.path.exists(file_path):
            return None, 'File not found'

        content = ""
        for enc in ('utf-8', 'cp949', 'euc-kr', 'latin-1'):
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                return content, None
            except UnicodeDecodeError:
                continue
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='ignore')
            return content, None
        except Exception as e:
            return None, f"Failed to decode file: {e}"

    @staticmethod
    def get_file_path(db_type, book_id):
        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM books WHERE id=?", (book_id,))
            row = cursor.fetchone()
            return row['file_path'] if row else None
        finally:
            if conn:
                conn.close()
