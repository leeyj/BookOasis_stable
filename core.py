import os
import sys
import subprocess
from dotenv import load_dotenv
load_dotenv()

# 자식 워커 프로세스 여부 감지
IS_WORKER = os.environ.get('BOOKOASIS_IS_WORKER') == 'true'

# 글로벌 자식 프로세스 레퍼런스
_worker_process = None

def start_scanner_worker_process():
    """독립 스캐너 워커 프로세스를 기동합니다."""
    global _worker_process
    if _worker_process is not None and _worker_process.poll() is None:
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    worker_script = os.path.join(base_dir, 'tools', 'scanner_worker.py')
    env = os.environ.copy()
    env['BOOKOASIS_IS_WORKER'] = 'true'
    _worker_process = subprocess.Popen(
        [sys.executable, worker_script],
        cwd=base_dir,
        env=env
    )
            
    print(f"[Scanner-Process] Started daemon worker process (PID: {_worker_process.pid})")


def is_scanner_worker_running_os():
    """OS 수준에서 scanner_worker.py 프로세스가 실제로 동작 중인지 검사합니다."""
    try:
        import psutil
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmd = proc.info.get('cmdline')
                if cmd and proc.info['pid'] != current_pid and any('scanner_worker.py' in str(arg) for arg in cmd):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass
    return False


def ensure_scanner_worker_running():
    """독립 스캐너 워커 프로세스가 실행 중인지 확인하고 필요 시 출발시킵니다."""
    global _worker_process
    if _worker_process is not None and _worker_process.poll() is None:
        return
    if is_scanner_worker_running_os():
        return
    start_scanner_worker_process()



if not IS_WORKER:
    from utils.logger import setup_rotating_logger
    setup_rotating_logger()

    from flask import Flask, request, jsonify
    from database import init_databases
    from api import api_bp
    from repositories.sqlite.scanner_queue_repository import ScannerQueueRepository

    # 부팅 시점 유령 태스크 및 고착 스캔 상태 정화
    try:
        ScannerQueueRepository.startup_cleanup_ghost_tasks()
    except Exception as _e:
        print(f"[Core-Startup Warning] Failed to cleanup ghost tasks: {_e}")

    # Set template and static folders relative to this script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__, 
                template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'))

    def _get_max_content_length_bytes():
        raw = os.environ.get('MAX_CONTENT_LENGTH_MB', '100').strip()
        try:
            size_mb = int(raw)
        except ValueError:
            size_mb = 100
        size_mb = max(1, min(size_mb, 1024))
        return size_mb * 1024 * 1024

    app.config['MAX_CONTENT_LENGTH'] = _get_max_content_length_bytes()

    # Flask 세션 관리용 암호화 키 설정 (환경변수 부재 시 보안 난수 자동 주입)
    app.secret_key = os.environ.get('SECRET_KEY')
    if not app.secret_key:
        import secrets
        app.secret_key = secrets.token_hex(32)

    # 블루프린트 등록
    app.register_blueprint(api_bp)

    @app.errorhandler(413)
    def handle_request_entity_too_large(_error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Request payload too large'}), 413
        return 'Request payload too large', 413

    @app.after_request
    def add_fingerprint_headers(response):
        response.headers['X-Powered-By'] = 'BookOasis Engine'
        response.headers['X-BookOasis-Engine'] = 'BookOasis Engine v1.0'
        response.headers['X-BookOasis-Version'] = '1.0'
        response.headers['X-BookOasis-License'] = 'AGPLv3'
        response.headers['X-BookOasis-Signature'] = 'boe-core-a17f3c9'
        is_cacheable_path = request.path.startswith('/static/lib/') or request.path.startswith('/static/fonts/')
        is_cacheable_ext = any(request.path.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot', '.png', '.jpg', '.jpeg', '.svg', '.ico'])
        if request.path.startswith('/static/') and (is_cacheable_path or is_cacheable_ext):
            response.cache_control.max_age = 31536000
            response.cache_control.public = True
        return response

    # 앱 기동 시 DB 초기화 수행
    init_databases()

    # 백그라운드 스케줄러 기동
    from services.scheduler_service import SchedulerService
    SchedulerService.start_scheduler()

    # ── 선택적 내장 스캐너 워커 기동 ──
    # 우선순위:
    # 1) BOOKOASIS_ENABLE_EMBEDDED_WORKER 명시값(true/false)
    # 2) 미지정 시: 도커 컨테이너 내부는 OFF, 그 외(리눅스 직접 실행 포함)는 ON
    embedded_worker_raw = os.environ.get('BOOKOASIS_ENABLE_EMBEDDED_WORKER', '').strip().lower()
    if embedded_worker_raw in ('1', 'true', 'yes', 'on'):
        embedded_worker_enabled = True
    elif embedded_worker_raw in ('0', 'false', 'no', 'off'):
        embedded_worker_enabled = False
    else:
        in_docker = os.path.exists('/.dockerenv')
        embedded_worker_enabled = not in_docker
    is_reloader_parent = os.environ.get('FLASK_DEBUG') in ('1', 'true', 'yes', 'on') and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    if embedded_worker_enabled and not is_reloader_parent:
        start_scanner_worker_process()

    # ── Graceful Shutdown 핸들러 등록 ──
    import atexit
    import signal
    from database import shutdown_all_pools

    def _graceful_shutdown(signum=None, frame=None):
        """SIGTERM/SIGINT 수신 시 스케줄러 및 자식 프로세스 중지, DB 풀 안전 종료"""
        sig_name = signal.Signals(signum).name if signum else 'atexit'
        print(f"\n[Graceful-Shutdown] {sig_name} 수신, 서버 종료 프로세스 시작...")
        
        # ── [Redis 캐시 강제 Flush 동기화] ──
        try:
            from services.reading_progress_service import ReadingProgressService
            ReadingProgressService.flush_progress_cache()
        except Exception as fe:
            print(f"[Graceful-Shutdown] Redis cache flush failed (ignored): {fe}")
        
        # 자식 스캐너 프로세스 및 독립 레이지 스캐너 정리
        global _worker_process
        if _worker_process is not None and _worker_process.poll() is None:
            try:
                print("[Graceful-Shutdown] 스캐너 워커 자식 프로세스 종료 중...")
                _worker_process.terminate()
                _worker_process.wait(timeout=5)
            except Exception as pe:
                print(f"[Graceful-Shutdown] 워커 프로세스 종료 오류: {pe}")

        # 실행 중인 독립 lazy_scanner 프로세스 감지 시 SIGTERM 및 안전 마감 대기
        try:
            import psutil
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmd = proc.info.get('cmdline')
                    if cmd and proc.info['pid'] != current_pid and any('lazy_scanner.py' in arg for arg in cmd):
                        print(f"[Graceful-Shutdown] 🛑 백그라운드 레이지 스캐너 감지 (PID: {proc.info['pid']}). SIGTERM 송신 후 대기...")
                        proc.terminate()
                        proc.wait(timeout=5)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(SchedulerService, 'stop_scheduler'):
                SchedulerService.stop_scheduler()
        except Exception as e:
            print(f"[Graceful-Shutdown] 스케줄러 중지 중 오류 (무시): {e}")
            
        shutdown_all_pools()
        print("[Graceful-Shutdown] 종료 완료.")
        if signum is not None:
            raise SystemExit(0)

    # atexit: 정상 종료 시 DB 풀 정리
    atexit.register(_graceful_shutdown)

    # SIGTERM/SIGINT 핸들러 등록
    try:
        signal.signal(signal.SIGTERM, _graceful_shutdown)
        signal.signal(signal.SIGINT, _graceful_shutdown)
    except (OSError, ValueError):
        pass

    if __name__ == '__main__':
        import argparse
        parser = argparse.ArgumentParser(description='BookOasis Media Server')
        parser.add_argument('-p', '--port', type=int, default=int(os.environ.get('PORT', 5930)), help='Port to run the server on (default: 5930 or $PORT)')
        parser.add_argument('--debug', action='store_true', help='Enable Flask debug mode (default: disabled)')
        args = parser.parse_args()

        env_debug = str(os.environ.get('FLASK_DEBUG', '')).strip().lower() in ('1', 'true', 'yes', 'on')
        debug_mode = bool(args.debug or env_debug)

        app.run(host='0.0.0.0', port=args.port, debug=debug_mode)
