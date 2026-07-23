# -*- coding: utf-8 -*-
"""
scanner_queue_repository.py – 백그라운드 스캐너 작업 대기열(scanner_tasks) 삽입, 처리, 갱신 트랜잭션 전담 데이터 액세스 레이어
"""
import datetime
import database

class ScannerQueueRepository:
    @staticmethod
    def cleanup_stale_tasks(timeout_seconds=None):
        """
        시간 기반 타임아웃이 아닌, OS 상에서 실제 워커 프로세스(worker_pid)의 생존 여부(Process Alive Check)를
        직접 검사하여 프로세스가 이미 소멸한 유령(Orphan/Stale) 태스크만 안전하게 정화합니다.
        프로세스가 살아서 작동 중인 경우 스캔 시간이 수 시간 이상 걸려도 절대로 취소하지 않습니다.
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
                # PID 정보가 없는 과거 레코드는 생킵
                if not pid:
                    continue

                is_alive = False
                try:
                    import psutil
                    is_alive = psutil.pid_exists(pid)
                except ImportError:
                    try:
                        os.kill(pid, 0)
                        is_alive = True
                    except (OSError, ProcessLookupError, ValueError):
                        is_alive = False

                # 프로세스가 OS에서 완전히 소멸된 경우 pending 상태로 복구하여 자동 재개(Auto-Resume) 보장
                if not is_alive:
                    cursor.execute(
                        """
                        UPDATE scanner_tasks 
                        SET status = 'pending', stage = 'Worker restarted (Auto-Resumed)' 
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
        """현재 실행(running/exit_pending) 중이거나 대기(pending) 상태인 대기열 현황 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        
        # running 또는 exit_pending(Lazy Scanner 재기동 대기 중) 작업 조회 (최대 1개)
        cursor.execute(
            """
            SELECT id, task_type, task_key, kwargs, enqueue_at, started_at, stage, status 
            FROM scanner_tasks 
            WHERE status IN ('running', 'exit_pending') 
            ORDER BY CASE WHEN status = 'running' THEN 1 ELSE 2 END, started_at DESC 
            LIMIT 1
            """
        )
        row_run = cursor.fetchone()
        running_task = dict(row_run) if row_run else None

        running_id = running_task['id'] if running_task else None

        # pending 작업 조회 (일반 스캔 선진행 우선순위 규칙 적용, 현재 실행 중인 태스크 ID 제외)
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
        """특정 태스크 취소"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'cancelled', finished_at = ? WHERE task_key = ? AND status = 'pending'",
                (now_str, task_key)
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
    def update_task_result(task_id, finished_str, error_message=None):
        """스캔 성공(completed) 또는 실패(failed) 상태 기록"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
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
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_scan_history(limit=20):
        """
        레이지 스캔(lazy_scan)을 제외한 최근 스캔 이력 목록을 조회합니다.
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
                FROM scanner_tasks
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
                trigger_type = kwargs.get('trigger_type') or kwargs.get('trigger') or ('cron' if kwargs.get('is_cron') else None)
                
                if not trigger_type:
                    if kwargs.get('is_cron') or 'cron' in item.get('task_key', ''):
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
