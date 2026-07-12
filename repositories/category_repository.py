# -*- coding: utf-8 -*-
"""
category_repository.py – 도서 카테고리(libraries) 정보 조회, 수정 및 스케줄 전담 데이터 액세스 레이어
"""
import database

class CategoryRepository:
    @staticmethod
    def get_all_libraries(db_type):
        """정렬된 전체 카테고리(라이브러리) 정보 반환"""
        conn = None
        try:
            conn = database.get_connection(db_type, wait_timeout=1.0)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color "
                "FROM libraries ORDER BY name ASC"
            )
            rows = cursor.fetchall()
        finally:
            if conn:
                conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_library_by_id(db_type, library_id):
        """특정 카테고리 단일 행 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color "
            "FROM libraries WHERE id = ?", (library_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_libraries_by_user_permissions(db_type, user_id):
        """일반 사용자 권한에 매핑된 카테고리 리스트 반환 (Join 쿼리)"""
        conn = None
        try:
            conn = database.get_connection(db_type, wait_timeout=1.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.id, l.name, l.physical_path, l.is_remote, l.vfs_refresh_before_scan, l.rclone_rc_url, l.icon, l.color 
                FROM libraries l
                JOIN user_category_permissions p ON l.id = p.library_id
                WHERE p.user_id = ? AND p.has_access = 1
                ORDER BY l.name ASC
            """, (user_id,))
            rows = cursor.fetchall()
        finally:
            if conn:
                conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon='fa-book', color='#94a3b8'):
        """신규 카테고리 추가"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO libraries (name, physical_path, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, physical_path, is_remote, is_remote, rclone_rc_url, icon, color)
            )
            library_id = cursor.lastrowid
            conn.commit()
            return library_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon='fa-book', color='#94a3b8'):
        """카테고리 메타 정보 수정"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE libraries SET name = ?, physical_path = ?, is_remote = ?, vfs_refresh_before_scan = ?, rclone_rc_url = ?, icon = ?, color = ? WHERE id = ?",
                (name, physical_path, is_remote, is_remote, rclone_rc_url, icon, color, library_id)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_library(db_type, library_id):
        """카테고리 및 하위 도서 연쇄 물리 삭제 트랜잭션"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM books WHERE library_id = ?", (library_id,))
            book_ids = [r['id'] for r in cursor.fetchall()]

            if book_ids:
                placeholders = ','.join('?' for _ in book_ids)
                cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({placeholders})", book_ids)
                cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({placeholders})", book_ids)
                cursor.execute("DELETE FROM books WHERE library_id = ?", (library_id,))

            cursor.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_schedule(db_type, library_id, cron_val, vfs_refresh, rclone_rc_url):
        """크론 스케줄 정보 갱신"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE libraries SET cron_schedule = ?, vfs_refresh_before_scan = ?, rclone_rc_url = ? WHERE id = ?", 
                (cron_val, vfs_refresh, rclone_rc_url, library_id)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
