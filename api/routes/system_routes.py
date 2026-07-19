# -*- coding: utf-8 -*-
"""
system_routes.py – 시스템 상태, 큐, 정보 조회 라우터
"""
import os
import re
from flask import Blueprint, request, jsonify, session
from api.auth import admin_required, login_required
from flask import render_template
from urllib.request import Request, urlopen
from services.plugin_service import PluginService
from services.settings_service import SettingsService
import database

system_bp = Blueprint('system', __name__)

def get_library_name(db_type, lib_id):
    """라이브러리 ID에 대치되는 실제 카테고리(라이브러리) 명칭을 DB에서 조회합니다."""
    if not lib_id:
        return None
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM libraries WHERE id = ?", (lib_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['name']
    except Exception:
        pass
    return None

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
    view_log_enabled = os.environ.get('VIEW_LOG', 'false').lower() == 'true'
    return render_template('index.html', active_page='media_library', settings=settings, view_log_enabled=view_log_enabled)

@system_bp.route('/api/system/status', methods=['GET'])
def get_system_status():
    """현재 백그라운드 스캔 상태를 메모리 기반으로 조회합니다."""
    db_type = request.args.get('type', 'general')
    try:
        # 1. DB 튜닝 중 여부 (메모리 플래그)
        tuning_active = database.is_db_tuning(db_type)
        from services.scanner_queue import scanner_queue
        status = scanner_queue.get_queue_status()

        running_tasks = []
        has_running = False
        has_pending = False
        is_active = False

        running = status.get('running')
        if running:
            has_running = True
            is_active = True
            task_type = running.get('type')
            kwargs = running.get('kwargs', {})
            db_t = kwargs.get('db_type', db_type)
            lib_id = kwargs.get('library_id')
            
            # 라이브러리 ID를 실제 명칭으로 치환
            lib_name = get_library_name(db_t, lib_id)
            target_disp = lib_name if lib_name else f"Library {lib_id}"
            
            if task_type == 'library_scan':
                running_tasks.append(f"[{target_disp} ({db_t})] 카테고리 도서 자동 스캔 동기화 진행 중...")
            elif task_type == 'cover_scan':
                running_tasks.append(f"[{target_disp} ({db_t})] 표지 전용 스캔 진행 중...")
            elif task_type == 'lazy_scan':
                running_tasks.append("[전체 시스템] Lazy Scanner 실행 중...")
            else:
                running_tasks.append("백그라운드 작업 진행 중...")

        pending = status.get('pending', [])
        if pending:
            has_pending = True
            running_tasks.append(f"스캔 대기열: {len(pending)}건")
        
        if tuning_active:
            is_active = True
            running_tasks.append("데이터베이스 파일 물리 파편화 압축 정리 및 인덱스 정밀 튜닝 실행 중...")

        # 실제 '동작 중' 표시는 running/tuning 기준으로만 활성화한다.
        # pending만 남아있는 경우는 대기 상태로 간주한다.
        is_active = bool(has_running or tuning_active)

        return jsonify({
            'success': True,
            'is_active': is_active,
            'tasks': running_tasks,
            'has_running': has_running,
            'has_pending': has_pending,
            'pending_count': len(pending)
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
        
        # 라이브러리 명칭 DB 룩업 보완
        def _enhance_task(task):
            if not task:
                return task
            if task['type'] in ('library_scan', 'cover_scan'):
                db_type = task['kwargs'].get('db_type', 'general')
                lib_id = task['kwargs'].get('library_id')
                lib_name = get_library_name(db_type, lib_id)
                task['library_name'] = f"{lib_name} ({db_type})" if lib_name else f"Library {lib_id} ({db_type})"
            elif task['type'] == 'lazy_scan':
                task['library_name'] = "전체 시스템 (Lazy Scanner)"
            return task
        
        if status['running']:
            status['running'] = _enhance_task(status['running'])
        
        enhanced_pending = []
        for t in status['pending']:
            enhanced_pending.append(_enhance_task(t))
        status['pending'] = enhanced_pending

        response = jsonify({'success': True, 'queue': status})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
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

@system_bp.route('/api/media/system/queue/cancel', methods=['POST'])
@admin_required
def cancel_system_queue_task():
    """대기열에 있는 특정 스캐너 작업 1건을 취소합니다."""
    task_id = request.args.get('task_id') or request.form.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'error': 'task_id가 필요합니다.'}), 400

    try:
        from services.scanner_queue import scanner_queue
        removed = scanner_queue.cancel_pending_task(task_id)
        if not removed:
            return jsonify({'success': False, 'error': '대기열에서 작업을 찾지 못했습니다.'}), 404

        return jsonify({'success': True, 'message': '대기열 작업이 취소되었습니다.'})
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
                    line_clean = line.strip().replace('"', '')
                    if line_clean.startswith('dashboard:'):
                        dashboard_ver = line_clean.split(':', 1)[1].strip()
                    elif line_clean.startswith('state:'):
                        state_ver = line_clean.split(':', 1)[1].strip()
        except Exception as e:
            pass
    
    github_dashboard_ver = None
    update_check = {
        'can_update': False,
        'reason': 'github_version_unavailable'
    }

    try:
        req = Request(
            'https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/VERSION',
            headers={'User-Agent': 'BookOasis/1.0'}
        )
        with urlopen(req, timeout=5) as resp:
            text = resp.read().decode('utf-8', errors='replace')
            match = re.search(r'"dashboard"\s*:\s*"([^"]+)"', text)
            if match:
                github_dashboard_ver = match.group(1).strip()
    except Exception:
        github_dashboard_ver = None

    if github_dashboard_ver:
        try:
            can_update, reason = PluginService.can_update_to_github_version(dashboard_ver, github_dashboard_ver)
            update_check = {
                'can_update': can_update,
                'reason': reason
            }
        except Exception:
            update_check = {
                'can_update': False,
                'reason': 'version_compare_failed'
            }

    return jsonify({
        'success': True,
        'version': {
            'dashboard': dashboard_ver,
            'state': state_ver
        },
        'github_version': {
            'dashboard': github_dashboard_ver
        },
        'update': update_check,
        'github_url': 'https://github.com/leeyj/BookOasis_stable'
    })

@system_bp.route('/api/webhook/scan', methods=['GET', 'POST'])
def trigger_scan_via_webhook():
    """외부 CLI 및 마운트 갱신 툴(gd-poller 등) 연동용 토큰 인증 방식 실시간 스캔 트리거 API"""
    token = request.args.get('token') or request.form.get('token')
    library_id = request.args.get('library_id') or request.form.get('library_id')
    db_type = request.args.get('type') or request.form.get('type') or 'general'
    
    # 1. 보안 토큰 검증
    sys_token = SettingsService.get('WEBHOOK_TOKEN', '', db_type='general') or os.environ.get('WEBHOOK_TOKEN')
    if not sys_token or not token or token != sys_token:
        return jsonify({'success': False, 'error': 'Invalid webhook token.'}), 401
        
    if not library_id:
        return jsonify({'success': False, 'error': 'library_id is required.'}), 400
        
    # 2. 백그라운드 스캔 대기열 주입
    try:
        from services.scanner_queue import scanner_queue
        scanner_queue.add_task('library_scan', db_type=db_type, library_id=int(library_id))
        
        # 실제 카테고리명 조회
        lib_name = get_library_name(db_type, int(library_id))
        disp_name = lib_name if lib_name else f"Library {library_id}"
        
        return jsonify({
            'success': True, 
            'message': f'"{disp_name} ({db_type})" 스캔 작업이 대기열에 성공적으로 등록되었습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
