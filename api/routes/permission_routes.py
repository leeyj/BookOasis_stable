# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from api.helpers.route_helpers import error_response
from api.auth import admin_required
from repositories.category_repository import CategoryRepository
from repositories.user_repository import UserRepository
from repositories.settings_repository import SettingsRepository
from services.content_rating_service import (
    LEVEL_PORN,
    SUPPORTED_CONTENT_RATING_LEVELS,
    get_user_content_rating_max,
)

permission_bp = Blueprint('permission', __name__)


def _fetch_library_permissions(db_type, include_plugins=False):
    categories = []
    raw_libs = CategoryRepository.get_all_libraries(db_type)
    for lib in raw_libs:
        categories.append({'id': lib['id'], 'name': lib['name'], 'db_type': db_type})

    if include_plugins and db_type == 'general':
        try:
            from services.metadata_factory import MetadataFactory
            providers = MetadataFactory.get_available_providers(include_view_ui=False, include_settings_ui=False)
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
        perm_map = SettingsRepository.get_settings_by_prefix('PERM_CATEGORY_')
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

# users 테이블은 4개 DB에 모두 있다(사용자 추가·삭제도 4개 모두). 권한 값도 4곳에 같이 쓴다.
USER_DB_TYPES = ('general', 'adult', 'audiobook', 'video')


@permission_bp.route('/api/admin/permissions', methods=['GET'])
@admin_required
def get_permissions():
    """사용자 목록, 세션별 카테고리/접근 권한 현황 조회"""
    try:
        # 1. 사용자 목록 조회 (general DB 기준)
        users = UserRepository.get_all_users('general')
        for user in users:
            if user.get('role') == 'admin':
                user['content_rating_max'] = get_user_content_rating_max(user)

        general_categories, general_permissions = _fetch_library_permissions('general', include_plugins=True)
        audiobook_categories, audiobook_permissions = _fetch_library_permissions('audiobook', include_plugins=False)
        video_categories, video_permissions = _fetch_library_permissions('video', include_plugins=False)

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
                },
                {
                    'id': 'video',
                    'title': '영상 강좌',
                    'subtitle': '영상 강좌 카테고리 권한',
                    'kind': 'matrix'
                },
                {
                    'id': 'download',
                    'title': '파일 다운로드',
                    'subtitle': 'EPUB/PDF/TXT 파일 다운로드 허용 권한',
                    'kind': 'switch',
                    'field': 'has_download_access'
                },
                {
                    'id': 'content_rating',
                    'title': '콘텐츠 등급',
                    'subtitle': '일반 도서관 내 등급(books_lv)/성인 장르·태그 콘텐츠 열람 허용 범위',
                    'kind': 'rating_select',
                    'field': 'content_rating_max'
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
                },
                'video': {
                    'categories': video_categories,
                    'permissions': video_permissions,
                }
            }
        })
    except Exception as e:
        return error_response(e)

def _apply_single_permission_change(change):
    """change 1건({user_id, library_id, has_access, target_db})을 실제로 반영한다.
    plugin_ 접두사 카테고리는 settings 키-값 저장소로, 나머지는 실제 라이브러리 권한 테이블로 간다
    (기존 /update 엔드포인트의 분기를 그대로 옮긴 것 - bulk-update/copy-from-user와 공유)."""
    user_id = change.get('user_id')
    library_id = change.get('library_id')
    has_access = 1 if change.get('has_access') else 0
    target_db = change.get('target_db', 'general')

    if user_id is None or library_id is None or str(library_id).strip() == '':
        raise ValueError('user_id와 library_id는 필수 항목입니다.')

    if target_db == 'plugin' or str(library_id).startswith('plugin_'):
        safe_library_id = str(library_id).strip()
        key_perm = f"PERM_CATEGORY_{user_id}_{safe_library_id}"
        SettingsRepository.set_value(key_perm, str(has_access))
    else:
        UserRepository.update_category_permission(target_db, user_id, library_id, has_access)


def _apply_permission_changes_bulk(changes):
    """change 목록을 순차 적용하고 (applied_count, errors) 반환. DB가 general/audiobook/video/
    plugin(설정 테이블)로 갈라져 있어 진짜 단일 트랜잭션은 못 묶으므로 best-effort 루프 +
    실패 항목 개별 보고 방식을 쓴다 - 기존 열 전체선택이 암묵적으로 하던 것과 같은 의미론이다."""
    applied = 0
    errors = []
    for idx, change in enumerate(changes or []):
        try:
            _apply_single_permission_change(change)
            applied += 1
        except Exception as e:
            errors.append({'index': idx, 'error': str(e)})
    return applied, errors


@permission_bp.route('/api/admin/permissions/update', methods=['POST'])
@admin_required
def update_permission():
    """사용자별 특정 카테고리 접근 권한 토글 업데이트"""
    data = request.get_json() or {}

    try:
        _apply_single_permission_change(data)
        return jsonify({'success': True, 'message': '권한 정보가 업데이트되었습니다.'})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return error_response(e)


@permission_bp.route('/api/admin/permissions/bulk-update', methods=['POST'])
@admin_required
def bulk_update_permissions():
    """여러 카테고리 권한 변경을 한 번의 요청으로 반영 (행/열 전체선택, 권한 복사 등에서 사용).
    changes: [{user_id, library_id, has_access, target_db}, ...]"""
    data = request.get_json() or {}
    changes = data.get('changes')
    if not isinstance(changes, list) or not changes:
        return jsonify({'success': False, 'error': 'changes는 비어있지 않은 배열이어야 합니다.'}), 400

    applied, errors = _apply_permission_changes_bulk(changes)
    return jsonify({'success': True, 'applied': applied, 'errors': errors})


@permission_bp.route('/api/admin/permissions/copy-from-user', methods=['POST'])
@admin_required
def copy_permissions_from_user():
    """source_user_id의 현재 카테고리 권한 상태를 target_user_ids 각각에 그대로 복사한다."""
    data = request.get_json() or {}
    source_user_id = data.get('source_user_id')
    target_user_ids = data.get('target_user_ids')
    target_db = data.get('target_db', 'general')

    if not source_user_id or not isinstance(target_user_ids, list) or not target_user_ids:
        return jsonify({'success': False, 'error': 'source_user_id와 target_user_ids는 필수 항목입니다.'}), 400

    try:
        categories, permissions = _fetch_library_permissions(target_db, include_plugins=(target_db == 'general'))
    except Exception as e:
        return error_response(e)

    source_perms = permissions.get(str(source_user_id), {})
    changes = []
    for cat in categories:
        key = f"{target_db}_{cat['id']}"
        has_access = source_perms.get(key, True)
        cat_target_db = cat.get('db_type') or target_db
        for target_user_id in target_user_ids:
            if str(target_user_id) == str(source_user_id):
                continue
            changes.append({
                'user_id': target_user_id,
                'library_id': cat['id'],
                'has_access': has_access,
                'target_db': cat_target_db,
            })

    applied, errors = _apply_permission_changes_bulk(changes)
    return jsonify({'success': True, 'applied': applied, 'errors': errors})

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
        for db_type in USER_DB_TYPES:
            UserRepository.update_adult_access(db_type, user_id, has_adult_access)
        return jsonify({'success': True, 'message': '성인 도서 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return error_response(e)


@permission_bp.route('/api/admin/permissions/update-download', methods=['POST'])
@admin_required
def update_download_permission():
    """사용자별 파일 다운로드 접근 권한 토글 업데이트"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    has_download_access = 1 if data.get('has_download_access') else 0

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id는 필수 항목입니다.'}), 400

    try:
        for db_type in USER_DB_TYPES:
            UserRepository.update_download_access(db_type, user_id, has_download_access)
        return jsonify({'success': True, 'message': '파일 다운로드 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return error_response(e)


@permission_bp.route('/api/admin/permissions/update-content-rating', methods=['POST'])
@admin_required
def update_content_rating_permission():
    """사용자별 콘텐츠 등급(최대 허용 books_lv 등급) 업데이트"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    content_rating_max = data.get('content_rating_max')

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id는 필수 항목입니다.'}), 400

    try:
        content_rating_max = int(content_rating_max)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'content_rating_max 값이 올바르지 않습니다.'}), 400

    if content_rating_max not in SUPPORTED_CONTENT_RATING_LEVELS:
        return jsonify({'success': False, 'error': 'content_rating_max는 0, 15, 18, 19, 20 중 하나여야 합니다.'}), 400

    try:
        target_user = UserRepository.find_by_id('general', user_id)
        if target_user and target_user.get('role') == 'admin' and content_rating_max != LEVEL_PORN:
            return jsonify({
                'success': False,
                'error': '관리자 계정의 최대 허용 등급은 포르노로 고정되어 있습니다.'
            }), 400

        for db_type in USER_DB_TYPES:
            UserRepository.update_content_rating_max(db_type, user_id, content_rating_max)
        return jsonify({'success': True, 'message': '콘텐츠 등급 권한이 변경되었습니다.'})
    except Exception as e:
        return error_response(e)


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
        for db_type in USER_DB_TYPES:
            UserRepository.update_audiobook_access(db_type, user_id, has_audiobook_access)
        return jsonify({'success': True, 'message': '오디오북 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return error_response(e)


@permission_bp.route('/api/admin/permissions/update-video', methods=['POST'])
@admin_required
def update_video_permission():
    """사용자별 영상 강좌 접근 권한 토글 업데이트"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    has_video_access = 1 if data.get('has_video_access') else 0

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id는 필수 항목입니다.'}), 400

    try:
        for db_type in USER_DB_TYPES:
            UserRepository.update_video_access(db_type, user_id, has_video_access)
        return jsonify({'success': True, 'message': '영상 강좌 접근 권한이 변경되었습니다.'})
    except Exception as e:
        return error_response(e)
