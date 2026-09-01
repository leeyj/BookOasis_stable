# -*- coding: utf-8 -*-
from repositories.settings_repository import SettingsRepository

class SettingsService:
    @staticmethod
    def get(key, default=''):
        """특정 설정 키의 값을 조회합니다."""
        try:
            val = SettingsRepository.get_value(key)
            if val is not None:
                return val
        except Exception as e:
            print(f"[SettingsService ERROR] get '{key}' failed: {e}")
        return default

    @staticmethod
    def set(key, value):
        """설정 키의 값을 등록/업데이트(UPSERT)합니다."""
        try:
            SettingsRepository.set_value(key, value)
        except Exception as e:
            print(f"[SettingsService ERROR] set '{key}' failed: {e}")
        return True

    @staticmethod
    def get_all():
        """모든 환경설정 키-값 목록을 반환합니다."""
        try:
            return SettingsRepository.get_all_settings()
        except Exception as e:
            print(f"[SettingsService ERROR] get_all failed: {e}")
            return {}

    @staticmethod
    def get_user_value(user_id, key, default=None):
        """특정 사용자의 개인화(override) 설정 값을 조회합니다."""
        try:
            val = SettingsRepository.get_user_value(user_id, key)
            if val is not None:
                return val
        except Exception as e:
            print(f"[SettingsService ERROR] get_user_value '{key}' (user {user_id}) failed: {e}")
        return default

    @staticmethod
    def set_user_value(user_id, key, value):
        """특정 사용자의 개인화(override) 설정 값을 등록/업데이트(UPSERT)합니다."""
        try:
            SettingsRepository.set_user_value(user_id, key, value)
        except Exception as e:
            print(f"[SettingsService ERROR] set_user_value '{key}' (user {user_id}) failed: {e}")
        return True

    @staticmethod
    def get_all_user_settings(user_id):
        """특정 사용자의 모든 개인화(override) 설정 목록을 반환합니다."""
        try:
            return SettingsRepository.get_all_user_settings(user_id)
        except Exception as e:
            print(f"[SettingsService ERROR] get_all_user_settings (user {user_id}) failed: {e}")
            return {}

    @staticmethod
    def get_effective(key, user_id=None, default=''):
        """user_settings override -> global settings -> default 순으로 값을 해석."""
        if user_id is not None:
            override = SettingsService.get_user_value(user_id, key)
            if override is not None:
                return override
        return SettingsService.get(key, default)
