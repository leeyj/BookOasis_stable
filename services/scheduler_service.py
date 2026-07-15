# -*- coding: utf-8 -*-
import os
import re
import database
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tools.scanner import scan_library


def normalize_cron_expression(cron_expression):
    """Convert Linux-style cron weekday numbers to APScheduler-compatible values.

    Linux cron uses 0-7 where 0 and 7 mean Sunday, 1-6 mean Monday-Saturday.
    APScheduler uses 0-6 where 0 means Monday and 6 means Sunday.
    """
    if not cron_expression:
        return cron_expression

    parts = cron_expression.split()
    if len(parts) != 5:
        return cron_expression

    minute, hour, day, month, day_of_week = parts

    if day_of_week == '*':
        return cron_expression

    if re.fullmatch(r'[A-Za-z]+', day_of_week):
        return cron_expression

    def convert_value(value):
        if value in {'*', '?'}:
            return value
        if value.isdigit():
            number = int(value)
            if number == 0:
                return '6'
            if number == 7:
                return '0'
            if 1 <= number <= 6:
                return str(number - 1)
        return value

    if ',' in day_of_week:
        converted = ','.join(convert_value(v) for v in day_of_week.split(','))
    elif '-' in day_of_week:
        start, end = day_of_week.split('-', 1)
        converted = f"{convert_value(start)}-{convert_value(end)}"
    else:
        converted = convert_value(day_of_week)

    if converted == day_of_week:
        return cron_expression

    return f"{minute} {hour} {day} {month} {converted}"

# 싱글톤 백그라운드 스케줄러 인스턴스 (동적으로 타임존을 재설정하여 가동)
scheduler = BackgroundScheduler()

class SchedulerService:
    @staticmethod
    def start_scheduler():
        """서버 기동 시 스케줄러를 시작하고 DB에서 기존 스케줄 로드"""
        if not scheduler.running:
            scheduler.start()
            print("[Scheduler] APScheduler started successfully!")
        SchedulerService.reload_all_jobs()
        try:
            SchedulerService.auto_resume_interrupted_jobs()
        except Exception as e:
            print(f"[Scheduler ERROR] Auto-resume failed: {e}")

    @staticmethod
    def auto_resume_interrupted_jobs():
        """이전 실행 중 비정상 종료(interrupted)된 카테고리를 찾아 자동으로 재인큐"""
        import database
        from services.scheduler_service import enqueue_scan_job
        
        print("[Scheduler] Checking for interrupted scan jobs to auto-resume...")
        for db_type in ['general', 'adult']:
            db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
            if not os.path.exists(db_path):
                continue
                
            try:
                conn = database.get_connection(db_type)
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, physical_path FROM libraries WHERE scan_status = 'interrupted'")
                interrupted_libs = cursor.fetchall()
                
                for lib in interrupted_libs:
                    lib_id = lib['id']
                    lib_name = lib['name']
                    phys_path = lib['physical_path']
                    
                    print(f"[Scheduler] 🔄 Auto-resuming interrupted scan: DB={db_type}, Name={lib_name}, ID={lib_id}")
                    
                    # 1. 큐에 적재 전 중복 인큐 방지를 위해 상태를 일단 ready로 업데이트
                    cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE id = ?", (lib_id,))
                    conn.commit()
                    
                    # 2. 스캔 큐에 인큐
                    enqueue_scan_job(db_type, db_path, lib_id, phys_path, force=False)
                    
                conn.close()
            except Exception as e:
                print(f"[Scheduler ERROR] Failed to auto-resume interrupted jobs for {db_type}: {e}")

    @staticmethod
    def reload_all_jobs():
        """모든 DB의 크론 스케줄링 Job 갱신"""
        # DB settings 테이블에서 TIMEZONE 설정을 가져와 스케줄러 타임존 동적 구성
        from services.settings_service import SettingsService
        from zoneinfo import ZoneInfo
        tz_str = SettingsService.get('TIMEZONE', 'UTC')
        try:
            scheduler.configure(timezone=ZoneInfo(tz_str))
            print(f"[Scheduler] Timezone configured successfully to: {tz_str}")
        except Exception as tz_err:
            print(f"[Scheduler ERROR] Failed to configure scheduler timezone ({tz_str}): {tz_err}")
            try:
                scheduler.configure(timezone=ZoneInfo('UTC'))
            except:
                pass

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
        
        normalized_expression = normalize_cron_expression(cron_expression)

        # 크론 검증
        try:
            trigger = CronTrigger.from_crontab(normalized_expression)
        except ValueError as e:
            print(f"[Scheduler] Invalid cron expression passed ({cron_expression}): {e}")
            return False

        # 기존 같은 ID의 job이 있으면 제거
        try:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        except Exception:
            pass

        from services.scheduler_service import enqueue_scan_job
        scheduler.add_job(
            enqueue_scan_job,
            trigger,
            id=job_id,
            args=[db_type, db_path, library_id, physical_path],
            replace_existing=True
        )
        print(f"[Scheduler] Job registered: ID={job_id}, Schedule={cron_expression} (normalized={normalized_expression})")
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

    # DB가 현재 최적화(VACUUM 등) 튜닝 진행 중인 경우, 완료될 때까지 안전하게 대기
    from services.db_tuning_service import is_db_tuning
    import time
    
    wait_count = 0
    while is_db_tuning(db_type):
        print(f"[Scanner-Trigger] ⚠️ DB Tuning ({db_type}) in progress. Waiting 3 seconds... (elapsed: {wait_count * 3}s)")
        write_scan_log("⚠️ 데이터베이스 최적화(튜닝) 작업이 진행 중입니다. 완료 시까지 일시 대기합니다.")
        time.sleep(10.0)
        wait_count += 1
        if wait_count > 40:  # 최대 2분 대기
            print(f"[Scanner-Trigger WARNING] DB Tuning wait timeout. Proceeding with scan anyway.")
            write_scan_log("⚠️ 튜닝 대기 시간을 초과하여 스캔을 강제 진행합니다.")
            break

    print(f"[Scanner-Trigger] 🚀 Immediate scan started: DB={db_type}, ID={library_id}, Path={physical_path}, Force={force}")
    write_scan_log(f"스캔 기동 시작 - DB={db_type}, LibraryID={library_id}, Path='{physical_path}', Force={force}")
    
    # 큐 세부 진행 단계를 VFS 갱신 중으로 기록
    from services.scanner_queue import scanner_queue
    if scanner_queue.current_task and scanner_queue.current_task.get('key') == f"library_scan_{db_type}_{library_id}":
        scanner_queue.current_task['stage'] = 'vfs_refresh'
    
    # VFS 캐시 사전 갱신 옵션 확인 및 수행
    vfs_refreshed_in_wrapper = False
    try:
        conn_chk = database.get_connection(db_type)
        cursor_chk = conn_chk.cursor()
        cursor_chk.execute("SELECT vfs_refresh_before_scan FROM libraries WHERE id = ?", (library_id,))
        row_chk = cursor_chk.fetchone()
        conn_chk.close()
        
        # 원격 경로가 있는지 확인
        from utils.drive_helper import is_remote_path
        target_paths_raw = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
        target_paths = list(dict.fromkeys(target_paths_raw))
        has_remote_paths = any(is_remote_path(p) for p in target_paths)
        
        # VFS 설정이 활성화되었거나, 원격 경로가 있으면 VFS 갱신 강제 수행
        should_vfs_refresh = (row_chk and row_chk['vfs_refresh_before_scan'] == 1) or has_remote_paths
        
        if should_vfs_refresh:
            vfs_refreshed_in_wrapper = True
            if has_remote_paths and not (row_chk and row_chk['vfs_refresh_before_scan'] == 1):
                print(f"[Scanner-Trigger] ⚠️ Remote paths detected but VFS refresh disabled. Forcing VFS refresh for data integrity.")
                write_scan_log("⚠️ 원격 경로 감지됨. VFS 새로고침을 강제 실행합니다 (데이터 무결성 보장).")
            else:
                print(f"[Scanner-Trigger] VFS pre-refresh active. Attempting rclone cache update.")
                write_scan_log("VFS 사전 새로고침 시도 (rclone API)")
            
            import urllib.request
            import urllib.parse
            import json
            import base64
            
            # RC URL 조회: 라이브러리별 rclone_rc_url 우선 → 전역 RCLONE_RC_URL 폴백 (vfs.py와 동일)
            rc_urls = ["http://localhost:5572"]
            try:
                conn_s = database.get_connection(db_type)
                cursor_s = conn_s.cursor()
                cursor_s.execute("SELECT vfs_refresh_before_scan, rclone_rc_url FROM libraries WHERE id = ?", (library_id,))
                row_lib = cursor_s.fetchone()
                conn_s.close()
                
                if row_lib and row_lib['rclone_rc_url'] and row_lib['rclone_rc_url'].strip():
                    # 라이브러리별 RC URL 우선 사용
                    rc_urls = [u.strip().rstrip('/') for u in str(row_lib['rclone_rc_url']).split(',') if u.strip()]
                else:
                    # 전역 설정 폴백
                    conn_g = None
                    try:
                        conn_g = database.get_connection(db_type)
                        cursor_g = conn_g.cursor()
                        cursor_g.execute("SELECT value FROM settings WHERE key = 'RCLONE_RC_URL'")
                        row_g = cursor_g.fetchone()
                        if row_g and row_g['value']:
                            rc_urls = [u.strip().rstrip('/') for u in str(row_g['value']).split(',') if u.strip()]
                    except Exception:
                        pass
                    finally:
                        if conn_g:
                            try:
                                conn_g.close()
                            except Exception:
                                pass
            except Exception:
                pass

            # 중복 RC URL 제거 (순서 보존)
            rc_urls = list(dict.fromkeys(rc_urls))
            
            try:
                from utils.drive_helper import get_rclone_relative_path
                
                remote_paths = list(dict.fromkeys([p for p in target_paths if is_remote_path(p)]))
                
                for r_path in remote_paths:
                    # 중간에 스캔 취소가 요청되었는지 확인
                    try:
                        conn_chk = database.get_connection(db_type)
                        cursor_chk = conn_chk.cursor()
                        cursor_chk.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
                        row_status = cursor_chk.fetchone()
                        conn_chk.close()
                        if row_status and row_status['scan_status'] == 'cancelling':
                            print(f"[Scanner-Trigger] Scan cancellation detected during VFS refresh loop. Aborting VFS updates.")
                            write_scan_log("스캔 취소 감지됨. VFS 갱신을 중단합니다.")
                            break
                    except Exception as e_status:
                        print(f"[Scanner-Trigger WARNING] Failed to check status: {e_status}")

                    rel_path = get_rclone_relative_path(r_path)
                    print(f"[Scanner-Trigger] VFS cache update target folder: '{rel_path}'")
                    
                    refreshed = False
                    for rc_url in rc_urls:
                        try:
                            parsed = urllib.parse.urlparse(rc_url)
                            headers = {'Content-Type': 'application/json'}
                            
                            # URL 내 인증 정보(user:pass@host) 파싱 및 Basic Auth 헤더 적용 (vfs.py와 동일)
                            if parsed.username and parsed.password:
                                auth_str = f"{parsed.username}:{parsed.password}"
                                auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
                                headers['Authorization'] = f"Basic {auth_b64}"
                                
                                # URL에서 인증 정보를 제거한 클린 URL 생성
                                netloc = parsed.netloc.split('@')[-1]
                                clean_rc_url = f"{parsed.scheme}://{netloc}"
                            else:
                                clean_rc_url = rc_url
                            
                            full_url = f"{clean_rc_url.rstrip('/')}/vfs/refresh"
                            req_data = json.dumps({"dir": rel_path, "recursive": "true"}).encode('utf-8')
                            req = urllib.request.Request(
                                full_url, 
                                data=req_data,
                                headers=headers
                            )
                            try:
                                with urllib.request.urlopen(req, timeout=1200) as resp:
                                    res_text = resp.read().decode('utf-8')
                                    print(f"[Scanner-Trigger] VFS update result (server={clean_rc_url}, path={rel_path}): {res_text}")
                                    write_scan_log(f"VFS 갱신 완료 (server={clean_rc_url}, path={rel_path}): {res_text}")
                                    refreshed = True
                                    break
                            except urllib.error.HTTPError as http_ex:
                                err_body = http_ex.read().decode('utf-8') if hasattr(http_ex, 'read') else str(http_ex)
                                print(f"[Scanner-Trigger ERROR] VFS update request failed ({rel_path}): {http_ex.code} - {err_body}")
                                write_scan_log(f"VFS update request failed ({rel_path}): {http_ex.code} - {err_body}")
                            except Exception as http_ex:
                                # 로그에 인증 정보 노출 방지
                                safe_url = rc_url
                                if '@' in rc_url:
                                    try:
                                        p = urllib.parse.urlparse(rc_url)
                                        safe_url = f"{p.scheme}://****:****@{p.netloc.split('@')[-1]}"
                                    except Exception:
                                        safe_url = "[Protected URL]"
                                print(f"[Scanner-Trigger ERROR] VFS update request failed ({rel_path}): Server='{safe_url}', Error={http_ex}")
                                write_scan_log(f"VFS update request failed ({rel_path}): {http_ex}")
                        except Exception as e_rc:
                            print(f"[Scanner-Trigger ERROR] VFS RC URL processing error: {e_rc}")
                            write_scan_log(f"VFS RC URL 처리 오류: {e_rc}")

                    if refreshed:
                        continue
            except Exception as e_vfs:
                print(f"[Scanner-Trigger ERROR] Error during VFS refresh: {e_vfs}")
                write_scan_log(f"VFS 새로고침 오류: {e_vfs}")
    except Exception as db_err:
        print(f"[Scanner-Trigger] VFS 옵션 DB 조회 Error: {db_err}")
    
    # 큐 세부 진행 단계를 도서 스캔 중으로 기록
    from services.scanner_queue import scanner_queue
    if scanner_queue.current_task and scanner_queue.current_task.get('key') == f"library_scan_{db_type}_{library_id}":
        scanner_queue.current_task['stage'] = 'book_scan'

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
        scan_library(db_path, library_id, physical_path, force=force, skip_vfs_refresh=vfs_refreshed_in_wrapper)
        
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


def enqueue_scan_job(db_type, db_path, library_id, physical_path, force=False):
    from services.scanner_queue import scanner_queue
    scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, library_id=library_id, physical_path=physical_path, force=force)

def run_lazy_scanner_job():
    """백그라운드 스캐너 작업을 큐에 적재"""
    from services.scanner_queue import scanner_queue
    print("[Scheduler] Lazy cover scanner job scheduled -> Enqueuing...")
    scanner_queue.enqueue('lazy_scan')

