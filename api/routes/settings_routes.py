# -*- coding: utf-8 -*-
"""
settings_routes.py – 시스템 설정 관리 라우터
"""
from flask import Blueprint, request, jsonify
from services.settings_service import SettingsService
from services.scheduler_service import SchedulerService
from api.auth import admin_required
from utils.i18n import _t

settings_bp = Blueprint('settings', __name__)

MAX_SETTINGS_REQUEST_BYTES = 32 * 1024
MAX_SETTING_KEY_LENGTH = 64
MAX_SETTING_VALUE_DEFAULT_LENGTH = 4096
SETTING_VALUE_LIMITS = {
    'RCLONE_RC_URL': 512,
    'LAZY_SCAN_CRON': 100,
    'TIMEZONE': 64,
    'SEARCH_SHORTCUT': 64,
    'PROXY_HEADER_TRUSTED_IPS': 2048,
    'WEBHOOK_TOKEN': 512,
    'WEBHOOK_EVENT_SECRET': 1024,
}

@settings_bp.route('/api/media/settings', methods=['GET'])
@admin_required
def get_system_settings():
    """모든 시스템 설정값 조회"""
    db_type = request.args.get('type', 'general')
    try:
        settings = SettingsService.get_all(db_type)
        return jsonify({'success': True, 'settings': settings})
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
