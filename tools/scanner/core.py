# -*- coding: utf-8 -*-
import os
import sys
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트 경로를 sys.path에 추가하여 패키지 임포트 오류 방지
MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import database
from tools.scanner.parser import parse_info_xml, parse_kavita_yaml, parse_series_json, parse_comicinfo_from_cbz, is_consonant_folder
from tools.scanner.cover import get_series_cover_fallback, extract_cover_from_b64, download_cover_from_url
from tools.scanner.offset import collect_zip_offsets_data
from tools.scanner.vfs import trigger_vfs_refresh
from utils.drive_helper import is_remote_path

import builtins
from contextlib import contextmanager

@contextmanager
def scanner_print_control(db_path):
    original_print = builtins.print
    write_log = True
    try:
        db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
        conn = database.get_connection(db_type)
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

    if not write_log:
        builtins.print = lambda *args, **kwargs: None
    try:
        yield
    finally:
        builtins.print = original_print

def scanner_print_control_decorator(func):
    def wrapper(db_path, *args, **kwargs):
        ctx = scanner_print_control(db_path)
        ctx.__enter__()
        try:
            return func(db_path, *args, **kwargs)
        finally:
            ctx.__exit__(None, None, None)
    return wrapper

# 경로 설정
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')
DB_GENERAL_PATH = os.path.join(DB_DIR, 'media_general.db')
DB_ADULT_PATH = os.path.join(DB_DIR, 'media_adult.db')

SUPPORTED_FORMATS = ('.zip', '.cbz', '.epub', '.pdf', '.txt')
MAX_SCANNER_THREADS = 4

from tools.scanner.memory_helper import check_memory_exceeded
from tools.scanner.db_writer import update_book_metadata, insert_new_book_v2, save_book_offsets
from tools.scanner.sync_detector import detect_and_handle_book_movement, handle_deleted_books

def process_folder_task(root, files, force, db_meta_full, db_offsets_cached, is_remote=False, library_id=None):
    """폴더별 독립 I/O 스캔 태스크 함수 (DB 무관, 순수 파일시스템/I/O 스케일링)"""
    print(f"[Scanner-DEBUG-Task] 📂 process_folder_task 진입 - 폴더: '{root}'")
    
    media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
    if not media_files:
        print(f"[Scanner-DEBUG-Task] 📁 미지원 폴더 (스킵) - 폴더: '{root}'")
        return None

    # 1. 메타데이터 파일이 존재하는지 사전 체크
    has_yaml = any(f.lower() == 'kavita.yaml' for f in files)
    has_xml = any(f.lower() == 'info.xml' for f in files)
    
    # 2. 강제 스캔이 아니고 메타데이터 파일이 없다면, 파일들이 모두 완벽히 캐시 등록되어 있는지 판별하여 조기 스킵
    if not force and not has_yaml and not has_xml:
        all_cached = True
        for filename in media_files:
            full_path = os.path.join(root, filename)
            if full_path not in db_meta_full or full_path not in db_offsets_cached:
                all_cached = False
                break
        if all_cached:
            print(f"[Scanner-DEBUG-Task] ⚡ [초고속 스킵] 모든 파일 캐싱 완료 및 메타데이터 무관 - 폴더: '{root}'")
            return None

    path_parts = os.path.normpath(root).split(os.sep)
    series_name = ""
    for i in range(len(path_parts) - 1):
        if is_consonant_folder(path_parts[i]):
            series_name = path_parts[i+1]
            break
    if not series_name and len(path_parts) > 0:
        series_name = path_parts[-1]

    print(f"[Scanner-DEBUG-Task]   - 메타데이터 YAML/XML/JSON 로드 시작")
    yaml_meta = parse_kavita_yaml(root, files=files)
    xml_meta = parse_info_xml(root, files=files)
    json_meta = parse_series_json(root, files=files)
    print(f"[Scanner-DEBUG-Task]   - 메타데이터 로드 완료")

    merged_meta = {
        'author': xml_meta['author'] or yaml_meta['author'] or json_meta['author'] or '',
        'publisher': xml_meta['publisher'] or yaml_meta['publisher'] or '',
        'summary': xml_meta['summary'] or yaml_meta['summary'] or json_meta['summary'] or '',
        'link': yaml_meta['link'] or '',
        'score': yaml_meta['score'] or 0,
        'release_date': xml_meta['release_date'] or '',
        'cover_b64_map': yaml_meta['cover_b64_map'] or {}
    }

    meta_has_data = bool(
        merged_meta['author'] or merged_meta['publisher'] or
        merged_meta['summary'] or merged_meta['release_date'] or
        merged_meta['cover_b64_map']
    )

    is_series_folder = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    is_json_only_webtoon = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    series_cover_url = json_meta.get('cover_image_url', '') if is_json_only_webtoon else ''
    shared_cover_image = None

    import zipfile
    results = []
    errors = []
    for filename in media_files:
        full_path = os.path.join(root, filename)
        _, ext = os.path.splitext(filename)
        file_format = ext.replace('.', '').lower()

        skip = False
        if not force and not meta_has_data and full_path in db_meta_full and full_path in db_offsets_cached:
            skip = True

        cover_image = None
        offsets_data = []
        offset_only = False  # 커버/메타 완비, 오프셋만 없는 고속 경로 플래그

        if skip:
            pass  # 완전히 캐싱된 도서 — 모든 처리 생략

        elif (
            not force and
            not meta_has_data and
            full_path in db_meta_full and
            full_path not in db_offsets_cached and
            file_format in ('zip', 'cbz') and
            not is_remote
        ):
            # ── [오프셋 전용 고속 경로] ──
            # 커버·메타 모두 완비된 기존 도서에 오프셋만 없는 경우:
            # ComicInfo 파싱·커버 추출 파이프라인을 완전히 건너뛰고
            # ZIP 중앙 디렉토리 읽기(오프셋 수집)만 실행 — I/O 최소화
            offset_only = True
            try:
                offsets_data = collect_zip_offsets_data(full_path)
                if offsets_data:
                    print(f"[Scanner-DEBUG-Task] ⚡ [오프셋 전용] '{filename}' ({len(offsets_data)}p)")
                else:
                    print(f"[Scanner-DEBUG-Task] ⚡ [오프셋 전용] 이미지 없는 ZIP 스킵: '{filename}'")
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ 오프셋 전용 수집 실패: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'OffsetError',
                    'message': f"오프셋 전용 수집 실패: {str(e)}"
                })

        else:
            # ── [일반 처리 경로] 커버 추출 + 오프셋 수집 ──
            print(f"[Scanner-DEBUG-Task]   - 파일 처리 시작: '{filename}'")
            try:
                # [ComicInfo.xml 파싱] 로컬 파일이고 CBZ 포맷인 경우, 파일 내부에서 메타데이터 보완
                # 원격 경로는 I/O 비용이 크므로 스킵 → Lazy 스캐너가 담당
                if not is_remote and file_format in ('cbz', 'zip') and (
                    not merged_meta['author'] or not merged_meta['summary']
                ):
                    try:
                        comicinfo = parse_comicinfo_from_cbz(full_path)
                        if comicinfo['author'] and not merged_meta['author']:
                            merged_meta['author'] = comicinfo['author']
                            print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml 저자 보완: {comicinfo['author']}")
                        if comicinfo['publisher'] and not merged_meta['publisher']:
                            merged_meta['publisher'] = comicinfo['publisher']
                        if comicinfo['summary'] and not merged_meta['summary']:
                            merged_meta['summary'] = comicinfo['summary']
                        if comicinfo['release_date'] and not merged_meta['release_date']:
                            merged_meta['release_date'] = comicinfo['release_date']
                    except Exception as ce:
                        print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml 파싱 스킵: {ce}")

                # 리눅스 환경 대소문자 문제 방지를 위해 소문자로 키 검색
                filename_lower = filename.lower()
                b64_keys_lower = {k.lower(): v for k, v in merged_meta['cover_b64_map'].items()}
                
                if filename_lower in b64_keys_lower:
                    print(f"[Scanner-DEBUG-Task]     - YAML b64 커버 디코딩 시작")
                    cover_image = extract_cover_from_b64(full_path, b64_keys_lower[filename_lower], force=force, library_id=library_id)
                
                if not cover_image:
                    if (is_series_folder or is_json_only_webtoon) and shared_cover_image:
                        print(f"[Scanner-DEBUG-Task]     - 시리즈 대표 커버(썸네일) 복제 적용")
                        cover_image = shared_cover_image
                    elif is_json_only_webtoon and series_cover_url:
                        print(f"[Scanner-DEBUG-Task]     - series.json URL 표지 다운로드 시작")
                        cover_image = download_cover_from_url(full_path, series_cover_url, force=force, library_id=library_id)
                    else:
                        print(f"[Scanner-DEBUG-Task]     - Fallback 커버 추출 시작")
                        cover_image = get_series_cover_fallback(series_name, root, force=force, is_remote=is_remote, filename=filename, file_path=full_path, library_id=library_id)
                
                # 출처(YAML/URL/Fallback)와 무관하게 시리즈 폴더라면 최초 성공한 표지를 공유용 썸네일로 보관
                if (is_series_folder or is_json_only_webtoon) and cover_image and not shared_cover_image:
                    shared_cover_image = cover_image

                # 표지 추출 결과가 0바이트 빈 파일인지 실시간 검증
                if cover_image:
                    cover_filepath = os.path.join(MEDIA_SERVER_DIR, 'covers', cover_image)
                    if os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) == 0:
                        print(f"[Scanner-DEBUG-Task] ⚠️ 추출된 표지 파일이 0바이트입니다: {cover_filepath}")
                        try:
                            os.remove(cover_filepath)
                        except Exception:
                            pass
                        cover_image = None  # 무효화하여 에러 리포트 수집 대상에 포함시킴
                
                # Zip/EPUB 포맷인데 표지가 확보되지 않은 경우 에러 리스트에 기록
                if not cover_image and file_format in ('zip', 'cbz', 'epub'):
                    errors.append({
                        'file_path': full_path,
                        'filename': filename,
                        'error_type': 'NoCover',
                        'message': '도서 내 표지 이미지가 존재하지 않거나 추출 결과가 0바이트(빈 파일)입니다.'
                    })
            except zipfile.BadZipFile as bzf:
                print(f"[Scanner-DEBUG-Task] ❌ BadZipFile 감지: '{filename}' - {bzf}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'BadZipFile',
                    'message': str(bzf)
                })
            except ValueError as ve:
                print(f"[Scanner-DEBUG-Task] ❌ ValueError 감지: '{filename}' - {ve}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'NoCover',
                    'message': str(ve)
                })
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ 일반 예외 감지: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'Exception',
                    'message': str(e)
                })

            try:
                if file_format in ('zip', 'cbz') and (force or full_path not in db_offsets_cached):
                    if is_remote:
                        offsets_data = []
                    else:
                        print(f"[Scanner-DEBUG-Task]     - 오프셋 분석 시작: '{filename}'")
                        offsets_data = collect_zip_offsets_data(full_path)
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ 오프셋 분석 실패: '{filename}' - {e}")
                if not any(err['file_path'] == full_path for err in errors):
                    errors.append({
                        'file_path': full_path,
                        'filename': filename,
                        'error_type': 'OffsetError',
                        'message': f"오프셋 분석 실패: {str(e)}"
                    })
            print(f"[Scanner-DEBUG-Task]   - 파일 처리 완료: '{filename}'")

        results.append({
            'full_path': full_path,
            'filename': filename,
            'file_format': file_format,
            'series_name': series_name,
            'cover_image': cover_image,
            'offsets_data': offsets_data,
            'skip': skip,
            'offset_only': offset_only,  # 오프셋-전용 고속 경로 여부
        })

    # 메모리 방출을 위해 사용이 완료된 대형 base64 맵 참조 소거
    merged_meta.pop('cover_b64_map', None)

    gc.collect()
    print(f"[Scanner-DEBUG-Task] 📁 process_folder_task 완료 - 폴더: '{root}'")
    return {
        'root': root,
        'merged_meta': merged_meta,
        'results': results,
        'errors': errors
    }

@scanner_print_control_decorator
def scan_library(db_path, library_id, physical_path, force=False):
    """지정된 라이브러리 경로를 스캔하여 DB를 파일 시스템과 동기화 (force=True인 경우 강제 전체 재색인)"""
    print(f"[Scanner] 스캔 시작: Library ID={library_id}, Path='{physical_path}', Force={force}")
    
    library_errors = []
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        print(f"[Scanner] 경고: 스캔할 경로가 존재하지 않습니다: {physical_path}")
        return

    trigger_vfs_refresh(db_path, library_id, physical_path)
    
    is_remote = any(is_remote_path(p) for p in target_paths)
    threads_to_use = 1 if is_remote else MAX_SCANNER_THREADS

    if is_remote:
        print(f"[Scanner-VFS] 원격 마운트 경로 감지로 스캔 스레드를 직렬화({threads_to_use}개)로 실행하고, 무거운 압축 파일 I/O 분석을 생략합니다.")

    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    conn = database.get_connection(db_type)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_path, has_offsets,
               cover_image, author, publisher, summary
        FROM books WHERE library_id = ?
    """, (library_id,))
    all_rows = cursor.fetchall()
    db_books = {}          
    db_meta_full = set()   
    db_offsets_cached = set() 
    for row in all_rows:
        db_books[row['file_path']] = row['id']
        if row['has_offsets'] == 1:
            db_offsets_cached.add(row['file_path'])
        if (row['cover_image'] and not row['cover_image'].startswith('series_') and
                row['author'] and row['publisher'] and row['summary']):
            db_meta_full.add(row['file_path'])

    # 0. 이전 중단 지점(체크포인트)의 스캔 완료 폴더 로드
    cursor.execute("SELECT folder_path FROM scanner_progress WHERE library_id = ?", (str(library_id),))
    scanned_folders = set(row['folder_path'] for row in cursor.fetchall())
    if scanned_folders:
        print(f"[Scanner-Progress] 🔄 이전 스캔 진행기록 감지 ({len(scanned_folders)}개 폴더 완료 상태). 이어서 스캔을 시작합니다.")

    # 1. 물리 폴더 트리 탐색 및 파일 목록 사전 수집
    tasks = []
    found_file_paths = set()
    print(f"[Scanner] 물리 폴더 트리 탐색 중...")
    folder_count = 0
    for t_path in target_paths:
        if not os.path.exists(t_path):
            print(f"[Scanner] 경고: 경로가 존재하지 않아 건너뜁니다: {t_path}")
            continue
        for root, dirs, files in os.walk(t_path):
            media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
            if not media_files:
                continue
            for f in media_files:
                found_file_paths.add(os.path.join(root, f))
            
            if root in scanned_folders:
                continue
                
            tasks.append((root, files))

    # ── [도서 이동 감지 및 기록 보존 레이어 - 스레드 구동 전 선처리] ──
    deleted_paths = detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached)
    conn.commit()

    # 2. 스레드 풀 구동 및 스트리밍 처리 (as_completed)
    print(f"[Scanner] 멀티스레드 스캔 풀 생성 (스레드 개수: {threads_to_use})")
    
    processed_folders_count = 0
    with ThreadPoolExecutor(max_workers=threads_to_use) as executor:
        futures = {
            executor.submit(process_folder_task, root, files, force, db_meta_full, db_offsets_cached, is_remote, library_id): root
            for root, files in tasks
        }
        
        for fut in as_completed(futures):
            root_folder = futures[fut]
            try:
                res = fut.result()
                if res:
                    merged_meta = res['merged_meta']
                    if 'errors' in res and res['errors']:
                        library_errors.extend(res['errors'])
                    for item in res['results']:
                        full_path = item['full_path']
                        if item['skip']:
                            continue

                        filename = item['filename']
                        file_format = item['file_format']
                        series_name = item['series_name']
                        cover_image = item['cover_image']
                        offsets_data = item['offsets_data']
                        is_offset_only = item.get('offset_only', False)

                        db_action_taken = False
                        if full_path in db_books:
                            book_id = db_books[full_path]
                            if is_offset_only:
                                # 오프셋 전용 경로: 커버/메타는 건드리지 않고 오프셋만 저장
                                if offsets_data:
                                    save_book_offsets(cursor, book_id, filename, offsets_data)
                                    db_action_taken = True
                            else:
                                # 일반 경로: 커버·메타 업데이트 + 오프셋 저장
                                print(f"[Scanner-Process] 도서 검사 진행: {filename} (Force={force})")
                                update_book_metadata(cursor, full_path, cover_image, merged_meta)
                                db_action_taken = True
                                if offsets_data:
                                    save_book_offsets(cursor, book_id, filename, offsets_data)
                        else:
                            # 신규 도서 등록 (offset_only가 될 수 없는 케이스)
                            book_id = insert_new_book_v2(cursor, library_id, full_path, filename, file_format, series_name, cover_image, merged_meta)
                            print(f"[Scanner] 신규 도서 등록: {filename} (시리즈: {series_name})")
                            db_action_taken = True
                            if offsets_data:
                                save_book_offsets(cursor, book_id, filename, offsets_data)

                        if db_action_taken:
                            conn.commit()

                    # 메모리 방출 및 체크포인트 즉시 세이브
                    del res
                
                cursor.execute("INSERT OR IGNORE INTO scanner_progress (library_id, folder_path) VALUES (?, ?)", (str(library_id), root_folder))
                conn.commit()
                
                processed_folders_count += 1
                if processed_folders_count % 10 == 0:
                    gc.collect()

                # 수동 취소(중단) 요청 감지 및 탈출
                cursor.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
                status_row = cursor.fetchone()
                if status_row and status_row['scan_status'] == 'cancelling':
                    print(f"[Scanner-Cancel] 🛑 사용자 취소 요청에 의해 스캔을 안전하게 중단합니다. (완료 폴더: {processed_folders_count}개)")
                    cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE id = ?", (library_id,))
                    conn.commit()
                    conn.close()
                    return

                # 실시간 OOM 방지 자진 탈출 처리
                if check_memory_exceeded():
                    print(f"[Scanner-Memory] 🛑 메모리 한계치 도달로 스캔을 긴급 일시중단합니다. (진행도: {processed_folders_count}개 폴더 반영완료)")
                    conn.close()
                    sys.exit(0)

            except Exception as e:
                print(f"[Scanner-DEBUG-Pool] ❌ 폴더 '{root_folder}' 처리 중 예외 발생: {e}")

    # 3. 실시간 삭제 감시: 파일 시스템에서 사라진 도서 정보 삭제
    if not handle_deleted_books(cursor, db_books, deleted_paths, target_paths, found_file_paths):
        conn.close()
        return
        
    # 완주 성공 시 해당 라이브러리의 체크포인트 초기화
    cursor.execute("DELETE FROM scanner_progress WHERE library_id = ?", (str(library_id),))
    conn.commit()
    conn.close()
    gc.collect()

    # 스캔 결과 에러 리포트 저장
    if library_errors:
        try:
            from utils.report_helper import save_scan_report
            save_scan_report(library_id, library_errors)
        except Exception as report_err:
            print(f"[Scanner ERROR] 스캔 리포트 저장 실패: {report_err}")

    # 스캔 종료 후 데이터베이스 최적화 자동 튜닝 트리거
    import threading
    t = threading.Thread(target=database.optimize_database, args=(db_type,))
    t.daemon = True
    t.start()

@scanner_print_control_decorator
def scan_library_covers_only(db_path, library_id, physical_path):
    """지정된 라이브러리 경로 내 기존 도서들의 표지만 강제로 재추출/재생성하여 동기화 (오프셋/메타 스킵)"""
    print(f"[Scanner-Covers] 표지 전용 스캔 시작: Library ID={library_id}, Path='{physical_path}'")
    
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        print(f"[Scanner-Covers] 경고: 스캔 경로가 존재하지 않습니다: {physical_path}")
        return

    db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
    conn = database.get_connection(db_type)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_path, series_name
        FROM books WHERE library_id = ?
    """, (library_id,))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"[Scanner-Covers] 스캔 대상 도서가 없습니다.")
        conn.close()
        return

    is_remote = any(is_remote_path(p) for p in target_paths)

    # 폴더별로 묶어서 처리 (폴더 내 첫 성공 커버를 shared_cover_image로 공유)
    from collections import defaultdict
    from utils.sort_helper import natural_sort_key
    
    folder_groups = defaultdict(list)
    for row in rows:
        parent_dir = os.path.dirname(row['file_path'])
        folder_groups[parent_dir].append(row)
    
    # 각 폴더 내 파일을 제목순 정렬
    for parent_dir in folder_groups:
        folder_groups[parent_dir].sort(key=lambda r: natural_sort_key(r['file_path']))

    def process_folder_covers(parent_dir, folder_rows):
        """폴더 단위로 커버 추출. 첫 권 성공 시 나머지에 공유."""
        yaml_meta = parse_kavita_yaml(parent_dir)
        json_meta = parse_series_json(parent_dir)
        
        is_series = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
        is_json_only = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
        series_cover_url = json_meta.get('cover_image_url', '') if is_json_only else ''
        b64_keys_lower = {k.lower(): v for k, v in yaml_meta.get('cover_b64_map', {}).items()}
        
        shared_cover = None
        results = []
        
        for row in folder_rows:
            book_id = row['id']
            file_path = row['file_path']
            filename = os.path.basename(file_path)
            series_name = row['series_name']
            
            file_exists = os.path.exists(file_path)
            
            cover_image = None
            filename_lower = filename.lower()
            
            # 1) kavita.yaml Base64 커버 — 실제 파일 접근 불필요, 원격 파일도 처리 가능
            if filename_lower in b64_keys_lower:
                cover_image = extract_cover_from_b64(file_path, b64_keys_lower[filename_lower], force=True, library_id=library_id)
            
            # 2) 이미 공유된 커버 재사용 (시리즈 폴더일 때) — 파일 접근 불필요
            if not cover_image and (is_series or is_json_only) and shared_cover:
                print(f"[Scanner-Covers] 시리즈 대표 커버 복제: '{filename}'")
                cover_image = shared_cover
            
            # 3) series.json URL 다운로드 — 실제 파일 접근 불필요, 원격 파일도 처리 가능
            if not cover_image and is_json_only and series_cover_url:
                cover_image = download_cover_from_url(file_path, series_cover_url, force=True, library_id=library_id)
            
            # 4) Fallback: 압축 파일 내 첫 이미지 — 파일 접근 필요, 없으면 스킵 → Lazy 스캐너로 위임
            if not cover_image:
                if not file_exists:
                    print(f"[Scanner-Covers] 원격 파일 접근 불가 → Lazy 스캐너로 위임: '{filename}'")
                else:
                    cover_image = get_series_cover_fallback(
                        series_name, parent_dir, force=True, is_remote=is_remote,
                        filename=filename, file_path=file_path, library_id=library_id
                    )

            
            # 공유 커버 최초 성공 시 캐싱
            if (is_series or is_json_only) and cover_image and not shared_cover:
                shared_cover = cover_image
            
            if cover_image:
                results.append((book_id, cover_image))
        
        return results

    print(f"[Scanner-Covers] 폴더 단위 커버 추출 시작 (총 {len(folder_groups)}개 폴더, {len(rows)}권)")
    
    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_SCANNER_THREADS) as executor:
        futures = {
            executor.submit(process_folder_covers, parent_dir, folder_rows): parent_dir
            for parent_dir, folder_rows in folder_groups.items()
        }
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                all_results.extend(res)
                
    print(f"[Scanner-Covers] 추출 완료. DB 커버 및 업데이트 타임스탬프 일괄 반영 시작...")
    processed_count = 0
    for book_id, cover_image in all_results:
        if cover_image:
            cursor.execute("""
                UPDATE books SET 
                    cover_image = ?,
                    cover_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (cover_image, book_id))
            processed_count += 1
            
    conn.commit()
    conn.close()
    print(f"[Scanner-Covers] 표지 전용 스캔 최종 완료! (총 {processed_count}권 표지 업데이트 완료)")

def run_sync_scanner():
    """모든 데이터베이스(일반, 성인)의 라이브러리를 순회하며 스캔 실행"""
    print("=== 파일 시스템 동기화 스캐너 가동 ===")
    
    if os.path.exists(DB_GENERAL_PATH):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path FROM libraries")
        libs = cursor.fetchall()
        conn.close()
        for lib in libs:
            scan_library(DB_GENERAL_PATH, lib['id'], lib['physical_path'])
            
    if os.path.exists(DB_ADULT_PATH):
        conn = database.get_connection('adult')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path FROM libraries")
        libs = cursor.fetchall()
        conn.close()
        for lib in libs:
            scan_library(DB_ADULT_PATH, lib['id'], lib['physical_path'])
