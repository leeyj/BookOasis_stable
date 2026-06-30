# -*- coding: utf-8 -*-
import os
import database
from tools.scanner import scan_library_covers_only
from datetime import datetime

class CoverScanService:
    @staticmethod
    def run_cover_scan_job(db_type, db_path, library_id, physical_path):
        """실제 라이브러리의 표지만 고속으로 재스캔하는 백그라운드 구동 래퍼"""
        start_time = datetime.now()
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 로그 파일 경로 설정
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'scan_history.log')
        
        def write_log(message):
            try:
                with open(log_file_path, 'a', encoding='utf-8') as f_log:
                    f_log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            except Exception as ex_log:
                print(f"[CoverLogger ERROR] Failed to write log file: {ex_log}")

        print(f"[CoverScanner-Trigger] 🚀 Immediate cover-only scan started: DB={db_type}, ID={library_id}, Path={physical_path}")
        write_log(f"표지 전용 스캔 기동 시작 - DB={db_type}, LibraryID={library_id}, Path='{physical_path}'")
        
        # 1. 상태를 'scanning'으로 업데이트
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("UPDATE libraries SET scan_status = 'scanning' WHERE id = ?", (library_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[CoverScanner] Scan state update error: {e}")
        
        try:
            # 표지 전용 고속 스캔 실행
            scan_library_covers_only(db_path, library_id, physical_path)
            
            # 2. 성공 시 'ready' 및 last_scanned_at 기록
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE libraries 
                SET scan_status = 'ready', 
                    last_scanned_at = ? 
                WHERE id = ?
            """, (end_str, library_id))
            conn.commit()
            conn.close()
            
            msg = f"표지 전용 스캔 성공 완료 - DB={db_type}, LibraryID={library_id}, 소요시간={duration:.2f}초"
            print(f"[CoverScanner-Trigger] ✅ {msg}")
            write_log(msg)
        except Exception as e:
            # 3. 실패 시 'failed' 기록
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            try:
                conn = database.get_connection(db_type)
                cursor = conn.cursor()
                cursor.execute("UPDATE libraries SET scan_status = 'failed' WHERE id = ?", (library_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass
            
            msg = f"표지 전용 스캔 실패 - DB={db_type}, LibraryID={library_id}, 소요시간={duration:.2f}초, 에러={e}"
            print(f"[CoverScanner-Trigger] ❌ {msg}")
            write_log(msg)
