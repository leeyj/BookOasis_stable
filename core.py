import os

from utils.logger import setup_rotating_logger
setup_rotating_logger()

from flask import Flask, jsonify, render_template
from database import init_databases
from api import api_bp
from api.auth import login_required

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
    response.headers['X-BookOasis-Version'] = '1.0'
    response.headers['X-BookOasis-License'] = 'AGPLv3'
    return response

# 앱 기동 시 DB 초기화 수행
init_databases()

# 백그라운드 스케줄러 기동
from services.scheduler_service import SchedulerService
SchedulerService.start_scheduler()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'BookOasis'
    })

@app.route('/', methods=['GET'])
@app.route('/media-library', methods=['GET'])
@login_required
def index():
    # Pass an empty dict or required settings for the template if needed
    settings = {}
    return render_template('index.html', active_page='media_library', settings=settings)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='BookOasis Media Server')
    parser.add_argument('-p', '--port', type=int, default=int(os.environ.get('PORT', 5930)), help='Port to run the server on (default: 5930 or $PORT)')
    args = parser.parse_args()

    # 파라미터 또는 환경변수에 따라 포트 할당
    app.run(host='0.0.0.0', port=args.port, debug=True)
