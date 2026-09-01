# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session

from services.metadata_service import MetadataService
from services.plugin_service import PluginService
from api.auth import login_required, check_adult_permission, admin_required, webhook_token_required
from utils.i18n import _t

plugin_routes_bp = Blueprint('media_plugin_routes', __name__)

PLUGIN_SESSION_TYPES = {'general', 'adult', 'audiobook', 'video'}


def _get_current_user_id_for_annotation():
    """annotation_routes.py의 _get_current_user_info()와 동일한 세션 조회 규약.
    plugin_marker는 book_annotations.user_id로 소유권을 확인해야 하므로 필요하다."""
    user_id = session.get('user_id')
    role = session.get('role')
    if not user_id:
        user_dict = session.get('user')
        if isinstance(user_dict, dict):
            user_id = user_dict.get('id')
            role = user_dict.get('role')
    return user_id, role


def _resolve_plugin_sessions(category_tab):
    """플러그인 매니페스트(category_tab)의 'sessions' 필드로 노출 세션을 결정한다.
    - 'all': 4개 세션(general/adult/audiobook/video) 전체에 노출
    - 리스트(예: ['adult']): 명시된 세션에만 노출
    - 미지정: 하위 호환을 위해 기존 동작과 동일하게 'general'에만 노출
    """
    raw = category_tab.get('sessions')
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

@plugin_routes_bp.route('/api/media/metadata/plugins', methods=['GET'])
@admin_required
def get_metadata_plugins_api():
    """수동 검색 모달에 사용 가능한 메타데이터 플러그인 목록 조회"""
    try:
        plugins = MetadataService.get_searchable_plugins()
        return jsonify({'success': True, 'plugins': plugins})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _build_plugin_load_status_payload():
    from services.metadata_factory import MetadataFactory
    from repositories.plugin_repository import PluginRepository

    # 조회 시점 기준 최신 상태를 보장하기 위해 discovery를 1회 갱신(성공/실패 상태 변화가 있으면 DB에 즉시 반영됨)
    MetadataFactory._discover_provider_classes()

    statuses = PluginRepository.get_latest_load_status('general')
    error_count = sum(1 for s in statuses if s.get('status') == 'error')
    recent_events = PluginRepository.get_recent_load_events('general', limit=50)

    return {
        'success': True,
        'statuses': statuses,
        'error_count': error_count,
        'recent_events': recent_events,
    }

@plugin_routes_bp.route('/api/media/plugins/load-status', methods=['GET'])
@admin_required
def get_plugin_load_status_api():
    """관리자 대시보드용 플러그인 로드 성공/실패 현황 및 최근 이력 조회"""
    try:
        return jsonify(_build_plugin_load_status_payload())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/webhook/plugins/status', methods=['GET'])
@webhook_token_required
def get_plugin_load_status_webhook_api():
    """
    외부 연동 프로그램(모니터링 스크립트 등)용 플러그인 로드 상태 조회 API.
    관리자 세션 없이, 기존 스캔 웹훅과 동일한 WEBHOOK_TOKEN으로 인증한다(?token=... 또는 X-Webhook-Token 헤더).
    """
    try:
        return jsonify(_build_plugin_load_status_payload())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/plugins/add-plugin-check', methods=['GET'])
def check_add_plugin_api():
    """
    비공개(private) 플러그인이 자기 자신의 선택적 활성화 여부를 스스로 판단할 수 있도록 하는 조회 API.
    베타 테스트 단계라 고정된 단일 plugin_id("security-bookoasis-plugin")만 지원하며,
    운영자가 .env/docker-compose override 또는 DB 설정값의 ADD_PLUGIN을 정확히 이 값으로
    설정해두지 않는 한, 비공개 플러그인은 이 값을 확인해 스스로 비활성 상태로 남아야 한다.
    조회한 plugin_id 하나의 일치 여부만 반환하며, ADD_PLUGIN 설정값 자체는 노출하지 않는다.
    """
    plugin_id = request.args.get('plugin_id', '').strip()
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400

    try:
        from utils.plugin_env import is_plugin_in_add_plugin_list
        enabled = is_plugin_in_add_plugin_list(plugin_id)
        return jsonify({'success': True, 'plugin_id': plugin_id, 'enabled': enabled})
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

@plugin_routes_bp.route('/api/media/metadata/plugins/samples', methods=['GET'])
@admin_required
def list_sample_plugins_api():
    """sample_plugins/metadata/ 에 있는, 아직 설치되지 않은 것 포함 전체 샘플 플러그인 카탈로그 조회"""
    try:
        samples = PluginService.list_sample_plugins()
        return jsonify({'success': True, 'samples': samples})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/api/media/metadata/plugins/install-from-sample', methods=['POST'])
@admin_required
def install_sample_plugin_api():
    """샘플 카탈로그의 플러그인 하나를 실제 plugins/metadata/ 로 복사 설치"""
    data = request.get_json(silent=True) or {}
    plugin_id = str(data.get('plugin_id', '')).strip()
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400

    try:
        success, payload = PluginService.install_from_sample(plugin_id)
        if not success:
            return jsonify({'success': False, **payload}), 400
        return jsonify({'success': True, **payload})
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

    if db_type not in PLUGIN_SESSION_TYPES:
        return jsonify({'success': True, 'category_plugins': []}), 200

    try:
        from services.metadata_factory import MetadataFactory
        from services.category_service import CategoryService
        providers = MetadataFactory.get_available_providers()

        perm_map = {}
        if user_id and user_role != 'admin':
            from repositories.settings_repository import SettingsRepository
            perm_map = SettingsRepository.get_settings_by_prefix(f"PERM_CATEGORY_{user_id}_plugin_")

        plugin_group_map = CategoryService.get_plugin_group_assignments(db_type)

        active_category_plugins = []
        for p in providers:
            if not p.get('enabled'):
                continue
            cat_tab = p.get('category_tab')
            if not isinstance(cat_tab, dict):
                continue

            # 플러그인이 매니페스트의 'sessions'로 자신이 노출될 세션을 선언한다
            # (예: sessions=['adult']면 일반 도서 사이드바에는 뜨지 않음, 'all'이면
            # 4개 세션 전체). 선언이 없으면 하위 호환을 위해 general에만 노출된다.
            if db_type not in _resolve_plugin_sessions(cat_tab):
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
                'ui': p.get('ui'),
                'group_id': plugin_group_map.get(p.get('id'))
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

def _resolve_cover_url(cover_image):
    """book_context_menu용과 동일하게, DB의 cover_image 원본값을 실제 접근 가능한 경로로
    정규화한다 (static/js/cover_fallback.js의 getBookCoverSrc()와 동일 규칙)."""
    if not cover_image:
        return None
    clean = str(cover_image).strip()
    if not clean:
        return None
    if clean.startswith('http://') or clean.startswith('https://') or clean.startswith('/api/'):
        return clean
    clean = clean.lstrip('/\\')
    if clean.lower().startswith('covers/'):
        clean = clean[len('covers/'):].lstrip('/\\')
    return f"/covers/{clean}" if clean else None


def _enrich_annotation_context(db_type, context):
    """클라이언트가 보낸 얕은 context(annotation_id, quote, note 등)에 도서 요약 정보
    (title/series_name/cover_image)를 서버에서 직접 조회해 채워 넣는다. 매번 각 플러그인이
    self.get_db_gateway(db_type)로 재조회하지 않아도 내보내기(옵시디언/노션 등)에 필요한
    최소한의 서지정보를 바로 쓸 수 있게 하기 위함."""
    enriched = dict(context)
    book_id = enriched.get('book_id')
    if not book_id:
        return enriched

    try:
        from repositories.book_repository import BookRepository

        info = BookRepository.get_book_annotation_context_info(db_type, book_id)
        if info:
            if info.get('title'):
                enriched['book_title'] = info['title']
            enriched['series_name'] = info.get('series_name') or None
            enriched['cover_image'] = _resolve_cover_url(info.get('cover_image'))
    except Exception:
        # 조회 실패 시에도 클라이언트가 보낸 얕은 context는 그대로 살려서 플러그인 호출은 계속 진행
        pass
    return enriched


@plugin_routes_bp.route('/api/media/context-menu/annotation/plugins', methods=['POST'])
@login_required
def get_annotation_context_menu_plugin_items_api():
    """활성화된 플러그인의 EPUB/TXT 하이라이트(주석) 컨텍스트 메뉴 항목을 동적으로 조회합니다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('type', 'general')

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    context = _enrich_annotation_context(db_type, payload.get('context') or {})

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
                items = provider.get_annotation_context_menu_items(db_type, context) or []
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

@plugin_routes_bp.route('/api/media/context-menu/annotation/plugins/action', methods=['POST'])
@login_required
def run_annotation_context_menu_plugin_action_api():
    """하이라이트 컨텍스트 메뉴에서 선택된 플러그인 액션을 실행합니다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('type', 'general')

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    plugin_id = (payload.get('plugin_id') or '').strip()
    action_id = (payload.get('action_id') or '').strip()
    context = _enrich_annotation_context(db_type, payload.get('context') or {})

    if not plugin_id:
        return jsonify({'success': False, 'error': 'plugin_id가 누락되었습니다.'}), 400
    if not action_id:
        return jsonify({'success': False, 'error': 'action_id가 누락되었습니다.'}), 400

    try:
        from services.metadata_factory import MetadataFactory

        provider = MetadataFactory.get_provider_by_id(plugin_id)
        result = provider.run_annotation_context_menu_action(db_type, action_id, context)
        if not isinstance(result, dict):
            result = {'success': False, 'error': '플러그인 액션 반환값 형식이 올바르지 않습니다.'}

        # 플러그인이 응답에 'marker' 키를 포함시키면(빈 문자열/None도 포함 - 마커 해제 용도),
        # 하이라이트 옆에 표시할 작은 시각적 신호를 코어가 대신 영속화해준다. 플러그인은
        # get_annotation_context_menu_items()에서 메뉴 라벨을("메모 작성" ↔ "메모 보기/수정")
        # 스스로 판단하기 위해 이미 자기 저장소를 조회하고 있으므로, 이 필드는 순전히
        # "본문 위에 뭘 그릴지"만을 위한 UI 힌트다 - 코어는 값의 의미를 해석하지 않는다.
        if 'marker' in result and result.get('success') and context.get('annotation_id'):
            try:
                from repositories.annotation_repository import AnnotationRepository

                user_id, _role = _get_current_user_id_for_annotation()
                if user_id:
                    AnnotationRepository.update_plugin_marker(
                        db_type, context['annotation_id'], user_id, result.get('marker')
                    )
            except Exception as marker_err:
                print(f"[Plugin-ContextMenu] plugin_marker persist failed: {marker_err}")

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@plugin_routes_bp.route('/callback', methods=['GET'])
@admin_required
def generic_oauth_callback_api():
    """서드파티 OAuth 제공자(Spotify 등)가 인가 코드와 함께 리다이렉트해오는 범용 콜백 다리.
    플러그인은 자체 라우트를 등록할 수 없으므로, 여러 OAuth 연동 플러그인이 이 경로 하나를
    공유해서 쓴다. 코어는 state에 인코딩된 "{plugin_id}:{nonce}" 형식만 보고 해당 plugin_id의
    handle_oauth_callback()에 그대로 위임할 뿐, 어떤 서드파티 서비스인지/무엇을 하는지는 전혀
    모른다 - CSRF nonce 검증 등 실제 로직은 각 플러그인이 자기 책임으로 처리한다."""
    code = request.args.get('code')
    state = request.args.get('state', '') or ''
    error = request.args.get('error')
    db_type = request.args.get('type', 'general')

    plugin_id = state.split(':', 1)[0] if state else ''
    if not plugin_id:
        return "잘못된 콜백 요청입니다 (state 누락).", 400

    try:
        from services.metadata_factory import MetadataFactory
        provider = MetadataFactory.get_provider_by_id(plugin_id)
    except ValueError:
        return f"플러그인 '{plugin_id}'을(를) 찾을 수 없습니다.", 404

    handler = getattr(provider, 'handle_oauth_callback', None)
    if not callable(handler):
        return f"'{plugin_id}' 플러그인은 OAuth 콜백을 지원하지 않습니다.", 400

    try:
        result = handler(db_type, code, state, error) or {}
    except Exception as e:
        result = {'success': False, 'message': f'콜백 처리 중 오류: {e}'}

    ok = bool(result.get('success'))
    message = result.get('message') or ('연결이 완료되었습니다.' if ok else '연결에 실패했습니다.')
    color = '#1db954' if ok else '#e74c3c'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>연결 결과</title></head>
<body style="font-family:sans-serif;background:#111;color:#eee;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
  <div style="text-align:center;padding:0 1.5rem;">
    <h2 style="color:{color};">{message}</h2>
    <p>이 창(탭)을 닫고 앱으로 돌아가셔도 됩니다.</p>
  </div>
</body></html>"""
