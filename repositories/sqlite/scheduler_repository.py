# -*- coding: utf-8 -*-
"""
scheduler_repository.py – 백그라운드 스캔 스케줄링 및 라이브러리 스캔 상태(scan_status) 관리 데이터 액세스 레이어
"""
import database

class SchedulerRepository:
    @staticmethod
    def update_task_stage(task_key, stage):
        """실행 중인 특정 스캔 태스크의 진행 단계(stage) 정보를 원자적 업데이트"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE scanner_tasks SET stage = ? WHERE task_key = ? AND status = 'running'",
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
        """비정상 종료(interrupted) 상태인 라이브러리 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path FROM libraries WHERE scan_status = 'interrupted'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_library_scan_status(db_type, library_id):
        """라이브러리의 스캔 상태(scan_status) 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.close()
        return row['scan_status'] if row else None

    @staticmethod
    def update_library_scan_status(db_type, library_id, status):
        """라이브러리의 스캔 상태(scan_status) 단순 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE libraries SET scan_status = ? WHERE id = ?", (status, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_scheduled_libraries(db_type):
        """크론 스케줄이 설정된 라이브러리 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path, cron_schedule FROM libraries WHERE cron_schedule IS NOT NULL AND cron_schedule != ''")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_library_vfs_config(db_type, library_id):
        """라이브러리의 VFS 사전 갱신 옵션 및 RC URL 설정 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT vfs_refresh_before_scan, rclone_rc_url FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_library_physical_path(db_type, library_id):
        """라이브러리의 최신 물리 경로 실시간 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (int(library_id),))
        row = cursor.fetchone()
        conn.close()
        return row['physical_path'] if row else None

    @staticmethod
    def update_library_scan_success(db_type, library_id, end_str):
        """라이브러리 스캔 성공 상태 및 마지막 완료 시간 기록"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries 
                SET scan_status = 'ready', 
                    last_scanned_at = ? 
                WHERE id = ?
            """, (end_str, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
