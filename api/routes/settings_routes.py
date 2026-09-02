# -*- coding: utf-8 -*-
"""
settings_routes.py – 시스템 설정 관리 라우터
"""
from flask import Blueprint, request, jsonify, session
from services.settings_service import SettingsService
from services.scheduler_service import SchedulerService
from api.auth import admin_required, login_required
from utils.i18n import _t

settings_bp = Blueprint('settings', __name__)

MAX_SETTINGS_REQUEST_BYTES = 32 * 1024
MAX_SETTING_KEY_LENGTH = 64
MAX_SETTING_VALUE_DEFAULT_LENGTH = 4096
SETTING_VALUE_LIMITS = {
    'RCLONE_RC_URL': 512,
    'LAZY_SCAN_CRON': 100,
    'SCAN_IGNORE_PATTERNS': 4096,
    'TIMEZONE': 64,
    'SEARCH_SHORTCUT': 64,
    'PROXY_HEADER_TRUSTED_IPS': 2048,
    'WEBHOOK_TOKEN': 512,
    'WEBHOOK_EVENT_SECRET': 1024,
}

# applySettingsToUI()가 모든 로그인 사용자의 화면 렌더링/동작에 사용하는 값들.
# 민감한 키(RCLONE_RC_URL, WEBHOOK_TOKEN, DB 풀 크기 등)는 절대 포함하지 않는다 -
# 그런 값은 /api/media/settings(관리자 전용)로만 제공된다.
PUBLIC_UI_SETTING_KEYS = (
    'BOOK_THUMBNAIL_WIDTH',
    'PAGE_LIMIT',
    'HIDE_COMPLETED_IN_HISTORY',
    'TAG_FILTER_SEARCH_SCOPE_ALL',
    'SHOW_TXT_NO_COVER_INFO_BANNER',
    'SHOW_SIDEBAR_CATEGORY_ALL',
    'HDD_AGGRESSIVE_WARMUP',
    'AUDIO_MINI_PLAYER_MODE',
    'AUDIO_RIGHT_DOCK_DIM_ENABLED',
    'TTS_ENABLED',
    'TTS_WAKE_LOCK',
    'DETAIL_VOLUME_GRID_VIEW',
    'COLLAPSE_DETAIL_GENRE_TAGS',
    'SMART_RECOMMEND_ENABLED',
    'BOOK_RECOMMEND_ENABLED',
)

# 사용자가 자신의 계정에서 개인화(override)할 수 있는 설정 키.
# 관리자 전역 설정(DB_POOL_SIZE, LAZY_SCAN_CRON, TIMEZONE, RCLONE_RC_URL, WEBHOOK_TOKEN 등
# 보안/스캔/시스템 값)은 절대 포함하지 않는다 - 이 목록은 UI/열람 취향에 한정된다.
USER_OVERRIDABLE_SETTING_KEYS = (
    'DASHBOARD_THEME',
    'SHOW_DASHBOARD_INSIGHTS',
    'VIEWER_FONT_SIZE',
    'VIEWER_FONT_FAMILY',
    'DETAIL_VOLUME_GRID_VIEW',
    'COLLAPSE_DETAIL_GENRE_TAGS',
    'AUDIO_MINI_PLAYER_MODE',
    'AUDIO_RIGHT_DOCK_DIM_ENABLED',
    'SHOW_SIDEBAR_CATEGORY_ALL',
    'HIDE_COMPLETED_IN_HISTORY',
    'TAG_FILTER_SEARCH_SCOPE_ALL',
    'SHOW_TXT_NO_COVER_INFO_BANNER',
    'SMART_RECOMMEND_ENABLED',
    'BOOK_RECOMMEND_ENABLED',
)

@settings_bp.route('/api/media/settings', methods=['GET'])
@admin_required
def get_system_settings():
    """모든 시스템 설정값 조회"""
    # 예전에는 도서관 종류(adult/audiobook/video)별로 settings 테이블을 따로 두고
    # ?type= 쿼리로 구분했으나, 실제로는 모두 general과 동일하거나(adult) 아무도
    # 편집한 적 없는 시드 기본값(audiobook/video)뿐이었다. 지금은 general 하나만
    # 읽고 쓰므로 type 파라미터는 무시한다 - 캐시된 구버전 JS가 여전히 붙여 보내도
    # 에러 없이 동작하도록 값만 받고 사용하지 않는다.
    try:
        settings = SettingsService.get_all()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/public', methods=['GET'])
@login_required
def get_public_ui_settings():
    """
    화면 렌더링/동작에 필요한 공개 설정값만 반환 (관리자 여부와 무관하게 모든 로그인
    사용자가 조회 가능). 관리자가 저장한 값이 일반 사용자 세션에도 동일하게 반영되도록
    최초 로드 시 이 엔드포인트를 사용한다.
    """
    try:
        all_settings = SettingsService.get_all()
        user_id = session.get('user_id')
        public_settings = {}
        for k, v in all_settings.items():
            if k not in PUBLIC_UI_SETTING_KEYS:
                continue
            if k in USER_OVERRIDABLE_SETTING_KEYS:
                public_settings[k] = SettingsService.get_effective(k, user_id=user_id, default=v)
            else:
                public_settings[k] = v
        return jsonify({'success': True, 'settings': public_settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings', methods=['POST'])
@admin_required
def update_system_setting():
    """시스템 설정값 추가 및 업데이트"""
    content_length = request.content_length
    if content_length is not None and content_length > MAX_SETTINGS_REQUEST_BYTES:
        return jsonify({'success': False, 'error': '설정 요청 본문이 너무 큽니다.'}), 413

    key = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()
    
    if not key:
        return jsonify({'success': False, 'error': _t('api.err_setting_key_required')}), 400
    if len(key) > MAX_SETTING_KEY_LENGTH:
        return jsonify({'success': False, 'error': f'설정 키 길이는 최대 {MAX_SETTING_KEY_LENGTH}자까지 허용됩니다.'}), 400

    max_value_len = SETTING_VALUE_LIMITS.get(key, MAX_SETTING_VALUE_DEFAULT_LENGTH)
    if len(value) > max_value_len:
        return jsonify({'success': False, 'error': f'설정 값 길이는 최대 {max_value_len}자까지 허용됩니다. ({key})'}), 400
    
    if key == 'DB_POOL_SIZE':
        try:
            val = int(value)
            if val < 1 or val > 50:
                raise ValueError()
        except ValueError:
            return jsonify({'success': False, 'error': _t('api.err_db_pool_size_range')}), 400
    
    try:
        SettingsService.set(key, value)
        if key == 'DB_POOL_SIZE':
            import database
            database.invalidate_pool_size_cache()
        if key in ('LAZY_SCAN_CRON', 'TIMEZONE'):
            try:
                SchedulerService.reload_all_jobs()
                print(f"[API] Scheduler reloaded due to {key} change: {value}")
            except Exception as e_sched:
                print(f"[API WARNING] Failed to reload scheduler on {key} change: {e_sched}")
        return jsonify({'success': True, 'message': _t('api.msg_setting_saved', key=key)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/user', methods=['GET'])
@login_required
def get_user_settings():
    """호출한 사용자 본인의 설정 오버라이드 + 전역 기본값을 병합한 유효값 반환."""
    user_id = session.get('user_id')
    try:
        effective = {}
        globals_ = SettingsService.get_all()
        user_overrides = SettingsService.get_all_user_settings(user_id)
        for k in USER_OVERRIDABLE_SETTING_KEYS:
            if k in user_overrides:
                effective[k] = user_overrides[k]
            elif k in globals_:
                effective[k] = globals_[k]
        return jsonify({'success': True, 'settings': effective, 'overrides': user_overrides})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/user', methods=['POST'])
@login_required
def update_user_setting():
    """호출한 사용자 본인의 설정 오버라이드 저장 (허용 목록 내 키만)."""
    user_id = session.get('user_id')
    key = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()
    if key not in USER_OVERRIDABLE_SETTING_KEYS:
        return jsonify({'success': False, 'error': f'허용되지 않은 사용자 설정 키입니다: {key}'}), 400
    max_value_len = SETTING_VALUE_LIMITS.get(key, MAX_SETTING_VALUE_DEFAULT_LENGTH)
    if len(value) > max_value_len:
        return jsonify({'success': False, 'error': f'설정 값 길이는 최대 {max_value_len}자까지 허용됩니다. ({key})'}), 400
    try:
        SettingsService.set_user_value(user_id, key, value)
        return jsonify({'success': True, 'message': _t('api.msg_setting_saved', key=key)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/trigger-lazy-scan', methods=['POST'])
@admin_required
def trigger_lazy_scan_api():
    """Lazy 표지 스캔 강제 즉시 실행 API"""
    try:
        from services.scheduler_service import run_lazy_scanner_job
        import threading
        threading.Thread(
            target=run_lazy_scanner_job,
            daemon=True
        ).start()
        return jsonify({'success': True, 'message': _t('api.msg_lazy_scanner_triggered')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/custom-themes', methods=['GET'])
@login_required
def get_custom_themes():
    """themes/*.yaml 검증 통과분의 id/label 목록 (테마 선택 드롭다운 동적 렌더링용)."""
    try:
        from services.custom_theme_service import get_themes
        themes = [{'id': t['id'], 'label': t['label']} for t in get_themes()]
        return jsonify({'success': True, 'themes': themes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/custom-themes.css', methods=['GET'])
@login_required
def get_custom_themes_css():
    """검증 통과한 커스텀 테마들을 [data-app-theme="id"] CSS 블록으로 렌더링."""
    try:
        from flask import Response
        from services.custom_theme_service import generate_css
        response = Response(generate_css(), mimetype='text/css')
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/media/settings/custom-themes/rescan', methods=['POST'])
@admin_required
def rescan_custom_themes():
    """themes/ 디렉토리를 다시 스캔해 캐시를 갱신 (관리자 전용)."""
    try:
        from services.custom_theme_service import load_themes, get_last_rejected
        loaded_count, rejected_count = load_themes()
        return jsonify({
            'success': True,
            'loaded_count': loaded_count,
            'rejected': get_last_rejected(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
