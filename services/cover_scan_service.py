# -*- coding: utf-8 -*-
from repositories.category_repository import CategoryRepository
from tools.scanner import scan_library_covers_only
from datetime import datetime
from utils.time_helper import scan_elapsed
from utils.scan_log_helper import write_scan_log

class CoverScanService:
    @staticmethod
    def run_cover_scan_job(db_type, db_path, library_id, physical_path):
        """실제 라이브러리의 표지만 고속으로 재스캔하는 백그라운드 구동 래퍼"""
        start_time = datetime.now()

        print(f"[CoverScanner-Trigger] 🚀 Immediate cover-only scan started: DB={db_type}, ID={library_id}, Path={physical_path}")
        write_scan_log(f"표지 전용 스캔 기동 시작 - DB={db_type}, LibraryID={library_id}, Path='{physical_path}'")

        # 1. 상태를 'scanning'으로 업데이트
        try:
            CategoryRepository.update_library_scan_status(db_type, library_id, 'scanning')
        except Exception as e:
            print(f"[CoverScanner] Scan state update error: {e}")

        try:
            # 표지 전용 고속 스캔 실행
            scan_library_covers_only(db_path, library_id, physical_path)

            # 2. 성공 시 'ready' 및 last_scanned_at 기록
            duration, end_str = scan_elapsed(start_time)

            CategoryRepository.update_library_scan_success(db_type, library_id, end_str)

            msg = f"표지 전용 스캔 성공 완료 - DB={db_type}, LibraryID={library_id}, 소요시간={duration:.2f}초"
            print(f"[CoverScanner-Trigger] ✅ {msg}")
            write_scan_log(msg)
        except Exception as e:
            # 3. 실패 시 'failed' 기록
            duration, _ = scan_elapsed(start_time)
            try:
                CategoryRepository.update_library_scan_status(db_type, library_id, 'failed')
            except Exception:
                pass

            msg = f"표지 전용 스캔 실패 - DB={db_type}, LibraryID={library_id}, 소요시간={duration:.2f}초, 에러={e}"
            print(f"[CoverScanner-Trigger] ❌ {msg}")
            write_scan_log(msg)
