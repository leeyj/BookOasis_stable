# -*- coding: utf-8 -*-
import os
import sys
import gc
import time
import argparse
from PIL import Image

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import builtins
import datetime
import database
from tools.scanner.cover import get_series_cover_fallback, COVER_THUMB_MAX_W, COVER_THUMB_MAX_H, save_as_thumbnail_webp

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


def _load_lazy_scan_no_cover_retry_days():
    """커버 추출에 이미 실패한(NO_COVER) 도서를 며칠 지나야 다시 재시도할지 설정에서 로드한다.
    기본값 7일 - 깨진 파일/추출 불가 PDF 등을 매 스캔(사실상 매일)마다 헛되이 재검사하던
    기존 동작 대신, 실패 마킹 후 일정 기간은 건너뛴다. 0으로 설정하면 기존처럼 매번 재시도한다."""
    days = 7
    try:
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value('LAZY_SCAN_NO_COVER_RETRY_DAYS')
        if val is not None:
            days = int(str(val).strip() or '7')
    except Exception as _re:
        print(f"[Lazy-Scanner] NO_COVER 재시도 대기일 설정 로드 실패 (기본 7일 적용): {_re}")
    return max(0, days)


def _fetch_lazy_scan_candidates(cursor, no_cover_retry_days=0):
    no_cover_clause = "cover_image = 'NO_COVER'"
    if no_cover_retry_days > 0:
        # 실패 마킹 시각(cover_updated_at)으로부터 N일이 지난 것만 재후보로 삼는다.
        # 마킹 이후 오프셋 전용 성공 등으로 cover_updated_at이 갱신되지 않는 케이스를 대비해
        # NULL(과거 데이터)은 항상 재시도 대상에 포함시킨다.
        # (interval은 신뢰 가능한 내부 정수라 f-string 삽입 - database.py의 MariaDB 변환기가
        #  'now', '-N days' 리터럴 패턴을 정규식으로 매칭해 DATE_SUB(NOW(), INTERVAL N DAY)로
        #  바꿔주므로 바인드 파라미터로 넘기면 그 변환이 동작하지 않는다)
        no_cover_clause = (
            "(cover_image = 'NO_COVER' AND "
            f"(cover_updated_at IS NULL OR cover_updated_at <= datetime('now', '-{no_cover_retry_days} days')))"
        )

    cursor.execute(f"""
        SELECT id, file_path, series_name, file_format, cover_image, library_id, total_pages, has_offsets,
               COALESCE(metadata_locked, 0) AS metadata_locked
        FROM books
        WHERE LOWER(file_path) NOT LIKE '%.txt'
          AND (
              (cover_image IS NULL OR cover_image = '')
              OR {no_cover_clause}
              OR (
                  LOWER(COALESCE(file_format, '')) IN ('zip', 'cbz')
                  AND COALESCE(has_offsets, 0) = 0
              )
          )
    """)
    return cursor.fetchall()


def _fetch_library_remote_map(cursor):
    """library_id -> is_remote(bool) 매핑을 한 번만 조회해서 캐싱합니다.

    파일 물리 점검 루프에서 매 도서마다 is_remote_path()(휴리스틱, /proc/mounts
    재파싱 + realpath 다중 호출)로 원격 여부를 추측하는 대신, 이미 라이브러리
    등록 시 확정된 libraries.is_remote 값을 그대로 신뢰합니다. 휴리스틱이
    원격 경로를 로컬로 오판하면 이후 os.path.exists()가 FUSE/rclone 마운트에서
    수십 초~무한정 커널 블로킹될 수 있어(과거 502 Bad Gateway 사고 사례 참고),
    대량 후보(수십만 건) 순회 시 이 오판 하나가 전체 lazy 스캔을 멈춰 세울 수 있습니다.
    """
    try:
        cursor.execute("SELECT id, COALESCE(is_remote, 0) AS is_remote FROM libraries")
        rows = cursor.fetchall()
        return {int(row['id']): bool(int(row['is_remote'] or 0)) for row in rows}
    except Exception as e:
        print(f"[Lazy-Scanner] 라이브러리 원격 여부 매핑 조회 실패: {e}")
        return {}


def _open_database_connection(db_type):
    if not database.is_mariadb_mode():
        db_path = database.get_db_path(db_type)
        if not os.path.exists(db_path):
            return None
    return database.get_connection(db_type, wait_timeout=60.0)


def setup_lazy_scanner_logging():
    write_log = True
    try:
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value('SCANNER_WRITE_LOG')
        if val is not None and str(val).strip() == '0':
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


def _load_lazy_scan_limits():
    """개별 파일 크기 제한(MB)과 세션 누적 처리 용량 한도(MB)를 설정에서 로드한다."""
    # ── 최대 스캔 허용 파일 크기(MB) 및 세션 누적 제한(MB) 설정 로드 ──
    max_size_mb = 300.0   # 개별 파일 안전 기본값 (300MB)
    max_batch_mb = 1024.0 # 세션 누적 안전 기본값 (1024MB = 1GB)
    try:
        from repositories.settings_repository import SettingsRepository
        size_val = SettingsRepository.get_value('LAZY_SCAN_MAX_FILE_SIZE_MB')
        batch_val = SettingsRepository.get_value('LAZY_SCAN_MAX_BATCH_SIZE_MB')
        if size_val is not None:
            max_size_mb = float(str(size_val).strip() or '300')
        if batch_val is not None:
            max_batch_mb = float(str(batch_val).strip() or '1024')
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
    return max_size_mb, max_batch_mb


def _load_lazy_scan_probe_workers():
    """영상 ffprobe 분석을 몇 개씩 동시에 돌릴지 설정에서 로드한다.
    ffprobe는 I/O 대기가 대부분이라 원격 마운트에서는 값을 올릴수록 체감 속도가 크게 빨라진다."""
    workers = 4
    try:
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value('LAZY_SCAN_VIDEO_PROBE_WORKERS')
        if val is not None:
            workers = int(str(val).strip() or '4')
    except Exception as _pe:
        print(f"[Lazy-Scanner] 영상 ffprobe 동시 처리 개수 설정 로드 실패 (기본 4개 적용): {_pe}")
    return max(1, workers)


def _build_scan_targets(db_type, books, library_remote_map):
    """DB에서 1차 선별된 후보 도서들을 실제 물리 파일 상태까지 점검해 최종 스캔
    대상 목록((book, offset_only) 튜플 리스트)으로 좁힌다. conn/세션 누적 상태와
    무관한 순수 필터링 단계라 별도 함수로 분리해도 안전하다."""
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

        metadata_locked = int(book['metadata_locked'] or 0) == 1
        if metadata_locked and cover_missing:
            if not offset_missing:
                print(f"[Lazy-Scanner] 메타데이터 잠금으로 커버 자동 갱신 스킵: {os.path.basename(file_path)}")
                continue
            cover_missing = False

        if not cover_missing and not offset_missing:
            # 커버도 있고 오프셋도 있음 → 완전히 처리된 도서, 스킵
            continue

        # ── offset_only 플래그: 커버는 정상이고 오프셋만 없는 경우 ──
        # 커버 재추출 없이 오프셋 수집만 수행하여 불필요한 I/O를 방지
        offset_only = (not cover_missing and offset_missing)
        
        library_id = book['library_id']
        if library_id in library_remote_map:
            # DB에 이미 확정돼 있는 라이브러리 원격 플래그를 신뢰 (휴리스틱 재판별 회피)
            _is_remote = library_remote_map[library_id]
        else:
            # library_id가 매핑에 없는 예외 케이스(고아 레코드 등)에 한해서만 휴리스틱 폴백
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
    return targets


def _group_targets_by_folder(targets):
    """같은 폴더의 kavita.yaml/series.json을 폴더당 1회만 파싱할 수 있도록,
    스캔 대상을 상위 폴더 기준으로 그룹핑하고 폴더 내부는 자연 정렬한다."""
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
    return folder_groups


def run_lazy_cover_extraction(target_book_id=None, target_db_type=None):
    global stop_requested

    if target_book_id is not None:
        print(f"[Lazy-Scanner] 🚀 단일 도서 즉시 스캔 기동 시작 (Book ID: {target_book_id})")
    else:
        print("[Lazy-Scanner] 🚀 독립 백그라운드 표지 스캐너 기동 시작")
    
    conn = None
    try:
        db_types = ['general', 'adult', 'audiobook']
        if target_db_type in ('general', 'adult', 'audiobook'):
            db_types = [target_db_type]


        # ── 최대 스캔 허용 파일 크기(MB) 및 세션 누적 제한(MB) 설정 로드 ──
        max_size_mb, max_batch_mb = _load_lazy_scan_limits()

        no_cover_retry_days = _load_lazy_scan_no_cover_retry_days()
        if no_cover_retry_days > 0:
            print(f"[Lazy-Scanner] 🔁 커버 추출 실패(NO_COVER) 도서 재시도 대기: {no_cover_retry_days}일")

        session_accumulated_bytes = 0.0
        batch_limit_reached = False

        for db_type in db_types:
            if stop_requested or batch_limit_reached:
                if stop_requested:
                    print("[Lazy-Scanner] ⚠️ 중단 요청(SIGTERM/SIGINT) 감지. DB 순회를 중단합니다.")
                else:
                    print("[Lazy-Scanner] 🛑 용량 한도 달성으로 DB 순회를 중단하고 차기 서브-배치로 이관합니다.")
                break

            conn = _open_database_connection(db_type)
            if conn is None:
                continue
                
            print(f"[Lazy-Scanner] 🔍 DB 연결 및 검사 시작: {db_type}")
            try:
                conn.execute("PRAGMA busy_timeout = 60000;")
                conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
            cursor = conn.cursor()
            
            if target_book_id is not None:
                cursor.execute("""
                    SELECT id, file_path, series_name, file_format, cover_image, library_id, total_pages, has_offsets,
                           COALESCE(metadata_locked, 0) AS metadata_locked
                    FROM books WHERE id = ?
                """, (target_book_id,))
            else:
                # ── DB SQL 필터링 최적화 ──
                # 1. txt 확장자 제외
                # 2. 커버 경로가 없거나 이전 추출에 실패한 경우
                # 3. ZIP/CBZ 포맷 중 페이지 수(total_pages)=0 이거나 오프셋(has_offsets)=0 인 경우
                # 위 스캔 후보 도서만 DB 인덱스 레벨에서 1차 선별하여 퍼포먼스 극대화
                books = _fetch_lazy_scan_candidates(cursor, no_cover_retry_days=no_cover_retry_days)
                
            if target_book_id is not None:
                books = cursor.fetchall()
            print(f"[Lazy-Scanner] 📋 DB({db_type}) 스캔 필요 후보 도서 레코드 조회 완료 (총 {len(books)}권). 파일 물리 점검 시작...")
            library_remote_map = _fetch_library_remote_map(cursor)

            targets = _build_scan_targets(db_type, books, library_remote_map)
            
            folder_groups = _group_targets_by_folder(targets)
            
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
                    # gdrive:// 가상 경로는 끝에 ?gid=<file_id>가 붙어있으므로, 로그/표시용
                    # filename에서는 제거한다 (실제 다운로드 시점의 file_path는 그대로 사용).
                    from utils.drive_helper import split_gdrive_file_id
                    filename = os.path.basename(split_gdrive_file_id(file_path)[0])
                    
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
                                    WHERE id = ? AND COALESCE(metadata_locked, 0) = 0
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
                                    WHERE id = ? AND COALESCE(metadata_locked, 0) = 0
                                """, (cover_image_path, book_id))
                            cover_updated = cursor.rowcount > 0
                            conn.commit()
                            if cover_updated:
                                print(f"[Lazy-Scanner] 표지 추출 및 DB 업데이트 완료: {cover_image_path}")
                            else:
                                print(f"[Lazy-Scanner] 메타데이터 잠금으로 추출 커버 DB 반영 스킵: {filename}")

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
                        elif file_path.lower().endswith('.pdf') and ("pdfium" in err_msg.lower() or "syntax error" in err_msg.lower() or "page tree" in err_msg.lower() or "cannot open" in err_msg.lower() or "data format error" in err_msg.lower()):
                            error_type = "PdfiumFormatError"
                            
                        # 실패 상태를 UI에 표시하되 다음 스케줄에서는 다시 추출을 시도합니다.
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
                        # 원격(rclone/GDrive) API 부하 조절용 sleep. 로컬 디스크는 그런
                        # 제약이 없는데도 예전엔 여기서 원격/로컬 구분 없이 무조건 3초를
                        # 대기해, 초기 스캔이 커버 추출을 미루는 PDF(tools/scanner/cover.py
                        # 참고)처럼 이 루프를 대량으로 거치는 포맷에서 로컬임에도 체감상
                        # 멈춘 것 같은 속도 저하를 유발했다. offset_only 분기(위쪽)와 동일한
                        # 기준으로 원격일 때만 3초, 로컬은 0.5초로 낮춘다.
                        _sleep_is_remote = library_remote_map.get(library_id, False)
                        time.sleep(3.0 if _sleep_is_remote else 0.5)
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

    # 커버 캐시 파일명은 DB에 저장된 원본(가상) 경로 기준으로 안정적으로 키잉해야 하므로,
    # 로컬 경로로 치환하기 전에 먼저 해시를 계산한다.
    book_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    cover_filename = f"book_{book_hash}.webp"
    local_cover_path = os.path.join(COVERS_DIR, str(library_id), cover_filename)
    db_cover_path = f"{library_id}/{cover_filename}"

    os.makedirs(os.path.dirname(local_cover_path), exist_ok=True)

    # gdrive:// 가상 경로(마운트 아닌 순수 등록 링크)는 공유자가 폴더를 정리해뒀다는 보장이
    # 없고, 서버가 그 사람 몫의 Drive 트래픽/쿼터를 직접적으로 통제할 수도 없다 — 그래서
    # 레이지 스캐너는 이 경로들을 위해 전체 파일을 내려받지 않는다(이전엔 여기서 무조건
    # resolve_gdrive_local_path()로 전체 다운로드했는데, 이게 뷰어에서 없앤 것과 똑같은
    # 동시-요청 API 차단 위험을 배경 스캔에서 다시 불러들이는 셈이었다). kavita.yaml
    # base64/series.json URL처럼 다운로드가 필요 없는 지름길(2~3단계)은 아래에서 계속
    # 시도하되, 그마저 안 되면(=사실상 항상, gdrive 가상 경로는 로컬 메타데이터 파싱
    # 대상이 아니라 b64_keys_lower/series_cover_url이 비어있기 때문) ComicInfo.xml
    # 파싱이나 zip/pdf 직접 열기 같은 "실제 바이트가 필요한" 단계 직전에 조용히 포기한다.
    # 커버/메타데이터가 꼭 필요하면 정석은 "Drive에서 복사해오기"로 내 드라이브에 옮긴
    # 뒤 그 로컬 사본을 다시 스캔하는 것이다.
    from utils.drive_helper import is_gdrive_url

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

    # 여기까지 왔다는 건 위 다운로드-불필요 지름길(공유 커버 재사용/b64/URL)이 전부 안 통했다는
    # 뜻이다 — gdrive 가상 경로는 이 아래부터 전부 실제 파일 바이트가 필요한데, 그러려면
    # 전체 다운로드가 강제되므로 여기서 포기한다 (사유는 함수 상단 주석 참조).
    if is_gdrive_url(file_path):
        print(f"[Lazy-Scanner] 공유 링크 원본은 전체 다운로드 없이 커버를 만들 수 없어 스킵: {filename}")
        return (None, None, [])

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
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_path)
            if len(pdf) > 0:
                page = pdf[0]
                # 표지에 필요한 크기(COVER_THUMB_MAX_W/H)를 훨씬 넘는 배율로 렌더링해봐야
                # (예: 300dpi+ 스캔 PDF를 원본 mediabox 그대로) 어차피 save_as_thumbnail_webp()가
                # 저장 직전에 다시 줄이므로 rasterize 시간만 낭비다. 그렇다고 딱 최종 크기로만
                # 그리면(1x) 축소 과정에서 나던 안티에일리어싱 효과가 없어져 글자가 흐릿해진다 —
                # 그래서 최종 크기의 PDF_COVER_SUPERSAMPLE배로 살짝 크게 그린 뒤
                # save_as_thumbnail_webp()의 LANCZOS 리샘플링이 그 여분 해상도로 텍스트 경계를
                # 부드럽게 다듬으며 축소하게 한다 - 전체 원본 해상도 렌더링보다는 훨씬 싸면서도
                # 1x 직접 렌더링보다 또렷한, 그 중간 지점.
                PDF_COVER_SUPERSAMPLE = 2
                page_w, page_h = page.get_size()
                scale = float(PDF_COVER_SUPERSAMPLE)
                if page_w > 0 and page_h > 0:
                    scale = min(
                        PDF_COVER_SUPERSAMPLE,
                        (COVER_THUMB_MAX_W * PDF_COVER_SUPERSAMPLE) / page_w,
                        (COVER_THUMB_MAX_H * PDF_COVER_SUPERSAMPLE) / page_h,
                    )
                bitmap = page.render(scale=scale)
                img = bitmap.to_pil()
                save_as_thumbnail_webp(img, local_cover_path)

                del img
                del bitmap
                page.close()
                pdf.close()
                del pdf
                # PDF는 오프셋 구조 없음 — 빈 리스트 반환
                return (db_cover_path, None, [])
        except Exception as e:
            print(f"[Lazy-Scanner] PDF pdfium 렌더링 실패: {e}")
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


def run_lazy_video_duration_backfill():
    """
    영상 강좌 스캔 시 duration=0(미분석)으로 남겨둔 에피소드를 백그라운드에서 ffprobe로 채웁니다.
    services/video_scanner.py::parse_video_folder()가 스캔 속도를 위해 duration/width/height를
    동기로 추출하지 않고 0으로 남겨두는데(Plex/Jellyfin처럼 발견과 분석을 분리), 그 뒷단을 이 함수가 담당합니다.
    """
    global stop_requested

    if not database.is_mariadb_mode():
        db_path = database.get_db_path('video')
        if not os.path.exists(db_path):
            return

    # 대량(수만 건) 서재에서는 배치가 작을수록 완료까지 필요한 서브프로세스 재기동 횟수가
    # 늘어나므로 기본값은 300건. 에피소드마다 진행 로그를 남기므로(아래 루프) 더 이상
    # "멈춘 것처럼" 보이지 않고, book 스캔의 LAZY_SCAN_MAX_FILE_SIZE_MB 등과 동일하게
    # 설정에서 재정의 가능하다 - 재시작이 잦은 환경에서는 값을 줄이는 걸 권장.
    MAX_EPISODES_PER_RUN = 300
    try:
        from repositories.settings_repository import SettingsRepository
        max_ep_val = SettingsRepository.get_value('LAZY_SCAN_VIDEO_MAX_EPISODES_PER_RUN')
        if max_ep_val is not None:
            MAX_EPISODES_PER_RUN = int(str(max_ep_val).strip() or '300')
    except Exception as _ve:
        print(f"[Lazy-Scanner] 영상 백필 배치 크기 설정 로드 실패 (기본 300건 적용): {_ve}")

    conn = _open_database_connection('video')
    if conn is None:
        return

    probe_workers = _load_lazy_scan_probe_workers()

    print("[Lazy-Scanner] 🎬 영상 에피소드 미분석(duration=0) 항목 백필 시작")
    try:
        from services.video_scanner import _probe_video_info, is_browser_compatible
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, video_id, file_path
            FROM video_episodes
            WHERE COALESCE(duration, 0) <= 0
            ORDER BY id ASC
            LIMIT ?
        """, (MAX_EPISODES_PER_RUN,))
        candidates = cursor.fetchall()

        if not candidates:
            print("[Lazy-Scanner] 🎬 미분석 영상 에피소드 없음. 스킵.")
            return

        valid_rows = [row for row in candidates if row['file_path'] and os.path.exists(row['file_path'])]
        skipped = len(candidates) - len(valid_rows)
        if skipped:
            print(f"[Lazy-Scanner] 🎬 파일 없음/경로 누락으로 {skipped}건 스킵")

        total = len(valid_rows)
        print(f"[Lazy-Scanner] 🎬 미분석 영상 에피소드 {total}건 발견. ffprobe 분석 시작 (동시 {probe_workers}개)...")

        updated_count = 0
        touched_video_ids = set()

        # ffprobe는 서브프로세스 종료를 기다리는 순수 I/O 대기라 GIL을 점유하지 않으므로,
        # 스레드풀로 여러 개를 동시에 돌려도 안전하다(원격 rclone 마운트에서 특히 체감 속도가
        # 크게 향상됨). 다만 sqlite3 커서/커넥션은 스레드 안전하지 않으므로 DB 쓰기(UPDATE/commit)는
        # 반드시 이 메인 스레드에서만, future 결과를 받은 뒤 순차로 수행한다.
        done = 0
        with ThreadPoolExecutor(max_workers=probe_workers) as executor:
            future_to_row = {}
            for row in valid_rows:
                if stop_requested:
                    break
                future_to_row[executor.submit(_probe_video_info, row['file_path'])] = row

            for future in as_completed(future_to_row):
                row = future_to_row[future]
                episode_id = row['id']
                video_id = row['video_id']
                file_path = row['file_path']
                done += 1

                if stop_requested:
                    continue

                try:
                    duration, width, height, vcodec, acodec, format_name = future.result()
                except Exception as probe_err:
                    print(f"[Lazy-Scanner] ({done}/{total}) ffprobe 분석 예외 무시 -> {os.path.basename(file_path)}: {probe_err}")
                    continue

                if duration <= 0:
                    # 여전히 실패(파일 손상/네트워크 일시 오류 등) - 다음 lazy 실행에서 재시도
                    print(f"[Lazy-Scanner] ({done}/{total}) ffprobe 분석 실패(재시도 예정) -> {os.path.basename(file_path)}")
                    continue

                print(f"[Lazy-Scanner] ({done}/{total}) ffprobe 분석 완료 -> {os.path.basename(file_path)}")

                needs_transcode = 0 if is_browser_compatible(file_path, vcodec, acodec, format_name) else 1

                cursor.execute(
                    "UPDATE video_episodes SET duration = ?, width = ?, height = ?, needs_transcode = ? WHERE id = ?",
                    (duration, width, height, needs_transcode, episode_id)
                )
                conn.commit()
                updated_count += 1
                touched_video_ids.add(video_id)

            if stop_requested:
                print("[Lazy-Scanner] ⚠️ 중단 요청(SIGTERM/SIGINT) 감지. 진행 중이던 ffprobe 작업 완료 후 영상 백필을 마감합니다.")

        for video_id in touched_video_ids:
            cursor.execute("SELECT COALESCE(SUM(duration), 0) AS total FROM video_episodes WHERE video_id = ?", (video_id,))
            total_row = cursor.fetchone()
            total = total_row['total'] if total_row else 0
            cursor.execute("UPDATE videos SET total_duration = ? WHERE id = ?", (total, video_id))
        conn.commit()

        print(f"[Lazy-Scanner] 🎬 영상 에피소드 백필 완료: {updated_count}건 업데이트, 강좌 {len(touched_video_ids)}건 total_duration 재계산")
    except Exception as e:
        print(f"[Lazy-Scanner] 영상 백필 중 오류: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_lazy_video_container_revalidation():
    """
    이미 duration이 채워져 '분석 완료 + 브라우저 호환(needs_transcode=0)'으로 확정된 mp4/webm
    에피소드 중, 실제 컨테이너 포맷이 확장자와 다른 파일(예: 인프런 등 강좌 플랫폼 다운로드
    도구가 MPEG-TS 스트림을 확장자만 .mp4로 잘못 저장한 경우)을 재검증한다.

    2026-08-17 실사용자 리포트로 발견: is_browser_compatible()이 확장자+코덱만 보고
    "호환"으로 판정했던 기존 로직 때문에, 실제로는 mpegts인 파일이 Chrome/Edge에서는
    관대하게 재생되지만 Safari/iOS에서는 MediaError code 4(포맷 미지원)로 거부당했다.
    이 함수는 그렇게 확정 완료된 상태로 남아있던 기존 데이터를 재검사해 바로잡는다
    (앞으로의 신규 스캔/JIT 체크는 is_browser_compatible()에 format_name 파라미터가
    추가되어 이미 올바르게 걸러진다 - 이 함수는 그 수정 이전에 이미 확정된 데이터 전용).

    container_verified 컬럼으로 이미 검사한 행을 표시해 매 실행마다 동일한 대량 데이터를
    반복 재검사하지 않도록 한다(1회성 백필, duration 백필과 동일한 배치/설정 재사용).
    """
    global stop_requested

    if not database.is_mariadb_mode():
        db_path = database.get_db_path('video')
        if not os.path.exists(db_path):
            return

    MAX_EPISODES_PER_RUN = 300
    try:
        from repositories.settings_repository import SettingsRepository
        max_ep_val = SettingsRepository.get_value('LAZY_SCAN_VIDEO_MAX_EPISODES_PER_RUN')
        if max_ep_val is not None:
            MAX_EPISODES_PER_RUN = int(str(max_ep_val).strip() or '300')
    except Exception as _ve:
        print(f"[Lazy-Scanner] 영상 컨테이너 재검증 배치 크기 설정 로드 실패 (기본 300건 적용): {_ve}")

    conn = _open_database_connection('video')
    if conn is None:
        return

    probe_workers = _load_lazy_scan_probe_workers()

    print("[Lazy-Scanner] 🎬 영상 에피소드 컨테이너 포맷 재검증(mislabeled mp4/webm) 시작")
    try:
        from services.video_scanner import _probe_video_info, is_browser_compatible
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, video_id, file_path
            FROM video_episodes
            WHERE format IN ('mp4', 'webm')
              AND COALESCE(needs_transcode, 0) = 0
              AND COALESCE(container_verified, 0) = 0
            ORDER BY id ASC
            LIMIT ?
        """, (MAX_EPISODES_PER_RUN,))
        candidates = cursor.fetchall()

        if not candidates:
            print("[Lazy-Scanner] 🎬 재검증 대상 영상 에피소드 없음. 스킵.")
            return

        flipped_count = 0
        verified_count = 0
        touched_video_ids = set()

        # 파일이 이미 없어진 항목은 ffprobe를 돌릴 필요가 없으니 먼저 걸러내 즉시 검증완료 처리
        valid_rows = []
        for row in candidates:
            if row['file_path'] and os.path.exists(row['file_path']):
                valid_rows.append(row)
            else:
                cursor.execute("UPDATE video_episodes SET container_verified = 1 WHERE id = ?", (row['id'],))
                conn.commit()
                verified_count += 1

        total = len(valid_rows)
        print(f"[Lazy-Scanner] 🎬 재검증 대상 영상 에피소드 {total}건 발견. ffprobe 컨테이너 검사 시작 (동시 {probe_workers}개)...")

        # duration 백필과 동일한 이유(ffprobe는 순수 I/O 대기)로 스레드풀 병렬화, DB 쓰기는 메인 스레드 전용
        done = 0
        with ThreadPoolExecutor(max_workers=probe_workers) as executor:
            future_to_row = {}
            for row in valid_rows:
                if stop_requested:
                    break
                future_to_row[executor.submit(_probe_video_info, row['file_path'])] = row

            for future in as_completed(future_to_row):
                row = future_to_row[future]
                episode_id = row['id']
                video_id = row['video_id']
                file_path = row['file_path']
                done += 1

                if stop_requested:
                    continue

                try:
                    duration, width, height, vcodec, acodec, format_name = future.result()
                except Exception as probe_err:
                    print(f"[Lazy-Scanner] ({done}/{total}) 컨테이너 재검증 ffprobe 예외 무시 -> {os.path.basename(file_path)}: {probe_err}")
                    continue

                if duration <= 0:
                    # ffprobe 실패(원격 마운트 일시 오류 등) - 다음 lazy 실행에서 재시도, 검증 완료로 표시하지 않음
                    continue

                print(f"[Lazy-Scanner] ({done}/{total}) 컨테이너 재검증 완료 -> {os.path.basename(file_path)}")

                still_compatible = is_browser_compatible(file_path, vcodec, acodec, format_name)
                if not still_compatible:
                    cursor.execute(
                        "UPDATE video_episodes SET needs_transcode = 1, container_verified = 1 WHERE id = ?",
                        (episode_id,)
                    )
                    flipped_count += 1
                    touched_video_ids.add(video_id)
                    print(f"[Lazy-Scanner] ⚠️ 컨테이너 불일치 발견(실제 포맷: {format_name}) -> 트랜스코딩 대상으로 전환: {os.path.basename(file_path)}")
                else:
                    cursor.execute("UPDATE video_episodes SET container_verified = 1 WHERE id = ?", (episode_id,))
                verified_count += 1
                conn.commit()

            if stop_requested:
                print("[Lazy-Scanner] ⚠️ 중단 요청(SIGTERM/SIGINT) 감지. 진행 중이던 ffprobe 작업 완료 후 영상 컨테이너 재검증을 마감합니다.")

        print(f"[Lazy-Scanner] 🎬 영상 컨테이너 재검증 완료: {verified_count}건 검사, {flipped_count}건 트랜스코딩 대상으로 전환 (강좌 {len(touched_video_ids)}건 영향)")
    except Exception as e:
        print(f"[Lazy-Scanner] 영상 컨테이너 재검증 중 오류: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


COVER_RESIZE_PROGRESS_FILE = os.path.join(MEDIA_SERVER_DIR, 'cache', 'cover_resize_progress.txt')
COVER_RESIZE_DONE_SENTINEL = '__DONE__'


def _load_lazy_scan_cover_resize_batch_size():
    """세션당 리사이즈 여부를 확인할 커버 파일 수. 원격 마운트 I/O 없이 로컬 covers/
    디렉토리만 다루는 순수 CPU 작업이라 개수 기준으로 간단히 배치를 끊는다."""
    batch_size = 2000
    try:
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value('LAZY_SCAN_COVER_RESIZE_BATCH_SIZE')
        if val is not None:
            batch_size = int(str(val).strip() or '2000')
    except Exception as _re:
        print(f"[Lazy-Scanner] 커버 리사이즈 배치 크기 설정 로드 실패 (기본 2000장 적용): {_re}")
    return max(1, batch_size)


def run_lazy_cover_resize():
    """이미 저장돼 있는 커버 이미지 중, 화면 표시 크기보다 훨씬 큰 원본 해상도 그대로
    저장됐던(리사이즈 로직 도입 이전) 파일을 찾아 축소·재저장하는 1회성 백필.

    신규로 생성되는 커버는 tools/scanner/cover.py의 save_as_thumbnail_webp()가 저장
    시점에 이미 축소하므로, 여기서는 과거에 저장된 기존 파일만 따라잡으면 된다.
    원격 마운트(rclone/GDrive)의 원본 도서 파일이 아니라 로컬 covers/ 캐시 파일만
    다루므로 원격 I/O 지연이 없다 - 그래서 다른 lazy 백필처럼 MB 단위가 아니라
    "이번 세션에 몇 장을 확인할지" 개수 기준으로 배치를 끊는다.

    재개 지점은 파일 경로 정렬 순서 기준 체크포인트(cache/cover_resize_progress.txt)에
    저장해서, 세션이 끊겨도(RAM 환수 재기동 등) 처음부터 33만 장을 다시 훑지 않는다.
    전체를 한 번 다 훑고 나면 완료 마킹을 남겨 이후 세션은 즉시 스킵한다.

    Returns:
        bool: 이번 세션에서 다 못 끝내 다음 세션에 이어서 할 작업이 남아있으면 True.
        (__main__에서 이 값을 보고 run_lazy_cover_extraction()이 exit(0)을 하려던 경우도
        exit(10)로 덮어써서, "더 할 일이 없어졌다"고 스캐너 큐가 오판해 재기동을 멈추지
        않도록 한다 - 그래야 리사이즈 백필도 이 lazy 스캔 루프에 얹혀 끝까지 진행된다.)
    """
    global stop_requested
    from tools.scanner.cover import COVERS_DIR, COVER_THUMB_MAX_W, COVER_THUMB_MAX_H, save_as_thumbnail_webp

    if not os.path.isdir(COVERS_DIR):
        return False

    os.makedirs(os.path.dirname(COVER_RESIZE_PROGRESS_FILE), exist_ok=True)

    last_processed = ''
    if os.path.exists(COVER_RESIZE_PROGRESS_FILE):
        try:
            with open(COVER_RESIZE_PROGRESS_FILE, 'r', encoding='utf-8') as f:
                last_processed = f.read().strip()
        except Exception:
            last_processed = ''

    if last_processed == COVER_RESIZE_DONE_SENTINEL:
        return False

    all_paths = []
    for root, _dirs, files in os.walk(COVERS_DIR):
        for fname in files:
            if fname.lower().endswith(('.webp', '.jpg', '.jpeg', '.png')):
                all_paths.append(os.path.join(root, fname))
    all_paths.sort()

    if not all_paths:
        with open(COVER_RESIZE_PROGRESS_FILE, 'w', encoding='utf-8') as f:
            f.write(COVER_RESIZE_DONE_SENTINEL)
        return False

    start_index = 0
    if last_processed:
        try:
            start_index = next(i for i, p in enumerate(all_paths) if p > last_processed)
        except StopIteration:
            start_index = len(all_paths)

    batch_size = _load_lazy_scan_cover_resize_batch_size()
    print(f"[Lazy-Scanner] 🖼️ 기존 커버 리사이즈 백필 진행 ({start_index:,}/{len(all_paths):,} 완료, 이번 세션 최대 {batch_size:,}장 확인)")

    resized_count = 0
    checked_count = 0
    last_seen = last_processed

    for path in all_paths[start_index:]:
        if stop_requested:
            print("[Lazy-Scanner] ⚠️ 중단 요청 감지. 커버 리사이즈 백필을 안전 중단합니다.")
            break
        checked_count += 1
        last_seen = path
        try:
            needs_resize = False
            with Image.open(path) as img:
                needs_resize = img.width > COVER_THUMB_MAX_W or img.height > COVER_THUMB_MAX_H
                if needs_resize:
                    tmp_path = path + '.resize_tmp'
                    save_as_thumbnail_webp(img, tmp_path)
            if needs_resize:
                os.replace(tmp_path, path)
                resized_count += 1
        except Exception as e:
            print(f"[Lazy-Scanner] 커버 리사이즈 확인/변환 실패(건너뜀): {path}: {e}")
        if checked_count >= batch_size:
            break

    if not stop_requested and (start_index + checked_count) >= len(all_paths):
        with open(COVER_RESIZE_PROGRESS_FILE, 'w', encoding='utf-8') as f:
            f.write(COVER_RESIZE_DONE_SENTINEL)
        print(f"[Lazy-Scanner] 🎉 커버 리사이즈 백필 전체 완료 (이번 세션 {resized_count}/{checked_count}건 축소)")
        return False

    with open(COVER_RESIZE_PROGRESS_FILE, 'w', encoding='utf-8') as f:
        f.write(last_seen)
    print(f"[Lazy-Scanner] 🖼️ 커버 리사이즈 백필 이번 세션 종료: {resized_count}/{checked_count}건 축소, 다음 세션에 이어서 진행")
    return True


if __name__ == '__main__':
    # 로그 설정은 영상 백필/표지 스캔 중 어느 쪽이 먼저 실행되든 둘 다 lazy_scanner.log에
    # 남도록 가장 먼저(다른 어떤 print()보다도 앞서) 활성화한다. 예전에는
    # run_lazy_cover_extraction() 내부에서만 호출했는데, 영상 백필을 먼저 실행하도록
    # 순서를 바꾼 뒤로는 백필 단계의 모든 출력이 로그 활성화 전에 발생해 통째로
    # 유실되고 있었다(부모 프로세스의 stdout 재중계도 로그 중복 문제로 이미 제거됨).
    setup_lazy_scanner_logging()

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

    cover_resize_has_more_work = False
    try:
        # run_lazy_cover_extraction()은 끝에서 항상 sys.exit(0/10)을 호출해 SystemExit을 던지므로,
        # 그 뒤에 이어 붙이면 아래 코드는 영원히 실행되지 않는다. 영상 백필은 반드시 먼저 실행한다.
        if args.book_id is None:
            run_lazy_video_duration_backfill()
            run_lazy_video_container_revalidation()
            cover_resize_has_more_work = run_lazy_cover_resize()
        run_lazy_cover_extraction(target_book_id=args.book_id, target_db_type=args.db_type)
    except SystemExit as se:
        # 표지 추출은 이미 다 끝나서(exit 0) 스캐너 큐가 이 lazy 스캔 태스크를 끝내려 하더라도,
        # 커버 리사이즈 백필이 아직 안 끝났으면 exit(10)로 덮어써서 재기동을 계속 요청한다.
        if se.code == 0 and cover_resize_has_more_work:
            sys.exit(10)
        sys.exit(se.code)
    except Exception as main_err:
        import traceback
        tb = traceback.format_exc()
        print(f"[Lazy-Scanner FATAL ERROR] 치명적 예외 발생으로 프로세스가 중단되었습니다:\n{tb}")
        sys.exit(1)

