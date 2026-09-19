# -*- coding: utf-8 -*-
import os
import subprocess
import sys
from repositories.book_scan_repository import BookScanRepository
from utils.redis_helper import redis_delete_pattern
from tools.scanner import (
    merge_local_metadata,
    extract_cover_from_b64,
    get_series_cover_fallback,
    collect_zip_offsets_data
)

# 문서(PDF) 표지 일괄 추출 제한 시간: PDF 파서가 멈추면 큐 워커가 영구히 붙잡히므로 상한을 둔다.
_DOCUMENT_SCAN_BASE_TIMEOUT_SECONDS = 300
_DOCUMENT_SCAN_PER_BOOK_TIMEOUT_SECONDS = 180
_DOCUMENT_SCAN_MAX_TIMEOUT_SECONDS = 3600


def _document_scan_timeout(book_count):
    return min(
        _DOCUMENT_SCAN_MAX_TIMEOUT_SECONDS,
        _DOCUMENT_SCAN_BASE_TIMEOUT_SECONDS + _DOCUMENT_SCAN_PER_BOOK_TIMEOUT_SECONDS * max(1, int(book_count)),
    )


def _cover_snapshot(covers_dir, cover_image):
    """(표지 상대경로, 수정 시각) - 표지 파일이 없거나 비어 있으면 (경로, None)."""
    if not cover_image or cover_image == 'NO_COVER':
        return (cover_image, None)
    cover_path = os.path.join(covers_dir, cover_image)
    try:
        if os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0:
            return (cover_image, os.path.getmtime(cover_path))
    except OSError:
        pass
    return (cover_image, None)


class BookScanService:
    @staticmethod
    def scan_document_books(db_type, book_ids, task_id=None):
        """선택한 PDF 표지를 격리된 프로세스 한 번으로 추출하고 끝날 때까지 기다린다.

        PDF 파서는 OOM/세그폴트 위험 때문에 API/큐 워커 안에서 직접 돌리지 않는다. 예전에는 권마다
        detached 프로세스를 띄우고 곧바로 성공을 보고해서, 시리즈 스캔 시 PDF 수만큼 프로세스가 동시에
        뜨고 결과는 확인되지 않았다. 여기서는 lazy_scanner 한 개가 모든 권을 순차 처리하고, 종료 후
        권마다 표지가 실제로 새로 추출됐는지(파일이 새로 생겼거나 갱신됨) 확인해서 결과를 돌려준다.
        반환: (전부 성공 여부, 메시지, {book_id: 표지 경로 또는 None})
        """
        ids = []
        for raw_id in book_ids or ():
            try:
                book_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if book_id > 0 and book_id not in ids:
                ids.append(book_id)
        if not ids:
            return False, 'PDF 표지 스캔에 유효한 도서 ID가 없습니다.', {}
        if db_type not in ('general', 'adult', 'audiobook'):
            return False, f'지원하지 않는 도서 데이터베이스입니다: {db_type}', {}

        from services.cover_storage_service import get_covers_dir
        covers_dir = get_covers_dir()

        before = {}
        for book_id in ids:
            try:
                book = BookScanRepository.get_book_basic_info_raw(db_type, book_id)
                before[book_id] = _cover_snapshot(covers_dir, book.get('cover_image') if book else None)
            except Exception as lookup_error:
                print(f"[BookScanService WARNING] 문서 표지 사전 조회 실패 (book_id={book_id}): {lookup_error}")
                before[book_id] = (None, None)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(base_dir, 'tools', 'lazy_scanner.py')
        command = [
            sys.executable, script_path,
            '--book-ids', *[str(book_id) for book_id in ids],
            '--db-type', str(db_type),
            '--force-document-covers',
        ]
        if task_id is not None:
            command.extend(['--task-id', str(int(task_id))])

        print(f"[BookScanService] 문서 표지 격리 스캔 시작: IDs={ids}, DB={db_type}")
        returncode = None
        timed_out = False
        try:
            result = subprocess.run(
                command,
                cwd=base_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=_document_scan_timeout(len(ids)),
            )
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            print(f"[BookScanService ERROR] 문서 표지 격리 스캔이 제한 시간을 넘겨 종료했습니다: IDs={ids}")
        except Exception as error:
            message = f'PDF 격리 스캐너 실행 실패: {error}'
            print(f"[BookScanService ERROR] {message}")
            return False, message, {book_id: None for book_id in ids}

        outcomes = {}
        for book_id in ids:
            try:
                book = BookScanRepository.get_book_basic_info_raw(db_type, book_id)
                after = _cover_snapshot(covers_dir, book.get('cover_image') if book else None)
                before_cover, before_mtime = before.get(book_id, (None, None))
                extracted = after[1] is not None and (
                    before_mtime is None or after[0] != before_cover or after[1] > before_mtime
                )
                if extracted:
                    outcomes[book_id] = after[0]
                    # 격리 스캐너가 books를 갱신하지만, 시리즈 대표 표지는 동기 스캔 경로처럼 함께 맞춘다.
                    try:
                        BookScanRepository.update_book_scanned_metadata(
                            db_type, book_id, book.get('series_name') or '', after[0],
                            {'author': '', 'publisher': '', 'link': '', 'score': 0,
                             'summary': '', 'release_date': ''},
                        )
                    except Exception as sync_error:
                        print(f"[BookScanService WARNING] 시리즈 표지 동기화 실패 (book_id={book_id}): {sync_error}")
                else:
                    outcomes[book_id] = None
            except Exception as check_error:
                print(f"[BookScanService WARNING] 문서 표지 결과 확인 실패 (book_id={book_id}): {check_error}")
                outcomes[book_id] = None

        try:
            redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
            redis_delete_pattern(f"cache:history*:{db_type}:*")
        except Exception as cache_error:
            print(f"[BookScanService WARNING] 레디스 캐시 소거 실패: {cache_error}")

        successful_count = sum(1 for cover in outcomes.values() if cover)
        message = f'PDF 표지 스캔 완료 · 표지 추출 {successful_count}/{len(ids)}권'
        if timed_out:
            message += ' (제한 시간 초과로 중단됨)'
        elif returncode not in (0, None):
            message += f' (격리 스캐너 종료 코드 {returncode})'
        return successful_count == len(ids), message, outcomes

    @staticmethod
    def scan_single_book(db_type, book_id):
        """지정된 단일 도서(book_id)의 메타데이터와 표지 이미지를 즉시 재스캔하여 동기화합니다."""
        print(f"[BookScanService] 단일 도서 스캔 요청 시작: DB={db_type}, ID={book_id}")
        # 방금 폴더에 넣은 cover.jpg 등을 이번 즉시 스캔이 바로 보도록 폴더 표지 조회 캐시를 비운다.
        from tools.scanner.folder_image import clear_folder_listing_cache
        clear_folder_listing_cache()
        try:
            # 1. 도서 기본 정보 조회
            book = BookScanRepository.get_book_basic_info_raw(db_type, book_id)
            if not book:
                print(f"[BookScanService ERROR] DB에서 book_id={book_id}를 찾을 수 없습니다.")
                return False, "존재하지 않는 도서입니다.", None
                
            file_path = book['file_path']
            library_id = book['library_id']
            series_name = book['series_name']
            file_format = book['file_format']
            print(f"[BookScanService] 대상 도서 매칭 성공: Title='{book['title']}', Path='{file_path}'")
            
            # gdrive:// 가상 경로(마운트가 아닌 순수 등록 링크)는 os.path.exists로 확인할 수 없으므로,
            # 실제 바이트를 로컬 디스크 캐시로 받아온 뒤 그 로컬 경로를 이후 처리에 그대로 사용한다.
            # parent_dir(시리즈명 유도용)은 원본 가상 경로를 그대로 쓴다 — merge_local_metadata는
            # 존재하지 않는 폴더에도 안전하게(빈 메타데이터로) 동작한다.
            original_file_path = file_path  # 시리즈명 등 "폴더 구조" 유도용 — gdrive면 아래에서 file_path만 로컬 캐시로 치환됨
            is_imgdir = (file_format == 'imgdir') or file_path.lower().endswith('.imgdir')

            from utils.drive_helper import is_gdrive_url
            if is_gdrive_url(file_path):
                from utils.drive_helper import resolve_gdrive_local_path
                resolved = resolve_gdrive_local_path(file_path)
                if resolved == file_path:
                    print(f"[BookScanService ERROR] gdrive 원격 파일 다운로드 실패: {file_path}")
                    return False, "원격(Google Drive) 파일을 받아오지 못했습니다.", None
                file_path = resolved
            else:
                # 가상 책(imgdir)인 경우 __folder__.imgdir 파일은 존재하지 않으므로 부모 폴더가 존재하는지 검증합니다.
                check_path = os.path.dirname(file_path) if is_imgdir else file_path

                if not os.path.exists(check_path):
                    print(f"[BookScanService ERROR] 물리 파일/디렉토리가 경로에 존재하지 않음: {check_path}")
                    return False, f"서버에 물리 파일/디렉토리가 존재하지 않습니다: {check_path}", None

            # PDF는 파서가 세그폴트/OOM을 일으킬 수 있어 API/큐 워커 안에서 직접 열지 않고, 격리된
            # lazy_scanner 프로세스가 끝날 때까지 기다린 실제 결과를 반환한다.
            filename = os.path.basename(file_path)
            if (file_format or '').lower() == 'pdf' or file_path.lower().endswith('.pdf'):
                scan_ok, scan_message, scan_outcomes = BookScanService.scan_document_books(db_type, [book_id])
                return scan_ok, f"'{filename}' {scan_message}", scan_outcomes.get(int(book_id))

            # 부모 폴더 경로
            parent_dir = os.path.dirname(file_path)
            print(f"[BookScanService] 부모 폴더 디렉토리 수색: '{parent_dir}'")
            
            # 2. 로컬 메타데이터 파일 탐색
            merged_meta = merge_local_metadata(parent_dir)
            # cover_b64_map은 파일별 Base64 커버 원본을 통째로 담고 있어 그대로 출력하면
            # 로그 파일 용량을 불필요하게 낭비하므로, 개수만 요약해서 남긴다.
            meta_summary = {k: (f"<{len(v)} items>" if k == 'cover_b64_map' else v) for k, v in merged_meta.items()}
            print(f"[BookScanService] 파싱된 로컬 메타데이터: {meta_summary}")
            
            # 3. 커버 이미지 결정 (Force 재추출 강제 지정)
            cover_image = None
            filename = os.path.basename(file_path)
            if filename in merged_meta['cover_b64_map']:
                print(f"[BookScanService] YAML cover_b64_map 매칭 발견, Base64 추출 진행")
                cover_image = extract_cover_from_b64(filename, merged_meta['cover_b64_map'][filename], force=True, library_id=library_id)
            if not cover_image:
                print(f"[BookScanService] get_series_cover_fallback 실행 시도 (Force=True)")
                cover_image = get_series_cover_fallback(series_name, parent_dir, force=True, filename=filename, library_id=library_id)
                
            print(f"[BookScanService] 최종 매핑된 커버 이미지명: {cover_image}")
            
            # 4. 오프셋 재수집 (ZIP/CBZ인 경우)
            offsets_data = []
            if file_format in ('zip', 'cbz'):
                print(f"[BookScanService] ZIP/CBZ 포맷 오프셋 재생성 진행...")
                offsets_data = collect_zip_offsets_data(file_path)
                
            # 5. DB 업데이트 실행
            print(f"[BookScanService] DB 업데이트 트랜잭션 쿼리 빌드")
            
            # 시리즈명은 (gdrive 로컬 캐시 경로가 아니라) 원본 가상/실제 경로의 폴더 구조에서 유도한다.
            series_parent_dir = os.path.dirname(original_file_path)
            if is_imgdir:
                series_folder = os.path.basename(os.path.dirname(series_parent_dir.rstrip('/\\')))
            else:
                series_folder = os.path.basename(series_parent_dir.rstrip('/\\'))
            real_series_name = series_folder or ""

            if real_series_name:
                import re
                real_series_name = re.sub(r'^\[(?:단행|연재|소설|만화|웹툰|일반)\]\s*', '', real_series_name).strip()

            BookScanRepository.update_book_scanned_metadata(
                db_type,
                book_id,
                real_series_name,
                cover_image,
                merged_meta
            )

            # 사용자가 직접 요청한 즉시 스캔에서만 파일 내장 메타데이터(CBZ의 ComicInfo.xml, EPUB의 OPF)로
            # DB의 "빈 칸"을 채운다. 폴더 사이드카(위)와 이미 있는 값이 우선이라 덮어쓰지 않으며, 일반/예약
            # 스캔은 이 경로를 쓰지 않는다(이미 스캔된 파일을 원격 마운트에서 대량으로 다시 열지 않기 위해).
            embedded_filled = []
            try:
                from tools.scanner.embedded_metadata import read_embedded_metadata
                embedded_metadata = read_embedded_metadata(file_path, file_format)
                if embedded_metadata:
                    embedded_filled = BookScanRepository.fill_empty_book_metadata(
                        db_type, book_id, embedded_metadata
                    )
                    if embedded_filled:
                        print(f"[BookScanService] 파일 내장 메타데이터로 빈 칸 채움: {', '.join(embedded_filled)}")
            except Exception as embedded_error:
                print(f"[BookScanService WARNING] 파일 내장 메타데이터 반영 실패(무시): {embedded_error}")
            
            if offsets_data:
                count = BookScanRepository.sync_book_offsets_transaction(db_type, book_id, offsets_data)
                print(f"[BookScanService] 오프셋 DB 데이터 {count}건 동기화 처리")

            # 대시보드 "신규 추가 도서"/최근기록 레디스 캐시가 갱신 전(빈 커버) 상태로
            # 굳어버리지 않도록, DB 반영 직후 관련 캐시를 함께 소거한다.
            try:
                redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
                redis_delete_pattern(f"cache:history*:{db_type}:*")
            except Exception as cache_err:
                print(f"[BookScanService WARNING] 레디스 캐시 소거 실패: {cache_err}")

            print(f"[BookScanService SUCCESS] '{filename}' 단독 재스캔 처리 최종 완료.")
            filled_note = f" (파일 내장 메타 {len(embedded_filled)}개 채움)" if embedded_filled else ""
            return True, f"'{filename}' 도서 스캔 및 메타데이터 동기화 완료!{filled_note}", cover_image
            
        except Exception as e:
            print(f"[BookScanService ERROR] 처리 중 예외 발생: {str(e)}")
            return False, f"도서 스캔 실패: {str(e)}", None
