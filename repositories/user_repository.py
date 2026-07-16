# -*- coding: utf-8 -*-
"""
user_repository.py – 사용자 계정(users) 및 카테고리 권한(user_category_permissions) 전담 데이터 액세스 레이어
"""
import database

class UserRepository:
    @staticmethod
    def find_by_username(db_type, username):
        """사용자 이름 기반 계정 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role, is_default_password, has_adult_access FROM users WHERE username = ?", 
            (username,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def find_by_id(db_type, user_id):
        """사용자 ID 기반 계정 정보 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role, is_default_password, has_adult_access FROM users WHERE id = ?", 
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
            "SELECT id, username, role, is_default_password, has_adult_access, created_at FROM users ORDER BY id ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def count_by_role(db_type, role):
        """특정 권한(role) 사용자 수 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = ?", (role,))
        row = cursor.fetchone()
        conn.close()
        return int(row['cnt']) if row else 0

    @staticmethod
    def add_user(db_type, username, password_hash, role, has_adult_access):
        """신규 사용자 등록 및 카테고리 권한 기본 매핑 시딩"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_default_password, has_adult_access) VALUES (?, ?, ?, 1, ?)", 
                (username, password_hash, role, has_adult_access)
            )
            user_id = cursor.lastrowid
            
            # 신규 사용자 생성 시 모든 라이브러리 카테고리 권한 기본적으로 1(허용) 처리
            cursor.execute("SELECT id FROM libraries")
            lib_ids = [row['id'] for row in cursor.fetchall()]
            for lid in lib_ids:
                cursor.execute(
                    "INSERT OR IGNORE INTO user_category_permissions (user_id, library_id, has_access) VALUES (?, ?, 1)", 
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
            cursor.execute("DELETE FROM user_category_permissions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
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
                "UPDATE users SET password_hash = ?, is_default_password = 0 WHERE id = ?", 
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
        """관리자에 의한 비밀번호 강제 재설정 (기본값: is_default_password = 1)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET password_hash = ?, is_default_password = ? WHERE id = ?", 
                (new_password_hash, set_default, user_id)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
