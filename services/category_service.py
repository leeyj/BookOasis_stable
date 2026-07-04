# -*- coding: utf-8 -*-
import database

class CategoryService:
    @staticmethod
    def get_libraries(db_type, user_id=None, role=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        if user_id and role != 'admin':
            # 일반 유저는 권한 테이블 조인하여 has_access = 1 인 카테고리만 필터
            cursor.execute("""
                SELECT l.id, l.name, l.physical_path, l.is_remote, l.vfs_refresh_before_scan, l.rclone_rc_url 
                FROM libraries l
                JOIN user_category_permissions p ON l.id = p.library_id
                WHERE p.user_id = ? AND p.has_access = 1
                ORDER BY l.name ASC
            """, (user_id,))
        else:
            cursor.execute("SELECT id, name, physical_path, is_remote, vfs_refresh_before_scan, rclone_rc_url FROM libraries ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [{
            'id': r['id'], 
            'name': r['name'], 
            'physical_path': r['physical_path'],
            'is_remote': r['is_remote'] or 0,
            'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
            'rclone_rc_url': r['rclone_rc_url'] or ''
        } for r in rows]

    @staticmethod
    def _clean_physical_path(raw_path):
        if not raw_path: return ""
        lines = [line.strip() for line in str(raw_path).replace('\r', '').split('\n')]
        return '\n'.join([line for line in lines if line])

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote=0, rclone_rc_url=None):
        # 이름 방어 로직: 양끝 공백 제거, 빈 이름 거부, 최대 100자 제한
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO libraries (name, physical_path, is_remote, rclone_rc_url) VALUES (?, ?, ?, ?)",
            (name, physical_path, is_remote, rclone_rc_url)
        )
        library_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return library_id

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote=0, rclone_rc_url=None):
        # 이름 방어 로직: 양끝 공백 제거, 빈 이름 거부, 최대 25자 제한
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE libraries SET name = ?, physical_path = ?, is_remote = ?, rclone_rc_url = ? WHERE id = ?",
            (name, physical_path, is_remote, rclone_rc_url, library_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def delete_library(db_type, library_id):
        # 관련 리포트 파일 연쇄 영구 소거
        try:
            from utils.report_helper import delete_all_reports
            delete_all_reports(library_id)
        except Exception as e:
            print(f"[CategoryService ERROR] Bulk report file removal failed: {e}")

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM books WHERE library_id = ?", (library_id,))
        book_ids = [r['id'] for r in cursor.fetchall()]

        if book_ids:
            placeholders = ','.join('?' for _ in book_ids)
            cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({placeholders})", book_ids)
            cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({placeholders})", book_ids)
            cursor.execute(f"DELETE FROM books WHERE library_id = ?", (library_id,))

        cursor.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
        conn.commit()
        conn.close()

        # 대량 삭제(Delete) 완료 후 물리 공간 회수 및 DB 성능 향상을 위해 백그라운드로 튜닝 구동
        import threading
        t = threading.Thread(target=database.optimize_database, args=(db_type,))
        t.daemon = True
        t.start()
