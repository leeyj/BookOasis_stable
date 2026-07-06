# -*- coding: utf-8 -*-
"""
admin.py – 관리자 라우터 블루프린트 등록 (Management/Admin Layer)

모든 관리자 라우트는 api/routes/ 하위 모듈로 분산 관리:
- library_routes.py: 라이브러리 CRUD 및 스케줄 관리
- scan_routes.py: 스캔 작업 관리 (라이브러리, 표지, 개별 도서 스캔)
- browse_routes.py: 경로 탐색 (로컬 및 rclone 원격 경로)
- settings_routes.py: 시스템 설정 관리
- report_routes.py: 스캔 에러 리포트 조회
- system_routes.py: 시스템 상태, 큐, 정보 조회
"""
from flask import Blueprint
from api.routes.library_routes import library_bp
from api.routes.scan_routes import scan_bp
from api.routes.browse_routes import browse_bp
from api.routes.settings_routes import settings_bp
from api.routes.report_routes import report_bp
from api.routes.system_routes import system_bp
from api.routes.permission_routes import permission_bp
from api.routes.trash_routes import trash_bp

# 통합 Blueprint (api/__init__.py에서 register_blueprint하기 위한 컨테이너)
admin_bp = Blueprint('media_admin', __name__)

# 모든 라우트 블루프린트를 admin_bp에 등록
admin_bp.register_blueprint(library_bp)
admin_bp.register_blueprint(scan_bp)
admin_bp.register_blueprint(browse_bp)
admin_bp.register_blueprint(settings_bp)
admin_bp.register_blueprint(report_bp)
admin_bp.register_blueprint(system_bp)
admin_bp.register_blueprint(permission_bp)
admin_bp.register_blueprint(trash_bp)
