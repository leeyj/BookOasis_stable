import os
from dotenv import load_dotenv
load_dotenv()

from utils.logger import setup_rotating_logger
setup_rotating_logger()

from flask import Flask, request
from database import init_databases
from api import api_bp

# Set template and static folders relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

# Flask 세션 관리용 암호화 키 설정 (환경변수 부재 시 보안 난수 자동 주입)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    import secrets
    app.secret_key = secrets.token_hex(32)

# 블루프린트 등록
app.register_blueprint(api_bp)

@app.after_request
def add_fingerprint_headers(response):
    response.headers['X-Powered-By'] = 'BookOasis Engine'
    response.headers['X-BookOasis-Engine'] = 'BookOasis Engine v1.0'
    response.headers['X-BookOasis-Version'] = '1.0'
    response.headers['X-BookOasis-License'] = 'AGPLv3'
    response.headers['X-BookOasis-Signature'] = 'boe-core-a17f3c9'
    # 폰트, 이미지 및 외부 라이브러리(lib) 등 거의 변경되지 않는 리소스만 브라우저 강제 캐싱 적용
    # 커스텀 CSS/JS 파일들은 즉각적인 업데이트 반영을 위해 캐싱에서 제외
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

# ── Graceful Shutdown 핸들러 등록 ──
# 서버 종료 시 (Docker stop, SIGTERM 등) DB 커넥션 풀을 안전하게 정리하고
# WAL 체크포인트를 수행하여 DB 손상을 방지합니다.
import atexit
import signal
from database import shutdown_all_pools

def _graceful_shutdown(signum=None, frame=None):
    """SIGTERM/SIGINT 수신 시 스케줄러 중지 및 DB 풀 안전 종료"""
    sig_name = signal.Signals(signum).name if signum else 'atexit'
    print(f"\n[Graceful-Shutdown] {sig_name} 수신, 서버 종료 프로세스 시작...")
    try:
        if hasattr(SchedulerService, 'stop_scheduler'):
            SchedulerService.stop_scheduler()
    except Exception as e:
        print(f"[Graceful-Shutdown] 스케줄러 중지 중 오류 (무시): {e}")
    shutdown_all_pools()
    print("[Graceful-Shutdown] 종료 완료.")
    if signum is not None:
        raise SystemExit(0)

# atexit: 정상 종료 시 DB 풀 정리 (중복 호출 방지 내장)
atexit.register(shutdown_all_pools)

# SIGTERM: Docker stop / kill -15 시 Graceful Shutdown
# SIGINT: Ctrl+C 종료 시
try:
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)
except (OSError, ValueError):
    # 메인 스레드가 아닌 경우 signal 등록 불가 (Gunicorn 워커 등) — atexit으로 대체
    pass

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='BookOasis Media Server')
    parser.add_argument('-p', '--port', type=int, default=int(os.environ.get('PORT', 5930)), help='Port to run the server on (default: 5930 or $PORT)')
    args = parser.parse_args()

    # 파라미터 또는 환경변수에 따라 포트 할당
    app.run(host='0.0.0.0', port=args.port, debug=True)
