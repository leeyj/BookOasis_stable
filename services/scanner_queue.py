# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import subprocess
import datetime
import database

# SIGTERM/SIGINT 수신 시 워커 루프를 안전 종료하기 위한 전역 플래그
stop_requested = False

class ScannerQueue:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ScannerQueue, cls).__new__(cls)
        return cls._instance

    def log(self, message):
        try:
            from utils.logger import print_msg
            print_msg(f"[Queue] {message}")
        except:
            print(f"[Queue] {message}")

    def _get_task_key(self, task_type, kwargs):
        if task_type == 'lazy_scan':
            return 'lazy_scan'
        elif task_type in ('library_scan', 'cover_scan'):
            db_type = kwargs.get('db_type', 'general')
            library_id = kwargs.get('library_id')
            return f"{task_type}_{db_type}_{library_id}"
        return str(task_type)

    def enqueue(self, task_type, **kwargs):
        task_key = self._get_task_key(task_type, kwargs)
        try:
            from repositories.scanner_queue_repository import ScannerQueueRepository
            existing = ScannerQueueRepository.get_task_by_key(task_key)
            if existing and existing['status'] in ('pending', 'running'):
                self.log(f"Task '{task_key}' is already in state '{existing['status']}'. Rejecting duplicate.")
                return False

            kwargs_json = json.dumps(kwargs, ensure_ascii=False)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if existing:
                success = ScannerQueueRepository.update_task_to_pending(existing['id'], task_type, kwargs_json, now_str)
            else:
                success = ScannerQueueRepository.insert_task(task_type, task_key, kwargs_json, now_str)

            if not success:
                self.log(
                    f"Task '{task_key}' was not enqueued because it is already pending/running "
                    f"(or no DB row was written)."
                )
                return False

            self.log(f"Task '{task_key}' enqueued successfully (DB-backed).")

            # Redis List에 작업 키 푸시
            try:
                from utils.redis_helper import redis_lpush
                redis_lpush("queue:scanner", task_key)
            except Exception as r_err:
                self.log(f"Redis queue push failed (ignored): {r_err}")

            return True
        except Exception as e:
            self.log(f"Enqueue failed: {e}")
            return False

    def add_task(self, task_type, **kwargs):
        """webhook 등에서 호출하는 하위 호환성용 메서드"""
        return self.enqueue(task_type, **kwargs)

    def get_queue_status(self):
        """현재 실행 중인 작업과 큐 대기열의 상태를 반환합니다."""
        status = {
            'running': None,
            'pending': []
        }
        try:
            from repositories.scanner_queue_repository import ScannerQueueRepository
            row_run, rows_pending = ScannerQueueRepository.fetch_queue_status()
            
            if row_run:
                try:
                    kwargs = json.loads(row_run['kwargs']) if row_run['kwargs'] else {}
                except:
                    kwargs = {}
                status['running'] = {
                    'type': row_run['task_type'],
                    'key': row_run['task_key'],
                    'kwargs': kwargs,
                    'enqueued_at': row_run['enqueue_at'],
                    'started_at': row_run['started_at'],
                    'stage': row_run['stage']
                }

            for row in rows_pending:
                try:
                    kwargs = json.loads(row['kwargs']) if row['kwargs'] else {}
                except:
                    kwargs = {}
                status['pending'].append({
                    'type': row['task_type'],
                    'key': row['task_key'],
                    'kwargs': kwargs,
                    'enqueued_at': row['enqueue_at'],
                    'stage': row['stage']
                })
        except Exception as e:
            self.log(f"Failed to get queue status from DB: {e}")
        return status

    def clear_queue(self):
        """대기열에 있는 모든 작업을 취소(cancelled) 처리합니다."""
        try:
            from repositories.scanner_queue_repository import ScannerQueueRepository
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            count = ScannerQueueRepository.clear_pending_tasks(now_str)
            self.log(f"Queue cleared. Cancelled {count} pending items in DB.")
            return count
        except Exception as e:
            self.log(f"Failed to clear queue: {e}")
            return 0

    def cancel_pending_task(self, task_key):
        """대기열에 있는 특정 작업 1건을 취소(cancelled) 처리합니다."""
        if not task_key:
            return False
        try:
            from repositories.scanner_queue_repository import ScannerQueueRepository
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            success = ScannerQueueRepository.cancel_task(task_key, now_str)
            if success:
                self.log(f"Pending task '{task_key}' cancelled successfully in DB.")
            return success
        except Exception as e:
            self.log(f"Failed to cancel pending task: {e}")
            return False


def run_scanner_worker_loop():
    """
    독립된 백그라운드 프로세스에서 동작할 워커의 무한루프 진입점입니다.
    """
    try:
        from utils.logger import setup_rotating_logger
        setup_rotating_logger()
    except:
        pass

    sq = ScannerQueue()
    sq.log(f"Scanner worker process started. PID: {os.getpid()}")

    from repositories.scanner_queue_repository import ScannerQueueRepository

    global stop_requested

    while True:
        if stop_requested:
            sq.log("Shutdown flag detected. Exiting scanner worker loop.")
            break

        try:
            # Redis가 사용 가능한 경우 BRPOP으로 작업 대기
            task_key_popped = None
            try:
                from utils.redis_helper import redis_brpop
                task_key_popped = redis_brpop("queue:scanner", timeout=3)
            except Exception:
                pass

            task = None
            if task_key_popped:
                task = ScannerQueueRepository.get_pending_task_by_key(task_key_popped)

            # Fallback
            if not task:
                task = ScannerQueueRepository.get_next_pending_task()
            
            if not task:
                from utils.redis_helper import get_redis_client
                if not get_redis_client():
                    time.sleep(3.0)
                else:
                    time.sleep(0.5)
                continue

            if stop_requested:
                sq.log("Shutdown flag detected before task acquisition. Exiting scanner worker loop.")
                break
                
            task_id = task['id']
            task_type = task['task_type']
            task_key = task['task_key']
            
            try:
                kwargs = json.loads(task['kwargs']) if task['kwargs'] else {}
            except Exception as j_err:
                kwargs = {}
                sq.log(f"Failed to parse kwargs JSON: {j_err}")

            # 2. Race Condition 방지를 위한 원자적 상태 변경 시도
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            success = ScannerQueueRepository.try_acquire_task(task_id, now_str)
            if not success:
                continue
                
            sq.log(f"Processing task: {task_key}")
            
            # 3. 작업 유형별 실행 분기
            error_message = None
            try:
                if task_type == 'lazy_scan':
                    _process_lazy_scan(sq)
                elif task_type == 'library_scan':
                    _process_library_scan(sq, **kwargs)
                elif task_type == 'cover_scan':
                    _process_cover_scan(sq, **kwargs)
                else:
                    error_message = f"Unknown task type: {task_type}"
                    sq.log(error_message)
            except Exception as work_err:
                error_message = str(work_err)
                sq.log(f"Task processing crashed: {work_err}")

            # 4. 작업 결과 반영
            finished_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ScannerQueueRepository.update_task_result(task_id, finished_str, error_message)

            if not error_message:
                # 스캔 완료 시 신규 추가 도서 대시보드 캐시 무효화
                try:
                    from utils.redis_helper import redis_delete_pattern
                    target_db = kwargs.get('db_type', 'general')
                    redis_delete_pattern(f"cache:recent_added:{target_db}:*")
                except Exception as cache_err:
                    sq.log(f"Failed to invalidate recently_added cache: {cache_err}")

            sq.log(f"Finished task: {task_key}.")
            
        except Exception as loop_err:
            sq.log(f"Error in worker loop: {loop_err}")
            time.sleep(5.0)

    sq.log("Scanner worker process terminated gracefully.")


active_subprocess = None

def _process_lazy_scan(sq):
    global active_subprocess, stop_requested
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(BASE_DIR, 'tools', 'lazy_scanner.py')
    
    active_subprocess = subprocess.Popen(
        [sys.executable, script_path],
        cwd=BASE_DIR
    )
    try:
        # 종료 시그널 수신 시 stop_requested 플래그와 함께 자식 종료를 기다립니다.
        while True:
            returncode = active_subprocess.poll()
            if returncode is not None:
                break
            if stop_requested:
                try:
                    active_subprocess.terminate()
                except Exception:
                    pass
            time.sleep(0.2)
    finally:
        active_subprocess = None
        
    if returncode != 0:
        # 우아한 종료에 의한 중단의 경우 exit 0 또는 시그널에 따른 음수 리턴코드가 뜰 수 있음
        if returncode in (-15, -9, 0):
            print(f"[Scanner-Queue] lazy_scanner terminated gracefully (code: {returncode})")
            return
        raise RuntimeError(f"lazy_scanner exited with code {returncode}")

def _process_library_scan(sq, **kwargs):
    from services.scheduler_service import run_scan_job
    # 가변 인자 딕셔너리를 그대로 포워딩하여 호출
    run_scan_job(**kwargs)
    
def _process_cover_scan(sq, **kwargs):
    from services.cover_scan_service import CoverScanService
    CoverScanService.run_cover_scan_job(**kwargs)


# 하위 호환성 유지를 위한 전역 싱글톤 인스턴스
scanner_queue = ScannerQueue()
