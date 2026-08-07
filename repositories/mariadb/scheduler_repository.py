# -*- coding: utf-8 -*-
"""
scheduler_repository.py – MariaDB 전용 백그라운드 스캔 스케줄링 및 라이브러리 스캔 상태 관리 데이터 액세스 레이어
"""
import database

class SchedulerRepository:
    @staticmethod
    def update_task_stage(task_key, stage):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET stage = %s WHERE task_key = %s AND status = 'running'",
                (stage, task_key)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_interrupted_libraries(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path FROM libraries WHERE scan_status = 'interrupted'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_library_scan_status(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT scan_status FROM libraries WHERE id = %s", (library_id,))
        row = cursor.fetchone()
        conn.close()
        return row['scan_status'] if row else None

    @staticmethod
    def update_library_scan_status(db_type, library_id, status):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE libraries SET scan_status = %s WHERE id = %s", (status, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_scheduled_libraries(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path, cron_schedule FROM libraries WHERE cron_schedule IS NOT NULL AND cron_schedule != ''")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_library_vfs_config(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_remote, vfs_refresh_before_scan, rclone_rc_url FROM libraries WHERE id = %s",
            (library_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_library_physical_path(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT physical_path FROM libraries WHERE id = %s", (int(library_id),))
        row = cursor.fetchone()
        conn.close()
        return row['physical_path'] if row else None

    @staticmethod
    def update_library_scan_success(db_type, library_id, end_str):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries 
                SET scan_status = 'ready', 
                    last_scanned_at = %s 
                WHERE id = %s
            """, (end_str, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
