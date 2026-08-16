# -*- coding: utf-8 -*-
"""
user_repository.py – MariaDB 전용 사용자 계정(users) 및 카테고리 권한(user_category_permissions) 데이터 액세스 레이어
"""
import database

class UserRepository:
    @staticmethod
    def find_by_username(db_type, username):
        """사용자 이름 기반 계정 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role, is_default_password, has_adult_access, has_audiobook_access FROM users WHERE username = %s", 
            (username,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_user_favorite_book_ids(db_type, user_id):
        """사용자의 즐겨찾기 도서 ID 세트 조회"""
        if not user_id:
            return set()
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT book_id FROM user_favorites WHERE user_id = %s", (user_id,))
            rows = cursor.fetchall()
            return {r['book_id'] for r in rows}
        except Exception:
            return set()
        finally:
            conn.close()

    @staticmethod
    def find_by_id(db_type, user_id):
        """사용자 ID 기반 계정 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role, is_default_password, has_adult_access, has_audiobook_access FROM users WHERE id = %s", 
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all_users(db_type):
        """전체 사용자 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, role, is_default_password, has_adult_access, has_audiobook_access, created_at FROM users ORDER BY id ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def count_by_role(db_type, role):
        """특정 권한(role) 사용자 수 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = %s", (role,))
        row = cursor.fetchone()
        conn.close()
        return int(row['cnt']) if row else 0

    @staticmethod
    def add_user(db_type, username, password_hash, role, has_adult_access, has_audiobook_access=1, has_video_access=1):
        """신규 사용자 등록 및 카테고리 권한 기본 매핑 시딩"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_default_password, has_adult_access, has_audiobook_access, has_video_access) VALUES (%s, %s, %s, 1, %s, %s, %s)",
                (username, password_hash, role, has_adult_access, has_audiobook_access, has_video_access)
            )
            user_id = cursor.lastrowid
            
            cursor.execute("SELECT id FROM libraries")
            lib_ids = [row['id'] for row in cursor.fetchall()]
            for lid in lib_ids:
                cursor.execute(
                    "INSERT IGNORE INTO user_category_permissions (user_id, library_id, has_access) VALUES (%s, %s, 1)", 
                    (user_id, lid)
                )
            conn.commit()
            return user_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_user(db_type, user_id):
        """사용자 정보 및 권한 연쇄 삭제"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM user_category_permissions WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_password(db_type, user_id, new_password_hash):
        """비밀번호 갱신 및 초기 비밀번호 상태 복구(0)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET password_hash = %s, is_default_password = 0 WHERE id = %s", 
                (new_password_hash, user_id)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def admin_reset_password(db_type, user_id, new_password_hash, set_default=1):
        """관리자에 의한 비밀번호 강제 재설정"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET password_hash = %s, is_default_password = %s WHERE id = %s", 
                (new_password_hash, set_default, user_id)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_all_category_permissions(db_type):
        """전체 카테고리 사용자 접근 권한 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, library_id, has_access FROM user_category_permissions")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_category_permission(db_type, user_id, library_id, has_access):
        """특정 사용자의 카테고리 접근 권한 업데이트 (MariaDB UPSERT)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO user_category_permissions (user_id, library_id, has_access)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE has_access = VALUES(has_access)
            """, (user_id, library_id, has_access))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_adult_access(db_type, user_id, has_adult_access):
        """사용자별 성인도서 접근 권한 갱신"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET has_adult_access = %s WHERE id = %s", (has_adult_access, user_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_audiobook_access(db_type, user_id, has_audiobook_access):
        """사용자별 오디오북 접근 권한 갱신"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET has_audiobook_access = %s WHERE id = %s", (has_audiobook_access, user_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
