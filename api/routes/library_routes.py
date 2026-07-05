# -*- coding: utf-8 -*-
"""
library_routes.py – 라이브러리(카테고리) CRUD 및 스케줄 관리 라우터
"""
import sqlite3
import threading
from flask import Blueprint, request, jsonify
from apscheduler.triggers.cron import CronTrigger
from services.category_service import CategoryService
from services.scheduler_service import run_scan_job, SchedulerService
from api.auth import admin_required
from utils.i18n import _t
from api.helpers.validation import validate_library_paths, parse_remote_flag, normalize_rclone_url
from repositories.category_repository import CategoryRepository
import database

library_bp = Blueprint('library', __name__)

@library_bp.route('/api/media/libraries/add', methods=['POST'])
@admin_required
def add_media_library():
    """신규 라이브러리 카테고리 추가 및 즉시 스캔"""
    db_type = request.form.get('type', 'general')
    name = request.form.get('name', '').strip()
    physical_path = request.form.get('physical_path', '').strip()
    
    target_paths, error = validate_library_paths(physical_path)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    if not name:
        return jsonify({'success': False, 'error': _t('api.err_name_required')}), 400
    
    is_remote_val = request.form.get('is_remote')
    is_remote = parse_remote_flag(is_remote_val, target_paths)
    rclone_rc_url = normalize_rclone_url(request.form.get('rclone_rc_url'))
    icon = request.form.get('icon', 'fa-book').strip() or 'fa-book'
    color = request.form.get('color', '#94a3b8').strip() or '#94a3b8'
    
    try:
        library_id = CategoryService.add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color)
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': _t('api.err_library_name_exists')}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    # 즉시 스캔 비동기 수행
    try:
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        from services.scanner_queue import scanner_queue
        scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path, force=False)
        SchedulerService.reload_all_jobs()
    except Exception as e:
        print(f"[API] Background scan failed: {e}")
    
    return jsonify({'success': True, 'message': _t('api.msg_library_added')})

@library_bp.route('/api/media/libraries/edit', methods=['POST'])
@admin_required
def edit_media_library():
    """라이브러리 카테고리 정보 수정 및 재스캔"""
    db_type = request.form.get('type', 'general')
    library_id = request.form.get('id')
    name = request.form.get('name', '').strip()
    physical_path = request.form.get('physical_path', '').strip()
    
    target_paths, error = validate_library_paths(physical_path)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    if not library_id or not name:
        return jsonify({'success': False, 'error': '필수 매개변수가 누락되었습니다.'}), 400
    
    is_remote_val = request.form.get('is_remote')
    is_remote = parse_remote_flag(is_remote_val, target_paths)
    rclone_rc_url = normalize_rclone_url(request.form.get('rclone_rc_url'))
    icon = request.form.get('icon', 'fa-book').strip() or 'fa-book'
    color = request.form.get('color', '#94a3b8').strip() or '#94a3b8'
    
    # 기존 라이브러리 정보 가져오기 (경로 변경 여부 판단용)
    try:
        old_library = CategoryRepository.get_library_by_id(db_type, int(library_id))
    except Exception as e:
        old_library = None
        print(f"[API Warning] Failed to fetch old library: {e}")
        
    try:
        CategoryService.edit_library(db_type, int(library_id), name, physical_path, is_remote, rclone_rc_url, icon, color)
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': _t('api.err_library_name_exists')}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    # 즉시 스캔 비동기 수행 (경로가 변경된 경우에만)
    is_path_changed = False
    try:
        old_path = CategoryService._clean_physical_path(old_library['physical_path']) if old_library else ""
        new_path = CategoryService._clean_physical_path(physical_path)
        is_path_changed = (old_path != new_path)
        
        if is_path_changed:
            db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
            from services.scanner_queue import scanner_queue
            scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                                 library_id=int(library_id), physical_path=physical_path, force=False)
            print(f"[API] Category {library_id} path changed. Enqueued scan job.")
        else:
            print(f"[API] Category {library_id} meta updated (no path change). Scan skipped.")
            
        SchedulerService.reload_all_jobs()
    except Exception as e:
        print(f"[API Warning] Conditional background scan triggering failed: {e}")
    
    msg_key = 'api.msg_library_edited_with_scan' if is_path_changed else 'api.msg_library_edited_meta_only'
    return jsonify({'success': True, 'message': _t(msg_key)})

@library_bp.route('/api/media/libraries/delete', methods=['POST'])
@admin_required
def delete_media_library():
    """라이브러리 카테고리 및 도서 연쇄 삭제"""
    db_type = request.form.get('type', 'general')
    library_id = request.form.get('id')
    
    if not library_id:
        return jsonify({'success': False, 'error': _t('api.err_library_id_required')}), 400
    
    try:
        CategoryService.delete_library(db_type, int(library_id))
        SchedulerService.remove_job(db_type, int(library_id))
        return jsonify({'success': True, 'message': _t('api.msg_library_deleted')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/libraries/schedules', methods=['GET'])
@admin_required
def get_libraries_schedules():
    """모든 카테고리의 스케줄 및 상태 목록 조회"""
    db_type = request.args.get('type', 'general')
    try:
        rows = CategoryRepository.get_all_libraries(db_type)
        libraries = [_format_library_row(r) for r in rows]
        return jsonify({'success': True, 'libraries': libraries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/libraries/<int:library_id>/schedule', methods=['POST'])
@admin_required
def update_library_schedule(library_id):
    """지정된 라이브러리 카테고리의 크론 스케줄 주기 업데이트"""
    db_type = request.form.get('type', 'general')
    cron_schedule = request.form.get('cron_schedule', '').strip()
    vfs_refresh_val = request.form.get('vfs_refresh_before_scan')
    rclone_rc_url = normalize_rclone_url(request.form.get('rclone_rc_url'))
    
    if len(cron_schedule) > 50:
        return jsonify({'success': False, 'error': _t('api.err_cron_too_long')}), 400
    
    cron_val = cron_schedule if cron_schedule else None
    
    if cron_val:
        try:
            CronTrigger.from_crontab(cron_val)
        except ValueError as e:
            return jsonify({'success': False, 'error': _t('api.err_invalid_cron', error=str(e))}), 400
    
    vfs_refresh = 1 if vfs_refresh_val in ('1', 'true', 'on') else 0
    
    try:
        CategoryRepository.update_schedule(db_type, library_id, cron_val, vfs_refresh, rclone_rc_url)
        row = CategoryRepository.get_library_by_id(db_type, library_id)
        
        if not row:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        import database
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        
        if cron_val:
            success = SchedulerService.register_job(db_type, db_path, library_id, row['physical_path'], cron_val)
            if not success:
                return jsonify({'success': False, 'error': _t('api.err_invalid_cron_general')}), 400
        else:
            SchedulerService.remove_job(db_type, library_id)
        
        return jsonify({'success': True, 'message': _t('api.msg_schedule_updated')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _format_library_row(r):
    """DB 행을 JSON 형식으로 변환"""
    return {
        'id': r['id'],
        'name': r['name'],
        'physical_path': r['physical_path'],
        'cron_schedule': r['cron_schedule'] or '',
        'last_scanned_at': r['last_scanned_at'] or '-',
        'scan_status': r['scan_status'] or 'ready',
        'is_remote': r['is_remote'] or 0,
        'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
        'rclone_rc_url': r['rclone_rc_url'] or ''
    }
