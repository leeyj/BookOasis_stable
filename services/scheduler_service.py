# -*- coding: utf-8 -*-
import os
import database
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tools.scanner import scan_library

# 싱글톤 백그라운드 스케줄러 인스턴스
scheduler = BackgroundScheduler()

class SchedulerService:
    @staticmethod
    def start_scheduler():
        """서버 기동 시 스케줄러를 시작하고 DB에서 기존 스케줄 로드"""
        if not scheduler.running:
            scheduler.start()
            print("[Scheduler] APScheduler started successfully!")
        SchedulerService.reload_all_jobs()

    @staticmethod
    def reload_all_jobs():
        """모든 DB의 크론 스케줄링 Job 갱신"""
        # 기존 모든 job 제거
        try:
            for job in list(scheduler.get_jobs()):
                scheduler.remove_job(job.id)
            print("[Scheduler] All existing scan jobs removed.")
        except Exception as e:
            print(f"[Scheduler] Error removing job: {e}")

        for db_type in ['general', 'adult']:
            db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
            if not os.path.exists(db_path):
                continue
                
            try:
                conn = database.get_connection(db_type)
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, physical_path, cron_schedule FROM libraries WHERE cron_schedule IS NOT NULL AND cron_schedule != ''")
                libs = cursor.fetchall()
                
                # general DB에서 LAZY_SCAN_CRON 설정을 가져와 등록
                if db_type == 'general':
                    cursor.execute("SELECT value FROM settings WHERE key = 'LAZY_SCAN_CRON'")
                    row_cron = cursor.fetchone()
                    if row_cron and row_cron['value']:
                        lazy_cron = row_cron['value']
                        try:
                            lazy_trigger = CronTrigger.from_crontab(lazy_cron)
                            scheduler.add_job(
                                run_lazy_scanner_job,
                                lazy_trigger,
                                id="lazy_scan_covers_job",
                                replace_existing=True
                            )
                            print(f"[Scheduler] Lazy cover scanner job registered: Schedule={lazy_cron}")
                        except ValueError as cron_err:
                            print(f"[Scheduler] Invalid lazy script cron passed ({lazy_cron}): {cron_err}")
                
                conn.close()
                
                for lib in libs:
                    SchedulerService.register_job(db_type, db_path, lib['id'], lib['physical_path'], lib['cron_schedule'])
            except Exception as e:
                print(f"[Scheduler] {db_type} Error loading library: {e}")

    @staticmethod
    def register_job(db_type, db_path, library_id, physical_path, cron_expression):
        """특정 라이브러리의 스케줄러 Job 등록"""
        job_id = f"scan_{db_type}_{library_id}"
        
        # 크론 검증
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
        except ValueError as e:
            print(f"[Scheduler] Invalid cron expression passed ({cron_expression}): {e}")
            return False

        # 기존 같은 ID의 job이 있으면 제거
        try:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        except Exception:
            pass

        from services.scheduler_service import run_scan_job
        scheduler.add_job(
            run_scan_job,
            trigger,
            id=job_id,
            args=[db_type, db_path, library_id, physical_path],
            replace_existing=True
        )
        print(f"[Scheduler] Job registered: ID={job_id}, Schedule={cron_expression}")
        return True

    @staticmethod
    def remove_job(db_type, library_id):
        """특정 라이브러리 Job 제거"""
        job_id = f"scan_{db_type}_{library_id}"
        try:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                print(f"[Scheduler] Job removed: ID={job_id}")
        except Exception as e:
            print(f"[Scheduler] Job removal failed: ID={job_id}, Error: {e}")


def run_scan_job(db_type, db_path, library_id, physical_path, force=False):
    """실제 스케줄에 맞춰 구동될 래핑 헬퍼 함수 (진행 및 내역 상세 로깅 보강)"""
    import database
    from tools.scanner import scan_library
    from datetime import datetime
    
    start_time = datetime.now()
    start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 로그 파일 경로 설정
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, 'scan_history.log')
    
    def write_scan_log(message):
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f_log:
                f_log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception as ex_log:
            print(f"[Logger ERROR] Failed to write log file: {ex_log}")

    print(f"[Scanner-Trigger] 🚀 Immediate scan started: DB={db_type}, ID={library_id}, Path={physical_path}, Force={force}")
    write_scan_log(f"스캔 기동 시작 - DB={db_type}, LibraryID={library_id}, Path='{physical_path}', Force={force}")
    
    # VFS 캐시 사전 갱신 옵션 확인 및 수행
    try:
        conn_chk = database.get_connection(db_type)
        cursor_chk = conn_chk.cursor()
        cursor_chk.execute("SELECT vfs_refresh_before_scan FROM libraries WHERE id = ?", (library_id,))
        row_chk = cursor_chk.fetchone()
        conn_chk.close()
        
        if row_chk and row_chk['vfs_refresh_before_scan'] == 1:
            print(f"[Scanner-Trigger] VFS pre-refresh active. Attempting rclone cache update.")
            write_scan_log("VFS 사전 새로고침 시도 (rclone API)")
            
            import urllib.request
            import json
            rc_url = "http://localhost:5572"
            try:
                conn_s = database.get_connection(db_type)
                cursor_s = conn_s.cursor()
                cursor_s.execute("SELECT value FROM settings WHERE key = 'RCLONE_RC_URL'")
                row_s = cursor_s.fetchone()
                if row_s:
                    rc_url = row_s['value'].rstrip('/')
                conn_s.close()
            except Exception:
                pass
            
            try:
                from utils.drive_helper import get_rclone_relative_path
                from utils.drive_helper import is_remote_path
                
                target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
                remote_paths = [p for p in target_paths if is_remote_path(p)]
                
                for r_path in remote_paths:
                    rel_path = get_rclone_relative_path(r_path)
                    print(f"[Scanner-Trigger] VFS cache update target folder: '{rel_path}'")
                    
                    full_url = f"{rc_url}/vfs/refresh"
                    req_data = json.dumps({"dir": rel_path}).encode('utf-8')
                    req = urllib.request.Request(
                        full_url, 
                        data=req_data,
                        headers={'Content-Type': 'application/json'}
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            res_text = resp.read().decode('utf-8')
                            print(f"[Scanner-Trigger] VFS update result ({rel_path}): {res_text}")
                            write_scan_log(f"VFS 갱신 완료 ({rel_path}): {res_text}")
                    except Exception as http_ex:
                        print(f"[Scanner-Trigger ERROR] VFS update request failed ({rel_path}): {http_ex}")
                        write_scan_log(f"VFS update request failed ({rel_path}): {http_ex}")
            except Exception as e_vfs:
                print(f"[Scanner-Trigger ERROR] Error during VFS refresh: {e_vfs}")
                write_scan_log(f"VFS 새로고침 오류: {e_vfs}")
    except Exception as db_err:
        print(f"[Scanner-Trigger] VFS 옵션 DB 조회 Error: {db_err}")
    
    # 1. 상태를 'scanning'으로 업데이트
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("UPDATE libraries SET scan_status = 'scanning' WHERE id = ?", (library_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Scheduler] Scan state update error: {e}")
    
    try:
        scan_library(db_path, library_id, physical_path, force=force)
        
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
        
        msg = f"스캔 성공 완료 - DB={db_type}, LibraryID={library_id}, 소요시간={duration:.2f}초"
        print(f"[Scanner-Trigger] ✅ {msg}")
        write_scan_log(msg)
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
        
        msg = f"스캔 실패 - DB={db_type}, LibraryID={library_id}, 소요시간={duration:.2f}초, 에러={e}"
        print(f"[Scanner-Trigger] ❌ {msg}")
        write_scan_log(msg)


def run_lazy_scanner_job():
    """백그라운드에서 python tools/lazy_scanner.py를 서브프로세스로 안전하게 실행"""
    import subprocess
    import sys
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(BASE_DIR, 'tools', 'lazy_scanner.py')
    print(f"[Scheduler] Lazy cover scanner standalone process triggered: {script_path}")
    try:
        subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=BASE_DIR
        )
    except Exception as e:
        print(f"[Scheduler ERROR] Lazy cover script execution failed: {e}")

