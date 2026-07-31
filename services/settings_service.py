# -*- coding: utf-8 -*-
from repositories.settings_repository import SettingsRepository

class SettingsService:
    @staticmethod
    def get(key, default='', db_type='general'):
        """특정 설정 키의 값을 조회합니다. (요청 DB에 없으면 general DB 순으로 Fallback)"""
        try:
            val = SettingsRepository.get_value(db_type, key)
            if val is not None:
                return val
            if db_type != 'general':
                gen_val = SettingsRepository.get_value('general', key)
                if gen_val is not None:
                    return gen_val
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
        """모든 환경설정 키-값 목록을 반환합니다. (general 설정을 Base로 가져온 후 db_type 고유 설정으로 병합)"""
        try:
            settings = {}
            # 1. general DB 설정을 베이스로 병합
            gen_settings = SettingsRepository.get_all_settings('general')
            if gen_settings:
                settings.update(gen_settings)
            
            # 2. 요청된 db_type이 general이 아닌 경우 해당 DB 설정으로 덮어씀
            if db_type != 'general':
                target_settings = SettingsRepository.get_all_settings(db_type)
                if target_settings:
                    settings.update(target_settings)
                    
            return settings
        except Exception as e:
            print(f"[SettingsService ERROR] get_all failed: {e}")
            return {}
