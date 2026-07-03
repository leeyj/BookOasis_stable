# -*- coding: utf-8 -*-
"""
scan_routes.py – 스캔 관리 라우터 (도서 스캔, 표지 스캔 등)
"""
from flask import Blueprint, request, jsonify
from services.book_scan_service import BookScanService
from api.auth import admin_required
from utils.i18n import _t
import database

scan_bp = Blueprint('scan', __name__)

@scan_bp.route('/api/media/books/<int:book_id>/scan', methods=['POST'])
@admin_required
def scan_single_book_api(book_id):
    """특정 개별 도서 즉시 부분 재스캔 실행"""
    db_type = request.form.get('type', 'general')
    try:
        success, message, cover_image = BookScanService.scan_single_book(db_type, book_id)
        if success:
            return jsonify({'success': True, 'message': message, 'cover_image': cover_image})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/<int:library_id>/scan', methods=['POST'])
@admin_required
def trigger_library_scan(library_id):
    """지정된 라이브러리 카테고리 즉시 비동기 스캔 실행"""
    db_type = request.form.get('type', 'general')
    force_val = request.form.get('force', 'false').lower()
    force = force_val in ('true', '1')
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        physical_path = row['physical_path']
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        
        from services.scanner_queue import scanner_queue
        scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path, force=force)
        
        return jsonify({'success': True, 'message': _t('api.msg_scan_started')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/<int:library_id>/cancel-scan', methods=['POST'])
@admin_required
def cancel_library_scan(library_id):
    """지정된 라이브러리 카테고리의 진행 중인 스캔을 중단하도록 플래그 갱신"""
    db_type = request.form.get('type', 'general')
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("UPDATE libraries SET scan_status = 'cancelling' WHERE id = ?", (library_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': _t('api.msg_scan_cancelling')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/<int:library_id>/scan-covers', methods=['POST'])
@admin_required
def trigger_library_cover_scan(library_id):
    """지정된 라이브러리 카테고리 표지 전용 즉시 비동기 스캔 실행"""
    db_type = request.form.get('type', 'general')
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        physical_path = row['physical_path']
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        
        from services.scanner_queue import scanner_queue
        scanner_queue.enqueue('cover_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path)
        
        return jsonify({'success': True, 'message': _t('api.msg_cover_scan_started')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
