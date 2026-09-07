# -*- coding: utf-8 -*-
"""
plugin_session_helper.py - 플러그인 매니페스트의 'sessions' 필드 해석 전담.

원래 api/routes/plugin_routes.py에만 있던 private 헬퍼였는데, 홈 대시보드 서버사이드
초기 렌더(services/home_dashboard_service.py)에서도 똑같은 규칙이 필요해져 라우터에
묶여있지 않은 공용 위치로 옮겼다. 라우트 모듈이 서비스 모듈을 import하고 서비스 모듈이
다시 라우트 모듈을 import하는 순환참조를 피하기 위한 목적도 있다.
"""

PLUGIN_SESSION_TYPES = {'general', 'adult', 'audiobook', 'video'}


def resolve_plugin_sessions(manifest):
    """플러그인 매니페스트(category_tab/home_widget 등)의 'sessions' 필드로 노출 세션을 결정한다.
    - 'all': 4개 세션(general/adult/audiobook/video) 전체에 노출
    - 리스트(예: ['adult']): 명시된 세션에만 노출
    - 미지정: 하위 호환을 위해 기존 동작과 동일하게 'general'에만 노출
    """
    raw = manifest.get('sessions')
    if raw is None:
        return {'general'}
    if isinstance(raw, str):
        if raw.strip().lower() == 'all':
            return set(PLUGIN_SESSION_TYPES)
        raw = [raw]
    if isinstance(raw, (list, tuple, set)):
        resolved = {str(s).strip().lower() for s in raw if str(s).strip().lower() in PLUGIN_SESSION_TYPES}
        if resolved:
            return resolved
    return {'general'}
