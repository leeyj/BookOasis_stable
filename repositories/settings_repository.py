# -*- coding: utf-8 -*-
"""
settings_repository.py – 시스템 환경설정(settings) 테이블 조회 및 업데이트 전담 데이터 액세스 레이어
"""
import database

class SettingsRepository:
    @staticmethod
    def get_value(db_type, key):
        """특정 설정 키에 대응하는 값 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None

    @staticmethod
    def set_value(db_type, key, value):
        """설정 키-값 등록 및 갱신 (UPSERT)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_all_settings(db_type):
        """지정된 데이터베이스의 모든 설정 딕셔너리 반환"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}
