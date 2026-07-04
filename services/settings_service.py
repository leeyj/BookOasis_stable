# -*- coding: utf-8 -*-
from repositories.settings_repository import SettingsRepository

class SettingsService:
    @staticmethod
    def get(key, default='', db_type='general'):
        """특정 설정 키의 값을 조회합니다."""
        try:
            val = SettingsRepository.get_value(db_type, key)
            if val is not None:
                return val
        except Exception as e:
            print(f"[SettingsService ERROR] get '{key}' failed: {e}")
        return default

    @staticmethod
    def set(key, value):
        """설정 키의 값을 양쪽 데이터베이스(general, adult) 모두에 저장/업데이트(UPSERT)합니다."""
        for db_type in ['general', 'adult']:
            try:
                SettingsRepository.set_value(db_type, key, value)
            except Exception as e:
                print(f"[SettingsService ERROR] set '{key}' (DB: {db_type}) failed: {e}")
        return True

    @staticmethod
    def get_all(db_type='general'):
        """모든 환경설정 키-값 목록을 반환합니다."""
        try:
            return SettingsRepository.get_all_settings(db_type)
        except Exception as e:
            print(f"[SettingsService ERROR] get_all failed: {e}")
            return {}
