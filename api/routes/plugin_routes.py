# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session

from services.metadata_service import MetadataService
from services.plugin_service import PluginService
from api.auth import login_required, check_adult_permission, admin_required
from utils.i18n import _t

plugin_routes_bp = Blueprint('media_plugin_routes', __name__)

@plugin_routes_bp.route('/api/media/metadata/plugins', methods=['GET'])
@admin_required
def get_metadata_plugins_api():
    """수동 검색 모달에 사용 가능한 메타데이터 플러그인 목록 조회"""
    try:
        plugins = MetadataService.get_searchable_plugins()
        return jsonify({'success': True, 'plugins': plugins})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/metadata/plugins/manage', methods=['GET'])
@admin_required
def get_metadata_plugins_manage_api():
    """환경설정 > 플러그인 관리에 표시할 전체 메타데이터 플러그인 목록 조회"""
    try:
        from services.metadata_factory import MetadataFactory
        plugins = MetadataFactory.get_available_providers()
        return jsonify({'success': True, 'plugins': plugins})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/plugins/update-eligibility', methods=['POST'])
def plugin_update_eligibility():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.get_json(silent=True) or {}
    current_version = str(data.get('current_version', '')).strip()
    github_version = str(data.get('github_version', '')).strip()

    if not current_version or not github_version:
        return jsonify({
            'success': False,
            'error': 'current_version and github_version are required'
        }), 400

    try:
        can_update, reason = PluginService.can_update_to_github_version(current_version, github_version)
        return jsonify({
            'success': True,
            'can_update': can_update,
            'reason': reason
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/books/search-metadata', methods=['GET'])
@admin_required
def search_book_metadata_api():
    """지정된 메타데이터 플러그인을 활용하여 도서 메타데이터 후보군 검색"""
    db_type = request.args.get('type', 'general')
    query = request.args.get('query', '').strip()
    source = request.args.get('source', '').strip() or None
    
    if not query:
        return jsonify({'success': False, 'error': _t('api.err_query_missing')}), 400
        
    try:
        results = MetadataService.search_metadata(db_type, query, source)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/books/<int:book_id>/apply-metadata', methods=['POST'])
@admin_required
def apply_book_metadata_api(book_id):
    """사용자가 선택한 메타데이터 정보를 도서 정보에 최종 반영"""
    db_type = request.json.get('type', 'general') if request.is_json else request.form.get('type', 'general')
    source = request.json.get('source') if request.is_json else request.form.get('source')
    source = source.strip() if source else None
    
    item_data = None
    if request.is_json:
        item_data = request.json.get('item_data') or request.json.get('aladin_item')
    else:
        item_data = request.form.to_dict()
        if 'type' in item_data:
            item_data.pop('type')
        if 'source' in item_data:
            item_data.pop('source')

    if not item_data:
        return jsonify({'success': False, 'error': _t('api.err_metadata_missing')}), 400
        
    try:
        success, message = MetadataService.apply_metadata(db_type, book_id, item_data, source)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/metadata/plugins/toggle', methods=['POST'])
@admin_required
def toggle_metadata_plugin_api():
    """특정 플러그인의 ON/OFF 활성화 상태를 업데이트합니다."""
    db_type = request.form.get('type', 'general')
    plugin_id = request.form.get('plugin_id', '').strip()
    enabled_val = request.form.get('enabled', '1').strip()
    
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400
        
    try:
        success, error = PluginService.toggle_plugin_enabled(db_type, plugin_id, enabled_val)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        status_txt = _t('api.status_enabled') if enabled_val == '1' else _t('api.status_disabled')
        return jsonify({'success': True, 'message': _t('api.msg_plugin_status_updated', plugin_id=plugin_id, status_txt=status_txt)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/metadata/plugins/save-config', methods=['POST'])
@admin_required
def save_metadata_plugin_config_api():
    """특정 플러그인의 JSON 설정 데이터를 DB에 저장합니다."""
    db_type = request.json.get('type', 'general') if request.is_json else request.form.get('type', 'general')
    plugin_id = request.json.get('plugin_id') if request.is_json else request.form.get('plugin_id')
    config_data = request.json.get('config') if request.is_json else request.form.get('config')
    
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400
        
    if config_data is None:
        return jsonify({'success': False, 'error': _t('api.err_config_data_missing')}), 400
        
    try:
        success, error = PluginService.save_plugin_config(db_type, plugin_id, config_data)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        return jsonify({'success': True, 'message': _t('api.msg_plugin_config_saved', plugin_id=plugin_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/metadata/plugins/sample-update', methods=['POST'])
@admin_required
def sample_update_metadata_plugin_api():
    data = request.get_json(silent=True) or {}
    plugin_id = str(data.get('plugin_id', '')).strip()
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400

    try:
        success, payload = PluginService.sample_update_plugin(plugin_id)
        if not success:
            return jsonify({'success': False, **payload}), 400
        return jsonify({'success': True, **payload})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/dashboard/widgets', methods=['GET'])
def get_dashboard_widgets_api():
    """대시보드에 표시할 활성화된 위젯(플러그인) 목록을 반환합니다."""
    db_type = request.args.get('type', 'general').strip()
    try:
        from services.metadata_factory import MetadataFactory
        providers = MetadataFactory.get_available_providers()

        active_widgets = []
        for p in providers:
            if not p.get('enabled'):
                continue
            widget = p.get('dashboard_widget')
            if not isinstance(widget, dict):
                continue

            supported_types = widget.get('supported_types')
            if isinstance(supported_types, list) and db_type not in supported_types:
                continue

            active_widgets.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'title': widget.get('title') or p.get('name'),
                'subtitle': widget.get('subtitle') or '',
                'provider': widget.get('provider') or p.get('name'),
                'icon': widget.get('icon') or 'fa-solid fa-puzzle-piece',
                'limit': int(widget.get('limit') or 10),
                'all_desk_tab': bool(widget.get('all_desk_tab') or False),
            })

        return jsonify({'success': True, 'widgets': active_widgets}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/dashboard/widgets/<plugin_id>/data', methods=['GET'])
def get_dashboard_widget_data_api(plugin_id):
    """대시보드 위젯 데이터 조회 (플러그인 동적 로딩)."""
    db_type = request.args.get('type', 'general')
    limit = int(request.args.get('limit', 10))

    try:
        from services.metadata_factory import MetadataFactory
        provider = MetadataFactory.get_provider_by_id(plugin_id)

        result = provider.get_dashboard_data(db_type, limit=limit)

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/category-plugins', methods=['GET'])
def get_category_plugins_api():
    """사이드바 및 뷰포트에 마운트할 활성화된 카테고리 레벨 플러그인 목록을 반환합니다."""
    db_type = request.args.get('type', 'general').strip()
    user_id = session.get('user_id')
    user_role = session.get('role', 'user')

    try:
        from services.metadata_factory import MetadataFactory
        providers = MetadataFactory.get_available_providers()

        perm_map = {}
        if user_id and user_role != 'admin':
            from repositories.settings_repository import SettingsRepository
            perm_map = SettingsRepository.get_settings_by_prefix('general', f"PERM_CATEGORY_{user_id}_plugin_")

        active_category_plugins = []
        for p in providers:
            if not p.get('enabled'):
                continue
            cat_tab = p.get('category_tab')
            if not isinstance(cat_tab, dict):
                continue

            plugin_cat_id = f"plugin_{p.get('id')}"
            if user_id and user_role != 'admin':
                perm_key = f"PERM_CATEGORY_{user_id}_{plugin_cat_id}"
                if perm_map.get(perm_key) == '0':
                    continue

            active_category_plugins.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'category_id': plugin_cat_id,
                'title': cat_tab.get('title') or p.get('name'),
                'icon': cat_tab.get('icon') or 'fa-solid fa-puzzle-piece',
                'order': int(cat_tab.get('order') or 50),
                'ui': p.get('ui')
            })

        active_category_plugins.sort(key=lambda x: x['order'])
        return jsonify({'success': True, 'category_plugins': active_category_plugins}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/plugins/<plugin_id>/ui', methods=['GET'])
def get_plugin_ui_bundle_api(plugin_id):
    """특정 플러그인의 풀페이지 UI 번들(index.html, style.css, script.js)을 반환합니다."""
    try:
        from services.metadata_factory import MetadataFactory
        bundle = MetadataFactory._load_plugin_ui_bundle(plugin_id)
        if not bundle:
            return jsonify({'success': False, 'error': 'UI bundle not found'}), 404
        return jsonify({'success': True, 'plugin_id': plugin_id, 'bundle': bundle}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/context-menu/book/plugins', methods=['POST'])
@login_required
def get_book_context_menu_plugin_items_api():
    """활성화된 플러그인의 도서 컨텍스트 메뉴 항목을 동적으로 조회합니다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('type', 'general')

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    context = payload.get('context') or {}

    try:
        from services.metadata_factory import MetadataFactory

        providers = MetadataFactory.get_available_providers()
        merged_items = []

        for provider_meta in providers:
            if not provider_meta.get('enabled'):
                continue

            provider_id = provider_meta.get('id')
            if not provider_id:
                continue

            try:
                provider = MetadataFactory.get_provider_by_id(provider_id)
                items = provider.get_context_menu_items(db_type, context) or []
            except Exception:
                items = []

            if not isinstance(items, list):
                continue

            for raw_item in items:
                if not isinstance(raw_item, dict):
                    continue

                action_id = str(raw_item.get('id') or '').strip()
                label = str(raw_item.get('label') or '').strip()
                if not action_id or not label:
                    continue

                merged_items.append({
                    'plugin_id': provider_id,
                    'plugin_name': provider_meta.get('name') or provider_id,
                    'id': action_id,
                    'label': label,
                    'icon': raw_item.get('icon') or 'fa-solid fa-puzzle-piece',
                })

        return jsonify({'success': True, 'items': merged_items}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/context-menu/book/plugins/action', methods=['POST'])
@login_required
def run_book_context_menu_plugin_action_api():
    """도서 컨텍스트 메뉴에서 선택된 플러그인 액션을 실행합니다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('type', 'general')

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    plugin_id = (payload.get('plugin_id') or '').strip()
    action_id = (payload.get('action_id') or '').strip()
    context = payload.get('context') or {}

    if not plugin_id:
        return jsonify({'success': False, 'error': 'plugin_id가 누락되었습니다.'}), 400
    if not action_id:
        return jsonify({'success': False, 'error': 'action_id가 누락되었습니다.'}), 400

    try:
        from services.metadata_factory import MetadataFactory

        provider = MetadataFactory.get_provider_by_id(plugin_id)
        result = provider.run_context_menu_action(db_type, action_id, context)
        if not isinstance(result, dict):
            result = {'success': False, 'error': '플러그인 액션 반환값 형식이 올바르지 않습니다.'}

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
