# -*- coding: utf-8 -*-
import threading
import queue
import sys
import subprocess
import os
import datetime

class ScannerQueue:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ScannerQueue, cls).__new__(cls)
                cls._instance._init_queue()
            return cls._instance

    def _init_queue(self):
        self.q = queue.Queue()
        self.enqueued_items = set()
        self.queue_lock = threading.Lock()
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="ScannerWorker")
        self.worker_thread.start()
        self.log("Scanner worker thread started.")

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
            db_type = kwargs.get('db_type')
            library_id = kwargs.get('library_id')
            return f"{task_type}_{db_type}_{library_id}"
        return str(task_type)

    def enqueue(self, task_type, **kwargs):
        task_key = self._get_task_key(task_type, kwargs)
        
        with self.queue_lock:
            if task_key in self.enqueued_items:
                self.log(f"Task '{task_key}' is already in the queue. Skipping duplicate.")
                return False
                
            self.enqueued_items.add(task_key)
            self.q.put({
                'type': task_type, 
                'key': task_key, 
                'kwargs': kwargs,
                'enqueued_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.log(f"Task '{task_key}' enqueued successfully. Queue size: {self.q.qsize()}")
            return True

    def get_queue_status(self):
        """현재 실행 중인 작업과 큐 대기열의 상태를 반환합니다."""
        status = {
            'running': getattr(self, 'current_task', None),
            'pending': []
        }
        with self.queue_lock:
            # 큐의 내부 deque 복사
            for item in list(self.q.queue):
                status['pending'].append(item)
        return status

    def clear_queue(self):
        """대기열에 있는 모든 작업을 삭제합니다."""
        with self.queue_lock:
            count = len(self.q.queue)
            self.q.queue.clear()
            self.enqueued_items.clear()
            self.log(f"Queue cleared. Removed {count} items.")
            return count

    def _worker_loop(self):
        while True:
            try:
                task = self.q.get()
                self.current_task = task
                self.current_task['started_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                task_type = task['type']
                task_key = task['key']
                kwargs = task['kwargs']

                # 큐에서 작업을 꺼냈으므로 대기열 목록에서 제거 (새로운 동일 요청 수락 가능)
                with self.queue_lock:
                    if task_key in self.enqueued_items:
                        self.enqueued_items.remove(task_key)

                self.log(f"Starting task: {task_key}")
                
                if task_type == 'lazy_scan':
                    self._process_lazy_scan()
                elif task_type == 'library_scan':
                    self._process_library_scan(**kwargs)
                elif task_type == 'cover_scan':
                    self._process_cover_scan(**kwargs)
                else:
                    self.log(f"Unknown task type: {task_type}")

            except Exception as e:
                self.log(f"Error processing task: {e}")
            finally:
                self.current_task = None
                self.q.task_done()
                self.log(f"Finished task: {task_key}. Remaining queue size: {self.q.qsize()}")

    def _process_lazy_scan(self):
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(BASE_DIR, 'tools', 'lazy_scanner.py')
        
        try:
            # 동기식(block)으로 실행하여 프로세스가 끝날 때까지 기다림
            subprocess.run(
                [sys.executable, script_path],
                cwd=BASE_DIR,
                check=False
            )
        except Exception as e:
            self.log(f"Lazy cover script execution failed: {e}")

    def _process_library_scan(self, db_type, db_path, library_id, physical_path, force=False):
        try:
            from services.scheduler_service import run_scan_job
            # 직접 함수 호출 (이미 Background 워커 스레드 위에서 도는 중)
            run_scan_job(db_type, db_path, library_id, physical_path, force=force)
        except Exception as e:
            self.log(f"Library scan failed: {e}")
            
    def _process_cover_scan(self, db_type, db_path, library_id, physical_path):
        try:
            from services.cover_scan_service import CoverScanService
            CoverScanService.run_cover_scan_job(db_type, db_path, library_id, physical_path)
        except Exception as e:
            self.log(f"Cover scan failed: {e}")

# 전역 싱글톤 인스턴스 노출
scanner_queue = ScannerQueue()
