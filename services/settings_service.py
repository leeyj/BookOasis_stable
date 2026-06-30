# -*- coding: utf-8 -*-
import database

class SettingsService:
    @staticmethod
    def get(key, default='', db_type='general'):
        """특정 설정 키의 값을 조회합니다."""
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row['value']
        except Exception as e:
            print(f"[SettingsService ERROR] get '{key}' failed: {e}")
        return default

    @staticmethod
    def set(key, value):
        """설정 키의 값을 양쪽 데이터베이스(general, adult) 모두에 저장/업데이트(UPSERT)합니다."""
        for db_type in ['general', 'adult']:
            try:
                conn = database.get_connection(db_type)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[SettingsService ERROR] set '{key}' (DB: {db_type}) failed: {e}")
        return True

    @staticmethod
    def get_all(db_type='general'):
        """모든 환경설정 키-값 목록을 반환합니다."""
        settings_dict = {}
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                settings_dict[row['key']] = row['value']
        except Exception as e:
            print(f"[SettingsService ERROR] get_all failed: {e}")
        return settings_dict
