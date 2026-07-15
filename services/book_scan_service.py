# -*- coding: utf-8 -*-
import os
import sqlite3
import database
from tools.scanner import (
    merge_local_metadata,
    extract_cover_from_b64,
    get_series_cover_fallback,
    collect_zip_offsets_data
)

class BookScanService:
    @staticmethod
    def scan_single_book(db_type, book_id):
        """지정된 단일 도서(book_id)의 메타데이터와 표지 이미지를 즉시 재스캔하여 동기화합니다."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        print(f"[BookScanService] 단일 도서 스캔 요청 시작: DB={db_type}, ID={book_id}")
        try:
            # 1. 도서 기본 정보 조회
            cursor.execute("""
                SELECT id, library_id, title, series_name, file_path, file_format, cover_image
                FROM books WHERE id = ?
            """, (book_id,))
            book = cursor.fetchone()
            
            if not book:
                print(f"[BookScanService ERROR] DB에서 book_id={book_id}를 찾을 수 없습니다.")
                conn.close()
                return False, "존재하지 않는 도서입니다.", None
                
            file_path = book['file_path']
            library_id = book['library_id']
            series_name = book['series_name']
            file_format = book['file_format']
            print(f"[BookScanService] 대상 도서 매칭 성공: Title='{book['title']}', Path='{file_path}'")
            
            # 가상 책(imgdir)인 경우 __folder__.imgdir 파일은 존재하지 않으므로 부모 폴더가 존재하는지 검증합니다.
            is_imgdir = (file_format == 'imgdir') or file_path.lower().endswith('.imgdir')
            check_path = os.path.dirname(file_path) if is_imgdir else file_path

            if not os.path.exists(check_path):
                print(f"[BookScanService ERROR] 물리 파일/디렉토리가 경로에 존재하지 않음: {check_path}")
                conn.close()
                return False, f"서버에 물리 파일/디렉토리가 존재하지 않습니다: {check_path}", None

            # PDF 단일 스캔인 경우: 안전하게 격리된 서브프로세스(lazy_scanner) 실행 방식으로 우회 (Segfault/OOM 방지)
            filename = os.path.basename(file_path)
            if file_path.lower().endswith('.pdf'):
                BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                global_lock_path = os.path.join(BASE_DIR, 'lazy_scanner.lock')
                if os.path.exists(global_lock_path):
                    print(f"[BookScanService] ⚠️ Lazy 스캐너 전역 락 감지. 처리를 대기시킵니다: {filename}")
                    conn.close()
                    return True, f"현재 백그라운드 표지 스캐너가 이미 작동 중입니다. '{filename}' 도서도 잠시 후 순차적으로 표지가 자동 추출됩니다.", None
                
                # 서브프로세스 격리 실행
                import subprocess
                import sys
                script_path = os.path.join(BASE_DIR, 'tools', 'lazy_scanner.py')
                print(f"[BookScanService] PDF 즉시 스캔 격리 구동: {script_path} --book-id {book_id}")
                try:
                    subprocess.Popen(
                        [sys.executable, script_path, '--book-id', str(book_id)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        cwd=BASE_DIR
                    )
                except Exception as sub_err:
                    print(f"[BookScanService ERROR] 격리 스캐너 구동 오류: {sub_err}")
                    conn.close()
                    return False, f"격리 표지 스캐너 구동 실패: {str(sub_err)}", None
                
                conn.close()
                return True, f"'{filename}' PDF 표지 복원 작업이 격리 백그라운드 프로세스에서 즉시 시작되었습니다.", None
                
            # 부모 폴더 경로
            parent_dir = os.path.dirname(file_path)
            print(f"[BookScanService] 부모 폴더 디렉토리 수색: '{parent_dir}'")
            
            # 2. 로컬 메타데이터 파일 탐색
            merged_meta = merge_local_metadata(parent_dir)
            print(f"[BookScanService] 파싱된 로컬 메타데이터: {merged_meta}")
            
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
            
            # 시리즈 규칙 통일:
            # - 일반 파일: 현재 폴더(=파일의 부모 폴더)
            # - IMGDIR: 부모의 부모 폴더(현재 폴더는 책 제목 폴더)
            if is_imgdir:
                series_folder = os.path.basename(os.path.dirname(parent_dir.rstrip('/\\')))
            else:
                series_folder = os.path.basename(parent_dir.rstrip('/\\'))
            real_series_name = series_folder or ""

            if real_series_name:
                import re
                real_series_name = re.sub(r'^\[(?:단행|연재|소설|만화|웹툰|일반)\]\s*', '', real_series_name).strip()

            cursor.execute("""
                UPDATE books SET 
                    series_name  = COALESCE(NULLIF(?, ''), series_name),
                    cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? IS NOT NULL AND ? != '' THEN ? ELSE cover_image END,
                    cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                    author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
                    publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
                    link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), link) ELSE link END,
                    score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != 0 THEN ? ELSE score END,
                    summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
                    release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END
                WHERE id = ?
            """, (
                real_series_name,
                cover_image, cover_image, cover_image,
                cover_image, cover_image,
                merged_meta['author'],
                merged_meta['publisher'],
                merged_meta['link'],
                merged_meta['score'], merged_meta['score'],
                merged_meta['summary'],
                merged_meta['release_date'],
                book_id
            ))
            
            if offsets_data:
                cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (book_id,))
                bulk_data = [(book_id, *offset) for offset in offsets_data]
                cursor.executemany("""
                    INSERT INTO book_offsets 
                    (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, bulk_data)
                cursor.execute("""
                    UPDATE books SET total_pages = ?, has_offsets = 1 WHERE id = ?
                """, (len(bulk_data), book_id))
                print(f"[BookScanService] 오프셋 DB 데이터 {len(bulk_data)}건 동기화 처리")
                
            conn.commit()
            conn.close()
            print(f"[BookScanService SUCCESS] '{filename}' 단독 재스캔 처리 최종 완료.")
            return True, f"'{filename}' 도서 스캔 및 메타데이터 동기화 완료!", cover_image
            
        except Exception as e:
            print(f"[BookScanService ERROR] 처리 중 예외 발생: {str(e)}")
            if conn:
                conn.close()
            return False, f"도서 스캔 실패: {str(e)}", None
