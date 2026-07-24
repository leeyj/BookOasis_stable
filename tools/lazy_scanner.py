# -*- coding: utf-8 -*-
import os
import sys
import gc
import time
import sqlite3
import argparse
from PIL import Image

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import builtins
import datetime
import database
from tools.scanner.cover import get_series_cover_fallback

# 우아한 종료 시그널 감지 플래그
stop_requested = False


def _collect_zip_offsets_safe(file_path):
    """ZIP/CBZ 파일의 이미지 오프셋 메타데이터를 안전하게 수집합니다.
    실패 시 빈 리스트를 반환하며 예외를 전파하지 않습니다."""
    try:
        from tools.scanner.offset import collect_zip_offsets_data
        return collect_zip_offsets_data(file_path)
    except Exception as e:
        print(f"[Lazy-Scanner] 오프셋 수집 중 예외 무시: {e}")
        return []

def setup_lazy_scanner_logging():
    write_log = True
    try:
        db_path = os.path.join(MEDIA_SERVER_DIR, 'db', 'media_general.db')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'SCANNER_WRITE_LOG'")
            row = cursor.fetchone()
            conn.close()
            if row:
                value = str(row['value']).strip()
                if value == '0':
                    write_log = False
    except Exception:
        pass

    original_print = builtins.print

    if write_log:
        log_dir = os.path.join(MEDIA_SERVER_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'lazy_scanner.log')
        from utils.logger import ZipRotatingLogger
        # 10MB 기준 자동 zip 회전 아카이빙 로거 생성
        zip_logger = ZipRotatingLogger(log_file_path, 10 * 1024 * 1024)
        
        def custom_print(*args, **kwargs):
            # 터미널용 출력 (콘솔 실행 시 확인용)
            original_print(*args, **kwargs)
            sys.stdout.flush()
            
            # lazy_scanner.log 파일 기록
            try:
                sep = kwargs.get('sep', ' ')
                end = kwargs.get('end', '\n')
                message = sep.join(map(str, args)) + end
                
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                formatted_message = f"[{timestamp}] {message}"
                
                zip_logger.write(formatted_message)
            except Exception:
                pass
        builtins.print = custom_print
    else:
        builtins.print = lambda *args, **kwargs: None


def run_lazy_cover_extraction(target_book_id=None, target_db_type=None):
    global stop_requested
    setup_lazy_scanner_logging()
    try:
        from utils.signal_helper import register_shutdown_handlers
        register_shutdown_handlers()
    except Exception:
        pass

    if target_book_id is not None:
        print(f"[Lazy-Scanner] 🚀 단일 도서 즉시 스캔 기동 시작 (Book ID: {target_book_id})")
    else:
        print("[Lazy-Scanner] 🚀 독립 백그라운드 표지 스캐너 기동 시작")
    
    conn = None
    try:
        db_types = ['general', 'adult']
        if target_db_type in ('general', 'adult'):
            db_types = [target_db_type]

        # ── 최대 스캔 허용 파일 크기(MB) 및 세션 누적 제한(MB) 설정 로드 ──
        max_size_mb = 300.0   # 개별 파일 안전 기본값 (300MB)
        max_batch_mb = 1024.0 # 세션 누적 안전 기본값 (1024MB = 1GB)
        try:
            gen_db_path = os.path.join(MEDIA_SERVER_DIR, 'db', 'media_general.db')
            if os.path.exists(gen_db_path):
                _tmp_conn = sqlite3.connect(gen_db_path, timeout=30.0)
                _tmp_conn.row_factory = sqlite3.Row
                _tmp_cur = _tmp_conn.cursor()
                _tmp_cur.execute("SELECT key, value FROM settings WHERE key IN ('LAZY_SCAN_MAX_FILE_SIZE_MB', 'LAZY_SCAN_MAX_BATCH_SIZE_MB')")
                _rows = {r['key']: r['value'] for r in _tmp_cur.fetchall()}
                _tmp_conn.close()
                if 'LAZY_SCAN_MAX_FILE_SIZE_MB' in _rows:
                    max_size_mb = float(str(_rows['LAZY_SCAN_MAX_FILE_SIZE_MB']).strip() or '300')
                if 'LAZY_SCAN_MAX_BATCH_SIZE_MB' in _rows:
                    max_batch_mb = float(str(_rows['LAZY_SCAN_MAX_BATCH_SIZE_MB']).strip() or '1024')
        except Exception as _se:
            print(f"[Lazy-Scanner] 크기 설정 로드 실패 (기본 300MB/1024MB 적용): {_se}")
        
        if max_size_mb > 0:
            print(f"[Lazy-Scanner] 📏 개별 파일 크기 제한: {max_size_mb:.0f} MB (초과 시 스킵)")
        else:
            print("[Lazy-Scanner] 📏 개별 파일 크기 제한 없음 (LAZY_SCAN_MAX_FILE_SIZE_MB=0)")

        if max_batch_mb > 0:
            print(f"[Lazy-Scanner] 📊 1회 세션 누적 처리 용량 한도: {max_batch_mb:.0f} MB (도달 시 다음 스케줄로 안전 이관)")
        else:
            print("[Lazy-Scanner] 📊 세션 누적 처리 용량 제한 없음 (LAZY_SCAN_MAX_BATCH_SIZE_MB=0)")

        session_accumulated_bytes = 0.0
        batch_limit_reached = False

        for db_type in db_types:
            if stop_requested or batch_limit_reached:
                if stop_requested:
                    print("[Lazy-Scanner] ⚠️ 중단 요청(SIGTERM/SIGINT) 감지. DB 순회를 중단합니다.")
                else:
                    print("[Lazy-Scanner] 🛑 용량 한도 달성으로 DB 순회를 중단하고 차기 서브-배치로 이관합니다.")
                break

            db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
            if not os.path.exists(db_path):
                continue
                
            print(f"[Lazy-Scanner] 🔍 DB 연결 및 검사 시작: {db_type}")
            conn = sqlite3.connect(db_path, timeout=60.0)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA busy_timeout = 60000;")
                conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
            cursor = conn.cursor()
            
            if target_book_id is not None:
                cursor.execute("""
                    SELECT id, file_path, series_name, file_format, cover_image, library_id, total_pages, has_offsets
                    FROM books WHERE id = ?
                """, (target_book_id,))
            else:
                # ── DB SQL 필터링 최적화 ──
                # 1. txt 확장자 제외
                # 2. 커버 경로가 없는 경우(NULL 또는 빈 문자열)
                # 3. ZIP/CBZ 포맷 중 페이지 수(total_pages)=0 이거나 오프셋(has_offsets)=0 인 경우
                # 위 스캔 후보 도서만 DB 인덱스 레벨에서 1차 선별하여 퍼포먼스 극대화
                cursor.execute("""
                    SELECT id, file_path, series_name, file_format, cover_image, library_id, total_pages, has_offsets
                    FROM books
                    WHERE LOWER(file_path) NOT LIKE '%.txt'
                      AND (
                          (cover_image IS NULL OR cover_image = '')
                          OR (LOWER(COALESCE(file_format, '')) IN ('zip', 'cbz') AND COALESCE(has_offsets, 0) = 0)
                      )
                      AND COALESCE(cover_image, '') != 'NO_COVER'
                      AND COALESCE(has_offsets, 0) != -1
                """)
                
            books = cursor.fetchall()
            print(f"[Lazy-Scanner] 📋 DB({db_type}) 스캔 필요 후보 도서 레코드 조회 완료 (총 {len(books)}권). 파일 물리 점검 시작...")
            
            targets = []
            for book in books:
                if stop_requested:
                    print(f"[Lazy-Scanner] ⚠️ DB({db_type}) 파일 물리 점검 도중 중단 요청(SIGTERM/SIGINT) 감지. 점검을 중단합니다.")
                    break

                file_path = book['file_path']
                cover_image = book['cover_image']
                
                # 텍스트 파일(.txt)은 표지가 없는 것이 정상이므로 복원 대상에서 사전에 제외
                if file_path.lower().endswith('.txt'):
                    continue
                
                # ── 커버 유효성 판단 ──
                cover_missing = False
                if not cover_image:
                    # 커버 경로 자체가 없음
                    cover_missing = True
                else:
                    cover_filepath = os.path.join(MEDIA_SERVER_DIR, 'covers', cover_image)
                    if not os.path.exists(cover_filepath) or os.path.getsize(cover_filepath) == 0:
                        # 커버 경로는 있지만 실제 파일이 없거나 0바이트
                        cover_missing = True

                # ── 오프셋 유효성 판단 (ZIP/CBZ 전용) ──
                offset_missing = False
                file_format = (book['file_format'] or '').lower()
                if file_format in ('zip', 'cbz'):
                    if book['total_pages'] == 0 or book['has_offsets'] == 0:
                        offset_missing = True

                if not cover_missing and not offset_missing:
                    # 커버도 있고 오프셋도 있음 → 완전히 처리된 도서, 스킵
                    continue

                # ── offset_only 플래그: 커버는 정상이고 오프셋만 없는 경우 ──
                # 커버 재추출 없이 오프셋 수집만 수행하여 불필요한 I/O를 방지
                offset_only = (not cover_missing and offset_missing)
                
                from utils.drive_helper import is_remote_path
                _is_remote = is_remote_path(file_path)
                
                # [원격 경로 최적화] 커버는 정상이고 오프셋만 없는 원격지(GDRIVE 등) 도서는
                # 백그라운드 대량 스캔 부하 차단을 위해 Lazy 스캔 수집 대상에서 원천 배제합니다.
                # (뷰어에서 열릴 때 실시간으로 파싱되므로 성능에 문제 없음)
                if offset_only and _is_remote:
                    continue
                    
                if offset_only:
                    print(f"[Lazy-Scanner] 오프셋 전용 재수집 대상: {os.path.basename(file_path)}")

                # 원격 경로(GDRIVE 등)는 os.path.exists가 느리거나 실패할 수 있으므로 무조건 포함
                if _is_remote or os.path.exists(file_path):
                    targets.append((book, offset_only))

                    
            cover_missing_count = sum(1 for _, offset_only in targets if not offset_only)
            offset_only_count   = sum(1 for _, offset_only in targets if offset_only)
            print(f"[Lazy-Scanner] DB={db_type} -> 처리 대상 도서 수: {len(targets)}권 (커버 재추출: {cover_missing_count}권 / 오프셋 전용: {offset_only_count} books)")
            
            # 폴더별 그룹핑: 같은 폴더의 kavita.yaml/series.json을 한 번만 파싱
            from collections import defaultdict
            from utils.sort_helper import natural_sort_key
            folder_groups = defaultdict(list)
            for book, offset_only in targets:
                parent_dir = os.path.dirname(book['file_path'])
                folder_groups[parent_dir].append((book, offset_only))
            
            # 폴더 내 파일을 정렬
            for parent_dir in folder_groups:
                folder_groups[parent_dir].sort(key=lambda t: natural_sort_key(t[0]['file_path']))
            
            # 카테고리별 에러 리스트 수집용 딕셔너리
            lib_errors = {}
            total = len(targets)
            done = 0
            
            for parent_dir, folder_books in folder_groups.items():
                # 폴더당 1회만 메타데이터 파싱 (커버 재추출이 필요한 도서가 있을 때만)
                has_cover_extraction = any(not oo for _, oo in folder_books)
                if has_cover_extraction:
                    from tools.scanner.metadata import merge_local_metadata
                    merged_meta = merge_local_metadata(parent_dir)
                    b64_keys_lower = {k.lower(): v for k, v in merged_meta.get('cover_b64_map', {}).items()}
                    is_json_only = bool(not merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
                    is_series = bool(merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
                    series_cover_url = merged_meta.get('cover_image_url', '') if (is_json_only or is_series) else ''
                else:
                    b64_keys_lower = {}
                    is_json_only = is_series = False
                    series_cover_url = ''
                shared_cover = None  # 폴더 내 최초 성공 커버 공유용
                
                for book, offset_only in folder_books:
                    done += 1
                    
                    # ─── 우아한 종료 시그널 감지 가드 ───
                    if stop_requested:
                        print("[Lazy-Scanner] ⚠️ 중단 요청(SIGTERM/SIGINT)이 감지되었습니다. 진행 중 트랜잭션 롤백 후 차기 재실행을 위해 우아하게 마감합니다 (Exit Code 10).")
                        if conn:
                            try:
                                conn.rollback()
                                conn.close()
                            except Exception:
                                pass
                        sys.exit(10)

                    # ─── 메모리 자가 진단 및 Graceful 자진 종료 가드 ───
                    try:
                        from tools.scanner.memory_helper import check_memory_exceeded
                        if check_memory_exceeded(db_type=db_type):
                            print(f"[Lazy-Scanner] ⚠️ 메모리 사용량 한계 초과 감지. 차기 세션 재기동을 위한 안전 자진 종료를 기동합니다 (Exit Code 10).")
                            if conn:
                                try:
                                    conn.close()
                                except:
                                    pass
                            sys.exit(10)
                    except Exception as mem_err:
                        pass
                        
                    book_id = book['id']
                    file_path = book['file_path']
                    series_name = book['series_name'] or ""
                    library_id = book['library_id']
                    filename = os.path.basename(file_path)
                    
                    if library_id not in lib_errors:
                        lib_errors[library_id] = []
                    
                    _fmt = (book['file_format'] or '').lower()
                    _offset_missing = _fmt in ('zip', 'cbz') and (book['total_pages'] == 0 or book['has_offsets'] == 0)
                    if offset_only:
                        mode_label = "[오프셋 전용]"
                    elif _offset_missing:
                        mode_label = "[커버+오프셋]"  # ZIP/CBZ: 커버도 없고 오프셋도 없음
                    else:
                        mode_label = "[커버]"          # EPUB/PDF 등: 커버만 없음
                    print(f"[Lazy-Scanner] ({done}/{total}) {mode_label} 처리 시작 -> {filename}")

                    # ─── 1. 개별 파일 크기 초과 체크 ───
                    curr_file_size = 0.0
                    try:
                        curr_file_size = os.path.getsize(file_path)
                    except OSError:
                        pass

                    if max_size_mb > 0:
                        try:
                            file_size_mb = curr_file_size / (1024.0 * 1024.0)
                            if file_size_mb > max_size_mb:
                                print(f"[Lazy-Scanner] ⛔ 파일 크기 초과 스킵 ({file_size_mb:.1f} MB > {max_size_mb:.0f} MB): {filename}")
                                lib_errors[library_id].append({
                                    'file_path': file_path,
                                    'filename': filename,
                                    'error_type': 'SkippedOversizedFile',
                                    'message': f"LAZY_SKIP: 개별 파일 크기({file_size_mb:.1f} MB)가 허용 한도({max_size_mb:.0f} MB)를 초과하여 스캔을 건너뜁니다."
                                })
                                gc.collect()
                                continue
                        except OSError as _size_err:
                            print(f"[Lazy-Scanner] ⚠️ 파일 크기 조회 실패 → 안전 스킵: {filename} ({_size_err})")
                            lib_errors[library_id].append({
                                'file_path': file_path,
                                'filename': filename,
                                'error_type': 'SizeCheckFailed',
                                'message': f"LAZY_SKIP: 파일 크기 조회 실패로 안전하게 스캔을 건너뜁니다. ({_size_err})"
                            })
                            gc.collect()
                            continue

                    try:
                        # ── 오프셋만 없는 경우: 커버 재추출 없이 오프셋만 수집 ──
                        if offset_only:
                            file_fmt = (book['file_format'] or '').lower()
                            from utils.drive_helper import is_remote_path
                            _is_remote = is_remote_path(file_path)
                            if file_fmt in ('zip', 'cbz'):
                                if _is_remote:
                                    try:
                                        import zipfile
                                        from utils.sort_helper import natural_sort_key
                                        img_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
                                        with zipfile.ZipFile(file_path, 'r') as zf:
                                            infolist = zf.infolist()
                                            img_infos = [info for info in infolist if info.filename.lower().endswith(img_ext)]
                                            img_infos.sort(key=lambda x: natural_sort_key(x.filename))
                                            offsets = []
                                            for page_idx, info in enumerate(img_infos):
                                                offsets.append((
                                                    page_idx,
                                                    info.filename,
                                                    info.header_offset,
                                                    info.compress_size,
                                                    info.file_size,
                                                    info.compress_type
                                                ))
                                    except Exception as re_err:
                                        print(f"[Lazy-Scanner] 원격 오프셋 직접 수집 실패: {re_err}")
                                        offsets = []
                                else:
                                    offsets = _collect_zip_offsets_safe(file_path)

                                if offsets:
                                    from tools.scanner.db_writer import save_book_offsets
                                    save_book_offsets(cursor, book_id, filename, offsets)
                                    conn.commit()
                                    print(f"[Lazy-Scanner] 오프셋 전용 저장 완료 ({len(offsets)}p): {filename}")
                                    
                                    # ── 성공 시 세션 누적 가산 ──
                                    session_accumulated_bytes += curr_file_size
                                    session_accumulated_mb = session_accumulated_bytes / (1024.0 * 1024.0)
                                    if max_batch_mb > 0 and session_accumulated_mb >= max_batch_mb:
                                        print(f"[Lazy-Scanner] 🛑 세션 성공 처리 누적 용량 한도 달성 ({session_accumulated_mb:.1f} MB / {max_batch_mb:.0f} MB). 차기 서브-배치 세션을 기동합니다.")
                                        batch_limit_reached = True
                                        break
                                else:
                                    print(f"[Lazy-Scanner] 오프셋 수집 결과 없음 (이미지 없는 ZIP?): {filename}")
                            if target_book_id is None:
                                if _is_remote:
                                    time.sleep(3.0)
                                else:
                                    time.sleep(0.5)
                            continue

                        result = get_series_cover_fallback_single(
                            series_name, parent_dir, filename, file_path, library_id,
                            b64_keys_lower=b64_keys_lower,
                            series_cover_url=series_cover_url,
                            shared_cover=shared_cover,
                            is_series=is_series,
                            is_json_only=is_json_only
                        )
                        
                        # 반환값은 (cover_path, comicinfo_meta, offsets_data) 3-튜플
                        if isinstance(result, tuple) and len(result) == 3:
                            cover_image_path, comicinfo_meta, offsets_data = result
                        elif isinstance(result, tuple) and len(result) == 2:
                            cover_image_path, comicinfo_meta = result
                            offsets_data = []
                        else:
                            cover_image_path, comicinfo_meta = result, None
                            offsets_data = []

                        if cover_image_path:
                            # 폴더 내 최초 성공 커버를 shared_cover로 캐싱
                            if (is_series or is_json_only) and not shared_cover:
                                shared_cover = cover_image_path

                            # ComicInfo.xml 메타데이터가 있으면 함께 업데이트
                            if comicinfo_meta and any(comicinfo_meta.get(k) for k in ('author', 'summary', 'publisher', 'release_date')):
                                cursor.execute("""
                                    UPDATE books SET
                                        cover_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN ? ELSE cover_image END,
                                        cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                                        author = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
                                        publisher = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
                                        summary = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
                                        release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END
                                    WHERE id = ?
                                """, (
                                    cover_image_path,
                                    comicinfo_meta.get('author', ''),
                                    comicinfo_meta.get('publisher', ''),
                                    comicinfo_meta.get('summary', ''),
                                    comicinfo_meta.get('release_date', ''),
                                    book_id
                                ))
                            else:
                                cursor.execute("""
                                    UPDATE books SET
                                        cover_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN ? ELSE cover_image END,
                                        cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN CURRENT_TIMESTAMP ELSE cover_updated_at END
                                    WHERE id = ?
                                """, (cover_image_path, book_id))
                            conn.commit()
                            print(f"[Lazy-Scanner] 표지 추출 및 DB 업데이트 완료: {cover_image_path}")

                            # ── 오프셋 저장 및 total_pages 갱신 ──
                            if offsets_data:
                                try:
                                    from tools.scanner.db_writer import save_book_offsets
                                    save_book_offsets(cursor, book_id, filename, offsets_data)
                                    conn.commit()
                                except Exception as oe:
                                    print(f"[Lazy-Scanner] 오프셋 저장 중 예외 무시: {oe}")

                        elif offsets_data:
                            # 커버 추출 실패해도 오프셋만 단독 저장 (total_pages 복구 목적)
                            try:
                                from tools.scanner.db_writer import save_book_offsets
                                save_book_offsets(cursor, book_id, filename, offsets_data)
                                conn.commit()
                                print(f"[Lazy-Scanner] 커버 없이 오프셋 단독 저장 완료: {filename}")
                            except Exception as oe:
                                print("[Lazy-Scanner] 표지 없이 오프셋 단독 저장 완료: " + filename)
                        else:
                            raise ValueError("표지 이미지를 추출할 수 없거나 파일 포맷이 무효합니다.")

                        # ── 성공(Success) 시에만 세션 누적 처리 용량 가산 및 마감 체크 ──
                        session_accumulated_bytes += curr_file_size
                        session_accumulated_mb = session_accumulated_bytes / (1024.0 * 1024.0)
                        if max_batch_mb > 0 and session_accumulated_mb >= max_batch_mb:
                            print(f"[Lazy-Scanner] 🛑 세션 성공 처리 누적 용량 한도 달성 ({session_accumulated_mb:.1f} MB / {max_batch_mb:.0f} MB). 메모리 환수를 위해 차기 서브-배치 세션을 기동합니다.")
                            batch_limit_reached = True
                            break

                    except Exception as e:
                        err_msg = str(e)
                        print(f"[Lazy-Scanner ERROR] 표지 추출 실패 ({filename}): {err_msg}")
                        
                        error_type = "Exception"
                        if "이중 압축" in err_msg or "Nested" in err_msg:
                            error_type = "NestedZipError"
                        elif "BadZipFile" in err_msg:
                            error_type = "BadZipFile"
                        elif "ValueError" in err_msg or "표지" in err_msg:
                            error_type = "NoCover"
                        elif file_path.lower().endswith('.pdf') and ("mupdf" in err_msg.lower() or "syntax error" in err_msg.lower() or "page tree" in err_msg.lower() or "cannot open" in err_msg.lower() or "fitz" in err_msg.lower()):
                            error_type = "MuPDFFormatError"
                            
                        # ── 실패한 도서는 cover_image = 'NO_COVER'로 갱신하여 다음 쿼리에서 무한 반복 스킵 ──
                        try:
                            cursor.execute("""
                                UPDATE books SET
                                    cover_image = CASE WHEN COALESCE(cover_image, '') = '' THEN 'NO_COVER' ELSE cover_image END,
                                    has_offsets = CASE WHEN (COALESCE(total_pages, 0) = 0 OR COALESCE(has_offsets, 0) = 0) THEN -1 ELSE has_offsets END
                                WHERE id = ?
                            """, (book_id,))
                            conn.commit()
                        except Exception as db_mark_err:
                            print(f"[Lazy-Scanner WARNING] 실패 상태 마킹 중 무시된 에러: {db_mark_err}")

                        lib_errors[library_id].append({
                            'file_path': file_path,
                            'filename': filename,
                            'error_type': error_type,
                            'message': f"ERR_LAZY_COVER_FAIL: {err_msg}"
                        })
                        
                    gc.collect()
                    if batch_limit_reached or stop_requested:
                        break
                    if target_book_id is None:
                        time.sleep(3.0)
                if batch_limit_reached or stop_requested:
                    break
                
            # 카테고리별 수집된 에러 리포트 저장 트리거
            from utils.report_helper import save_scan_report
            for lib_id, err_list in lib_errors.items():
                if err_list:
                    save_scan_report(lib_id, err_list)
            
            try:
                if conn:
                    try:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    except Exception:
                        pass
                    conn.close()
            except Exception:
                pass
            conn = None

            if batch_limit_reached or stop_requested:
                break

    finally:
        if conn:
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
    if batch_limit_reached or stop_requested:
        if stop_requested:
            print("[Lazy-Scanner] 🛑 서버 재기동/종료 시그널 감지로 안전 중단 (잔여 도서 자동 재개 대기, Exit Code 10)")
        else:
            print("[Lazy-Scanner] 🔄 세션 용량 한도 도달로 인한 차기 서브-배치 세션 기동 요청 (Exit Code 10)")
        sys.exit(10)
    else:
        print("[Lazy-Scanner] 🎉 더 이상 스캔할 대상 도서가 없습니다. 모든 Lazy 표지 스캔 작업이 완료되었습니다. (Exit Code 0)")
        sys.exit(0)

def get_series_cover_fallback_single(series_name, parent_dir, filename, file_path, library_id,
                                     b64_keys_lower=None, series_cover_url=None, shared_cover=None,
                                     is_series=False, is_json_only=False):
    """
    단일 도서의 커버를 추출합니다.
    폴더 그룹핑 환경에서 호출 시 b64_keys_lower, series_cover_url 등을 미리 계산하여 전달하여
    폴더당 YAML/JSON 재파싱 비용을 절약합니다.
    """
    import io
    import hashlib
    from tools.scanner.cover import COVERS_DIR, extract_cover_from_b64, download_cover_from_url
    
    book_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    cover_filename = f"book_{book_hash}.webp"
    local_cover_path = os.path.join(COVERS_DIR, str(library_id), cover_filename)
    db_cover_path = f"{library_id}/{cover_filename}"
    
    os.makedirs(os.path.dirname(local_cover_path), exist_ok=True)
    
    # 미리 파싱된 메타데이터가 없으면 여기서 직접 파싱 (단독 호출 시 하위 호환)
    if b64_keys_lower is None:
        from tools.scanner.metadata import merge_local_metadata
        merged_meta = merge_local_metadata(parent_dir)
        filename_lower = filename.lower()
        b64_keys_lower = {k.lower(): v for k, v in merged_meta.get('cover_b64_map', {}).items()}
        is_json_only = bool(not merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
        is_series = bool(merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
        series_cover_url = merged_meta.get('cover_image_url', '') if (is_json_only or is_series) else ''
    
    filename_lower = filename.lower()
    
    # 1) 폴더 내 공유 커버 재사용 (시리즈/웹툰 폴더이고 이미 첫 권에서 추출 성공한 경우)
    if (is_series or is_json_only) and shared_cover:
        print(f"[Lazy-Scanner] 시리즈 대표 커버 복제: '{filename}'")
        # 오프셋은 파일마다 별도 수집
        offsets = _collect_zip_offsets_safe(file_path) if file_path.lower().endswith(('.zip', '.cbz')) else []
        return (shared_cover, None, offsets)
    
    # 2) Kavita.yaml 표지 (Base64) — 대소문자 무시 매핑 (파일 다운로드 불필요, 즉시 처리)
    if filename_lower in b64_keys_lower:
        try:
            extracted_path = extract_cover_from_b64(file_path, b64_keys_lower[filename_lower], force=True, library_id=library_id)
            if extracted_path:
                print(f"[Lazy-Scanner] Kavita.yaml 표지(Base64) 우선 복원 성공: {filename}")
                offsets = _collect_zip_offsets_safe(file_path) if file_path.lower().endswith(('.zip', '.cbz')) else []
                return (extracted_path, None, offsets)
        except Exception as e:
            print(f"[Lazy-Scanner] Kavita.yaml 표지 우선 추출 중 예외 무시: {e}")
    
    # 3) series.json image URL 다운로드 (웹툰/json-only, 파일 직접 열기보다 가벼운 방식)
    if series_cover_url:
        try:
            extracted_path = download_cover_from_url(file_path, series_cover_url, force=True, library_id=library_id)
            if extracted_path:
                print(f"[Lazy-Scanner] series.json URL 표지 다운로드 성공: {filename}")
                offsets = _collect_zip_offsets_safe(file_path) if file_path.lower().endswith(('.zip', '.cbz')) else []
                return (extracted_path, None, offsets)
        except Exception as e:
            print(f"[Lazy-Scanner] series.json URL 표지 다운로드 중 예외 무시: {e}")
            
    # 3.5) CBZ 내부 ComicInfo.xml 메타데이터 추출 — 반환값에 함께 포함 (Lazy 핵심 강화)
    comicinfo_meta = None
    if file_path.lower().endswith(('.zip', '.cbz')):
        try:
            from tools.scanner.metadata import parse_comicinfo_from_cbz
            comicinfo_meta = parse_comicinfo_from_cbz(file_path)
            if any(comicinfo_meta.get(k) for k in ('author', 'summary', 'publisher')):
                print(f"[Lazy-Scanner] ComicInfo.xml 메타데이터 추출 성공: {filename}")
        except Exception as e:
            print(f"[Lazy-Scanner] ComicInfo.xml 파싱 중 예외 무시: {e}")
    
    # 4) 실제 파일을 열어 커버 추출 (Lazy 스캐너 핵심 기능 — 원격 파일도 여기서 직접 처리)
    if file_path.lower().endswith('.pdf'):

        try:
            import fitz
            doc = fitz.open(file_path)
            if len(doc) > 0:
                page = doc.load_page(0)
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                
                from PIL import Image
                img = Image.open(io.BytesIO(img_data))
                img.save(local_cover_path, "WEBP", quality=80)
                
                del img
                del pix
                del page
                doc.close()
                del doc
                # PDF는 오프셋 구조 없음 — 빈 리스트 반환
                return (db_cover_path, None, [])
        except Exception as e:
            print(f"[Lazy-Scanner] PDF fitz 렌더링 실패: {e}")
            raise e
    elif file_path.lower().endswith(('.zip', '.cbz')):
        # 이중 압축 사전 감지 차단
        import zipfile
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                infolist = zf.infolist()
                for info in infolist:
                    if info.filename.lower().endswith(('.zip', '.cbz')):
                        raise ValueError(f"이중 압축(Nested ZIP) 구조가 감지되었습니다. 내부 파일: {info.filename}")
        except zipfile.BadZipFile as bzf:
            raise zipfile.BadZipFile(f"압축 파일 헤더가 손상되었습니다: {str(bzf)}")

        from tools.scanner.cover import get_series_cover_fallback
        cover = get_series_cover_fallback(series_name, parent_dir, force=True, is_remote=False, filename=filename, file_path=file_path, library_id=library_id)
        # 커버 추출 성공 여부와 무관하게 오프셋 수집
        offsets = _collect_zip_offsets_safe(file_path)
        return (cover, comicinfo_meta, offsets)
    else:
        from tools.scanner.cover import get_series_cover_fallback
        cover = get_series_cover_fallback(series_name, parent_dir, force=True, is_remote=False, filename=filename, file_path=file_path, library_id=library_id)
        return (cover, None, [])

    return (None, None, [])


if __name__ == '__main__':
    # ─── 종료 시그널 핸들러 등록 ───
    try:
        from utils.signal_helper import register_shutdown_handlers
        register_shutdown_handlers()
    except Exception as sig_err:
        print(f"[Lazy-Scanner] 시그널 핸들러 등록 실패: {sig_err}")

    parser = argparse.ArgumentParser(description='Lazy scanner runner')
    parser.add_argument('--book-id', type=int, default=None)
    parser.add_argument('--db-type', choices=['general', 'adult'], default=None)
    args = parser.parse_args()

    try:
        run_lazy_cover_extraction(target_book_id=args.book_id, target_db_type=args.db_type)
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as main_err:
        import traceback
        tb = traceback.format_exc()
        print(f"[Lazy-Scanner FATAL ERROR] 치명적 예외 발생으로 프로세스가 중단되었습니다:\n{tb}")
        sys.exit(1)

