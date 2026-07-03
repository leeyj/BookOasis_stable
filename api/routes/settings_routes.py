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
    key = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()
    
    if not key:
        return jsonify({'success': False, 'error': _t('api.err_setting_key_required')}), 400
    
    if key == 'DB_POOL_SIZE':
        try:
            val = int(value)
            if val < 1 or val > 50:
                raise ValueError()
        except ValueError:
            return jsonify({'success': False, 'error': _t('api.err_db_pool_size_range')}), 400
    
    try:
        SettingsService.set(key, value)
        if key == 'LAZY_SCAN_CRON':
            try:
                SchedulerService.reload_all_jobs()
                print(f"[API] Scheduler reloaded due to LAZY_SCAN_CRON change: {value}")
            except Exception as e_sched:
                print(f"[API WARNING] Failed to reload scheduler on LAZY_SCAN_CRON change: {e_sched}")
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
