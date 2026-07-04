# -*- coding: utf-8 -*-
"""
system_routes.py – 시스템 상태, 큐, 정보 조회 라우터
"""
import os
from flask import Blueprint, request, jsonify, session
from api.auth import admin_required, login_required
from flask import render_template
import database

system_bp = Blueprint('system', __name__)

@system_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'BookOasis'
    })

@system_bp.route('/', methods=['GET'])
@system_bp.route('/media-library', methods=['GET'])
@login_required
def index():
    settings = {}
    return render_template('index.html', active_page='media_library', settings=settings)

@system_bp.route('/api/system/status', methods=['GET'])
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

@system_bp.route('/api/media/system/queue', methods=['GET'])
@admin_required
def get_system_queue_status():
    """현재 스캐너 대기열의 상태를 조회합니다."""
    try:
        from services.scanner_queue import scanner_queue
        status = scanner_queue.get_queue_status()
        
        # 라이브러리 ID를 이름으로 변환 (보기 좋게 하기 위함)
        def _enhance_task(task):
            if not task:
                return task
            if task['type'] in ('library_scan', 'cover_scan'):
                db_type = task['kwargs'].get('db_type', 'general')
                lib_id = task['kwargs'].get('library_id')
                task['library_name'] = f"Library {lib_id}"
                if lib_id:
                    try:
                        conn = database.get_connection(db_type)
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM libraries WHERE id = ?", (lib_id,))
                        row = cursor.fetchone()
                        if row:
                            task['library_name'] = f"{row['name']} ({db_type})"
                        conn.close()
                    except Exception:
                        pass
            elif task['type'] == 'lazy_scan':
                task['library_name'] = "전체 시스템 (Lazy Scanner)"
            return task
        
        if status['running']:
            status['running'] = _enhance_task(status['running'])
        
        enhanced_pending = []
        for t in status['pending']:
            enhanced_pending.append(_enhance_task(t))
        status['pending'] = enhanced_pending
        
        return jsonify({'success': True, 'queue': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@system_bp.route('/api/media/system/queue/clear', methods=['POST'])
@admin_required
def clear_system_queue():
    """스캐너 대기열을 일괄 삭제합니다."""
    try:
        from services.scanner_queue import scanner_queue
        count = scanner_queue.clear_queue()
        return jsonify({'success': True, 'message': f'대기열 {count}건이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@system_bp.route('/api/media/about', methods=['GET'])
def get_about_info():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401
    """BookOasis 소프트웨어 정보 및 버전 데이터 리턴"""
    version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'VERSION')
    
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
