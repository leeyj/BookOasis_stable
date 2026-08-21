# -*- coding: utf-8 -*-
"""
scan_routes.py – 스캔 관리 라우터 (도서 스캔, 표지 스캔 등)
"""
import os
from flask import Blueprint, request, jsonify
from services.book_scan_service import BookScanService
from api.auth import admin_required
from utils.i18n import _t
import database

scan_bp = Blueprint('scan', __name__)

def get_db_path_for_scan(db_type):
    """db_type에 대응하는 스캔 대상 데이터베이스 경로/식별자 반환 (MariaDB 모드 대응)"""
    return database.get_db_path(db_type)

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
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
        
        if not lib_info:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        physical_path = lib_info['physical_path']
        db_path = get_db_path_for_scan(db_type)
        
        print(
            f"[API-ScanTrigger] 🚀 User requested scan for library_id={library_id}, "
            f"db_type={db_type}, path='{physical_path}', force_raw='{force_val}', force={force}"
        )
        
        from services.scanner_queue import scanner_queue
        enqueued = scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path, force=force, force_requeue=True, trigger_type='manual', is_cron=False)
        if not enqueued:
            print(f"[API-ScanTrigger WARNING] ❌ Enqueue rejected for library_id={library_id}")
            return jsonify({
                'success': False,
                'error': '동일 라이브러리 스캔이 이미 실행 중이거나 대기 중입니다.'
            }), 409
        
        print(f"[API-ScanTrigger SUCCESS] ✅ Library_id={library_id} scan task enqueued successfully.")
        return jsonify({'success': True, 'message': _t('api.msg_scan_started')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _resolve_library_scoped_path(physical_path, rel_path):
    """라이브러리 physical_path(복수 루트 가능) 기준 상대경로를 절대경로로 해석하고,
    경로 탈출(디렉터리 트래버설) 여부를 검증해서 반환한다. 유효하지 않으면 None."""
    from utils.drive_helper import is_gdrive_url

    roots = [p.strip() for p in str(physical_path or '').replace('\r', '').split('\n') if p.strip()]
    roots = [r for r in roots if not is_gdrive_url(r)]

    for root in roots:
        root_norm = os.path.normpath(root)
        candidate = os.path.normpath(os.path.join(root_norm, rel_path))
        root_cmp = os.path.normcase(root_norm)
        cand_cmp = os.path.normcase(candidate)
        if cand_cmp != root_cmp and not cand_cmp.startswith(root_cmp + os.sep):
            continue
        if os.path.exists(candidate):
            return candidate
    return None


@scan_bp.route('/api/media/libraries/<int:library_id>/scan-path', methods=['POST'])
@admin_required
def trigger_library_path_scan(library_id):
    """새로 추가한 특정 도서/시리즈 폴더 하나만 즉시 동기 스캔하여 등록 (주기 전체 스캔과 별개)"""
    db_type = request.form.get('type', 'general')
    rel_path = (request.form.get('path') or '').strip()
    force_val = request.form.get('force', 'false').lower()
    force = force_val in ('true', '1')

    if not rel_path:
        return jsonify({'success': False, 'error': '스캔할 경로(path)가 필요합니다.'}), 400

    try:
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
        if not lib_info:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404

        target_path = _resolve_library_scoped_path(lib_info['physical_path'], rel_path)
        if not target_path:
            return jsonify({'success': False, 'error': '해당 경로를 라이브러리 내에서 찾을 수 없습니다.'}), 404

        db_path = get_db_path_for_scan(db_type)

        print(
            f"[API-ScanPath] 🎯 User requested single-path scan for library_id={library_id}, "
            f"db_type={db_type}, path='{target_path}', force={force}"
        )

        from tools.scanner.core import scan_library_path
        scan_library_path(db_path, library_id, target_path, force=force)

        # 이 경로는 scanner_queue를 거치지 않는 동기 단건 스캔이라 큐 완료 시 캐시 소거가
        # 실행되지 않으므로, 신규 등록 도서가 반영되지 않은 대시보드 캐시가 남지 않도록 직접 소거한다.
        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
            redis_delete_pattern(f"cache:history*:{db_type}:*")
        except Exception as cache_err:
            print(f"[API-ScanPath WARNING] 레디스 캐시 소거 실패: {cache_err}")

        return jsonify({'success': True, 'message': '지정한 경로의 스캔 및 등록이 완료되었습니다.'})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scan_bp.route('/api/media/libraries/<int:library_id>/cancel-scan', methods=['POST'])
@admin_required
def cancel_library_scan(library_id):
    """지정된 라이브러리 카테고리의 진행 중인 스캔을 중단하도록 플래그 갱신"""
    db_type = request.form.get('type', 'general')
    try:
        from repositories.category_repository import CategoryRepository
        CategoryRepository.update_library_scan_status(db_type, library_id, 'cancelling')
        return jsonify({'success': True, 'message': _t('api.msg_scan_cancelling')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/<int:library_id>/scan-covers', methods=['POST'])
@admin_required
def trigger_library_cover_scan(library_id):
    """지정된 라이브러리 카테고리 표지 전용 즉시 비동기 스캔 실행"""
    db_type = request.form.get('type', 'general')
    try:
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
        
        if not lib_info:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        physical_path = lib_info['physical_path']
        db_path = get_db_path_for_scan(db_type)
        
        from services.scanner_queue import scanner_queue
        enqueued = scanner_queue.enqueue('cover_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path, force_requeue=True)
        if not enqueued:
            return jsonify({
                'success': False,
                'error': '동일 라이브러리 표지 스캔이 이미 실행 중이거나 대기 중입니다.'
            }), 409
        
        return jsonify({'success': True, 'message': _t('api.msg_cover_scan_started')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/scan-all', methods=['POST'])
@admin_required
def trigger_all_libraries_scan():
    """모든 라이브러리 카테고리를 순차적으로 대기열(큐)에 적재하여 전체 스캔 실행"""
    db_type = request.form.get('type', 'general')
    force_val = request.form.get('force', 'false').lower()
    force = force_val in ('true', '1')
    try:
        from repositories.category_repository import CategoryRepository
        rows = CategoryRepository.get_all_libraries(db_type)
        
        if not rows:
            return jsonify({'success': False, 'error': _t('api.err_no_libraries')}), 404
        
        db_path = get_db_path_for_scan(db_type)
        from services.scanner_queue import scanner_queue
        
        enqueued_count = 0
        skipped_count = 0
        for r in rows:
            res = scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                                        library_id=r['id'], physical_path=r['physical_path'], force=force, force_requeue=True, trigger_type='manual', is_cron=False)
            if res:
                enqueued_count += 1
            else:
                skipped_count += 1
            
        return jsonify({'success': True, 'message': f'{enqueued_count}개의 카테고리가 순차 스캔 대기열에 추가되었습니다. (중복 제외: {skipped_count})'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def format_relative_time(target_dt_str):
    if not target_dt_str or target_dt_str == '-':
        return '-'
    try:
        from datetime import datetime
        dt = datetime.strptime(target_dt_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 0:
            return '방금 전'
        if seconds < 60:
            return '방금 전'
        minutes = seconds // 60
        if minutes < 60:
            return f'{minutes}분 전'
        hours = minutes // 60
        if hours < 24:
            return f'{hours}시간 전'
        days = hours // 24
        if days == 1:
            return '어제'
        if days < 30:
            return f'{days}일 전'
        months = days // 30
        return f'{months}달 전'
    except Exception:
        return target_dt_str


@scan_bp.route('/api/media/scan-history', methods=['GET'])
@admin_required
def get_scan_history_api():
    """최근 스캔 이력 목록 (최대 20건, 레이지스캔 제외) 조회"""
    try:
        from repositories.scanner_queue_repository import ScannerQueueRepository
        history = ScannerQueueRepository.get_scan_history(limit=20)
        
        for item in history:
            ref_time = item.get('finished_at') or item.get('started_at') or item.get('enqueue_at')
            item['time_ago'] = format_relative_time(ref_time)
            
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

