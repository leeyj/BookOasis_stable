# -*- coding: utf-8 -*-
"""
settings_repository.py – MariaDB 전용 시스템 환경설정(settings) 데이터 액세스 레이어

adult/audiobook/video DB의 settings 테이블은 general과 항상 동일하거나(adult) 아무도
편집한 적 없는 시드 기본값(audiobook/video)만 갖고 있어 실질적으로 general DB 하나만
읽고 쓰면 충분하다. 그래서 연결은 항상 general DB로 고정한다.
"""
import database

class SettingsRepository:
    @staticmethod
    def get_value(key):
        """특정 설정 키에 대응하는 값 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT `value` FROM settings WHERE `key` = %s", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def set_value(key, value):
        """설정 키-값 등록 및 갱신 (UPSERT / REPLACE)"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                REPLACE INTO settings (`key`, `value`, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_all_settings():
        """general 데이터베이스의 모든 설정 딕셔너리 반환"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings")
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}

    @staticmethod
    def get_settings_by_prefix(prefix):
        """지정된 접두어로 시작하는 설정 키-값 딕셔너리 반환"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings WHERE `key` LIKE %s", (f"{prefix}%",))
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}

    @staticmethod
    def get_user_value(user_id, key):
        """특정 사용자의 개인화(override) 설정 값 조회"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT `value` FROM user_settings WHERE user_id = %s AND `key` = %s", (user_id, key))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def set_user_value(user_id, key, value):
        """사용자별 개인화(override) 설정 키-값 등록 및 갱신 (UPSERT)"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO user_settings (user_id, `key`, value, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = CURRENT_TIMESTAMP
            """, (user_id, key, value))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_all_user_settings(user_id):
        """특정 사용자의 모든 개인화(override) 설정 딕셔너리 반환"""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM user_settings WHERE user_id = %s", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}
