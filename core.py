import os
import sys
import json
import time
import hashlib
import subprocess
from urllib.parse import urlencode
from dotenv import load_dotenv
load_dotenv()

from utils.engine_signature import ENGINE_NAME, ENGINE_SIGNATURE, ENGINE_LICENSE

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
    from repositories.scanner_queue_repository import ScannerQueueRepository

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

    def _load_release_version():
        """VERSION 파일의 dashboard 값을 읽어 릴리스 식별자로 사용."""
        default_version = 'dev'
        version_path = os.path.join(BASE_DIR, 'VERSION')
        try:
            if not os.path.exists(version_path):
                return default_version
            with open(version_path, 'r', encoding='utf-8') as vf:
                for raw_line in vf:
                    line = raw_line.strip()
                    if not line.startswith('"dashboard"'):
                        continue
                    parts = line.split(':', 1)
                    if len(parts) != 2:
                        continue
                    value = parts[1].strip().rstrip(',').strip().strip('"').strip("'")
                    return value or default_version
        except Exception as ve:
            print(f"[Core-Version Warning] failed to load VERSION dashboard key: {ve}")
        return default_version

    app.config['RELEASE_VERSION'] = _load_release_version()

    def _env_flag(name, default=False):
        raw = os.environ.get(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')

    def _env_int(name, default, min_value=0, max_value=1000000):
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            value = int(str(raw).strip())
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    def _build_csp_policy(report_path='/api/security/csp-report'):
        override = os.environ.get('SECURITY_CSP_POLICY', '').strip()
        if override:
            return override

        directives = [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'self'",
            "img-src 'self' data: blob: https:",
            "font-src 'self' data: https:",
            "style-src 'self' 'unsafe-inline' https:",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:",
            "connect-src 'self' https: ws: wss:",
            "frame-src 'self' https:",
            "media-src 'self' data: blob: https:",
            "worker-src 'self' blob:",
            "manifest-src 'self'",
            f"report-uri {report_path}",
        ]
        return '; '.join(directives)

    app.config['SECURITY_CSP_ENABLED'] = _env_flag('SECURITY_CSP_ENABLED', True)
    app.config['SECURITY_CSP_REPORT_ONLY'] = _env_flag('SECURITY_CSP_REPORT_ONLY', True)
    app.config['SECURITY_CSP_ENFORCE'] = _env_flag('SECURITY_CSP_ENFORCE', False)
    app.config['SECURITY_CSP_LOG_REPORTS'] = _env_flag('SECURITY_CSP_LOG_REPORTS', True)
    app.config['SECURITY_CSP_REPORT_PATH'] = '/api/security/csp-report'
    app.config['SECURITY_CSP_REPORT_FILE'] = os.environ.get(
        'SECURITY_CSP_REPORT_FILE',
        os.path.join(BASE_DIR, 'logs', 'csp_reports.jsonl')
    ).strip()
    app.config['SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN'] = _env_int(
        'SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN',
        120,
        min_value=1,
        max_value=20000
    )
    app.config['SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC'] = _env_int(
        'SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC',
        30,
        min_value=0,
        max_value=3600
    )
    app.config['SECURITY_CSP_POLICY'] = _build_csp_policy(app.config['SECURITY_CSP_REPORT_PATH'])
    app.config['SECURITY_CSP_REPORT_STATE'] = {
        'minute_bucket': int(time.time() // 60),
        'count_in_bucket': 0,
        'suppressed_in_bucket': 0,
        'last_seen_by_fingerprint': {},
    }

    def _append_csp_report_file(entry):
        report_file = (app.config.get('SECURITY_CSP_REPORT_FILE') or '').strip()
        if not report_file:
            return
        try:
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, 'a', encoding='utf-8') as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as file_err:
            print(f"[CSP-REPORT-WARN] failed to write report file: {file_err}")

    @app.context_processor
    def inject_asset_helpers():
        def static_asset_url(filename, **kwargs):
            from flask import url_for
            params = dict(kwargs or {})
            params.setdefault('v', app.config.get('RELEASE_VERSION', 'dev'))
            return url_for('static', filename=filename, **params)

        def append_release_version(url):
            if not url:
                return url
            if 'v=' in url:
                return url
            sep = '&' if '?' in url else '?'
            return f"{url}{sep}{urlencode({'v': app.config.get('RELEASE_VERSION', 'dev')})}"

        return {
            'release_version': app.config.get('RELEASE_VERSION', 'dev'),
            'static_asset_url': static_asset_url,
            'append_release_version': append_release_version,
        }

    # 블루프린트 등록
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_feature_flags():
        # 오디오북 기능은 기본 상시 활성화 정책으로 전환
        audiobook_enabled = True
        return dict(audiobook_enabled=audiobook_enabled)

    @app.errorhandler(413)
    def handle_request_entity_too_large(_error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Request payload too large'}), 413
        return 'Request payload too large', 413

    @app.route('/api/security/csp-report', methods=['POST'])
    def csp_report_receiver():
        """CSP 위반 리포트를 수집합니다. (Report-Only 단계 관측용)"""
        payload = request.get_json(silent=True)
        if payload is None:
            raw = (request.get_data(cache=False, as_text=True) or '').strip()
            if raw:
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {'raw': raw[:2000]}

        report = {}
        if isinstance(payload, dict):
            if isinstance(payload.get('csp-report'), dict):
                report = payload.get('csp-report') or {}
            elif isinstance(payload.get('body'), dict):
                report = payload.get('body') or {}
            else:
                report = payload

        if not isinstance(report, dict):
            report = {'raw': str(report)[:1000]}

        now_ts = int(time.time())
        log_line = {
            'ts': now_ts,
            'effective_directive': report.get('effective-directive') or report.get('violated-directive'),
            'violated_directive': report.get('violated-directive'),
            'blocked_uri': report.get('blocked-uri'),
            'source_file': report.get('source-file'),
            'line_number': report.get('line-number'),
            'column_number': report.get('column-number'),
            'document_uri': report.get('document-uri'),
            'user_agent': request.headers.get('User-Agent', ''),
            'referer': request.headers.get('Referer', ''),
        }

        # 동일 리포트 반복 스팸을 줄이기 위해 핵심 필드 기반 지문 + dedup window 적용
        fp_source = '|'.join([
            str(log_line.get('effective_directive') or ''),
            str(log_line.get('violated_directive') or ''),
            str(log_line.get('blocked_uri') or ''),
            str(log_line.get('source_file') or ''),
            str(log_line.get('line_number') or ''),
            str(log_line.get('document_uri') or ''),
        ])
        fingerprint = hashlib.sha1(fp_source.encode('utf-8', errors='ignore')).hexdigest()

        state = app.config.get('SECURITY_CSP_REPORT_STATE') or {}
        minute_bucket = int(now_ts // 60)
        prev_bucket = state.get('minute_bucket', minute_bucket)
        if minute_bucket != prev_bucket:
            suppressed_prev = int(state.get('suppressed_in_bucket', 0) or 0)
            if suppressed_prev > 0:
                summary = {
                    'ts': now_ts,
                    'type': 'csp_report_suppressed_summary',
                    'minute_bucket': prev_bucket,
                    'suppressed_count': suppressed_prev,
                }
                _append_csp_report_file(summary)
                if app.config.get('SECURITY_CSP_LOG_REPORTS', True):
                    print(f"[CSP-REPORT] {json.dumps(summary, ensure_ascii=False)}")
            state['minute_bucket'] = minute_bucket
            state['count_in_bucket'] = 0
            state['suppressed_in_bucket'] = 0

        dedup_window = int(app.config.get('SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC', 30) or 0)
        last_seen = state.get('last_seen_by_fingerprint', {})
        last_seen_ts = int(last_seen.get(fingerprint, 0) or 0)
        if dedup_window > 0 and now_ts - last_seen_ts < dedup_window:
            state['suppressed_in_bucket'] = int(state.get('suppressed_in_bucket', 0) or 0) + 1
            app.config['SECURITY_CSP_REPORT_STATE'] = state
            return ('', 204)

        per_min_limit = int(app.config.get('SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN', 120) or 120)
        if int(state.get('count_in_bucket', 0) or 0) >= per_min_limit:
            state['suppressed_in_bucket'] = int(state.get('suppressed_in_bucket', 0) or 0) + 1
            app.config['SECURITY_CSP_REPORT_STATE'] = state
            return ('', 204)

        last_seen[fingerprint] = now_ts
        if len(last_seen) > 2000:
            cutoff_ts = now_ts - max(dedup_window, 60)
            last_seen = {k: v for k, v in last_seen.items() if int(v) >= cutoff_ts}
        state['last_seen_by_fingerprint'] = last_seen
        state['count_in_bucket'] = int(state.get('count_in_bucket', 0) or 0) + 1
        app.config['SECURITY_CSP_REPORT_STATE'] = state

        _append_csp_report_file(log_line)
        if app.config.get('SECURITY_CSP_LOG_REPORTS', True):
            try:
                print(f"[CSP-REPORT] {json.dumps(log_line, ensure_ascii=False)}")
            except Exception:
                print(f"[CSP-REPORT] {str(log_line)}")

        return ('', 204)

    @app.after_request
    def add_fingerprint_headers(response):
        response.headers['X-Powered-By'] = ENGINE_NAME
        response.headers['X-BookOasis-Engine'] = f'{ENGINE_NAME} v1.0'
        response.headers['X-BookOasis-Version'] = app.config.get('RELEASE_VERSION', 'dev')
        response.headers['X-BookOasis-License'] = ENGINE_LICENSE
        response.headers['X-BookOasis-Signature'] = ENGINE_SIGNATURE
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        csp_enabled = app.config.get('SECURITY_CSP_ENABLED', True)
        csp_policy = app.config.get('SECURITY_CSP_POLICY', '')
        if csp_enabled and csp_policy:
            if app.config.get('SECURITY_CSP_ENFORCE', False):
                response.headers['Content-Security-Policy'] = csp_policy
            elif app.config.get('SECURITY_CSP_REPORT_ONLY', True):
                response.headers['Content-Security-Policy-Report-Only'] = csp_policy

        if request.path in ('/', '/login'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        is_cacheable_path = request.path.startswith('/static/lib/') or request.path.startswith('/static/fonts/')
        is_cacheable_ext = any(request.path.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot', '.png', '.jpg', '.jpeg', '.svg', '.ico'])
        if request.path.startswith('/static/') and (is_cacheable_path or is_cacheable_ext):
            response.cache_control.max_age = 31536000
            response.cache_control.public = True
            response.cache_control.immutable = True
        return response

    from utils.engine_signature import engine_banner_line
    print(f"[Scanner-Trigger] {engine_banner_line()}")

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
