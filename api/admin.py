# -*- coding: utf-8 -*-
"""
admin.py – 라이브러리 CUD, 스케줄 관리 및 강제 재스캔 라우터 (Management/Admin Layer)
"""
import os
import sqlite3
import threading
from flask import Blueprint, request, jsonify
from services.category_service import CategoryService
from services.scheduler_service import run_scan_job, SchedulerService
from services.book_scan_service import BookScanService
from services.settings_service import SettingsService
import database

from api.auth import admin_required

admin_bp = Blueprint('media_admin', __name__)

@admin_bp.route('/api/media/libraries/add', methods=['POST'])
@admin_required
def add_media_library():
    """신규 라이브러리 카테고리 추가 및 즉시 스캔"""
    db_type = request.form.get('type', 'general')
    name = request.form.get('name', '').strip()
    physical_path = request.form.get('physical_path', '').strip()
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        return jsonify({'success': False, 'error': '물리 경로를 최소 1개 이상 입력해야 합니다.'}), 400

    is_remote_val = request.form.get('is_remote')
    if is_remote_val in ('1', 'true', 'on'):
        is_remote = 1
    elif is_remote_val in ('0', 'false'):
        is_remote = 0
    else:
        from utils.drive_helper import is_remote_path
        is_remote = 1 if any(is_remote_path(p) for p in target_paths) else 0

    if not name:
        return jsonify({'success': False, 'error': '이름은 필수 입력 사항입니다.'}), 400

    invalid_paths = [p for p in target_paths if not os.path.exists(p)]
    if invalid_paths:
        error_msg = '다음 경로들이 서버에 존재하지 않거나 오타가 있습니다:\n' + '\n'.join(invalid_paths)
        return jsonify({'success': False, 'error': error_msg}), 400

    rclone_rc_url = request.form.get('rclone_rc_url', '').strip() or None
    try:
        library_id = CategoryService.add_library(db_type, name, physical_path, is_remote, rclone_rc_url)
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': '이미 존재하는 라이브러리 이름입니다.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    # 즉시 스캔 비동기 수행
    try:
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        threading.Thread(
            target=run_scan_job,
            args=(db_type, db_path, library_id, physical_path),
            daemon=True
        ).start()
        SchedulerService.reload_all_jobs()
    except Exception as e:
        print(f"[API] 스캔 백그라운드 구동 실패: {e}")

    return jsonify({'success': True, 'message': '라이브러리가 추가되었으며 백그라운드 스캔을 시작합니다.'})

@admin_bp.route('/api/media/libraries/edit', methods=['POST'])
@admin_required
def edit_media_library():
    """라이브러리 카테고리 정보 수정 및 재스캔"""
    db_type = request.form.get('type', 'general')
    library_id = request.form.get('id')
    name = request.form.get('name', '').strip()
    physical_path = request.form.get('physical_path', '').strip()
    target_paths = [p.strip() for p in str(physical_path).replace('\r', '').split('\n') if p.strip()]
    if not target_paths:
        return jsonify({'success': False, 'error': '물리 경로를 최소 1개 이상 입력해야 합니다.'}), 400

    is_remote_val = request.form.get('is_remote')
    if is_remote_val in ('1', 'true', 'on'):
        is_remote = 1
    elif is_remote_val in ('0', 'false'):
        is_remote = 0
    else:
        from utils.drive_helper import is_remote_path
        is_remote = 1 if any(is_remote_path(p) for p in target_paths) else 0

    if not library_id or not name:
        return jsonify({'success': False, 'error': '필수 매개변수가 누락되었습니다.'}), 400

    invalid_paths = [p for p in target_paths if not os.path.exists(p)]
    if invalid_paths:
        error_msg = '다음 경로들이 서버에 존재하지 않거나 오타가 있습니다:\n' + '\n'.join(invalid_paths)
        return jsonify({'success': False, 'error': error_msg}), 400

    rclone_rc_url = request.form.get('rclone_rc_url', '').strip() or None
    try:
        CategoryService.edit_library(db_type, int(library_id), name, physical_path, is_remote, rclone_rc_url)
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': '이미 존재하는 라이브러리 이름입니다.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    # 즉시 스캔 비동기 수행
    try:
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        threading.Thread(
            target=run_scan_job,
            args=(db_type, db_path, int(library_id), physical_path),
            daemon=True
        ).start()
        SchedulerService.reload_all_jobs()
    except Exception as e:
        print(f"[API] 수정 후 재스캔 구동 실패: {e}")

    return jsonify({'success': True, 'message': '라이브러리 정보가 수정되었으며 스캔을 갱신합니다.'})

@admin_bp.route('/api/media/libraries/delete', methods=['POST'])
@admin_required
def delete_media_library():
    """라이브러리 카테고리 및 도서 연쇄 삭제"""
    db_type = request.form.get('type', 'general')
    library_id = request.form.get('id')

    if not library_id:
        return jsonify({'success': False, 'error': '라이브러리 ID가 필요합니다.'}), 400

    try:
        CategoryService.delete_library(db_type, int(library_id))
        SchedulerService.remove_job(db_type, int(library_id))
        return jsonify({'success': True, 'message': '라이브러리 및 하위 도서 정보가 정상적으로 연쇄 소거되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/books/<int:book_id>/scan', methods=['POST'])
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

@admin_bp.route('/api/media/libraries/schedules', methods=['GET'])
@admin_required
def get_libraries_schedules():
    """모든 카테고리의 스케줄 및 상태 목록 조회"""
    db_type = request.args.get('type', 'general')
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url FROM libraries ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        
        libraries = []
        for r in rows:
            libraries.append({
                'id': r['id'],
                'name': r['name'],
                'physical_path': r['physical_path'],
                'cron_schedule': r['cron_schedule'] or '',
                'last_scanned_at': r['last_scanned_at'] or '-',
                'scan_status': r['scan_status'] or 'ready',
                'is_remote': r['is_remote'] or 0,
                'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
                'rclone_rc_url': r['rclone_rc_url'] or ''
            })
        return jsonify({'success': True, 'libraries': libraries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/libraries/<int:library_id>/scan', methods=['POST'])
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
            return jsonify({'success': False, 'error': '존재하지 않는 라이브러리입니다.'}), 404
            
        physical_path = row['physical_path']
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        
        threading.Thread(
            target=run_scan_job,
            args=(db_type, db_path, library_id, physical_path),
            kwargs={'force': force},
            daemon=True
        ).start()
        
        return jsonify({'success': True, 'message': '즉시 스캔을 시작했습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/libraries/<int:library_id>/cancel-scan', methods=['POST'])
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
        return jsonify({'success': True, 'message': '스캔 중단 요청이 전달되었습니다. 곧 안전하게 멈춥니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/libraries/<int:library_id>/scan-covers', methods=['POST'])
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
            return jsonify({'success': False, 'error': '존재하지 않는 라이브러리입니다.'}), 404
            
        physical_path = row['physical_path']
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        
        from services.cover_scan_service import CoverScanService
        threading.Thread(
            target=CoverScanService.run_cover_scan_job,
            args=(db_type, db_path, library_id, physical_path),
            daemon=True
        ).start()
        
        return jsonify({'success': True, 'message': '표지 새로고침 스캔을 시작했습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/libraries/<int:library_id>/schedule', methods=['POST'])
@admin_required
def update_library_schedule(library_id):
    """지정된 라이브러리 카테고리의 크론 스케줄 주기 업데이트"""
    db_type = request.form.get('type', 'general')
    cron_schedule = request.form.get('cron_schedule', '').strip()
    vfs_refresh_val = request.form.get('vfs_refresh_before_scan')
    rclone_rc_url = request.form.get('rclone_rc_url', '').strip() or None
    
    if len(cron_schedule) > 50:
        return jsonify({'success': False, 'error': '크론 표현식은 50자를 초과할 수 없습니다.'}), 400
        
    cron_val = cron_schedule if cron_schedule else None
    
    if cron_val:
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(cron_val)
        except ValueError as e:
            return jsonify({'success': False, 'error': f'잘못된 크론 형식입니다: {e}'}), 400
            
    vfs_refresh = 1 if vfs_refresh_val in ('1', 'true', 'on') else 0
    
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("UPDATE libraries SET cron_schedule = ?, vfs_refresh_before_scan = ?, rclone_rc_url = ? WHERE id = ?", (cron_val, vfs_refresh, rclone_rc_url, library_id))
        
        cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': '존재하지 않는 라이브러리입니다.'}), 404
            
        db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
        
        if cron_val:
            success = SchedulerService.register_job(db_type, db_path, library_id, row['physical_path'], cron_val)
            if not success:
                return jsonify({'success': False, 'error': '유효하지 않은 크론 표현식입니다.'}), 400
        else:
            SchedulerService.remove_job(db_type, library_id)
            
        return jsonify({'success': True, 'message': '스케줄이 성공적으로 업데이트되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/settings', methods=['GET'])
@admin_required
def get_system_settings():
    """모든 시스템 설정값 조회"""
    db_type = request.args.get('type', 'general')
    try:
        settings = SettingsService.get_all(db_type)
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/media/settings', methods=['POST'])
@admin_required
def update_system_setting():
    """시스템 설정값 추가 및 업데이트"""
    key = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()
    
    if not key:
        return jsonify({'success': False, 'error': '설정 키(key)는 필수 파라미터입니다.'}), 400
        
    if key == 'DB_POOL_SIZE':
        try:
            val = int(value)
            if val < 1 or val > 50:
                raise ValueError()
        except ValueError:
            return jsonify({'success': False, 'error': 'DB 커넥션 풀 크기는 1에서 50 사이의 정수여야 합니다.'}), 400

    try:
        SettingsService.set(key, value)
        if key == 'LAZY_SCAN_CRON':
            try:
                SchedulerService.reload_all_jobs()
                print(f"[API] LAZY_SCAN_CRON 변경으로 스케줄러 리로드 완료: {value}")
            except Exception as e_sched:
                print(f"[API WARNING] LAZY_SCAN_CRON 변경 시 스케줄러 갱신 실패: {e_sched}")
        return jsonify({'success': True, 'message': f'"{key}" 설정이 성공적으로 저장되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/system/status', methods=['GET'])
def get_system_status():
    """현재 백그라운드 스캔 상태 및 DB 최적화 튜닝 작업 상태 조회"""
    db_type = request.args.get('type', 'general')
    try:
        # 1. DB 튜닝 중 여부 파악
        tuning_active = database.is_db_tuning(db_type)
        
        # 2. 카테고리 중 'scanning' 상태인 건이 있는지 파악
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM libraries WHERE scan_status = 'scanning'")
        scanning_libs = cursor.fetchall()
        conn.close()
        
        running_tasks = []
        is_active = False
        
        if scanning_libs:
            is_active = True
            for lib in scanning_libs:
                running_tasks.append(f"[{lib['name']}] 카테고리 도서 자동 스캔 동기화 진행 중...")
                
        if tuning_active:
            is_active = True
            running_tasks.append("데이터베이스 파일 물리 파편화 압축 정리 및 인덱스 정밀 튜닝 실행 중...")
            
        return jsonify({
            'success': True,
            'is_active': is_active,
            'tasks': running_tasks
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/media/libraries/<int:library_id>/reports', methods=['GET'])
@admin_required
def get_library_reports(library_id):
    """특정 라이브러리 카테고리의 스캔 에러 리포트 목록 조회"""
    try:
        from utils.report_helper import get_reports_dir
        import glob
        import json
        reports_dir = get_reports_dir()
        pattern = os.path.join(reports_dir, f"{library_id}_*.json")
        files = glob.glob(pattern)
        # 파일명 기준 역순(최신순) 정렬
        files.sort(key=os.path.basename, reverse=True)
        
        report_list = []
        for filepath in files:
            filename = os.path.basename(filepath)
            parts = filename.replace('.json', '').split('_')
            timestamp_str = parts[-1] if len(parts) > 1 else ''
            try:
                formatted_time = f"{timestamp_str[0:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]} {timestamp_str[8:10]}:{timestamp_str[10:12]}:{timestamp_str[12:14]}"
            except Exception:
                formatted_time = timestamp_str
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    errors_count = data.get('errors_count', 0)
            except Exception:
                errors_count = 0
                
            report_list.append({
                'filename': filename,
                'timestamp': formatted_time,
                'errors_count': errors_count
            })
        return jsonify({'success': True, 'reports': report_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/media/libraries/reports/view', methods=['GET'])
@admin_required
def view_report_detail():
    """특정 리포트 파일의 에러 리스트 상세 조회"""
    filename = request.args.get('file', '').strip()
    if not filename:
        return jsonify({'success': False, 'error': '파일명(file) 파라미터가 유효하지 않습니다.'}), 400
        
    filename = os.path.basename(filename)
    
    try:
        from utils.report_helper import get_reports_dir
        import json
        reports_dir = get_reports_dir()
        filepath = os.path.join(reports_dir, filename)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': '요청한 리포트 파일을 찾을 수 없습니다.'}), 404
            
        with open(filepath, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        return jsonify({'success': True, 'report': report_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/media/settings/trigger-lazy-scan', methods=['POST'])
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
        return jsonify({'success': True, 'message': 'Lazy 표지 스캐너를 즉시 기동했습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/media/about', methods=['GET'])
@admin_required
def get_about_info():
    """BookOasis 소프트웨어 정보 및 버전 데이터 리턴"""
    import os
    version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'VERSION')
    
    dashboard_ver = '0.2.6'
    state_ver = 'pre-alpha'
    
    if os.path.exists(version_path):
        try:
            with open(version_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('"dashboard":'):
                        dashboard_ver = line.replace('"dashboard":', '').replace('"', '').strip()
                    elif line.startswith('"state":'):
                        state_ver = line.replace('"state":', '').replace('"', '').strip()
        except Exception as e:
            pass
            
    return jsonify({
        'success': True,
        'version': {
            'dashboard': dashboard_ver,
            'state': state_ver
        },
        'github_url': 'https://github.com/leeyj/BookOasis_stable'
    })



