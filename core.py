import os
from dotenv import load_dotenv
load_dotenv()

# 자식 워커 프로세스 여부 감지
IS_WORKER = os.environ.get('BOOKOASIS_IS_WORKER') == 'true'

# 글로벌 자식 프로세스 레퍼런스
_worker_process = None

def _worker_process_entry():
    """자식 프로세스용 격리 실행 진입점"""
    os.environ['BOOKOASIS_IS_WORKER'] = 'true'
    # Gunicorn 등의 시그널 간섭 차단을 위해 시그널 핸들러 초기화
    import signal
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    except:
        pass
    from services.scanner_queue import run_scanner_worker_loop
    run_scanner_worker_loop()

def start_scanner_worker_process():
    """독립 스캐너 워커 프로세스를 기동합니다."""
    global _worker_process
    if _worker_process is not None and _worker_process.is_alive():
        return
        
    import multiprocessing
    # 자식 프로세스가 spawn될 때 부모 환경변수를 그대로 복사하여 전달하므로,
    # start() 직전에 환경변수를 주입하고 직후에 제거하는 방식으로 안전 격리를 보장합니다.
    os.environ['BOOKOASIS_IS_WORKER'] = 'true'
    try:
        _worker_process = multiprocessing.Process(
            target=_worker_process_entry,
            name="BookOasis-Scanner-Worker",
            daemon=True
        )
        _worker_process.start()
    finally:
        # 부모 프로세스는 자신이 워커가 아니므로 환경변수를 지워줍니다.
        if 'BOOKOASIS_IS_WORKER' in os.environ:
            del os.environ['BOOKOASIS_IS_WORKER']
            
    print(f"[Scanner-Process] Started daemon worker process (PID: {_worker_process.pid})")


if not IS_WORKER:
    from utils.logger import setup_rotating_logger
    setup_rotating_logger()

    from flask import Flask, request, jsonify
    from database import init_databases
    from api import api_bp

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

    # ── 백그라운드 스캐너 프로세스 기동 (Debug 리로더 parent 프로세스 중복 실행 차단) ──
    # Gunicorn 충돌 방지를 위해, 워커 프로세스는 manage.sh를 통해 독자적 프로세스로 백그라운드 기동됩니다.
    # is_reloader_parent = os.environ.get('FLASK_DEBUG') in ('1', 'true', 'yes', 'on') and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    # if not is_reloader_parent:
    #     start_scanner_worker_process()

    # ── Graceful Shutdown 핸들러 등록 ──
    import atexit
    import signal
    from database import shutdown_all_pools

    def _graceful_shutdown(signum=None, frame=None):
        """SIGTERM/SIGINT 수신 시 스케줄러 및 자식 프로세스 중지, DB 풀 안전 종료"""
        sig_name = signal.Signals(signum).name if signum else 'atexit'
        print(f"\n[Graceful-Shutdown] {sig_name} 수신, 서버 종료 프로세스 시작...")
        
        # 자식 스캐너 프로세스 강제 종료
        global _worker_process
        if _worker_process is not None and _worker_process.is_alive():
            try:
                print("[Graceful-Shutdown] 스캐너 워커 프로세스 종료 중...")
                _worker_process.terminate()
                _worker_process.join(timeout=5)
            except Exception as pe:
                print(f"[Graceful-Shutdown] 워커 프로세스 종료 오류: {pe}")

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
