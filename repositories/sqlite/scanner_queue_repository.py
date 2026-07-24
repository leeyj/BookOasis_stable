# -*- coding: utf-8 -*-
"""
scanner_queue_repository.py – 백그라운드 스캐너 작업 대기열(scanner_tasks) 삽입, 처리, 갱신 트랜잭션 전담 데이터 액세스 레이어
"""
import datetime
import database

class ScannerQueueRepository:
    @staticmethod
    def startup_cleanup_ghost_tasks():
        """
        스캐너 워커 단독 재시작 시 기존 대기열(pending)을 지우지 않고 보존하며,
        중단되었던 태스크(running/exit_pending)를 pending으로 복원하여 1순위로 이어서 수행하게 합니다.
        """
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            # 1. 중단된 running/exit_pending 태스크를 pending으로 복원 (큐 지우지 않음!)
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'pending', stage = '워커 재기동 후 자동 이어서 수행' WHERE status IN ('running', 'exit_pending')"
            )
            restored_count = cursor.rowcount

            # 2. scanning 상태였던 카테고리를 interrupted로 안전 변경
            cursor.execute("UPDATE libraries SET scan_status = 'interrupted' WHERE scan_status = 'scanning'")
            cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE scan_status = 'cancelling'")

            conn.commit()

            print(f"[Queue-Startup] 🔄 Restored {restored_count} interrupted tasks to pending for Auto-Resume on worker restart.")
            return restored_count
        except Exception as e:
            conn.rollback()
            print(f"[Queue-Startup WARNING] Failed to restore scan queue on worker startup: {e}")
            return 0
        finally:
            conn.close()

    @staticmethod
    def cleanup_stale_tasks(timeout_seconds=None):
        """
        시간 기반 타임아웃이 아닌, OS 상에서 실제 워커 프로세스(worker_pid)의 생존 여부(Process Alive Check)를
        직접 검사하여 프로세스가 이미 소멸한 유령(Orphan/Stale) 태스크만 안전하게 정화합니다.
        PID 정보가 누락되었거나 소멸된 running/exit_pending 태스크를 즉시 pending으로 정화합니다.
        """
        import os
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("SELECT id, worker_pid FROM scanner_tasks WHERE status IN ('running', 'exit_pending')")
            rows = cursor.fetchall()
            cleaned_count = 0
            
            for row in rows:
                pid = row['worker_pid']
                is_alive = False
                if pid:
                    try:
                        import psutil
                        is_alive = psutil.pid_exists(pid)
                    except ImportError:
                        try:
                            os.kill(pid, 0)
                            is_alive = True
                        except (OSError, ProcessLookupError, ValueError):
                            is_alive = False

                # PID 정보가 없거나 프로세스가 OS에서 완전히 소멸된 경우 pending 상태로 복구하여 자동 재개(Auto-Resume) 보장
                if not is_alive:
                    cursor.execute(
                        """
                        UPDATE scanner_tasks 
                        SET status = 'pending', stage = 'Worker restarted (Auto-Resumed)', worker_pid = NULL
                        WHERE id = ?
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
        """특정 작업 키에 대응하는 태스크 정보 조회 (동일 키 중 최신 행 우선 반환)"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        # [버그픽스] ORDER BY id DESC LIMIT 1: 동일 task_key 레코드가 여러 개 쌓인 경우
        # 과거의 completed/failed 행이 먼저 반환되어 중복 판정이 오염되는 것을 방지.
        cursor.execute(
            "SELECT id, status FROM scanner_tasks WHERE task_key = ? ORDER BY id DESC LIMIT 1",
            (task_key,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def insert_task(task_type, task_key, kwargs_json, now_str):
        """신규 태스크 대기열 추가"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO scanner_tasks (task_type, task_key, status, kwargs, enqueue_at)
                VALUES (?, ?, 'pending', ?, ?)
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
        """완료되었거나 취소된 기존 태스크(또는 force_requeue 시 running/exit_pending 상태 포함)를 다시 pending으로 대기 상태 갱신"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            if force_requeue:
                where_clause = "WHERE id = ?"
            else:
                where_clause = "WHERE id = ? AND status NOT IN ('pending', 'running')"

            cursor.execute(
                f"""
                UPDATE scanner_tasks
                SET task_type = ?,
                    status = 'pending',
                    kwargs = ?,
                    stage = NULL,
                    enqueue_at = ?,
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
        """태스크 상태(예: exit_pending, pending 등) 임의 변경"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET status = ?, stage = ?, error_message = ? WHERE id = ?",
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
        """현재 실행(running/exit_pending) 중이거나 대기(pending) 상태인 대기열 현황 조회 (DB 락 대비 5회 백오프 재시도)"""
        import time
        for attempt in range(1, 6):
            try:
                conn = database.get_connection('general')
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 10000;")
                
                # running 또는 exit_pending 작업 조회
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

                # pending 작업 조회
                if running_id:
                    cursor.execute(
                        """
                        SELECT id, task_type, task_key, kwargs, enqueue_at, stage 
                        FROM scanner_tasks 
                        WHERE status = 'pending' AND id != ?
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
                if attempt < 5:
                    time.sleep(0.2 * attempt)
                else:
                    print(f"[QueueRepo WARNING] fetch_queue_status failed after 5 retries: {e}")
                    return None, []


    @staticmethod
    def clear_pending_tasks(now_str):
        """대기열에 적재된 모든 pending 작업을 cancelled로 일괄 취소"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = ? WHERE status = 'pending'",
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
        """특정 태스크 취소 (pending 및 running 상태 모두 취소 처리 및 libraries.scan_status 갱신)"""
        import json
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            # 1. 취소 대상 태스크 정보 조회
            cursor.execute(
                "SELECT id, task_type, kwargs, status FROM scanner_tasks WHERE task_key = ? AND status IN ('pending', 'running')",
                (task_key,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            task_id = row['id']
            task_type = row['task_type']
            kwargs_str = row['kwargs']

            # 2. scanner_tasks 상태를 cancelled 로 갱신
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = ? WHERE id = ?",
                (now_str, task_id)
            )
            success = cursor.rowcount > 0

            # 3. library_scan 인 경우 해당 라이브러리의 scan_status를 'cancelling'으로 변경하여 진행 중인 스캐너 엔진 즉시 중단 유도
            if task_type == 'library_scan' and kwargs_str:
                try:
                    kwargs = json.loads(kwargs_str)
                    lib_id = kwargs.get('library_id')
                    db_type = kwargs.get('db_type', 'general')
                    if lib_id:
                        import time
                        for lib_attempt in range(1, 6):
                            try:
                                lib_conn = database.get_connection(db_type)
                                lib_cur = lib_conn.cursor()
                                lib_cur.execute("PRAGMA busy_timeout = 10000;")
                                lib_cur.execute("UPDATE libraries SET scan_status = 'cancelling' WHERE id = ?", (lib_id,))
                                lib_conn.commit()
                                lib_conn.close()
                                break
                            except Exception as lib_retry_err:
                                if lib_attempt < 5:
                                    time.sleep(0.3 * lib_attempt)
                                else:
                                    print(f"[Queue-Cancel Warning] Failed to update library scan_status to cancelling: {lib_retry_err}")
                except Exception as lib_err:
                    print(f"[Queue-Cancel Warning] Parse error in cancel task kwargs: {lib_err}")

            conn.commit()

            # 4. 영구 scan_history 테이블에 취소 이력 저장
            try:
                cursor.execute("SELECT enqueue_at, started_at FROM scanner_tasks WHERE id = ?", (task_id,))
                t_row = cursor.fetchone()
                enq_at = t_row['enqueue_at'] if t_row else now_str
                str_at = t_row['started_at'] if t_row else now_str
                ScannerQueueRepository.record_scan_history(
                    task_type, task_key, 'cancelled', kwargs_str,
                    enq_at, str_at, now_str, "User cancelled scan from queue UI"
                )
                cursor.execute("DELETE FROM scanner_tasks WHERE id = ?", (task_id,))
                conn.commit()
            except Exception:
                pass

            return success
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_pending_task_by_key(task_key):
        """특정 작업 키의 pending/exit_pending 태스크 상세 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, task_key, kwargs 
            FROM scanner_tasks 
            WHERE task_key = ? AND status IN ('pending', 'exit_pending')
            ORDER BY id DESC LIMIT 1
            """,
            (task_key,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_next_pending_task():
        """우선순위에 맞추어 대기 중인 다음 첫 번째 태스크 가져오기"""
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
        """경합 선점을 극복하여 태스크를 running 상태로 원자적 갱신 시도 (워커 PID 함께 기록)"""
        import os
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            # 방어선: 이미 실행(running) 중인 다른 작업이 존재하는 경우 동시 선점 금지 (Single-Worker Lock 보장)
            cursor.execute("SELECT id, worker_pid FROM scanner_tasks WHERE status = 'running' AND id != ?", (task_id,))
            already_running = cursor.fetchone()
            if already_running:
                pid = already_running['worker_pid']
                is_alive = False
                if pid:
                    try:
                        import psutil
                        is_alive = psutil.pid_exists(pid)
                    except ImportError:
                        try:
                            os.kill(pid, 0)
                            is_alive = True
                        except (OSError, ProcessLookupError, ValueError):
                            is_alive = False
                if is_alive:
                    return False
                else:
                    # 유령 태스크 감지 시 즉시 pending 처리 후 현 태스크 선점 계속
                    cursor.execute("UPDATE scanner_tasks SET status = 'pending', worker_pid = NULL WHERE id = ?", (already_running['id'],))

            worker_pid = os.getpid()
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'running', started_at = ?, worker_pid = ? WHERE id = ? AND status IN ('pending', 'exit_pending')",
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
        """독립된 scan_history 영구 이력 테이블에 스캔 결과 기록"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout = 10000;")
            cursor.execute(
                """
                INSERT INTO scan_history (task_type, task_key, status, kwargs, enqueue_at, started_at, finished_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        """스캔 성공(completed) 또는 실패(failed) 상태 기록 및 영구 scan_history 이력 저장"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout = 10000;")
            cursor.execute("SELECT task_type, task_key, kwargs, enqueue_at, started_at FROM scanner_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            
            status = 'failed' if error_message else 'completed'
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
            conn.commit()

            if row:
                ScannerQueueRepository.record_scan_history(
                    row['task_type'], row['task_key'], status, row['kwargs'],
                    row['enqueue_at'], row['started_at'], finished_str, error_message
                )

            # 스캔 완료/실패 후 영구 이력 저장이 끝났으므로 대기열 테이블에서 해당 태스크 완전 삭제 (100% 큐 Clean)
            cursor.execute("DELETE FROM scanner_tasks WHERE id = ?", (task_id,))
            conn.commit()

            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_scan_history(limit=20):
        """
        레이지 스캔(lazy_scan)을 제외한 영구 scan_history 테이블의 최근 스캔 이력 목록을 조회합니다.
        카테고리명, 스캔 시작/종료 시각, 스캔 종류(수동/크론), 상태 등을 반환합니다.
        """
        import json
        conn_gen = database.get_connection('general')
        cursor_gen = conn_gen.cursor()
        
        # 카테고리 ID -> 카테고리명 맵 사전 구축 (general/adult 양쪽)
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
                LIMIT ?
                """,
                (limit,)
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
                
                # 카테고리명 조인 매핑
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
