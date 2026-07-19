# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import subprocess
import datetime
import database

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
        conn = None
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()

            # task_key가 UNIQUE이므로 과거 완료/실패 이력은 재사용하고,
            # 현재 pending/running 인 작업만 중복으로 간주합니다.
            cursor.execute(
                "SELECT id, status FROM scanner_tasks WHERE task_key = ?",
                (task_key,)
            )
            existing = cursor.fetchone()
            if existing and existing['status'] in ('pending', 'running'):
                self.log(f"Task '{task_key}' is already in state '{existing['status']}'. Rejecting duplicate.")
                return False

            kwargs_json = json.dumps(kwargs, ensure_ascii=False)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if existing:
                cursor.execute(
                    """
                    UPDATE scanner_tasks
                    SET task_type = ?,
                        status = 'pending',
                        kwargs = ?,
                        stage = NULL,
                        enqueue_at = ?,
                        started_at = NULL,
                        finished_at = NULL,
                        error_message = NULL
                    WHERE id = ?
                      AND status NOT IN ('pending', 'running')
                    """,
                    (task_type, kwargs_json, now_str, existing['id'])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO scanner_tasks (task_type, task_key, status, kwargs, enqueue_at)
                    VALUES (?, ?, 'pending', ?, ?)
                    """,
                    (task_type, task_key, kwargs_json, now_str)
                )

            if cursor.rowcount == 0:
                conn.rollback()
                self.log(
                    f"Task '{task_key}' was not enqueued because it is already pending/running "
                    f"(or no DB row was written)."
                )
                return False

            conn.commit()
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
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def add_task(self, task_type, **kwargs):
        """webhook 등에서 호출하는 하위 호환성용 메서드"""
        return self.enqueue(task_type, **kwargs)

    def get_queue_status(self):
        """현재 실행 중인 작업과 큐 대기열의 상태를 반환합니다."""
        status = {
            'running': None,
            'pending': []
        }
        conn = None
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            
            # running 작업 조회 (최대 1개)
            cursor.execute(
                "SELECT task_type, task_key, kwargs, enqueue_at, started_at, stage FROM scanner_tasks WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
            )
            row_run = cursor.fetchone()
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

            # pending 작업 조회 (정렬 규칙 적용: 일반 스캔이 lazy_scan보다 항상 먼저 진행되도록 함)
            cursor.execute(
                """
                SELECT task_type, task_key, kwargs, enqueue_at, stage 
                FROM scanner_tasks 
                WHERE status = 'pending' 
                ORDER BY CASE WHEN task_type = 'lazy_scan' THEN 2 ELSE 1 END, id ASC
                """
            )
            rows_pending = cursor.fetchall()
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
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
        return status

    def clear_queue(self):
        """대기열에 있는 모든 작업을 취소(cancelled) 처리합니다."""
        conn = None
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = ? WHERE status = 'pending'",
                (now_str,)
            )
            count = cursor.rowcount
            conn.commit()
            self.log(f"Queue cleared. Cancelled {count} pending items in DB.")
            return count
        except Exception as e:
            self.log(f"Failed to clear queue: {e}")
            return 0
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def cancel_pending_task(self, task_key):
        """대기열에 있는 특정 작업 1건을 취소(cancelled) 처리합니다."""
        if not task_key:
            return False
        conn = None
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = ? WHERE task_key = ? AND status = 'pending'",
                (now_str, task_key)
            )
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                self.log(f"Pending task '{task_key}' cancelled successfully in DB.")
            return success
        except Exception as e:
            self.log(f"Failed to cancel pending task: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass


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

    while True:
        conn = None
        try:
            # Redis가 사용 가능한 경우 BRPOP으로 작업 대기
            task_key_popped = None
            try:
                from utils.redis_helper import redis_brpop
                # 3초 동안 블로킹 대기. (SQLite 폴링 간격 3초와 주기를 맞춤)
                task_key_popped = redis_brpop("queue:scanner", timeout=3)
            except Exception:
                pass

            conn = database.get_connection('general')
            cursor = conn.cursor()
            
            task = None
            if task_key_popped:
                # Redis에서 팝된 특정 작업 정보를 우선 조회
                cursor.execute(
                    """
                    SELECT id, task_type, task_key, kwargs 
                    FROM scanner_tasks 
                    WHERE task_key = ? AND status = 'pending'
                    """,
                    (task_key_popped,)
                )
                task = cursor.fetchone()

            # Redis 팝 결과가 없거나 DB 조회 실패 시 Fallback으로 SQLite 전체 pending 조회
            if not task:
                cursor.execute(
                    """
                    SELECT id, task_type, task_key, kwargs 
                    FROM scanner_tasks 
                    WHERE status = 'pending' 
                    ORDER BY CASE WHEN task_type = 'lazy_scan' THEN 2 ELSE 1 END, id ASC
                    LIMIT 1
                    """
                )
                task = cursor.fetchone()
            
            if not task:
                conn.close()
                conn = None
                
                # Redis가 살아있을 때는 이미 BRPOP으로 3초 대기했거나 즉시 반응했으므로 추가 sleep 최소화.
                # Redis 미연결(Fallback) 시 3초 간격 대기
                from utils.redis_helper import get_redis_client
                if not get_redis_client():
                    time.sleep(3.0)
                else:
                    time.sleep(0.5)
                continue
                
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
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'running', started_at = ? WHERE id = ? AND status = 'pending'",
                (now_str, task_id)
            )
            conn.commit()
            
            # 업데이트가 성공했는지 검증 (다른 프로세스가 먼저 선점하지 않았는지)
            if cursor.rowcount == 0:
                conn.close()
                conn = None
                continue
                
            conn.close()
            conn = None
            
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
            conn = database.get_connection('general')
            cursor = conn.cursor()
            finished_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if error_message:
                cursor.execute(
                    "UPDATE scanner_tasks SET status = 'failed', finished_at = ?, error_message = ? WHERE id = ?",
                    (finished_str, error_message, task_id)
                )
            else:
                cursor.execute(
                    "UPDATE scanner_tasks SET status = 'completed', finished_at = ? WHERE id = ?",
                    (finished_str, task_id)
                )
                # 스캔 완료 시 신규 추가 도서 대시보드 캐시 무효화
                try:
                    from utils.redis_helper import redis_delete_pattern
                    target_db = kwargs.get('db_type', 'general')
                    redis_delete_pattern(f"cache:recent_added:{target_db}:*")
                except Exception as cache_err:
                    sq.log(f"Failed to invalidate recently_added cache: {cache_err}")
            conn.commit()
            sq.log(f"Finished task: {task_key}.")
            
        except Exception as loop_err:
            sq.log(f"Error in worker loop: {loop_err}")
            time.sleep(5.0)
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass


def _process_lazy_scan(sq):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(BASE_DIR, 'tools', 'lazy_scanner.py')
    
    # 동기식(block)으로 실행하여 프로세스가 끝날 때까지 기다림
    proc = subprocess.run(
        [sys.executable, script_path],
        cwd=BASE_DIR,
        check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"lazy_scanner exited with code {proc.returncode}")

def _process_library_scan(sq, **kwargs):
    from services.scheduler_service import run_scan_job
    # 가변 인자 딕셔너리를 그대로 포워딩하여 호출
    run_scan_job(**kwargs)
    
def _process_cover_scan(sq, **kwargs):
    from services.cover_scan_service import CoverScanService
    CoverScanService.run_cover_scan_job(**kwargs)


# 하위 호환성 유지를 위한 전역 싱글톤 인스턴스
scanner_queue = ScannerQueue()
