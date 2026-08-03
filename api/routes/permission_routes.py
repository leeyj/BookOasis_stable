# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
import database
from api.auth import admin_required

permission_bp = Blueprint('permission', __name__)

@permission_bp.route('/api/admin/permissions', methods=['GET'])
@admin_required
def get_permissions():
    """사용자 목록, 전체 카테고리(libraries) 목록 및 카테고리별 접근 권한 현황 조회"""
    try:
        # 1. 사용자 목록 조회 (general DB 기준)
        conn_g = database.get_connection('general')
        cursor_g = conn_g.cursor()
        cursor_g.execute("SELECT id, username, role, has_adult_access FROM users ORDER BY id ASC")
        users = [dict(row) for row in cursor_g.fetchall()]
        conn_g.close()

        # 2. 카테고리(libraries) 목록 및 카테고리 레벨 플러그인 목록 수집
        categories = []
        
        # 일반 DB 카테고리
        conn_gen = database.get_connection('general')
        cursor_gen = conn_gen.cursor()
        cursor_gen.execute("SELECT id, name FROM libraries ORDER BY name ASC")
        for r in cursor_gen.fetchall():
            categories.append({'id': r['id'], 'name': r['name'], 'db_type': 'general'})
        conn_gen.close()

        # 카테고리 레벨 플러그인 목록 수집
        try:
            from services.metadata_factory import MetadataFactory
            providers = MetadataFactory.get_available_providers()
            for p in providers:
                if p.get('enabled') and p.get('category_tab'):
                    cat_tab = p.get('category_tab')
                    title = cat_tab.get('title') if isinstance(cat_tab, dict) else p.get('name')
                    cat_id = f"plugin_{p['id']}"
                    categories.append({
                        'id': cat_id,
                        'name': f"🧩 {title}",
                        'db_type': 'plugin'
                    })
        except Exception as p_err:
            print(f"[PermissionRoutes] Failed to fetch plugin categories: {p_err}")

        # 3. 사용자별 카테고리 권한 정보 조회 (일반 DB 및 플러그인 권한)
        permissions = {}
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, library_id, has_access FROM user_category_permissions")
        for r in cursor.fetchall():
            uid = str(r['user_id'])
            lid = str(r['library_id'])
            key = f"general_{lid}"
            if uid not in permissions:
                permissions[uid] = {}
            permissions[uid][key] = bool(r['has_access'])

        # 플러그인 카테고리 권한 조회 (settings 테이블의 PERM_CATEGORY_{uid}_{cat_id})
        cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'PERM_CATEGORY_%'")
        perm_rows = cursor.fetchall()
        conn.close()

        perm_map = {r['key']: r['value'] for r in perm_rows}
        for u in users:
            uid = str(u['id'])
            if uid not in permissions:
                permissions[uid] = {}
            for cat in categories:
                if cat['db_type'] == 'plugin':
                    key_perm = f"PERM_CATEGORY_{uid}_{cat['id']}"
                    val = perm_map.get(key_perm, '1')
                    perm_matrix_key = f"plugin_{cat['id']}"
                    permissions[uid][perm_matrix_key] = (val == '1')

        return jsonify({
            'success': True,
            'users': users,
            'categories': categories,
            'permissions': permissions
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
            conn = database.get_connection('general')
            cursor = conn.cursor()
            key_perm = f"PERM_CATEGORY_{user_id}_{safe_library_id}"
            cursor.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """, (key_perm, str(has_access)))
            conn.commit()
            conn.close()
        else:
            conn = database.get_connection(target_db)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_category_permissions (user_id, library_id, has_access)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, library_id) DO UPDATE SET has_access = excluded.has_access
            """, (user_id, library_id, has_access))
            conn.commit()
            conn.close()
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
        for db_type in ['general', 'adult']:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET has_adult_access = ? WHERE id = ?", (has_adult_access, user_id))
            conn.commit()
            conn.close()
        return jsonify({'success': True, 'message': '성인 도서 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
