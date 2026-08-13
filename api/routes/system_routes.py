# -*- coding: utf-8 -*-
"""
system_routes.py – 시스템 상태, 큐, 정보 조회 라우터
"""
import os
import re
from flask import Blueprint, request, jsonify, session
from api.auth import admin_required, login_required, verify_webhook_token
from flask import render_template
from urllib.request import Request, urlopen
from services.plugin_service import PluginService
from services.settings_service import SettingsService
import database

system_bp = Blueprint('system', __name__)

_LIB_NAME_MEM_CACHE = {}

def get_library_name(db_type, lib_id):
    """라이브러리 ID에 대치되는 실제 카테고리(라이브러리) 명칭을 메모리 캐시에서 즉시 조회합니다 (DB Lock 예방)."""
    if not lib_id:
        return None
    cache_key = f"{db_type}:{lib_id}"
    if cache_key in _LIB_NAME_MEM_CACHE:
        return _LIB_NAME_MEM_CACHE[cache_key]

    try:
        from repositories.category_repository import CategoryRepository
        lib = CategoryRepository.get_library_by_id(db_type, lib_id)
        if lib:
            name = lib.get('name')
            _LIB_NAME_MEM_CACHE[cache_key] = name
            return name
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
@login_required
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

        # 실행 중인 스캔 태스크, 대기열(pending) 태스크, DB 튜닝 작업 중 하나라도 존재하면 활성화
        is_active = bool(has_running or has_pending or tuning_active)

        def _add_library_name(task):
            if not task:
                return task
            kwargs = task.get('kwargs', {})
            task_db_type = kwargs.get('db_type', db_type)
            library_id = kwargs.get('library_id')
            if library_id is not None:
                library_name = get_library_name(task_db_type, library_id)
                if library_name:
                    task['library_name'] = library_name
            elif task.get('type') == 'lazy_scan':
                task['library_name'] = '전체 시스템'
            return task

        if status.get('running'):
            _add_library_name(status['running'])
        for pending_task in status.get('pending', []):
            _add_library_name(pending_task)

        response = jsonify({
            'success': True,
            'is_active': is_active,
            'tasks': running_tasks,
            'raw_status': status,
            'has_running': has_running,
            'has_pending': has_pending,
            'pending_count': len(pending)
        })
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
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
    force_param = request.args.get('force') or request.form.get('force')
    force_requeue = True if force_param in ('1', 'true', 'True', 'on') else False
    rel_path = (request.args.get('path') or request.form.get('path') or '').strip()

    # 1. 보안 토큰 검증
    if not verify_webhook_token(token):
        return jsonify({'success': False, 'error': 'Invalid webhook token.'}), 401

    if not library_id:
        return jsonify({'success': False, 'error': 'library_id is required.'}), 400

    try:
        lib_id_int = int(library_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid library_id format.'}), 400

    # 2. 보관함 존재 여부, 경로 및 카테고리명 조회
    physical_path = None
    lib_name = None
    try:
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, lib_id_int)
        if lib_info:
            physical_path = lib_info.get('physical_path')
            lib_name = lib_info.get('name')
    except Exception as db_err:
        return jsonify({'success': False, 'error': f'Failed to query library info: {db_err}'}), 500

    if not lib_name or not physical_path:
        return jsonify({'success': False, 'error': f'Library ID {library_id} not found in {db_type}.'}), 404

    # 2-1. path가 지정된 경우: 시리즈/폴더 단위 즉시 동기 스캔 (전체 스캔 큐를 타지 않음)
    if rel_path:
        try:
            from api.routes.scan_routes import _resolve_library_scoped_path, get_db_path_for_scan
            target_path = _resolve_library_scoped_path(physical_path, rel_path)
            if not target_path:
                return jsonify({'success': False, 'error': f'Path not found within library: {rel_path}'}), 404

            db_path = get_db_path_for_scan(db_type)
            from tools.scanner.core import scan_library_path
            scan_library_path(db_path, lib_id_int, target_path, force=force_requeue)

            return jsonify({
                'success': True,
                'message': f'"{lib_name} ({db_type})" 내 "{rel_path}" 경로의 스캔 및 등록이 완료되었습니다.'
            })
        except FileNotFoundError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # 3. 백그라운드 스캔 대기열 주입 (스캐너 워커 필수 인자 포함)
    try:
        db_path = database.get_db_path(db_type)
        from services.scanner_queue import scanner_queue
        enqueued = scanner_queue.enqueue(
            'library_scan',
            db_type=db_type,
            db_path=db_path,
            library_id=lib_id_int,
            physical_path=physical_path,
            force=force_requeue,
            force_requeue=force_requeue
        )
        
        if not enqueued:
            return jsonify({
                'success': True,
                'already_queued': True,
                'message': f'"{lib_name} ({db_type})" 스캔 작업이 이미 진행 중이거나 대기열에 존재합니다.'
            }), 200

        return jsonify({
            'success': True,
            'already_queued': False,
            'message': f'"{lib_name} ({db_type})" 스캔 작업이 대기열에 성공적으로 등록되었습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
