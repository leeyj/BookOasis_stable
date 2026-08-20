# -*- coding: utf-8 -*-
"""
scanner_queue_repository.py – MariaDB 전용 백그라운드 스캐너 작업 대기열(scanner_tasks) 및 이력(scan_history) 데이터 액세스 레이어
"""
import datetime
import json
import database

class ScannerQueueRepository:
    @staticmethod
    def startup_cleanup_ghost_tasks():
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, worker_pid, task_type, kwargs FROM scanner_tasks WHERE status IN ('running', 'exit_pending')"
            )
            restored_count = 0
            interrupted_libraries = []
            from utils.process_helper import is_scanner_worker_pid_alive
            for row in cursor.fetchall():
                pid = row['worker_pid']
                is_alive = is_scanner_worker_pid_alive(pid)

                if is_alive:
                    continue

                cursor.execute(
                    """
                    UPDATE scanner_tasks
                    SET status = 'pending', stage = '워커 재기동 후 자동 이어서 수행', worker_pid = NULL
                    WHERE id = %s AND status IN ('running', 'exit_pending')
                    """,
                    (row['id'],)
                )
                restored_count += cursor.rowcount

                if row['task_type'] == 'library_scan' and row['kwargs']:
                    try:
                        kwargs = json.loads(row['kwargs'])
                        interrupted_libraries.append((kwargs.get('db_type', 'general'), kwargs.get('library_id')))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass

            conn.commit()

            for db_type, library_id in interrupted_libraries:
                if library_id is None:
                    continue
                try:
                    library_conn = database.get_connection(db_type)
                    library_cursor = library_conn.cursor()
                    library_cursor.execute(
                        "UPDATE libraries SET scan_status = 'interrupted' WHERE id = %s AND scan_status = 'scanning'",
                        (library_id,)
                    )
                    library_conn.commit()
                except Exception as library_error:
                    print(f"[Queue-Startup WARNING] Failed to mark library {library_id} interrupted: {library_error}")
                finally:
                    if 'library_conn' in locals():
                        library_conn.close()
                        del library_conn

            print(f"[Queue-Startup] Restored {restored_count} stale tasks to pending for auto-resume.")
            return restored_count
        except Exception as e:
            conn.rollback()
            print(f"[Queue-Startup WARNING] Failed to restore scan queue on worker startup: {e}")
            return 0
        finally:
            conn.close()

    @staticmethod
    def cleanup_stale_tasks(timeout_seconds=None):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, worker_pid FROM scanner_tasks WHERE status IN ('running', 'exit_pending')")
            rows = cursor.fetchall()
            cleaned_count = 0

            from utils.process_helper import is_scanner_worker_pid_alive
            for row in rows:
                pid = row['worker_pid']
                is_alive = is_scanner_worker_pid_alive(pid)

                if not is_alive:
                    cursor.execute(
                        """
                        UPDATE scanner_tasks 
                        SET status = 'pending', stage = 'Worker restarted (Auto-Resumed)', worker_pid = NULL
                        WHERE id = %s
                        """,
                        (row['id'],)
                    )
                    cleaned_count += cursor.rowcount

            conn.commit()
            return cleaned_count
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_task_by_key(task_key):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, status FROM scanner_tasks WHERE task_key = %s ORDER BY id DESC LIMIT 1",
            (task_key,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def insert_task(task_type, task_key, kwargs_json, now_str):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO scanner_tasks (task_type, task_key, status, kwargs, enqueue_at)
                VALUES (%s, %s, 'pending', %s, %s)
                """,
                (task_type, task_key, kwargs_json, now_str)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_task_to_pending(task_id, task_type, kwargs_json, now_str, force_requeue=False):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            if force_requeue:
                where_clause = "WHERE id = %s"
            else:
                where_clause = "WHERE id = %s AND status NOT IN ('pending', 'running')"

            cursor.execute(
                f"""
                UPDATE scanner_tasks
                SET task_type = %s,
                    status = 'pending',
                    kwargs = %s,
                    stage = NULL,
                    enqueue_at = %s,
                    started_at = NULL,
                    finished_at = NULL,
                    error_message = NULL
                {where_clause}
                """,
                (task_type, kwargs_json, now_str, task_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_task_status(task_id, status, stage=None, error_message=None):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET status = %s, stage = %s, error_message = %s WHERE id = %s",
                (status, stage, error_message, task_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def fetch_queue_status():
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, task_type, task_key, kwargs, enqueue_at, started_at, stage, status 
                FROM scanner_tasks 
                WHERE status IN ('running', 'exit_pending') 
                ORDER BY CASE WHEN status = 'running' THEN 1 ELSE 2 END, started_at ASC 
                LIMIT 1
                """
            )
            row_run = cursor.fetchone()
            running_task = dict(row_run) if row_run else None
            running_id = running_task['id'] if running_task else None

            if running_id:
                cursor.execute(
                    """
                    SELECT id, task_type, task_key, kwargs, enqueue_at, stage 
                    FROM scanner_tasks 
                    WHERE status = 'pending' AND id != %s
                    ORDER BY CASE WHEN task_type = 'lazy_scan' THEN 2 ELSE 1 END, id ASC
                    """,
                    (running_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, task_type, task_key, kwargs, enqueue_at, stage 
                    FROM scanner_tasks 
                    WHERE status = 'pending' 
                    ORDER BY CASE WHEN task_type = 'lazy_scan' THEN 2 ELSE 1 END, id ASC
                    """
                )
            rows_pending = cursor.fetchall()
            pending_tasks = [dict(row) for row in rows_pending]
            
            conn.close()
            return running_task, pending_tasks
        except Exception as e:
            print(f"[QueueRepo WARNING] fetch_queue_status failed: {e}")
            return None, []

    @staticmethod
    def clear_pending_tasks(now_str):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = %s WHERE status = 'pending'",
                (now_str,)
            )
            count = cursor.rowcount
            conn.commit()
            return count
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def cancel_task(task_key, now_str):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, task_type, kwargs, enqueue_at, started_at
                FROM scanner_tasks
                WHERE task_key = %s AND status IN ('pending', 'exit_pending')
                ORDER BY id DESC
                LIMIT 1
                """,
                (task_key,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            task_id = row['id']
            cursor.execute(
                """
                UPDATE scanner_tasks
                SET status = 'cancelled', finished_at = %s
                WHERE id = %s AND status IN ('pending', 'exit_pending')
                """,
                (now_str, task_id)
            )
            success = cursor.rowcount > 0
            conn.commit()
            if not success:
                return False

            try:
                ScannerQueueRepository.record_scan_history(
                    row['task_type'], task_key, 'cancelled', row['kwargs'],
                    row['enqueue_at'], row['started_at'], now_str, "User cancelled pending scan from queue UI"
                )
                cursor.execute("DELETE FROM scanner_tasks WHERE id = %s", (task_id,))
                conn.commit()
            except Exception as history_error:
                print(f"[Queue-Cancel Warning] Failed to archive cancelled task: {history_error}")

            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def request_cancel_running_task(task_key):
        """실행(running/exit_pending) 중인 태스크에 취소 플래그를 설정합니다. 워커가 자체적으로 확인 후 안전 중단합니다."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET cancel_requested = 1 WHERE task_key = %s AND status IN ('running', 'exit_pending')",
                (task_key,)
            )
            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def is_cancel_requested(task_id):
        """워커 루프가 주기적으로 폴링하여 사용자 취소 요청 여부를 확인합니다."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT cancel_requested FROM scanner_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            return bool(row and row['cancel_requested'])
        finally:
            conn.close()

    @staticmethod
    def mark_task_cancelled(task_id, finished_str, message="사용자 요청으로 중지되었습니다."):
        """실행 도중 취소 요청을 받아 중단된 태스크를 이력(cancelled)으로 이동합니다."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT task_type, task_key, kwargs, enqueue_at, started_at FROM scanner_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()

            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = %s WHERE id = %s",
                (finished_str, task_id)
            )
            conn.commit()

            if row:
                ScannerQueueRepository.record_scan_history(
                    row['task_type'], row['task_key'], 'cancelled', row['kwargs'],
                    row['enqueue_at'], row['started_at'], finished_str, message
                )

            cursor.execute("DELETE FROM scanner_tasks WHERE id = %s", (task_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_pending_task_by_key(task_key):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, task_key, kwargs 
            FROM scanner_tasks 
            WHERE task_key = %s AND status IN ('pending', 'exit_pending')
            ORDER BY id DESC LIMIT 1
            """,
            (task_key,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_next_pending_task():
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, task_key, kwargs 
            FROM scanner_tasks 
            WHERE status IN ('pending', 'exit_pending') 
            ORDER BY CASE WHEN status = 'exit_pending' THEN 1 ELSE 2 END,
                     CASE WHEN task_type = 'lazy_scan' THEN 2 ELSE 1 END, id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def try_acquire_task(task_id, now_str):
        import os
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, worker_pid FROM scanner_tasks WHERE status = 'running' AND id != %s", (task_id,))
            already_running = cursor.fetchone()
            if already_running:
                pid = already_running['worker_pid']
                from utils.process_helper import is_scanner_worker_pid_alive
                is_alive = is_scanner_worker_pid_alive(pid)
                if is_alive:
                    return False
                else:
                    cursor.execute("UPDATE scanner_tasks SET status = 'pending', worker_pid = NULL WHERE id = %s", (already_running['id'],))

            worker_pid = os.getpid()
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'running', started_at = %s, worker_pid = %s WHERE id = %s AND status IN ('pending', 'exit_pending')",
                (now_str, worker_pid, task_id)
            )
            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def record_scan_history(task_type, task_key, status, kwargs_str, enqueue_at, started_at, finished_at, error_message=None):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO scan_history (task_type, task_key, status, kwargs, enqueue_at, started_at, finished_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (task_type, task_key, status, kwargs_str, enqueue_at, started_at, finished_at, error_message)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[Queue-History Warning] Failed to record scan_history: {e}")
        finally:
            conn.close()

    @staticmethod
    def update_task_result(task_id, finished_str, error_message=None):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT task_type, task_key, kwargs, enqueue_at, started_at FROM scanner_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            
            status = 'failed' if error_message else 'completed'
            if error_message:
                cursor.execute(
                    "UPDATE scanner_tasks SET status = 'failed', finished_at = %s, error_message = %s WHERE id = %s",
                    (finished_str, error_message, task_id)
                )
            else:
                cursor.execute(
                    "UPDATE scanner_tasks SET status = 'completed', finished_at = %s WHERE id = %s",
                    (finished_str, task_id)
                )
            conn.commit()

            if row:
                ScannerQueueRepository.record_scan_history(
                    row['task_type'], row['task_key'], status, row['kwargs'],
                    row['enqueue_at'], row['started_at'], finished_str, error_message
                )

            cursor.execute("DELETE FROM scanner_tasks WHERE id = %s", (task_id,))
            conn.commit()

            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_scan_history(limit=20):
        import json
        conn_gen = database.get_connection('general')
        cursor_gen = conn_gen.cursor()
        
        lib_names = {}
        try:
            cursor_gen.execute("SELECT id, name FROM libraries")
            for r in cursor_gen.fetchall():
                lib_names[f"general_{r['id']}"] = r['name']
        except Exception:
            pass

        try:
            conn_adult = database.get_connection('adult')
            cursor_adult = conn_adult.cursor()
            cursor_adult.execute("SELECT id, name FROM libraries")
            for r in cursor_adult.fetchall():
                lib_names[f"adult_{r['id']}"] = r['name']
            conn_adult.close()
        except Exception:
            pass

        try:
            cursor_gen.execute(
                """
                SELECT id, task_type, task_key, status, kwargs, enqueue_at, started_at, finished_at, error_message
                FROM scan_history
                WHERE task_type != 'lazy_scan'
                ORDER BY id DESC
                LIMIT %s
                """,
                (int(limit),)
            )
            rows = cursor_gen.fetchall()
            
            history = []
            for r in rows:
                item = dict(r)
                kwargs = {}
                if item.get('kwargs'):
                    try:
                        kwargs = json.loads(item['kwargs'])
                    except Exception:
                        pass
                
                db_type = kwargs.get('db_type', 'general')
                library_id = kwargs.get('library_id')
                is_cron_val = kwargs.get('is_cron')
                trigger_val = kwargs.get('trigger_type') or kwargs.get('trigger')
                
                if trigger_val == 'cron' or is_cron_val is True:
                    trigger_type = 'cron'
                elif trigger_val == 'manual' or is_cron_val is False:
                    trigger_type = 'manual'
                elif 'cron' in str(item.get('task_key', '')).lower():
                    trigger_type = 'cron'
                else:
                    trigger_type = 'manual'
                
                lib_key = f"{db_type}_{library_id}"
                library_name = lib_names.get(lib_key)
                if not library_name:
                    if item['task_type'] == 'cover_scan':
                        library_name = f"표지 스캔 (DB: {db_type})"
                    elif library_id:
                        library_name = f"카테고리 #{library_id}"
                    else:
                        library_name = f"전체 스캔 ({db_type})"

                item['db_type'] = db_type
                item['library_id'] = library_id
                item['library_name'] = library_name
                item['trigger_type'] = trigger_type
                history.append(item)

            return history
        except Exception as e:
            print(f"[ScannerQueueRepository ERROR] get_scan_history failed: {e}")
            return []
        finally:
            conn_gen.close()
