# -*- coding: utf-8 -*-
import os
import sys
import gc
import time
import sqlite3
from PIL import Image

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import builtins
import datetime
import database
from tools.scanner.cover import get_series_cover_fallback


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
            conn = sqlite3.connect(db_path)
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
        
        def custom_print(*args, **kwargs):
            # 터미널용 출력 (콘솔 실행 시 확인용)
            original_print(*args, **kwargs)
            
            # lazy_scanner.log 파일 기록
            try:
                sep = kwargs.get('sep', ' ')
                end = kwargs.get('end', '\n')
                message = sep.join(map(str, args)) + end
                
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                formatted_message = f"[{timestamp}] {message}"
                
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(formatted_message)
            except Exception:
                pass
        builtins.print = custom_print
    else:
        builtins.print = lambda *args, **kwargs: None


def run_lazy_cover_extraction(target_book_id=None):
    setup_lazy_scanner_logging()
    if target_book_id is not None:
        print(f"[Lazy-Scanner] 🚀 단일 도서 즉시 스캔 기동 시작 (Book ID: {target_book_id})")
    else:
        print("[Lazy-Scanner] 🚀 독립 백그라운드 표지 스캐너 기동 시작")
    
    conn = None
    try:
        for db_type in ['general', 'adult']:
            db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
            if not os.path.exists(db_path):
                continue
                
            print(f"[Lazy-Scanner] DB 검사 중: {db_type}")
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            
            if target_book_id is not None:
                cursor.execute("""
                    SELECT id, file_path, series_name, file_format, cover_image, library_id, total_pages, has_offsets
                    FROM books WHERE id = ?
                """, (target_book_id,))
            else:
                cursor.execute("""
                    SELECT id, file_path, series_name, file_format, cover_image, library_id, total_pages, has_offsets
                    FROM books
                """)
                
            books = cursor.fetchall()
            
            targets = []
            for book in books:
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
                if offset_only:
                    print(f"[Lazy-Scanner] 오프셋 전용 재수집 대상: {os.path.basename(file_path)}")

                # 원격 경로(GDRIVE 등)는 os.path.exists가 느리거나 실패할 수 있으므로 무조건 포함
                from utils.drive_helper import is_remote_path
                if is_remote_path(file_path) or os.path.exists(file_path):
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
                from tools.scanner.parser import parse_kavita_yaml, parse_series_json
                if has_cover_extraction:
                    yaml_meta = parse_kavita_yaml(parent_dir)
                    json_meta = parse_series_json(parent_dir)
                    b64_keys_lower = {k.lower(): v for k, v in yaml_meta.get('cover_b64_map', {}).items()}
                    is_json_only = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
                    is_series = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
                    series_cover_url = json_meta.get('cover_image_url', '') if (is_json_only or is_series) else ''
                else:
                    b64_keys_lower = {}
                    is_json_only = is_series = False
                    series_cover_url = ''
                shared_cover = None  # 폴더 내 최초 성공 커버 공유용
                
                for book, offset_only in folder_books:
                    done += 1
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
                    
                    try:
                        # ── 오프셋만 없는 경우: 커버 재추출 없이 오프셋만 수집 ──
                        if offset_only:
                            file_fmt = (book['file_format'] or '').lower()
                            from utils.drive_helper import is_remote_path
                            _is_remote = is_remote_path(file_path)
                            if _is_remote:
                                # 원격 경로(rclone/GDrive): zipfile.ZipFile이 Central Directory 읽기 위해
                                # Google Drive API 호출 발생 → 과부하 위험이 있어 스킵
                                print(f"[Lazy-Scanner] 원격 경로 오프셋 수집 스킵: {filename}")
                            elif file_fmt in ('zip', 'cbz'):
                                offsets = _collect_zip_offsets_safe(file_path)
                                if offsets:
                                    from tools.scanner.db_writer import save_book_offsets
                                    save_book_offsets(cursor, book_id, filename, offsets)
                                    conn.commit()
                                    print(f"[Lazy-Scanner] 오프셋 전용 저장 완료 ({len(offsets)}p): {filename}")
                                else:
                                    print(f"[Lazy-Scanner] 오프셋 수집 결과 없음 (이미지 없는 ZIP?): {filename}")
                            if target_book_id is None:
                                # 로컬 파일: ZIP Central Directory만 읽으므로 0.5초로 충분
                                # 원격 파일: 스킵했으므로 대기 불필요
                                if not _is_remote:
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
                                        cover_image = ?,
                                        cover_updated_at = CURRENT_TIMESTAMP,
                                        author = COALESCE(NULLIF(?, ''), author),
                                        publisher = COALESCE(NULLIF(?, ''), publisher),
                                        summary = COALESCE(NULLIF(?, ''), summary),
                                        release_date = COALESCE(NULLIF(?, ''), release_date)
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
                                        cover_image = ?,
                                        cover_updated_at = CURRENT_TIMESTAMP
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
                                print(f"[Lazy-Scanner] 오프셋 단독 저장 중 예외 무시: {oe}")
                        else:
                            raise ValueError("표지 이미지를 추출할 수 없거나 파일 포맷이 무효합니다.")

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
                            
                        lib_errors[library_id].append({
                            'file_path': file_path,
                            'filename': filename,
                            'error_type': error_type,
                            'message': f"ERR_LAZY_COVER_FAIL: {err_msg}"
                        })
                        
                    gc.collect()
                    if target_book_id is None:
                        time.sleep(3.0)
                
            # 카테고리별 수집된 에러 리포트 저장 트리거
            from utils.report_helper import save_scan_report
            for lib_id, err_list in lib_errors.items():
                if err_list:
                    save_scan_report(lib_id, err_list)
            
            try:
                conn.close()
            except Exception:
                pass
            conn = None

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    print("[Lazy-Scanner] ✅ 모든 DB의 Lazy 표지 스캔 작업 완료")

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
        from tools.scanner.parser import parse_kavita_yaml, parse_series_json
        yaml_meta = parse_kavita_yaml(parent_dir)
        json_meta = parse_series_json(parent_dir)
        filename_lower = filename.lower()
        b64_keys_lower = {k.lower(): v for k, v in yaml_meta.get('cover_b64_map', {}).items()}
        is_json_only = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
        is_series = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
        series_cover_url = json_meta.get('cover_image_url', '') if (is_json_only or is_series) else ''
    
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
            from tools.scanner.parser import parse_comicinfo_from_cbz
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
    target_id = None
    if len(sys.argv) > 2 and sys.argv[1] == '--book-id':
        try:
            target_id = int(sys.argv[2])
        except ValueError:
            pass
    run_lazy_cover_extraction(target_book_id=target_id)

