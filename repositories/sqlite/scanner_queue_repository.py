# -*- coding: utf-8 -*-
"""
scanner_queue_repository.py – 백그라운드 스캐너 작업 대기열(scanner_tasks) 삽입, 처리, 갱신 트랜잭션 전담 데이터 액세스 레이어
"""
import database

class ScannerQueueRepository:
    @staticmethod
    def get_task_by_key(task_key):
        """특정 작업 키에 대응하는 태스크 정보 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM scanner_tasks WHERE task_key = ?", (task_key,))
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
        """현재 실행(running) 중이거나 대기(pending) 상태인 대기열 현황 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        
        # running 작업 조회 (최대 1개)
        cursor.execute(
            "SELECT task_type, task_key, kwargs, enqueue_at, started_at, stage FROM scanner_tasks WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
        )
        row_run = cursor.fetchone()
        running_task = dict(row_run) if row_run else None

        # pending 작업 조회 (일반 스캔 선진행 우선순위 규칙 적용)
        cursor.execute(
            """
            SELECT task_type, task_key, kwargs, enqueue_at, stage 
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
        """특정 작업 키의 pending 태스크 상세 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, task_key, kwargs 
            FROM scanner_tasks 
            WHERE task_key = ? AND status = 'pending'
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
            WHERE status = 'pending' 
            ORDER BY CASE WHEN task_type = 'lazy_scan' THEN 2 ELSE 1 END, id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def try_acquire_task(task_id, now_str):
        """경합 선점을 극복하여 태스크를 running 상태로 원자적 갱신 시도"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET status = 'running', started_at = ? WHERE id = ? AND status = 'pending'",
                (now_str, task_id)
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
