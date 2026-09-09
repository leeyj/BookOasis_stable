# -*- coding: utf-8 -*-
"""
home_dashboard_service.py - 홈 대시보드 "플러그인 배치 모드"의 위젯 순서/카탈로그 계산 전담.

api/routes/plugin_routes.py의 GET /api/media/home-layout(클라이언트가 세션 전환/재배치
시 재조회하는 용도)과, api/routes/system_routes.py의 index 라우트(최초 페이지 로드 시
서버사이드로 이미 올바른 순서를 HTML에 렌더링해서, 코어 위젯이 기본 배치로 먼저 그려졌다가
JS가 재배치하며 눈에 띄는 리플로우가 생기던 문제를 근본적으로 없애기 위함) 양쪽에서
정확히 같은 결과가 나와야 한다 - 계산 로직을 여기 하나로 모아두고 두 호출부는 이 함수만 쓴다.

docs/plan_home_dashboard_pluginization.md 참고.
"""
import json

from utils.plugin_session_helper import resolve_plugin_sessions

_CORE_WIDGET_DEFS = {
    'core.reading_insights': {
        'id': 'core.reading_insights', 'kind': 'core', 'order': 10, 'layout': 'full',
        'title': '독서 인사이트', 'icon': 'fa-solid fa-chart-line',
    },
    'core.recent': {
        'id': 'core.recent', 'kind': 'core', 'order': 20, 'layout': 'full',
        'title': '최근 읽은 도서', 'icon': 'fa-solid fa-clock-rotate-left',
    },
    'core.new': {
        'id': 'core.new', 'kind': 'core', 'order': 30, 'layout': 'full',
        'title': '신규 추가 도서', 'icon': 'fa-solid fa-square-plus',
    },
}


class HomeDashboardService:
    @staticmethod
    def get_layout(user_id, db_type='general'):
        """사용자의 홈 화면 플러그인 배치 모드 여부와, 켜져 있는 경우의 위젯 순서/숨김 상태 및
        아직 추가하지 않은 위젯 카탈로그를 계산해 반환한다.

        Returns:
            dict: {'mode': 'classic'|'plugin', 'widgets': [...], 'catalog': [...]}
                  mode == 'classic'이면 widgets/catalog는 항상 빈 리스트.
        """
        from services.settings_service import SettingsService

        mode = SettingsService.get_effective('HOME_DASHBOARD_PLUGIN_MODE', user_id=user_id, default='0')
        if mode != '1':
            return {'mode': 'classic', 'widgets': [], 'catalog': []}

        from services.metadata_factory import MetadataFactory
        providers = MetadataFactory.get_available_providers(include_view_ui=False, include_settings_ui=False)

        available = {k: dict(v) for k, v in _CORE_WIDGET_DEFS.items()}

        for p in providers:
            if not p.get('enabled'):
                continue
            widget = p.get('home_widget')
            if not isinstance(widget, dict):
                continue
            if db_type not in resolve_plugin_sessions(widget):
                continue

            raw_order = widget.get('order')
            try:
                order_val = int(raw_order) if raw_order is not None else 50
            except (TypeError, ValueError):
                order_val = 50

            layout_val = str(widget.get('layout') or 'full').strip().lower()
            if layout_val not in ('full', 'grid'):
                layout_val = 'full'

            # 'grid' 위젯 전용 폭 단계 - grid-column을 몇 칸(auto-fill 컬럼 기준) 차지할지.
            # 'full'에는 의미 없으므로 무시된다.
            try:
                size_val = int(widget.get('size') or 1)
            except (TypeError, ValueError):
                size_val = 1
            if size_val not in (1, 2, 3):
                size_val = 1

            widget_id = f"plugin_{p.get('id')}"
            available[widget_id] = {
                'id': widget_id,
                'kind': 'plugin',
                'plugin_id': p.get('id'),
                'title': widget.get('title') or p.get('name'),
                'subtitle': widget.get('subtitle') or '',
                'provider': widget.get('provider') or p.get('name'),
                'icon': widget.get('icon') or 'fa-solid fa-puzzle-piece',
                'limit': int(widget.get('limit') or 10),
                'order': order_val,
                'layout': layout_val,
                'size': size_val,
            }

        default_order = sorted(available.values(), key=lambda w: w['order'])

        saved_layout = []
        raw_saved = SettingsService.get_user_value(user_id, 'HOME_WIDGET_LAYOUT', default=None) if user_id else None
        if raw_saved:
            try:
                parsed = json.loads(raw_saved)
                if isinstance(parsed, list):
                    saved_layout = parsed
            except (TypeError, ValueError):
                saved_layout = []

        ordered_widgets = []
        seen_ids = set()
        # 저장된 순서를 먼저 적용하되, 더 이상 존재하지 않는(플러그인 삭제/비활성화) id는 건너뛴다
        for entry in saved_layout:
            if not isinstance(entry, dict):
                continue
            widget_id = str(entry.get('id') or '').strip()
            if not widget_id or widget_id in seen_ids or widget_id not in available:
                continue
            item = dict(available[widget_id])
            item['hidden'] = bool(entry.get('hidden'))
            ordered_widgets.append(item)
            seen_ids.add(widget_id)

        # 코어 3섹션은 "저장된 레이아웃이 아예 없는(=한 번도 커스터마이징 안 한) 최초 진입"에만
        # 기본으로 채워 넣는다. 사용자가 최근/신규 도서 섹션을 명시적으로 닫은 뒤에는 저장된
        # 레이아웃이 생기므로, 그 뒤로는 여기서 다시 끼워 넣지 않아야 닫은 게 유지된다.
        # 플러그인 위젯은 애초에 여기서 자동으로 끼워 넣지 않는다 - 설치된 플러그인이 많아질수록
        # 사용자가 원치 않는 위젯까지 전부 노출되는 걸 막기 위해, 사용자가 아래 'catalog'에서
        # 명시적으로 "위젯 추가"한 것만 화면에 보이게 한다 (2026-09-07 결정).
        if not saved_layout:
            for widget in default_order:
                if widget['id'] in seen_ids or widget['kind'] != 'core':
                    continue
                item = dict(widget)
                item['hidden'] = False
                ordered_widgets.append(item)
                seen_ids.add(widget['id'])

        # 현재 화면에 없는(플러그인 위젯 미추가 또는 코어 섹션을 닫은 경우) 항목의 카탈로그 -
        # 프론트의 "+ 위젯 추가" UI가 이 목록을 보여준다. 코어도 포함시켜서 최근/신규 도서
        # 섹션을 닫았던 사용자가 나중에 다시 켤 수 있게 한다.
        catalog = [dict(w) for w in default_order if w['id'] not in seen_ids]

        return {'mode': 'plugin', 'widgets': ordered_widgets, 'catalog': catalog}
