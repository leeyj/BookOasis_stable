# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from api.auth import admin_required
from repositories.category_repository import CategoryRepository
from repositories.user_repository import UserRepository
from repositories.settings_repository import SettingsRepository

permission_bp = Blueprint('permission', __name__)


def _fetch_library_permissions(db_type, include_plugins=False):
    categories = []
    raw_libs = CategoryRepository.get_all_libraries(db_type)
    for lib in raw_libs:
        categories.append({'id': lib['id'], 'name': lib['name'], 'db_type': db_type})

    if include_plugins and db_type == 'general':
        try:
            from services.metadata_factory import MetadataFactory
            providers = MetadataFactory.get_available_providers()
            for p in providers:
                if p.get('enabled') and p.get('category_tab'):
                    cat_tab = p.get('category_tab')
                    title = cat_tab.get('title') if isinstance(cat_tab, dict) else p.get('name')
                    categories.append({
                        'id': f"plugin_{p['id']}",
                        'name': f"🧩 {title}",
                        'db_type': 'plugin'
                    })
        except Exception as p_err:
            print(f"[PermissionRoutes] Failed to fetch plugin categories: {p_err}")

    permissions = {}
    raw_perms = UserRepository.get_all_category_permissions(db_type)
    for row in raw_perms:
        uid = str(row['user_id'])
        lid = str(row['library_id'])
        if uid not in permissions:
            permissions[uid] = {}
        permissions[uid][f"{db_type}_{lid}"] = bool(row['has_access'])

    if include_plugins and db_type == 'general':
        perm_map = SettingsRepository.get_settings_by_prefix(db_type, 'PERM_CATEGORY_')
        user_rows = [u['id'] for u in UserRepository.get_all_users(db_type)]
        for uid in user_rows:
            uid_str = str(uid)
            if uid_str not in permissions:
                permissions[uid_str] = {}
            for cat in categories:
                if cat['db_type'] == 'plugin':
                    key_perm = f"PERM_CATEGORY_{uid_str}_{cat['id']}"
                    val = perm_map.get(key_perm, '1')
                    permissions[uid_str][f"{db_type}_{cat['id']}"] = (val == '1')

    return categories, permissions

@permission_bp.route('/api/admin/permissions', methods=['GET'])
@admin_required
def get_permissions():
    """사용자 목록, 세션별 카테고리/접근 권한 현황 조회"""
    try:
        # 1. 사용자 목록 조회 (general DB 기준)
        users = UserRepository.get_all_users('general')

        general_categories, general_permissions = _fetch_library_permissions('general', include_plugins=True)
        audiobook_categories, audiobook_permissions = _fetch_library_permissions('audiobook', include_plugins=False)

        return jsonify({
            'success': True,
            'users': users,
            'sessions': [
                {
                    'id': 'general',
                    'title': '일반 도서',
                    'subtitle': '일반 카테고리와 플러그인 권한',
                    'kind': 'matrix'
                },
                {
                    'id': 'adult',
                    'title': '성인 서재',
                    'subtitle': '성인 도서 DB 접근 권한',
                    'kind': 'switch',
                    'field': 'has_adult_access'
                },
                {
                    'id': 'audiobook',
                    'title': '오디오북 서재',
                    'subtitle': '오디오북 카테고리 권한',
                    'kind': 'matrix'
                }
            ],
            'matrices': {
                'general': {
                    'categories': general_categories,
                    'permissions': general_permissions,
                },
                'audiobook': {
                    'categories': audiobook_categories,
                    'permissions': audiobook_permissions,
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@permission_bp.route('/api/admin/permissions/update', methods=['POST'])
@admin_required
def update_permission():
    """사용자별 특정 카테고리 접근 권한 토글 업데이트"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    library_id = data.get('library_id')
    has_access = 1 if data.get('has_access') else 0
    target_db = data.get('target_db', 'general') # 'general' or 'plugin'

    if user_id is None or library_id is None or str(library_id).strip() == '':
        return jsonify({'success': False, 'error': 'user_id와 library_id는 필수 항목입니다.'}), 400

    try:
        if target_db == 'plugin' or str(library_id).startswith('plugin_'):
            safe_library_id = str(library_id).strip()
            key_perm = f"PERM_CATEGORY_{user_id}_{safe_library_id}"
            SettingsRepository.set_value('general', key_perm, str(has_access))
        else:
            UserRepository.update_category_permission(target_db, user_id, library_id, has_access)
        return jsonify({'success': True, 'message': '권한 정보가 업데이트되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@permission_bp.route('/api/admin/permissions/update-adult', methods=['POST'])
@admin_required
def update_adult_permission():
    """사용자별 성인도서 접근 권한 토글 업데이트"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    has_adult_access = 1 if data.get('has_adult_access') else 0

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id는 필수 항목입니다.'}), 400

    try:
        # 양쪽 DB 모두 사용자 권한 동기화 업데이트
        for db_type in ['general', 'adult', 'audiobook']:
            UserRepository.update_adult_access(db_type, user_id, has_adult_access)
        return jsonify({'success': True, 'message': '성인 도서 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@permission_bp.route('/api/admin/permissions/update-audiobook', methods=['POST'])
@admin_required
def update_audiobook_permission():
    """사용자별 오디오북 접근 권한 토글 업데이트"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    has_audiobook_access = 1 if data.get('has_audiobook_access') else 0

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id는 필수 항목입니다.'}), 400

    try:
        # 3개 DB 모두 사용자 오디오북 권한 동기화 업데이트
        for db_type in ['general', 'adult', 'audiobook']:
            UserRepository.update_audiobook_access(db_type, user_id, has_audiobook_access)
        return jsonify({'success': True, 'message': '오디오북 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
