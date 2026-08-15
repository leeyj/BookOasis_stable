# -*- coding: utf-8 -*-
"""
비공개(private) 플러그인의 선택적 활성화를 위한 ADD_PLUGIN 유틸.

베타 테스트 단계라 우선 고정된 단일 plugin_id("security-bookoasis-plugin")만 지원한다.
운영자가 .env/docker-compose override 또는 DB 설정값(ADD_PLUGIN)에 정확히 이 값을
설정해두지 않는 한, 해당 비공개 플러그인은 스스로 비활성 상태로 남아야 한다.
이 판단은 플러그인 코드 스스로가 api/routes/plugin_routes.py의
/api/media/plugins/add-plugin-check 엔드포인트를 호출해 확인한다.
"""
import os

# 베타 테스트 기간 동안 허용되는 유일한 비공개 plugin_id (고정값)
SUPPORTED_ADD_PLUGIN_ID = 'security-bookoasis-plugin'


def _get_add_plugin_value(db_type='general'):
    """ADD_PLUGIN 설정값(DB 우선, .env/환경변수 폴백)을 그대로 반환합니다."""
    try:
        from services.settings_service import SettingsService
        return SettingsService.get('ADD_PLUGIN', '', db_type=db_type) or os.environ.get('ADD_PLUGIN', '')
    except Exception:
        return os.environ.get('ADD_PLUGIN', '')


def is_plugin_in_add_plugin_list(plugin_id, db_type='general'):
    """
    주어진 plugin_id가 활성화 대상인지 여부를 반환합니다.
    베타 테스트 단계에서는 고정값 SUPPORTED_ADD_PLUGIN_ID 하나만 지원하며,
    ADD_PLUGIN 설정값이 정확히 이 값과 일치할 때만 True를 반환합니다.
    """
    if not plugin_id:
        return False

    target = str(plugin_id).strip().lower()
    if target != SUPPORTED_ADD_PLUGIN_ID:
        return False

    raw_value = str(_get_add_plugin_value(db_type=db_type) or '').strip().lower()
    return raw_value == SUPPORTED_ADD_PLUGIN_ID
